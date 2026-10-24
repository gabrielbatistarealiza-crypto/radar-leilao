"""Guarda dos scripts soltos que contactam a CAIXA ou a base de dados.

Verificação estática: os scripts NUNCA são executados. Lê-se o ficheiro,
confirma-se que a guarda é a primeira instrução (antes de qualquer import com
efeitos) e executam-se apenas as linhas da guarda num espaço isolado.

Os scripts estão no .gitignore: numa cópia sem eles, os testes são ignorados.
"""
import ast
import re
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
VARIAVEL = "RADAR_PERMITIR_SCRIPT_LEGADO"

GUARDADOS_NO_TOPO = [
    "enriquecer_datas.py",
    "enriquecer_datas_paralelo.py",
    "testar_datas.py",
    "diagnostico_elementos.py",
    "diagnostico_galeria.py",
    "enriquecer_fotos_caixa.py",
    "enriquecer_fotos_caixa_1lote_backup.py",
    "enriquecer_fotos_caixa_antes_indentacao.py",
    "enriquecer_fotos_caixa_antes_verificacao.py",
    "enriquecer_fotos_caixa_backup.py",
    "enriquecer_fotos_caixa_ESTAVEL.py",
    "teste_browser_fotos.py",
    "teste_caixa_selenium.py",
    "teste_extrator_fotos.py",
    "teste_fotos.py",
    "teste_galeria.py",
    "teste_gravacao_foto.py",
    "teste_imagem.py",
    "teste_importacao.py",
]

# Ficheiros soltos que mencionam a CAIXA mas não precisam de guarda, com motivo.
EXCECOES = {
    # Não é Python válido (despejo de objetos, ex.: "x = <function>()"):
    # não pode ser executado.
    "imoveis_recuperado.py",
}

SINAIS_CAIXA = re.compile(
    r"caixa\.gov\.br|CaixaScraper|CaixaDownloader|selenium|webdriver|"
    r"playwright|Browser\(|coletar_imagens|extrair_datas"
)


def _ler(caminho: Path) -> str:
    return caminho.read_bytes().decode("utf-8-sig")


def _fonte_da_guarda(caminho: Path) -> str:
    """Texto do início do ficheiro até ao fim do bloco `if` da guarda.

    Analisa só este prefixo: assim funciona mesmo em scripts cujo resto tem
    erros de sintaxe (que, de qualquer modo, impedem o script de correr).
    """
    linhas = _ler(caminho).splitlines()
    inicio_if = next(
        i for i, linha in enumerate(linhas) if linha.startswith("if ") and VARIAVEL in linha
    )
    fim = inicio_if + 1
    while fim < len(linhas) and (linhas[fim].startswith((" ", "\t")) or not linhas[fim].strip()):
        if not linhas[fim].strip() and fim + 1 < len(linhas) and not linhas[fim + 1].startswith((" ", "\t")):
            break
        fim += 1
    return "\n".join(linhas[:fim]) + "\n"


def _nos_da_guarda(caminho: Path):
    """Devolve as 3 instruções da guarda, exigindo que sejam as primeiras."""
    corpo = ast.parse(_fonte_da_guarda(caminho)).body
    # Exatamente: import os, import sys, if — nada antes (comentários não contam).
    assert len(corpo) == 3, ast.dump(ast.Module(body=corpo, type_ignores=[]))
    importa_os, importa_sys, condicao = corpo
    return importa_os, importa_sys, condicao


def _existente(nome: str) -> Path:
    caminho = BACKEND / nome
    if not caminho.exists():
        pytest.skip(f"{nome} não existe nesta cópia")
    return caminho


def _executar_so_a_guarda(caminho: Path):
    modulo = ast.Module(body=list(_nos_da_guarda(caminho)), type_ignores=[])
    exec(compile(modulo, str(caminho), "exec"), {"__name__": "guarda_isolada"})


@pytest.mark.parametrize("nome", GUARDADOS_NO_TOPO)
def test_guarda_e_a_primeira_instrucao(nome):
    importa_os, importa_sys, condicao = _nos_da_guarda(_existente(nome))

    assert isinstance(importa_os, ast.Import)
    assert [a.name for a in importa_os.names] == ["os"]
    assert isinstance(importa_sys, ast.Import)
    assert [a.name for a in importa_sys.names] == ["sys"]
    assert isinstance(condicao, ast.If)
    texto = ast.unparse(condicao)
    assert f"getenv('{VARIAVEL}') != '1'" in texto
    assert ".exit(" in texto
    # Nenhum else: a guarda não tem caminho alternativo.
    assert condicao.orelse == []


@pytest.mark.parametrize("nome", GUARDADOS_NO_TOPO)
def test_recusa_sem_a_variavel(nome, monkeypatch):
    monkeypatch.delenv(VARIAVEL, raising=False)
    with pytest.raises(SystemExit) as saida:
        _executar_so_a_guarda(_existente(nome))
    assert "Script legado desativado" in str(saida.value)


@pytest.mark.parametrize("valor", ["true", "yes", "0", " 1", ""])
def test_so_o_valor_1_exato_desbloqueia(valor, monkeypatch):
    monkeypatch.setenv(VARIAVEL, valor)
    with pytest.raises(SystemExit):
        _executar_so_a_guarda(_existente("enriquecer_fotos_caixa.py"))


def test_com_a_variavel_a_1_a_guarda_deixa_passar(monkeypatch):
    monkeypatch.setenv(VARIAVEL, "1")
    _executar_so_a_guarda(_existente("enriquecer_fotos_caixa.py"))  # não sai


def test_todos_os_scripts_soltos_com_acesso_a_caixa_tem_guarda():
    """Um script novo na raiz do backend que contacte a CAIXA falha aqui."""
    sem_guarda = []
    for caminho in sorted(BACKEND.glob("*.py")):
        if caminho.name in EXCECOES:
            continue
        texto = _ler(caminho)
        if SINAIS_CAIXA.search(texto) and VARIAVEL not in texto:
            sem_guarda.append(caminho.name)
    assert sem_guarda == []


def test_excecoes_continuam_a_nao_ser_python_valido():
    for nome in EXCECOES:
        caminho = BACKEND / nome
        if not caminho.exists():
            continue
        with pytest.raises(SyntaxError):
            ast.parse(_ler(caminho))


def test_verificar_datas_origem_so_guarda_a_amostra():
    caminho = _existente("scripts/verificar_datas_origem.py")
    funcoes = {
        no.name: no
        for no in ast.parse(_ler(caminho)).body
        if isinstance(no, ast.FunctionDef)
    }
    primeira = funcoes["testar_paginas"].body[0]
    assert isinstance(primeira, ast.If)
    assert f"getenv('{VARIAVEL}') != '1'" in ast.unparse(primeira)
    # As etapas sem CAIXA (--csv, --db-url) não ficam bloqueadas.
    outras = [n for n in funcoes if n != "testar_paginas"]
    assert all(VARIAVEL not in ast.unparse(funcoes[n]) for n in outras)
