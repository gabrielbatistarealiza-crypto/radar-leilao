"""Lock consultivo da CAIXA entre DOIS PROCESSOS independentes (PostgreSQL).

Só corre com TEST_DATABASE_URL a apontar para um PostgreSQL de teste cujo nome
contenha "test" (a proteção do conftest recusa outros nomes). Sem isso, é
ignorado: o lock entre processos NÃO fica validado.

Cada caso lança um processo-filho que usa o porteiro real (acesso_caixa) contra
a base de teste e prende o lock; o processo do teste confirma que não o
consegue adquirir e que o consegue depois de o filho:
  - terminar normalmente;
  - sair por exceção dentro do bloco protegido;
  - ser terminado à força (kill).
Não há rede para a CAIXA: o filho não faz pedidos, só segura o lock.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from app.services import caixa_acesso
from app.services.caixa_acesso import CaixaOcupada

BACKEND = Path(__file__).resolve().parent.parent

FILHO = r"""
import os, sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.services.caixa_acesso import acesso_caixa

modo = sys.argv[1]
motor = create_engine(os.environ["TEST_DATABASE_URL"])
db = sessionmaker(bind=motor)()
try:
    with acesso_caixa(db, "processo-filho", esperar=False):
        print("LOCK", flush=True)
        sys.stdin.readline()          # espera ordem do processo do teste
        if modo == "excecao":
            raise RuntimeError("falha simulada dentro do porteiro")
finally:
    db.close()
    motor.dispose()
"""


@pytest.fixture()
def pg(motor):
    if motor.dialect.name != "postgresql":
        pytest.skip("só com TEST_DATABASE_URL a apontar para PostgreSQL de teste")
    nome = motor.url.database or ""
    assert "test" in nome, "recusa: a base não é de teste"
    return motor


def _lancar_filho(modo: str) -> subprocess.Popen:
    ambiente = dict(os.environ)
    ambiente["RADAR_DISABLE_BACKGROUND_JOBS"] = "1"
    filho = subprocess.Popen(
        [sys.executable, "-c", FILHO, modo],
        cwd=str(BACKEND),
        env=ambiente,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    linha = filho.stdout.readline().strip()
    assert linha == "LOCK", f"o filho não adquiriu o lock: {filho.stderr.read()}"
    return filho


def _tentar_adquirir(motor):
    db = sessionmaker(bind=motor)()
    try:
        ligacao = caixa_acesso._adquirir_lock_entre_processos(db)
        caixa_acesso._libertar_lock_entre_processos(ligacao)
        return True
    except CaixaOcupada:
        return False
    finally:
        db.close()


def _adquire_em_ate(motor, segundos=10.0):
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if _tentar_adquirir(motor):
            return True
        time.sleep(0.2)
    return False


@pytest.mark.parametrize("modo", ["sucesso", "excecao"])
def test_outro_processo_fica_de_fora_e_entra_depois(pg, modo):
    filho = _lancar_filho(modo)
    try:
        assert _tentar_adquirir(pg) is False
        filho.stdin.write("\n")
        filho.stdin.flush()
        filho.wait(timeout=30)
    finally:
        if filho.poll() is None:
            filho.kill()
    if modo == "excecao":
        assert filho.returncode != 0
    else:
        assert filho.returncode == 0
    assert _adquire_em_ate(pg) is True


def test_lock_e_libertado_quando_o_processo_morre(pg):
    filho = _lancar_filho("sucesso")
    try:
        assert _tentar_adquirir(pg) is False
    finally:
        filho.kill()
        filho.wait(timeout=30)
    # O PostgreSQL liberta o lock de sessão quando a ligação cai.
    assert _adquire_em_ate(pg) is True
