"""Worker de datas da CAIXA por imóvel + edital.

Sem rede: o pedido HTTP é trocado por respostas prontas (ou por uma sessão
falsa nos testes de pedir_caixa). O Selenium é trocado por uma função que
falha o teste se for chamada. A base é a de teste do conftest.
"""
from datetime import date, datetime

import pytest

from app.models.caixa_data_worker_state import CaixaDataWorkerState
from app.scrapers.caixa import CaixaScraper
from app.services import caixa_datas_edital as ce
from app.services import caixa_datas_worker as worker
from app.services.caixa_datas_edital import RespostaCaixa

URL = "https://venda-imoveis.caixa.gov.br/sistema/detalhe-imovel.asp?hdnimovel={}"
EDITAL_A = "https://venda-imoveis.caixa.gov.br/editais/EL00490226CPARE.PDF"
D1, D2 = date(2026, 10, 20), date(2026, 10, 26)
N1, N2, N3, N4 = "8444408241749", "8444408241750", "8444408241751", "8444408241752"


def pagina(d1=None, d2=None, edital="EL00490226CPARE", licitacao=None):
    partes = ["<html><head><title>Detalhe</title></head><body>"]
    if d1:
        partes.append(f"<span>Data do 1º Leilão - {d1:%d/%m/%Y} - 10h00</span>")
    if d2:
        partes.append(f"<span>Data do 2º Leilão - {d2:%d/%m/%Y} - 10h00</span>")
    if licitacao:
        partes.append(f"<p>Data da Licitação Aberta - {licitacao:%d/%m/%Y}</p>")
    if edital:
        partes.append(f"<a href='#' onclick=javascript:ExibeDoc('/editais/{edital}.PDF')>"
                      "<strong>Baixar edital e anexos</strong></a>")
    partes.append("</body></html>")
    return "".join(partes).encode("utf-8")


def texto_edital(numeros, d1=D1, d2=D2):
    return (f"1.1 – Data e Hora da Sessão do 1º Leilão {d1:%d/%m/%Y} às 10:00h.\n"
            f"1.2 – Data e Hora da Sessão do 2º Leilão {d2:%d/%m/%Y} às 10:00h.\n"
            "Anexo II – RELAÇÃO DE IMÓVEIS\n"
            + "\n".join(f"Casa ... {n}  180.000,00  108.000,00" for n in numeros))


def pdf(numeros, **kw):
    return b"%PDF-" + texto_edital(numeros, **kw).encode("utf-8")


@pytest.fixture(autouse=True)
def sem_selenium_e_pdf_de_texto(monkeypatch):
    def proibido(*a, **k):
        raise AssertionError("o worker não pode abrir o Selenium")

    monkeypatch.setattr(CaixaScraper, "_coletar_detalhes_com_selenium", proibido)
    # Os PDFs falsos dos testes são texto depois de "%PDF-".
    monkeypatch.setattr(ce, "ler_edital", lambda corpo: ce.interpretar_texto_edital(corpo[5:].decode()))


class Rede:
    """pedir() falso: devolve respostas prontas por URL e regista os pedidos."""

    def __init__(self, respostas):
        self.respostas, self.pedidos = respostas, []

    def __call__(self, url, tipo):
        self.pedidos.append((url, tipo))
        r = self.respostas[url]
        return r if isinstance(r, RespostaCaixa) else RespostaCaixa("OK", status=200, corpo=r)


def imovel(fabrica, numero, **campos):
    base = dict(fonte="Caixa", url=URL.format(numero), data_primeiro_leilao=None, data_segundo_leilao=None)
    base.update(campos)
    return fabrica.imovel(**base)


def estado(sessao):
    sessao.expire_all()
    return sessao.get(CaixaDataWorkerState, 1)


def recarregar(sessao, *objs):
    sessao.expire_all()
    for o in objs:
        sessao.refresh(o)


# ------------------------------------------------------------ passo do worker

def test_pagina_e_edital_preenchem_todos_os_imoveis_do_edital(sessao, fabrica):
    a, b, c = imovel(fabrica, N1), imovel(fabrica, N2), imovel(fabrica, N3)
    ja = imovel(fabrica, N4, data_primeiro_leilao=D1, data_segundo_leilao=D2)
    rede = Rede({a.url: pagina(D1, D2), EDITAL_A: pdf([N1, N2, N3, N4])})

    r = worker.processar_lote_datas_caixa(sessao, pedir=rede)

    recarregar(sessao, a, b, c, ja)
    assert rede.pedidos == [(a.url, "pagina"), (EDITAL_A, "edital")]
    assert r["pedidos"] == 2 and r["estado_edital"] == "LIDO" and "paragem" not in r
    for i in (a, b, c):
        assert (i.data_primeiro_leilao, i.data_segundo_leilao) == (D1, D2)
        assert i.link_edital == EDITAL_A
    assert ja.link_edital == EDITAL_A  # só o link: as datas já lá estavam
    assert r["preenchidos_pelo_edital"] == 2  # b e c (a veio da página)
    assert estado(sessao).cursor_id == a.id and estado(sessao).bloqueado_ate is None


def test_edital_ja_lido_nao_e_pedido_outra_vez(sessao, fabrica):
    imovel(fabrica, N1, data_primeiro_leilao=D1, data_segundo_leilao=D2, link_edital=EDITAL_A)
    b = imovel(fabrica, N2)
    rede = Rede({b.url: pagina(D1, D2)})

    r = worker.processar_lote_datas_caixa(sessao, pedir=rede)

    recarregar(sessao, b)
    assert rede.pedidos == [(b.url, "pagina")]
    assert r["estado_edital"] == "JA_LIDO" and r["pedidos"] == 1
    assert (b.data_primeiro_leilao, b.data_segundo_leilao, b.link_edital) == (D1, D2, EDITAL_A)


def test_limite_de_um_pedido_adia_o_edital(sessao, fabrica):
    a, b = imovel(fabrica, N1), imovel(fabrica, N2)
    rede = Rede({a.url: pagina(D1, D2)})

    r = worker.processar_lote_datas_caixa(sessao, pedir=rede, max_pedidos=1)

    recarregar(sessao, a, b)
    assert rede.pedidos == [(a.url, "pagina")]
    assert r["estado_edital"] == "ADIADO_LIMITE_DE_PEDIDOS"
    assert a.data_primeiro_leilao == D1 and a.link_edital is None
    assert b.data_primeiro_leilao is None


def test_pagina_sem_datas_nem_edital_avanca_sem_parar(sessao, fabrica):
    a, b = imovel(fabrica, N1), imovel(fabrica, N2)
    rede = Rede({a.url: pagina(edital=None)})

    r = worker.processar_lote_datas_caixa(sessao, pedir=rede)

    assert r["estado_edital"] == "SEM_EDITAL_NA_PAGINA" and r["atualizados"] == 0
    assert estado(sessao).cursor_id == a.id and estado(sessao).ativo is True
    assert r["tem_mais"] is True and "paragem" not in r


@pytest.mark.parametrize("veredicto", [
    "REDIRECIONADO", "BLOQUEADO_HTTP_403", "BLOQUEADO_HTTP_429", "BLOQUEADO", "PISTA_ANTIBOT",
    "TIMEOUT_LIGACAO", "ERRO_DE_REDE", "HTTP_INESPERADO_404",
])
def test_bloqueio_na_pagina_para_ate_revisao_manual(sessao, fabrica, veredicto):
    a, b = imovel(fabrica, N1), imovel(fabrica, N2)
    rede = Rede({a.url: RespostaCaixa(veredicto)})
    agora = datetime(2026, 10, 28, 12, 0, 0)

    r = worker.processar_lote_datas_caixa(sessao, agora=agora, pedir=rede)

    atual = estado(sessao)
    assert r["paragem"] == veredicto and r["paragem_manual"] is True and r["pedidos"] == 1
    assert atual.bloqueado_ate == ce.PARAGEM_MANUAL and atual.ativo is False
    assert atual.cursor_id == a.id - 1  # depois da revisão, o mesmo imóvel é o próximo
    recarregar(sessao, a, b)
    assert a.data_primeiro_leilao is None and b.data_primeiro_leilao is None

    # Volta seguinte: não pede nada (fila inativa).
    r2 = worker.processar_lote_datas_caixa(sessao, agora=agora, pedir=rede)
    assert r2["pedidos"] == 0 and len(rede.pedidos) == 1


def test_paragem_manual_resiste_a_reativacao_e_ao_tempo(sessao, fabrica):
    a = imovel(fabrica, N1)
    rede = Rede({a.url: RespostaCaixa("BLOQUEADO")})
    worker.processar_lote_datas_caixa(sessao, pedir=rede)

    worker.reativar_worker_datas_caixa(sessao)  # o que a importação diária faz
    sessao.commit()
    r = worker.processar_lote_datas_caixa(sessao, agora=datetime(2030, 1, 1), pedir=rede)

    assert r["aguardando_bloqueio"] is True and r["paragem_manual"] is True
    assert len(rede.pedidos) == 1


def test_porteiro_recusa_todas_as_rotinas_durante_a_paragem(sessao, fabrica):
    from app.services.caixa_rotinas import executar_lote_datas

    a = imovel(fabrica, N1)
    worker.processar_lote_datas_caixa(sessao, pedir=Rede({a.url: RespostaCaixa("REDIRECIONADO")}))

    assert executar_lote_datas(sessao)["aguardando_bloqueio"] is True


def test_bloqueio_no_edital_guarda_so_as_datas_da_pagina_e_para(sessao, fabrica):
    a, b = imovel(fabrica, N1), imovel(fabrica, N2)
    rede = Rede({a.url: pagina(D1, D2), EDITAL_A: RespostaCaixa("BLOQUEADO_HTTP_403")})

    r = worker.processar_lote_datas_caixa(sessao, pedir=rede)

    recarregar(sessao, a, b)
    assert r["paragem"] == "BLOQUEADO_HTTP_403" and r["pedidos"] == 2
    assert a.data_primeiro_leilao == D1 and a.link_edital is None  # edital não ficou marcado como lido
    assert b.data_primeiro_leilao is None
    assert estado(sessao).bloqueado_ate == ce.PARAGEM_MANUAL


@pytest.mark.parametrize("caso, paragem", [
    ("membro_com_outras_datas", "EDITAL_INCOERENTE"),
    ("imovel_fora_do_edital", "IMOVEL_FORA_DO_EDITAL"),
    ("pagina_diferente_do_edital", "PAGINA_E_EDITAL_DIFERENTES"),
    ("edital_sem_datas", "EDITAL_NAO_INTERPRETAVEL"),
])
def test_edital_que_nao_confere_nao_grava_nada_do_edital(sessao, fabrica, caso, paragem):
    a, b = imovel(fabrica, N1), imovel(fabrica, N2)
    numeros, pagina_a = [N1, N2, N3], pagina(D1, D2)
    corpo_edital = pdf(numeros)
    if caso == "membro_com_outras_datas":
        imovel(fabrica, N3, data_primeiro_leilao=date(2026, 11, 3), data_segundo_leilao=date(2026, 11, 9))
    elif caso == "imovel_fora_do_edital":
        corpo_edital = pdf([N2, N3])
    elif caso == "pagina_diferente_do_edital":
        pagina_a = pagina(date(2026, 10, 21), D2)
    else:
        corpo_edital = ("%PDF-Anexo II – RELAÇÃO DE IMÓVEIS\n" + N1).encode("utf-8")
    rede = Rede({a.url: pagina_a, EDITAL_A: corpo_edital})

    r = worker.processar_lote_datas_caixa(sessao, pedir=rede)

    recarregar(sessao, a, b)
    assert r["paragem"] == paragem
    assert b.data_primeiro_leilao is None and b.link_edital is None and a.link_edital is None
    assert estado(sessao).bloqueado_ate == ce.PARAGEM_MANUAL


def test_imovel_de_licitacao_aberta_no_edital_nao_recebe_datas_de_leilao(sessao, fabrica):
    a = imovel(fabrica, N1)
    lic = imovel(fabrica, N2, modalidade="Licitação Aberta")
    rede = Rede({a.url: pagina(D1, D2), EDITAL_A: pdf([N1, N2])})

    worker.processar_lote_datas_caixa(sessao, pedir=rede)

    recarregar(sessao, lic)
    assert lic.data_primeiro_leilao is None and lic.data_segundo_leilao is None


def test_datas_existentes_nunca_sao_substituidas(sessao, fabrica):
    existente = date(2026, 1, 1)
    a = imovel(fabrica, N1, data_primeiro_leilao=existente)
    rede = Rede({a.url: pagina(D1, D2, edital=None)})

    worker.processar_lote_datas_caixa(sessao, pedir=rede)

    recarregar(sessao, a)
    assert a.data_primeiro_leilao == existente and a.data_segundo_leilao == D2


def test_fila_vazia_conclui_sem_pedidos(sessao, fabrica):
    imovel(fabrica, N1, data_primeiro_leilao=D1, data_segundo_leilao=D2)
    rede = Rede({})

    r = worker.processar_lote_datas_caixa(sessao, pedir=rede)

    assert r["concluido"] is True and rede.pedidos == []
    assert estado(sessao).ativo is False


# ------------------------------------------------- marca de pedido em curso

def test_marca_gravada_antes_de_cada_pedido_e_retirada_no_fim(sessao, fabrica, motor):
    from sqlalchemy.orm import sessionmaker

    a, b = imovel(fabrica, N1), imovel(fabrica, N2)
    vistos = []
    outra = sessionmaker(bind=motor)()  # outra sessão: só vê o que já teve commit

    def pedir(url, tipo):
        # Sem transação aberta na sessão do worker = o commit da marca acabou de acontecer.
        assert not sessao.in_transaction()
        outra.expire_all()
        vistos.append((tipo, outra.get(CaixaDataWorkerState, 1).bloqueado_ate))
        corpo = pagina(D1, D2) if tipo == "pagina" else pdf([N1, N2])
        return RespostaCaixa("OK", status=200, corpo=corpo)

    try:
        worker.processar_lote_datas_caixa(sessao, pedir=pedir)
    finally:
        outra.close()

    assert vistos == [("pagina", ce.PARAGEM_MANUAL), ("edital", ce.PARAGEM_MANUAL)]
    assert estado(sessao).bloqueado_ate is None  # retirada depois de gravar o resultado


def test_excecao_durante_o_pedido_deixa_o_worker_parado_sem_repetir(sessao, fabrica):
    a = imovel(fabrica, N1)
    pedidos = []

    def pedir(url, tipo):
        pedidos.append(url)
        raise RuntimeError("o processo caiu a meio do pedido")

    with pytest.raises(RuntimeError):
        worker.processar_lote_datas_caixa(sessao, pedir=pedir)

    assert estado(sessao).bloqueado_ate == ce.PARAGEM_MANUAL
    r = worker.processar_lote_datas_caixa(sessao, pedir=pedir)
    assert r["aguardando_bloqueio"] is True and r["paragem_manual"] is True
    assert pedidos == [a.url]


def test_executar_lote_datas_passa_o_limite_de_pedidos(sessao, fabrica):
    from app.services.caixa_rotinas import executar_lote_datas

    a, b = imovel(fabrica, N1), imovel(fabrica, N2)
    rede = Rede({a.url: pagina(D1, D2)})

    r = executar_lote_datas(sessao, max_pedidos=1, pedir=rede)

    assert r["estado_edital"] == "ADIADO_LIMITE_DE_PEDIDOS" and rede.pedidos == [(a.url, "pagina")]


# ------------------------------------------------------------------ pedir_caixa

class RespostaHttpFalsa:
    def __init__(self, status, corpo=b"", headers=None):
        self.status_code, self._corpo, self.headers = status, corpo, headers or {}
        self.lidos, self.fechada = 0, False

    def iter_content(self, n):
        for i in range(0, len(self._corpo), n):
            self.lidos += len(self._corpo[i:i + n])
            yield self._corpo[i:i + n]

    def close(self):
        self.fechada = True


def sessao_falsa(resposta=None, erro=None):
    registo = {}

    class SessaoFalsa:
        trust_env = True

        def get(self, url, **kw):
            registo.update(kw, url=url, trust_env=self.trust_env, pedidos=registo.get("pedidos", 0) + 1)
            if erro:
                raise erro
            registo["resposta"] = resposta
            return resposta

        def close(self):
            registo["sessao_fechada"] = True

    return SessaoFalsa, registo


@pytest.mark.parametrize("status, veredicto", [
    (302, "REDIRECIONADO"), (301, "REDIRECIONADO"), (403, "BLOQUEADO_HTTP_403"), (429, "BLOQUEADO_HTTP_429"),
])
def test_3xx_403_429_param_sem_ler_o_corpo(status, veredicto):
    resposta = RespostaHttpFalsa(status, b"x" * 100_000, {"Location": "https://validate.perfdrive.com/a"})
    fabrica, registo = sessao_falsa(resposta)

    r = ce.pedir_caixa(URL.format(N1), "pagina", sessao_factory=fabrica)

    assert r.veredicto == veredicto and resposta.lidos == 0 and resposta.fechada
    assert registo["pedidos"] == 1 and registo["allow_redirects"] is False
    assert registo["stream"] is True and registo["trust_env"] is False


@pytest.mark.parametrize("corpo, veredicto", [
    (b"<html><body>Resolva o CAPTCHA para continuar</body></html>", "BLOQUEADO"),
    (b"<html><script src='https://x.perfdrive.com/a.js'></script><body>ok</body></html>", "PISTA_ANTIBOT"),
])
def test_bloqueio_no_conteudo_html(corpo, veredicto):
    fabrica, _ = sessao_falsa(RespostaHttpFalsa(200, corpo))
    assert ce.pedir_caixa(URL.format(N1), "pagina", sessao_factory=fabrica).veredicto == veredicto


def test_pagina_normal_e_ok():
    fabrica, _ = sessao_falsa(RespostaHttpFalsa(200, pagina(D1, D2)))
    r = ce.pedir_caixa(URL.format(N1), "pagina", sessao_factory=fabrica)
    assert r.ok and ce.ler_pagina(r.corpo) == ((D1, D2, None), EDITAL_A)


def test_edital_que_nao_e_pdf_para():
    fabrica, _ = sessao_falsa(RespostaHttpFalsa(200, b"<html><body>erro</body></html>"))
    assert ce.pedir_caixa(EDITAL_A, "edital", sessao_factory=fabrica).veredicto == "NAO_E_PDF"


def test_404_e_resposta_inesperada():
    fabrica, _ = sessao_falsa(RespostaHttpFalsa(404, b"<html><body>Not found</body></html>"))
    assert ce.pedir_caixa(URL.format(N1), "pagina", sessao_factory=fabrica).veredicto == "HTTP_INESPERADO_404"


def test_timeouts_e_erros_de_rede_sem_repetir():
    import requests

    for erro, veredicto in ((requests.ConnectTimeout(), "TIMEOUT_LIGACAO"),
                            (requests.ReadTimeout(), "TIMEOUT_LEITURA_CABECALHOS"),
                            (requests.ConnectionError(), "ERRO_DE_REDE")):
        fabrica, registo = sessao_falsa(erro=erro)
        assert ce.pedir_caixa(URL.format(N1), "pagina", sessao_factory=fabrica).veredicto == veredicto
        assert registo["pedidos"] == 1


@pytest.mark.parametrize("url, tipo", [
    ("http://venda-imoveis.caixa.gov.br/sistema/detalhe-imovel.asp?hdnimovel=1", "pagina"),
    ("https://outro.gov.br/sistema/detalhe-imovel.asp?hdnimovel=1", "pagina"),
    ("https://venda-imoveis.caixa.gov.br:8443/sistema/detalhe-imovel.asp?hdnimovel=1", "pagina"),
    ("https://u:s@venda-imoveis.caixa.gov.br/sistema/detalhe-imovel.asp?hdnimovel=1", "pagina"),
    ("https://venda-imoveis.caixa.gov.br/editais/X.PDF?a=1", "edital"),
    ("https://venda-imoveis.caixa.gov.br/sistema/detalhe-imovel.asp?hdnimovel=1", "edital"),
])
def test_url_fora_do_permitido_nao_faz_pedido(url, tipo):
    fabrica, registo = sessao_falsa(RespostaHttpFalsa(200, b""))
    assert ce.pedir_caixa(url, tipo, sessao_factory=fabrica).veredicto == "URL_RECUSADO"
    assert "pedidos" not in registo


# ------------------------------------------------------------ leitura sem rede

def test_ler_pagina_com_dois_editais_diferentes_nao_escolhe():
    html = pagina(D1, D2) + b"<a onclick=\"ExibeDoc('/editais/EL99999999CPARE.PDF')\">x</a>"
    assert ce.ler_pagina(html)[1] is None


def test_ler_pagina_ignora_pdfs_que_nao_sao_editais():
    html = b"<script>window.open('/editais/regras-VOL/comocomprar.pdf?v=01');</script>"
    assert ce.ler_pagina(html)[1] is None


def test_interpretar_edital():
    e = ce.interpretar_texto_edital(texto_edital([N1, N2]))
    assert (e.data_primeiro_leilao, e.data_segundo_leilao, e.numeros) == (D1, D2, {N1, N2})


def test_edital_com_datas_trocadas_nao_e_interpretavel():
    assert ce.interpretar_texto_edital(texto_edital([N1], d1=D2, d2=D1)) is None


def test_numero_do_imovel():
    assert ce.numero_do_imovel(URL.format("0000010311523")) == "10311523"
    assert ce.numero_do_imovel(URL.format("8444408241749")) == "8444408241749"
    assert ce.numero_do_imovel("https://x/y") is None


ANEXO_REAL = (
    "1.1 – Data e Hora da Sessão do 1º Leilão 20/10/2026 às 10:00h.\n"
    "1.2 – Data e Hora da Sessão do 2º Leilão 26/10/2026 às 10:00h.\n"
    "Anexo II – RELAÇÃO DE IMÓVEIS\n"
    "cozinha. IPTU: 0102141074001 Matrícula: 20090 Ofício: 1.  \n"
    "8444428731636  180.000,00  108.000,00  180.000,00  \n"
    "garagem. IPTU: \n10311523  230.000,00  265.163,79  230.000,00  \n"
    "IPTU: S0131401036200 \nMatrícula: 72929 \n"
    "1444405673771  ANULADO    \n"
    "1444404561864  Arrematado \n1º leilão \n"
)


def test_anexo_ii_numeros_curtos_iptu_e_lotes_sem_venda():
    e = ce.interpretar_texto_edital(ANEXO_REAL)
    assert e.numeros == {"8444428731636", "10311523"}  # 13 e 8 dígitos, com valores
    assert e.numeros_sem_venda == {"1444405673771", "1444404561864"}
    # números de IPTU nunca contam como imóveis
    assert "102141074001" not in e.numeros | e.numeros_sem_venda
    assert "131401036200" not in e.numeros | e.numeros_sem_venda


def test_imovel_com_numero_curto_e_reconhecido_e_preenchido(sessao, fabrica):
    a = imovel(fabrica, "10311523")
    b = imovel(fabrica, "8444428731636")
    corpo = b"%PDF-" + ANEXO_REAL.encode("utf-8")
    rede = Rede({a.url: pagina(D1, D2), EDITAL_A: corpo})

    r = worker.processar_lote_datas_caixa(sessao, pedir=rede)

    recarregar(sessao, a, b)
    assert "paragem" not in r and r["estado_edital"] == "LIDO"
    assert (b.data_primeiro_leilao, b.data_segundo_leilao) == (D1, D2)


def test_lote_anulado_esta_no_edital_mas_nao_recebe_datas(sessao, fabrica):
    a = imovel(fabrica, "8444428731636")
    anulado = imovel(fabrica, "1444405673771")
    corpo = b"%PDF-" + ANEXO_REAL.encode("utf-8")
    rede = Rede({a.url: pagina(D1, D2), EDITAL_A: corpo})

    r = worker.processar_lote_datas_caixa(sessao, pedir=rede)

    recarregar(sessao, anulado)
    assert "paragem" not in r and r["sem_venda_na_base"] == 1
    assert anulado.data_primeiro_leilao is None and anulado.link_edital == EDITAL_A


def test_imovel_anulado_na_pagina_nao_e_tratado_como_fora_do_edital(sessao, fabrica):
    anulado = imovel(fabrica, "1444405673771")
    corpo = b"%PDF-" + ANEXO_REAL.encode("utf-8")
    rede = Rede({anulado.url: pagina(), EDITAL_A: corpo})

    r = worker.processar_lote_datas_caixa(sessao, pedir=rede)

    recarregar(sessao, anulado)
    assert "paragem" not in r and r["estado_edital"] == "LIDO"
    assert anulado.data_primeiro_leilao is None


# ------------------------------------------------------- comando para a cópia

def test_comando_recusa_base_que_nao_e_a_copia():
    import importlib.util
    from pathlib import Path

    from sqlalchemy import create_engine

    caminho = Path(__file__).resolve().parent.parent / "scripts" / "datas_caixa_copia.py"
    spec = importlib.util.spec_from_file_location("datas_caixa_copia", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)

    ok, motivo = modulo.confirmar_copia(create_engine("sqlite://"))
    assert ok is False and "não foi possível confirmar" in motivo
