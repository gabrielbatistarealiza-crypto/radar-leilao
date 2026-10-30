"""Datas da CAIXA por imóvel + edital, só com requests (nunca Selenium).

Um passo do worker:
  1. lê a página de UM imóvel pendente (1 pedido);
  2. grava as datas que a página mostra e o link do edital;
  3. se esse edital ainda não foi lido, descarrega o PDF (1 pedido) e preenche
     as datas de todos os imóveis que ele lista no Anexo II.

Regras de segurança:
  - um GET por URL, sem novas tentativas, sem seguir redirecionamentos e sem
    proxy do ambiente (trust_env = False);
  - decide pelo estado HTTP ANTES de ler o corpo: 3xx, 403 e 429 param sem o ler;
  - CAPTCHA/Radware/pistas antibot só se detetam no conteúdo, depois de o ler;
  - qualquer resposta que não seja a esperada (bloqueio, erro, timeout, edital
    que não se consegue interpretar ou incoerente) PARA o worker até revisão
    manual: grava `bloqueado_ate = PARAGEM_MANUAL`, que o porteiro
    (caixa_acesso) respeita para todas as rotinas da CAIXA.

Para retomar depois de rever: pôr `bloqueado_ate = NULL` e `ativo = true` na
linha 1 de `caixa_data_worker_state`.
"""
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from sqlalchemy import and_, not_, or_

from app.models.imovel import Imovel, ImovelEvento

logger = logging.getLogger(__name__)

DOMINIO_CAIXA = "venda-imoveis.caixa.gov.br"
CABECALHOS = {"User-Agent": "Mozilla/5.0"}
TIMEOUT_SEGUNDOS = (10, 30)  # ligação, leitura
MAX_BYTES_PAGINA = 2 * 1024 * 1024
MAX_BYTES_EDITAL = 30 * 1024 * 1024  # aproximado: pode ler mais um bloco de 64 KiB
MAX_BYTES_LISTA = 20 * 1024 * 1024  # CSV de uma UF (o maior, RJ, tem ~3 MB)
PISTAS_ANTIBOT = ("perfdrive", "radware", "hcaptcha", "recaptcha", "cf-chl", "bot manager")

# Data muito no futuro = parado até alguém rever e limpar à mão.
PARAGEM_MANUAL = datetime(9999, 12, 31)

_RE_EDITAL = re.compile(r"""["'(/]editais/([A-Za-z0-9]+\.pdf)\b""", re.IGNORECASE)
_RE_HDNIMOVEL = re.compile(r"hdnimovel=(\d+)", re.IGNORECASE)


def e_paragem_manual(bloqueado_ate) -> bool:
    return bool(bloqueado_ate and bloqueado_ate.year >= 9999)


# ----------------------------------------------------------------- pedido HTTP

@dataclass
class RespostaCaixa:
    veredicto: str  # "OK" ou o motivo da paragem
    status: int | None = None
    corpo: bytes | None = None
    destino: str | None = None
    detalhe: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.veredicto == "OK"


def url_permitido(url: str, tipo: str) -> bool:
    partes = urlparse(url or "")
    if partes.scheme != "https" or partes.hostname != DOMINIO_CAIXA:
        return False
    if partes.username or partes.password or "@" in partes.netloc:
        return False
    try:
        if partes.port not in (None, 443):
            return False
    except ValueError:
        return False
    caminho = partes.path.lower()
    if tipo == "edital":
        return caminho.startswith("/editais/") and caminho.endswith(".pdf") and not partes.query
    if tipo == "lista":
        return bool(re.fullmatch(r"/listaweb/lista_imoveis_[a-z]{2}\.csv", caminho)) and not partes.query
    return caminho == "/sistema/detalhe-imovel.asp"


def pedir_caixa(url: str, tipo: str, sessao_factory=None) -> RespostaCaixa:
    """UM GET à CAIXA. `tipo` é "pagina", "edital" ou "lista" (CSV de uma UF). Nunca repete."""
    import requests

    if not url_permitido(url, tipo):
        return RespostaCaixa("URL_RECUSADO")
    sessao = (sessao_factory or requests.Session)()
    sessao.trust_env = False
    try:
        try:
            resposta = sessao.get(url, headers=CABECALHOS, timeout=TIMEOUT_SEGUNDOS,
                                  allow_redirects=False, stream=True)
        except requests.ConnectTimeout:
            return RespostaCaixa("TIMEOUT_LIGACAO")
        except requests.ReadTimeout:
            return RespostaCaixa("TIMEOUT_LEITURA_CABECALHOS")
        except requests.RequestException as erro:
            return RespostaCaixa("ERRO_DE_REDE", detalhe={"erro": type(erro).__name__})
        try:
            return _tratar_resposta(requests, resposta, tipo)
        finally:
            resposta.close()
    finally:
        sessao.close()


def _tratar_resposta(requests, resposta, tipo) -> RespostaCaixa:
    status = resposta.status_code
    if 300 <= status < 400:  # nunca lê o corpo
        destino = urlparse(resposta.headers.get("Location", "")).hostname or "(relativo)"
        return RespostaCaixa("REDIRECIONADO", status=status, destino=destino)
    if status in (403, 429):
        return RespostaCaixa(f"BLOQUEADO_HTTP_{status}", status=status)

    limite = {"edital": MAX_BYTES_EDITAL, "lista": MAX_BYTES_LISTA}.get(tipo, MAX_BYTES_PAGINA)
    corpo = bytearray()
    try:
        for bloco in resposta.iter_content(64 * 1024):
            corpo += bloco
            if len(corpo) > limite:
                return RespostaCaixa("TAMANHO_EXCEDIDO", status=status)
    except requests.RequestException as erro:
        e_timeout = isinstance(erro, requests.Timeout) or "ReadTimeout" in repr(erro)
        return RespostaCaixa("TIMEOUT_LEITURA_CORPO" if e_timeout else "ERRO_LEITURA_CORPO",
                             status=status)
    corpo = bytes(corpo)

    if not corpo.startswith(b"%PDF-"):
        bloqueio = _bloqueio_no_html(corpo)
        if bloqueio:
            return RespostaCaixa(bloqueio, status=status)
    if status != 200:
        return RespostaCaixa(f"HTTP_INESPERADO_{status}", status=status)
    if tipo == "edital" and not corpo.startswith(b"%PDF-"):
        return RespostaCaixa("NAO_E_PDF", status=status)
    if tipo in ("pagina", "lista") and corpo.startswith(b"%PDF-"):
        return RespostaCaixa("NAO_E_HTML" if tipo == "pagina" else "NAO_E_CSV_DA_CAIXA", status=status)
    return RespostaCaixa("OK", status=status, corpo=corpo)


def _bloqueio_no_html(corpo: bytes) -> str | None:
    from app.scrapers.caixa import CaixaScraper

    html = corpo.decode("utf-8", errors="replace")
    pagina = BeautifulSoup(html, "html.parser")
    titulo = pagina.title.get_text(" ", strip=True) if pagina.title else ""
    if CaixaScraper._tem_marcador_bloqueio(f"{titulo} {CaixaScraper._texto_visivel(pagina)}"):
        return "BLOQUEADO"
    if any(pista in html.lower() for pista in PISTAS_ANTIBOT):
        return "PISTA_ANTIBOT"
    return None


# -------------------------------------------------------------- leitura (sem rede)

def ler_fotos(corpo: bytes, url_pagina: str) -> list[str]:
    """URLs absolutos das fotos da galeria (/fotos/...) na página do imóvel."""
    from app.scrapers.caixa import CaixaScraper

    pagina = BeautifulSoup(corpo.decode("utf-8", errors="replace"), "html.parser")
    return CaixaScraper._extrair_imagens_da_pagina(pagina, url_pagina)


def _gravar_fotos(db, imovel, fotos: list[str]) -> int:
    """Acrescenta as fotos que faltam e marca a verificação como COM_FOTOS.

    Só é chamada com pelo menos uma foto: uma página sem galeria nunca apaga
    nem desclassifica fotos já gravadas. Devolve quantas fotos são novas.
    """
    from app.models.imovel import ImovelFotoVerificacao, ImovelImagem

    existentes = {
        url for (url,) in db.query(ImovelImagem.url).filter(ImovelImagem.imovel_id == imovel.id)
    }
    novas = [f for f in fotos if f not in existentes]
    inicio = len(existentes)
    for deslocamento, url in enumerate(novas):
        db.add(ImovelImagem(imovel_id=imovel.id, url=url, ordem=inicio + deslocamento))
    verificacao = (
        db.query(ImovelFotoVerificacao).filter(ImovelFotoVerificacao.imovel_id == imovel.id).first()
    )
    if verificacao is None:
        db.add(ImovelFotoVerificacao(imovel_id=imovel.id, resultado="COM_FOTOS",
                                     verificado_em=datetime.utcnow()))
    elif verificacao.resultado != "COM_FOTOS":
        verificacao.resultado = "COM_FOTOS"
        verificacao.verificado_em = datetime.utcnow()
    return len(novas)


def ler_pagina(corpo: bytes) -> tuple[tuple, str | None]:
    """Datas (1.º, 2.º, licitação aberta) e o URL do edital, se for único."""
    from app.scrapers.caixa import CaixaScraper

    html = corpo.decode("utf-8", errors="replace")
    datas = CaixaScraper._extrair_datas_da_pagina(BeautifulSoup(html, "html.parser"))
    editais = {nome.upper() for nome in _RE_EDITAL.findall(html)}
    link = f"https://{DOMINIO_CAIXA}/editais/{editais.pop()}" if len(editais) == 1 else None
    return datas, link


@dataclass
class Edital:
    data_primeiro_leilao: date
    data_segundo_leilao: date
    numeros: set[str]  # lotes à venda (número seguido dos valores); sem zeros à esquerda
    numeros_sem_venda: set[str] = field(default_factory=set)  # ANULADO / Arrematado
    # número -> (valor de venda no 1.º leilão, no 2.º leilão, valor de avaliação), em R$
    valores: dict[str, tuple[float, float, float]] = field(default_factory=dict)


# "Número do bem" no Anexo II: 8 a 13 dígitos seguidos dos valores de venda
# (lote ativo) ou de ANULADO / Arrematado. Não apanha IPTU nem matrículas,
# que vêm seguidos de outro texto (ex.: "IPTU: 0102141074001 Matrícula").
_VALOR = r"\d{1,3}(?:\.\d{3})*,\d{2}"
_RE_BEM_COM_VALOR = re.compile(rf"(?<![\w.,/-])(\d{{8,13}})\s+{_VALOR}")
_RE_BEM_SEM_VENDA = re.compile(r"(?<![\w.,/-])(\d{8,13})[ \t]{2,}(?:ANULADO|Arrematado)\b")
# Colunas do Anexo II: VALOR DE VENDA 1º LEILÃO, VALOR DE VENDA 2º LEILÃO, VALOR DE AVALIAÇÃO.
_RE_BEM_TRES_VALORES = re.compile(
    rf"(?<![\w.,/-])(\d{{8,13}})\s+({_VALOR})\s+({_VALOR})\s+({_VALOR})(?![\d,])"
)


def _normalizar_numero(numero: str) -> str:
    return numero.lstrip("0") or "0"


def _reais(texto: str) -> float:
    return float(texto.replace(".", "").replace(",", "."))


def _valores_do_anexo(anexo: str) -> dict[str, tuple[float, float, float]]:
    """Número do bem -> (1.º leilão, 2.º leilão, avaliação).

    Um número que apareça com valores diferentes fica de fora (não se adivinha)."""
    valores: dict[str, tuple[float, float, float]] = {}
    repetidos = set()
    for numero, v1, v2, aval in _RE_BEM_TRES_VALORES.findall(anexo):
        chave = _normalizar_numero(numero)
        trio = (_reais(v1), _reais(v2), _reais(aval))
        if chave in valores and valores[chave] != trio:
            repetidos.add(chave)
        valores[chave] = trio
    for chave in repetidos:
        valores.pop(chave)
    return valores


def interpretar_texto_edital(texto: str) -> Edital | None:
    """Datas de sessão do 1.º e 2.º leilão e os números do Anexo II; None se faltar algo."""
    def data(ordem):
        # "Sessão do 1º Leilão 20/10/2026" (edital 0049) ou "... Leilão: 30/11/2026" (edital 0052).
        m = re.search(rf"Sess[ãa]o do {ordem}\S* Leil[ãa]o\s*:?\s+(\d{{2}})/(\d{{2}})/(\d{{4}})", texto)
        if not m:
            return None
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None

    d1, d2 = data(1), data(2)
    inicio = texto.find("Anexo II – RELAÇÃO DE IMÓVEIS")
    if not d1 or not d2 or d2 < d1 or inicio < 0:
        return None
    anexo = texto[inicio:]
    numeros = {_normalizar_numero(n) for n in _RE_BEM_COM_VALOR.findall(anexo)}
    sem_venda = {_normalizar_numero(n) for n in _RE_BEM_SEM_VENDA.findall(anexo)} - numeros
    valores = {n: v for n, v in _valores_do_anexo(anexo).items() if n in numeros}
    return Edital(d1, d2, numeros, sem_venda, valores) if numeros else None


def ler_edital(corpo: bytes) -> Edital | None:
    if not corpo.startswith(b"%PDF-"):
        return None
    import io

    logging.getLogger("pypdf").setLevel(logging.ERROR)
    from pypdf import PdfReader

    try:
        leitor = PdfReader(io.BytesIO(corpo))
        texto = "\n".join((pagina.extract_text() or "") for pagina in leitor.pages)
    except Exception:  # PDF que não se consegue ler = não interpretável
        return None
    return interpretar_texto_edital(texto)


def numero_do_imovel(url: str | None) -> str | None:
    """hdnimovel do URL, sem zeros à esquerda (o edital usa 8 ou 13 dígitos)."""
    m = _RE_HDNIMOVEL.search(url or "")
    return _normalizar_numero(m.group(1)) if m else None


# ------------------------------------------------------------------ fila e passo

def filtro_pendentes():
    """Mesma regra de pendência de ScraperService.enriquecer_datas_caixa."""
    licitacao = Imovel.modalidade.ilike("%licitação aberta%")
    return and_(
        Imovel.fonte.ilike("%caixa%"),
        Imovel.url.isnot(None),
        # Não gasta pedidos à Caixa com imóveis que já saíram da lista.
        Imovel.na_lista.is_(True),
        or_(
            and_(licitacao, Imovel.data_licitacao_aberta.is_(None)),
            and_(
                or_(Imovel.modalidade.is_(None), not_(licitacao)),
                or_(Imovel.data_primeiro_leilao.is_(None), Imovel.data_segundo_leilao.is_(None)),
            ),
        ),
    )


def _e_licitacao(imovel) -> bool:
    return "licitação aberta" in (imovel.modalidade or "").lower()


def _sem_datas(imovel) -> bool:
    return (imovel.data_primeiro_leilao is None and imovel.data_segundo_leilao is None
            and imovel.data_licitacao_aberta is None)


def _hoje() -> date:
    """Data de hoje (UTC); função própria para os testes a poderem fixar."""
    return datetime.utcnow().date()


def _ultima_data(datas) -> date | None:
    presentes = [d for d in datas if d is not None]
    return max(presentes) if presentes else None


def _datas_vencidas(imovel, hoje: date) -> bool:
    """O último leilão conhecido do imóvel já passou."""
    ultima = _ultima_data((imovel.data_primeiro_leilao, imovel.data_segundo_leilao))
    return ultima is not None and ultima < hoje


def _aplicar_edital(db, edital: Edital, link: str, atual, saltar_incoerentes: bool = False) -> dict:
    """Valida e aplica o edital. Devolve {"paragem": motivo} sem gravar nada se não conferir.

    Um imóvel que não foi vendido volta a um edital novo com datas novas. Se as
    datas que tem já passaram e as do edital ainda não, o edital substitui-as
    (fica um evento no histórico). Datas diferentes ainda por acontecer
    continuam a parar tudo para revisão (EDITAL_INCOERENTE).
    """
    caixa = db.query(Imovel).filter(Imovel.fonte.ilike("%caixa%"), Imovel.url.isnot(None)).all()
    ativos = [i for i in caixa if numero_do_imovel(i.url) in edital.numeros]
    sem_venda = [i for i in caixa if numero_do_imovel(i.url) in edital.numeros_sem_venda]
    if atual not in ativos and atual not in sem_venda:
        return {"paragem": "IMOVEL_FORA_DO_EDITAL"}
    esperado = (edital.data_primeiro_leilao, edital.data_segundo_leilao)
    hoje = _hoje()
    ultima_do_edital = _ultima_data(esperado)
    edital_por_acontecer = ultima_do_edital is not None and ultima_do_edital >= hoje
    a_renovar, saltados = [], []
    for i in ativos:
        tem = (i.data_primeiro_leilao, i.data_segundo_leilao)
        if i.data_licitacao_aberta is not None:
            incoerente = True
        elif any(tem) and tem != esperado:
            if edital_por_acontecer and _datas_vencidas(i, hoje) and not _e_licitacao(i):
                a_renovar.append(i)
                continue
            incoerente = True
        else:
            incoerente = False
        if incoerente:
            if not saltar_incoerentes:
                return {"paragem": "EDITAL_INCOERENTE", "imovel_incoerente": i.id}
            # Só na aplicação manual: este fica como está e é listado para revisão.
            saltados.append(i)
    ativos = [i for i in ativos if i not in saltados]
    preenchidos = 0
    for i in ativos + sem_venda:
        if i.link_edital is None:
            i.link_edital = link
    for i in ativos:  # lotes ANULADO / Arrematado não recebem datas do edital
        if _sem_datas(i) and not _e_licitacao(i):
            i.data_primeiro_leilao, i.data_segundo_leilao = esperado
            preenchidos += 1
    # Valores de venda do 1.º e 2.º leilão (a lista da Caixa só traz um preço,
    # que nos leilões SFI é igual à avaliação). O edital em vigor substitui os anteriores.
    com_valores = 0
    for i in ativos:
        trio = edital.valores.get(numero_do_imovel(i.url))
        if trio and not _e_licitacao(i):
            i.valor_primeiro_leilao, i.valor_segundo_leilao = trio[0], trio[1]
            com_valores += 1
    agora = datetime.utcnow()
    for i in a_renovar:
        i.data_primeiro_leilao, i.data_segundo_leilao = esperado
        i.link_edital = link  # o edital em vigor passa a ser este
        db.add(ImovelEvento(imovel_id=i.id, tipo=ImovelEvento.DATAS, momento=agora))
    resultado = {"membros_na_base": len(ativos) + len(saltados), "sem_venda_na_base": len(sem_venda),
                 "preenchidos_pelo_edital": preenchidos, "renovados_pelo_edital": len(a_renovar),
                 "valores_de_leilao_gravados": com_valores}
    if saltados:
        resultado["saltados_incoerentes"] = [
            {"imovel_id": i.id, "numero": numero_do_imovel(i.url),
             "datas_atuais": [d.isoformat() if d else None for d in (i.data_primeiro_leilao, i.data_segundo_leilao)]}
            for i in saltados
        ]
    return resultado


def _edital_ja_lido(db, link: str, imovel_id: int) -> bool:
    # link_edital só é gravado depois de o edital ter sido lido e aplicado com
    # sucesso; por isso serve de marca de "edital já lido".
    return db.query(Imovel.id).filter(Imovel.link_edital == link, Imovel.id != imovel_id).first() is not None


def _ler_e_aplicar_edital(db, imovel, link: str, pedir, resultado: dict, datas_pagina) -> dict:
    """Pede o edital (1 GET), confere-o com a página e aplica-o. Altera e devolve `resultado`."""
    resultado["pedidos"] += 1
    resposta = pedir(link, "edital")
    if not resposta.ok:
        resultado.update(paragem=resposta.veredicto, destino=resposta.destino)
        return resultado
    edital = ler_edital(resposta.corpo)
    if edital is None:
        resultado["paragem"] = "EDITAL_NAO_INTERPRETAVEL"
        return resultado
    pagina = (imovel.data_primeiro_leilao, imovel.data_segundo_leilao)
    if any(datas_pagina[:2]) and pagina != (edital.data_primeiro_leilao, edital.data_segundo_leilao):
        resultado["paragem"] = "PAGINA_E_EDITAL_DIFERENTES"
        return resultado
    aplicado = _aplicar_edital(db, edital, link, imovel)
    resultado.update(aplicado)
    if "paragem" not in aplicado:
        resultado["estado_edital"] = "LIDO"
        resultado["atualizados"] += aplicado["preenchidos_pelo_edital"] + aplicado["renovados_pelo_edital"]
    return resultado


_RE_NOME_EDITAL = re.compile(r"^(EL[0-9A-Z]+)", re.IGNORECASE)


def link_do_ficheiro_edital(nome_ficheiro: str) -> str | None:
    """Link do edital a partir do nome do PDF guardado (ex.: EL00520226CPARE.PDF ou el00520226cpare (1).pdf).

    Tem de ser igual ao que as páginas mostram: é por ele que o worker sabe que
    o edital já foi lido.
    """
    m = _RE_NOME_EDITAL.match(nome_ficheiro.strip())
    return f"https://{DOMINIO_CAIXA}/editais/{m.group(1).upper()}.PDF" if m else None


_RE_NUMERO_EDITAL = re.compile(r"/editais/EL(\d{4})(\w+)\.PDF$", re.IGNORECASE)


def resumo_editais(db, pasta_editais=None) -> dict:
    """Lembrete sem contactar a CAIXA: pendentes, último edital aplicado e o que fazer a seguir.

    Os editais "Edital Único" têm numeração nacional seguida (EL0050..., EL0051...):
    sugere os números a seguir ao maior já aplicado e lista os PDFs da pasta que
    ainda não foram aplicados (o link deles não está em nenhum imóvel).
    """
    from pathlib import Path

    from sqlalchemy import func

    pendentes = db.query(func.count(Imovel.id)).filter(filtro_pendentes()).scalar() or 0
    por_uf = (db.query(Imovel.estado, func.count(Imovel.id)).filter(filtro_pendentes())
              .group_by(Imovel.estado).order_by(func.count(Imovel.id).desc()).limit(5).all())
    aplicados = {link for (link,) in db.query(Imovel.link_edital).filter(
        Imovel.link_edital.ilike("%/editais/EL%")).distinct()}
    numeros = []
    for link in aplicados:
        m = _RE_NUMERO_EDITAL.search(link)
        if m:
            numeros.append((int(m.group(1)), m.group(2).upper()))
    resumo = {"pendentes_de_datas": pendentes, "pendentes_por_uf": dict(por_uf),
              "editais_aplicados": len(aplicados)}
    if numeros:
        ultimo, sufixo = max(numeros)
        resumo["ultimo_edital"] = f"EL{ultimo:04d}{sufixo}"
        resumo["experimentar"] = [f"https://{DOMINIO_CAIXA}/editais/EL{n:04d}{sufixo}.PDF"
                                  for n in (ultimo + 1, ultimo + 2)]
    if pasta_editais is not None and Path(pasta_editais).is_dir():
        resumo["pdfs_por_aplicar"] = sorted(
            f.name for f in Path(pasta_editais).iterdir()
            if f.is_file() and f.suffix.upper() == ".PDF"
            and link_do_ficheiro_edital(f.name) not in aplicados
        )
    return resumo


def aplicar_edital_local(db, corpo: bytes, link: str, gravar: bool = False,
                         saltar_incoerentes: bool = False) -> dict:
    """Aplica um edital já descarregado (PDF no disco), sem contactar a CAIXA.

    Mesmas verificações do worker (_aplicar_edital): preenche quem não tem datas,
    renova datas já passadas se o edital for por acontecer e pára (nada gravado)
    se houver datas diferentes ainda por acontecer. Sem `gravar` faz rollback.
    """
    edital = ler_edital(corpo)
    if edital is None:
        return {"recusado": "EDITAL_NAO_INTERPRETAVEL"}
    resumo = {"link": link, "data_primeiro_leilao": edital.data_primeiro_leilao.isoformat(),
              "data_segundo_leilao": edital.data_segundo_leilao.isoformat(),
              "numeros_no_edital": len(edital.numeros), "sem_venda_no_edital": len(edital.numeros_sem_venda),
              "valores_no_edital": len(edital.valores)}
    if edital.data_segundo_leilao < _hoje():
        # Datas já passadas seriam mostradas como se fossem o próximo leilão.
        return {**resumo, "recusado": "EDITAL_JA_PASSOU"}
    membros = [
        i for i in db.query(Imovel).filter(Imovel.fonte.ilike("%caixa%"), Imovel.url.isnot(None)).all()
        if numero_do_imovel(i.url) in edital.numeros | edital.numeros_sem_venda
    ]
    if not membros:
        db.rollback()
        return {**resumo, "recusado": "NENHUM_IMOVEL_DA_BASE_NO_EDITAL"}
    aplicado = _aplicar_edital(db, edital, link, min(membros, key=lambda i: i.id),
                               saltar_incoerentes=saltar_incoerentes)
    if "paragem" in aplicado or not gravar:
        db.rollback()
    else:
        db.commit()
    return {**resumo, **aplicado, "gravado": gravar and "paragem" not in aplicado}


def processar_edital_pendente(db, imovel_id: int, link: str, pedir=None, antes_de_pedir=None) -> dict:
    """Só o edital que ficou adiado numa volta anterior (1 GET, nunca a página).

    Permite espaçar os pedidos: página numa volta, edital na seguinte. As datas
    que a página trouxe já estão gravadas no imóvel e servem para conferir.
    """
    imovel = db.get(Imovel, imovel_id)
    resultado = {"pedidos": 0, "processados": 0, "imovel_id": imovel_id, "atualizados": 0,
                 "edital": link, "so_edital": True}
    if imovel is None:
        resultado["estado_edital"] = "IMOVEL_DESAPARECEU"
        return resultado
    if _edital_ja_lido(db, link, imovel_id):
        if imovel.link_edital is None:
            imovel.link_edital = link
        resultado["estado_edital"] = "JA_LIDO"
        return resultado
    pedir_real = pedir or pedir_caixa

    def pedir_(url, tipo):
        if antes_de_pedir:
            antes_de_pedir(imovel_id)
        return pedir_real(url, tipo)

    datas = (imovel.data_primeiro_leilao, imovel.data_segundo_leilao)
    return _ler_e_aplicar_edital(db, imovel, link, pedir_, resultado, datas)


def proximo_de_outra_uf(db, excluir_ufs) -> Imovel | None:
    """Imóvel pendente mais antigo do estado com MAIS pendentes, fora de `excluir_ufs`.

    Os editais da CAIXA são regionais: ler uma página por estado (começando pelos
    que têm mais pendentes) encontra depressa os links dos editais de cada região.
    """
    from sqlalchemy import func

    excluir = {uf.upper() for uf in excluir_ufs if uf}
    contagens = (
        db.query(Imovel.estado, func.count(Imovel.id))
        .filter(filtro_pendentes(), Imovel.estado.isnot(None))
        .group_by(Imovel.estado)
        .all()
    )
    candidatas = sorted(((n, uf) for uf, n in contagens if uf.upper() not in excluir),
                        key=lambda par: (-par[0], par[1]))
    if not candidatas:
        return None
    uf = candidatas[0][1]
    return (db.query(Imovel).filter(filtro_pendentes(), Imovel.estado == uf)
            .order_by(Imovel.id.asc()).first())


def processar_passo(db, estado, pedir=None, max_pedidos: int = 2, antes_de_pedir=None,
                    excluir_ufs=None) -> dict:
    """Um imóvel (+ o seu edital, se ainda não lido). Não trata do estado.

    `excluir_ufs` (conjunto, mesmo vazio) troca a ordem do cursor por "um imóvel
    do estado com mais pendentes ainda não visto" (proximo_de_outra_uf).

    `antes_de_pedir(imovel_id)` é chamado imediatamente antes de CADA GET (o
    worker usa-o para gravar, com commit, a marca de pedido em curso).
    Devolve sempre "pedidos" (quantos GET foram feitos) e, se for preciso parar,
    "paragem" com o motivo; nesse caso o chamador grava a paragem manual.
    """
    pedir_real = pedir or pedir_caixa
    if excluir_ufs is not None:
        imovel = proximo_de_outra_uf(db, excluir_ufs)
        if imovel is None:
            return {"pedidos": 0, "processados": 0, "ufs_esgotadas": True}
    else:
        consulta = db.query(Imovel).filter(filtro_pendentes())
        if estado.cursor_id is not None:
            consulta = consulta.filter(Imovel.id > estado.cursor_id)
        imovel = consulta.order_by(Imovel.id.asc()).first()
        if imovel is None:
            return {"pedidos": 0, "processados": 0, "concluido": True}
    imovel_id = imovel.id

    def pedir(url, tipo):
        if antes_de_pedir:
            antes_de_pedir(imovel_id)
        return pedir_real(url, tipo)

    resultado = {"pedidos": 1, "processados": 1, "imovel_id": imovel_id, "atualizados": 0,
                 "uf": imovel.estado}
    resposta = pedir(imovel.url, "pagina")
    if not resposta.ok:
        resultado.update(paragem=resposta.veredicto, destino=resposta.destino)
        return resultado

    datas, link = ler_pagina(resposta.corpo)
    campos = ("data_primeiro_leilao", "data_segundo_leilao", "data_licitacao_aberta")
    alterou = False
    for campo, valor in zip(campos, datas):
        if getattr(imovel, campo) is None and valor is not None:
            setattr(imovel, campo, valor)
            alterou = True
    resultado["atualizados"] = int(alterou)
    resultado["datas_da_pagina"] = [d.isoformat() if d else None for d in datas]
    # Fotos da galeria na mesma página: nenhum pedido extra.
    fotos = ler_fotos(resposta.corpo, imovel.url)
    resultado["fotos"] = len(fotos)
    resultado["fotos_novas"] = _gravar_fotos(db, imovel, fotos) if fotos else 0
    resultado["edital"] = link
    db.flush()

    if not link:
        resultado["estado_edital"] = "SEM_EDITAL_NA_PAGINA"
        return resultado
    if _edital_ja_lido(db, link, imovel.id):
        if imovel.link_edital is None:
            imovel.link_edital = link
        resultado["estado_edital"] = "JA_LIDO"
        return resultado
    if max_pedidos < 2:
        # O chamador pode pedi-lo numa volta seguinte (processar_edital_pendente).
        resultado["estado_edital"] = "ADIADO_LIMITE_DE_PEDIDOS"
        return resultado

    return _ler_e_aplicar_edital(db, imovel, link, pedir, resultado, datas)
