"""scripts/rotina_caixa.py: guarda da base de produção (sem rede e sem PostgreSQL).

O fluxo completo (lista + datas, bloqueios, paragem manual já gravada, limite diário)
foi validado contra bases PostgreSQL temporárias; aqui fica a parte que não precisa delas.
"""
import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import create_engine

CAMINHO = Path(__file__).resolve().parent.parent / "scripts" / "rotina_caixa.py"


@pytest.fixture(scope="module")
def rotina():
    spec = importlib.util.spec_from_file_location("rotina_caixa", CAMINHO)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.mark.parametrize("url", [
    "sqlite://",
    "postgresql://postgres@localhost:5433/arremata_copia",
    "postgresql://u:s@127.0.0.1:5432/radar",
    "postgresql://u:s@exemplo.com/radar",
    "postgresql://u:s@render.com.exemplo.com/radar",
])
def test_producao_so_aceita_servidores_do_render(rotina, url):
    ok, motivo = rotina.confirmar_producao(create_engine("sqlite://"), url)
    assert ok is False and "Render" in motivo


def test_servidor_render_que_nao_responde_e_recusado(rotina):
    ok, motivo = rotina.confirmar_producao(
        create_engine("sqlite://"), "postgresql://u:s@dpg-x-a.oregon-postgres.render.com/radar"
    )
    assert ok is False and "não foi possível confirmar" in motivo


def test_variaveis_de_ligacao_por_base(rotina):
    assert rotina.VARIAVEL_URL == {"copia": "RADAR_COPIA_DB_URL", "producao": "RADAR_RENDER_DB_URL"}
