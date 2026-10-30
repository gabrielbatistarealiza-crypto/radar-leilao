"""Importar os CSV já descarregados (sem contactar a CAIXA) e a ligação da rotina. Sem rede."""
import os
import sys
import time
from pathlib import Path

import pytest

from app.models.caixa_data_worker_state import CaixaDataWorkerState
from app.models.imovel import Imovel
from app.services import scraper_service
from app.services.caixa_datas_edital import PARAGEM_MANUAL
from app.services.caixa_lista_segura import CaixaListaSegura, descarga_dos_ficheiros_locais
from app.services.scraper_service import ScraperService

URL = "https://venda-imoveis.caixa.gov.br/sistema/detalhe-imovel.asp?hdnimovel={}"
CABECALHO = (" N° do imóvel;UF;Cidade;Bairro;Endereço;Preço;Valor de avaliação;Desconto;"
             "Financiamento;Descrição;Modalidade de venda;Link de acesso")


def escrever(pasta, uf, numeros=(), geracao="29/10/2026", horas_atras=1):
    linhas = [";".join([str(n), uf, "CIDADE", "CENTRO", f"RUA A, {n}", "100.000,00", "200.000,00",
                        "50,00", "Sim", "Casa, 2 qto(s).", "Leilão SFI - Edital Único", URL.format(n)])
              for n in numeros]
    texto = (f" Lista de Imóveis da Caixa;;Data de geração:;{geracao};;;;;;;\n{CABECALHO}\n"
             + "\n".join(linhas) + "\n")
    caminho = Path(pasta) / f"Lista_imoveis_{uf}.csv"
    caminho.write_bytes(texto.encode("cp1252"))
    antigo = time.time() - horas_atras * 3600
    os.utime(caminho, (antigo, antigo))


@pytest.fixture()
def pasta(tmp_path):
    for i, uf in enumerate(CaixaListaSegura.UFS):
        escrever(tmp_path, uf, numeros=[1000 + i])
    return tmp_path


# ------------------------------------------------------ verificar ficheiros

def test_aceita_os_27_ficheiros_recentes(pasta):
    descarga, problemas = descarga_dos_ficheiros_locais(pasta)
    assert problemas == []
    assert descarga["sucesso"] == CaixaListaSegura.UFS and descarga["pedidos"] == 0
    assert {str(g) for g in descarga["geracoes"].values()} == {"2026-10-29"}


@pytest.mark.parametrize("estrago, mensagem", [
    (lambda p: (p / "Lista_imoveis_SP.csv").unlink(), "SP: ficheiro em falta"),
    (lambda p: escrever(p, "RJ", horas_atras=13), "RJ: descarregado há 13 h"),
    (lambda p: (p / "Lista_imoveis_GO.csv").write_text("<html>bloqueio</html>"), "GO: não é uma lista"),
])
def test_recusa_se_faltar_ou_estiver_velho_ou_invalido(pasta, estrago, mensagem):
    estrago(pasta)
    descarga, problemas = descarga_dos_ficheiros_locais(pasta)
    assert descarga is None
    assert any(p.startswith(mensagem) for p in problemas), problemas


# --------------------------------------------------------------- importação

def test_importa_e_tira_ausentes_sem_contactar_a_caixa_nem_mexer_na_paragem(
    pasta, sessao, fabrica, monkeypatch
):
    class NuncaContactar:
        UFS = CaixaListaSegura.UFS

        def __init__(self, *a, **k):
            raise AssertionError("não pode contactar a CAIXA")

    monkeypatch.setattr(scraper_service, "CaixaDownloader", NuncaContactar)
    monkeypatch.setattr(ScraperService, "preparar_fila_fotos_caixa", lambda self, i: {"pendentes": 0})

    class LeitorDaPasta(scraper_service.CaixaScraper):
        def __init__(self):
            super().__init__()
            self.pasta_dados = str(pasta)

    monkeypatch.setattr(scraper_service, "CaixaScraper", LeitorDaPasta)
    ausente = fabrica.imovel(url=URL.format(9), fonte="Caixa")
    estado = CaixaDataWorkerState(id=1, ativo=True, bloqueado_ate=PARAGEM_MANUAL, bloqueios_consecutivos=0)
    sessao.add(estado)
    sessao.commit()

    descarga, _ = descarga_dos_ficheiros_locais(pasta)
    r = ScraperService(sessao).atualizar_lista_caixa(remover=True, descarga_local=descarga)

    sessao.expire_all()
    assert r["ufs_importadas"] == sorted(CaixaListaSegura.UFS)
    assert r["imoveis_atualizados"] == 27 and r["imoveis_removidos"] == 1
    assert sessao.get(Imovel, ausente.id).na_lista is False
    # A paragem manual fica como estava: quem a tira é o dono, depois de rever.
    assert sessao.get(CaixaDataWorkerState, 1).bloqueado_ate == PARAGEM_MANUAL


# ----------------------------------------------------------- ligação da rotina

def test_rotina_cria_ligacao_que_se_confirma_e_se_mantem_viva():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import rotina_caixa

    motor = rotina_caixa.criar_motor("sqlite://")
    assert motor.pool._pre_ping is True

    capturado = {}

    def falso_create_engine(url, **kwargs):
        capturado.update(kwargs)
        return "motor"

    import sqlalchemy
    original = sqlalchemy.create_engine
    sqlalchemy.create_engine = falso_create_engine
    try:
        rotina_caixa.criar_motor("postgresql://u@exemplo.render.com/base")
    finally:
        sqlalchemy.create_engine = original
    assert capturado["pool_pre_ping"] is True
    assert capturado["connect_args"]["keepalives"] == 1
    assert capturado["connect_args"]["keepalives_idle"] <= 60
