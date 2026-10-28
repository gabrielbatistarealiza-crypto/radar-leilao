"""Descarga das listas de imóveis da CAIXA (CSV por UF), só com requests.

Substitui, na importação, o CaixaDownloader com Selenium. Mesma interface:
`UFS` e `baixar_todos()` devolvendo {"sucesso", "falhas", "bloqueado", ...}.

Regras de segurança (iguais às do worker de datas):
  - UM GET por UF ao endereço direto da lista, sem novas tentativas, sem
    seguir redirecionamentos, sem proxy do ambiente e nunca com Selenium;
  - o estado HTTP decide antes do corpo (3xx, 403 e 429 param sem o ler);
  - qualquer resposta inesperada (bloqueio, erro, timeout, ficheiro que não é
    a lista da CAIXA) PARA a descarga inteira: as UFs seguintes não são pedidas
    e quem chamou grava a paragem manual;
  - pausa entre UFs (RADAR_CAIXA_LISTA_INTERVALO_SEGUNDOS, mínimo 30 s);
  - o CSV anterior de cada UF fica em dados/_anterior/ e o novo só substitui o
    antigo depois de validado (escrita num temporário + os.replace).
"""
import logging
import os
import re
import time
from datetime import date
from pathlib import Path

from app.services.caixa_acesso import intervalo_env
from app.services.caixa_datas_edital import pedir_caixa

logger = logging.getLogger(__name__)

URL_LISTA = "https://venda-imoveis.caixa.gov.br/listaweb/Lista_imoveis_{uf}.csv"
INTERVALO_PADRAO_SEGUNDOS = 60
INTERVALO_MINIMO_SEGUNDOS = 30

_RE_GERACAO = re.compile(r"Data de gera\S*:?;*\s*(\d{2})/(\d{2})/(\d{4})", re.IGNORECASE)


def intervalo_entre_ufs() -> int:
    return intervalo_env("RADAR_CAIXA_LISTA_INTERVALO_SEGUNDOS",
                         INTERVALO_PADRAO_SEGUNDOS, INTERVALO_MINIMO_SEGUNDOS)


def _decodificar(corpo: bytes) -> str:
    try:
        return corpo.decode("utf-8-sig")
    except UnicodeDecodeError:
        return corpo.decode("cp1252", errors="replace")


def data_de_geracao(corpo: bytes) -> date | None:
    """Data de geração se o ficheiro for mesmo uma lista da CAIXA; None caso contrário."""
    texto = _decodificar(corpo[:4000])
    linhas = [linha for linha in texto.splitlines() if linha.strip()][:3]
    if len(linhas) < 2:
        return None
    if "lista de im" not in linhas[0].lower():
        return None
    cabecalho = linhas[1].lower()
    if not all(coluna in cabecalho for coluna in ("uf", "cidade", "link de acesso")):
        return None
    m = _RE_GERACAO.search(linhas[0])
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


class CaixaListaSegura:
    UFS = [
        "AC", "AL", "AP", "AM", "BA", "CE", "DF",
        "ES", "GO", "MA", "MT", "MS", "MG", "PA",
        "PB", "PR", "PE", "PI", "RJ", "RN", "RS",
        "RO", "RR", "SC", "SP", "SE", "TO",
    ]

    def __init__(self, pasta_dados=None, pedir=None, dormir=None, intervalo=None):
        self.pasta_dados = Path(pasta_dados) if pasta_dados else (
            Path(__file__).resolve().parent.parent / "scrapers" / "dados"
        )
        self.pedir = pedir or pedir_caixa
        self.dormir = dormir or time.sleep
        self.intervalo = intervalo if intervalo is not None else intervalo_entre_ufs()

    def _gravar(self, uf: str, corpo: bytes) -> Path:
        self.pasta_dados.mkdir(parents=True, exist_ok=True)
        final = self.pasta_dados / f"Lista_imoveis_{uf}.csv"
        temporario = self.pasta_dados / f".Lista_imoveis_{uf}.csv.tmp"  # não acaba em .csv
        with open(temporario, "wb") as f:
            f.write(corpo)
            f.flush()
            os.fsync(f.fileno())
        if final.exists():
            reserva = self.pasta_dados / "_anterior"
            reserva.mkdir(exist_ok=True)
            os.replace(final, reserva / final.name)
        os.replace(temporario, final)
        return final

    def baixar_todos(self, max_ufs: int | None = None) -> dict:
        ufs = self.UFS[:max_ufs] if max_ufs else list(self.UFS)
        resultado = {"sucesso": [], "falhas": [], "bloqueado": False, "uf_bloqueada": None,
                     "paragem": None, "pedidos": 0, "geracoes": {}}
        for indice, uf in enumerate(ufs):
            if indice:
                self.dormir(self.intervalo)
            resposta = self.pedir(URL_LISTA.format(uf=uf), "lista")
            resultado["pedidos"] += 1
            motivo = None if resposta.ok else resposta.veredicto
            geracao = data_de_geracao(resposta.corpo) if resposta.ok else None
            if motivo is None and geracao is None:
                motivo = "NAO_E_CSV_DA_CAIXA"
            if motivo:
                # Para tudo: nenhuma UF seguinte é pedida; o CSV anterior fica.
                resultado.update(bloqueado=True, uf_bloqueada=uf, paragem=motivo)
                resultado["falhas"].append({"uf": uf, "erro": motivo, "destino": resposta.destino})
                logger.warning("Lista da CAIXA: descarga parada em %s (%s).", uf, motivo)
                break
            self._gravar(uf, resposta.corpo)
            resultado["sucesso"].append(uf)
            resultado["geracoes"][uf] = geracao.isoformat()
        return resultado
