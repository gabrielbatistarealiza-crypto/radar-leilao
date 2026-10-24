"""Verificação SOMENTE LEITURA da origem das datas de leilão do Radar Leilão.

Nada aqui altera o banco nem os arquivos. Três etapas independentes:

  --csv                 Audita os CSVs da Caixa que já estão no disco: quais
                        colunas existem e se alguma traz a data do leilão.
                        Não usa internet nem banco.

  --db-url URL          Conta, no banco, quantos imóveis têm datas, quantos
                        estão ativos hoje e quando o catálogo foi atualizado
                        pela última vez. Usa uma transação somente leitura.

  --amostra N           (precisa de --db-url) Sorteia N imóveis SEM data no
                        banco, abre a página de detalhe de cada um na Caixa e
                        diz o que ela mostra: COM_DATA (1º ou 2º leilão),
                        SO_LICITACAO_ABERTA, SEM_DATA_NA_PAGINA ou BLOQUEADO.
                        Máximo 20, com pausa entre as páginas.

Rode a partir da pasta backend/:

  python scripts/verificar_datas_origem.py --csv
  python scripts/verificar_datas_origem.py --db-url "postgresql://..."
  python scripts/verificar_datas_origem.py --db-url "postgresql://..." --amostra 10

Não cole a URL do banco em chats nem em commits: ela contém a senha. Também
pode usar a variável de ambiente DATABASE_URL em vez de --db-url.
"""
from __future__ import annotations

import argparse
import csv
import glob
import os
import re
import sys
import time
import unicodedata
from collections import Counter
from datetime import date

RAIZ_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ_BACKEND)

PASTA_CSV_PADRAO = os.path.join(RAIZ_BACKEND, "app", "scrapers", "dados")
MODALIDADE_IMPORTADA = "Leilão SFI - Edital Único"
MAXIMO_AMOSTRA = 20


def normalizar(texto) -> str:
    texto = unicodedata.normalize("NFKD", str(texto or "").strip().lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def titulo(texto: str) -> None:
    print()
    print("=" * 70)
    print(texto)
    print("=" * 70)


# ----------------------------------------- leitura do resultado da página

def separar_datas(resultado):
    """Aceita o retorno de _extrair_datas_da_pagina com 2 ou mais valores.

    Versões antigas devolvem (1º leilão, 2º leilão). Versões novas acrescentam
    a data da licitação aberta como terceiro valor. Retorna
    (primeira, segunda, licitacao, quantidade_de_valores_recebidos).
    """
    if isinstance(resultado, (tuple, list)):
        valores = list(resultado)
    else:
        valores = [resultado]
    quantidade = len(valores)
    valores = (valores + [None, None, None])[:3]
    return valores[0], valores[1], valores[2], quantidade


def classificar(primeira, segunda, licitacao) -> str:
    """Licitação aberta é outra modalidade: não conta como data de leilão."""
    if primeira or segunda:
        return "COM_DATA"
    if licitacao:
        return "SO_LICITACAO_ABERTA"
    return "SEM_DATA_NA_PAGINA"


# ---------------------------------------------------------------- CSV

def ler_linhas(caminho: str) -> list[list[str]]:
    for codificacao in ("utf-8-sig", "latin-1"):
        try:
            with open(caminho, "r", encoding=codificacao, newline="") as arquivo:
                return list(csv.reader(arquivo, delimiter=";"))
        except UnicodeDecodeError:
            continue
    return []


def achar_cabecalho(linhas: list[list[str]]) -> int | None:
    for indice, linha in enumerate(linhas):
        nomes = [normalizar(c) for c in linha]
        if "uf" in nomes and ("cidade" in nomes or "municipio" in nomes) and "preco" in " ".join(nomes):
            return indice
    return None


def auditar_csvs(pasta: str) -> None:
    titulo(f"ETAPA 1: CSVs da Caixa em {pasta}")
    arquivos = sorted(glob.glob(os.path.join(pasta, "*.csv")))
    if not arquivos:
        print("Nenhum CSV encontrado. Rode a atualização da Caixa uma vez ou aponte --csv-dir.")
        return

    modalidades: Counter = Counter()
    colunas_com_data: dict[str, int] = {}
    total_linhas = 0
    primeiro_cabecalho: list[str] | None = None

    for caminho in arquivos:
        linhas = ler_linhas(caminho)
        indice = achar_cabecalho(linhas)
        if indice is None:
            print(f"- {os.path.basename(caminho)}: cabeçalho NÃO encontrado")
            continue

        cabecalho = linhas[indice]
        dados = [l for l in linhas[indice + 1:] if any(c.strip() for c in l)]
        total_linhas += len(dados)
        if primeiro_cabecalho is None:
            primeiro_cabecalho = cabecalho

        posicao = {normalizar(c): i for i, c in enumerate(cabecalho)}
        i_modalidade = next((i for n, i in posicao.items() if n.startswith("modalidade")), None)
        for linha in dados:
            if i_modalidade is not None and i_modalidade < len(linha):
                modalidades[linha[i_modalidade].strip()] += 1

        for nome, i in posicao.items():
            if "leil" in nome or nome.startswith("data") or "prazo" in nome:
                preenchidas = sum(1 for l in dados if i < len(l) and l[i].strip())
                colunas_com_data[nome] = colunas_com_data.get(nome, 0) + preenchidas

    print(f"Arquivos lidos: {len(arquivos)} | linhas de imóveis: {total_linhas}")
    if primeiro_cabecalho:
        print("\nColunas do CSV (primeiro arquivo):")
        for coluna in primeiro_cabecalho:
            print(f"  - {coluna}")

    print("\nColunas que parecem trazer data de leilão:")
    if not colunas_com_data:
        print("  NENHUMA. Neste CSV a data do leilão não está disponível como coluna;")
        print("  ela teria de vir da página de detalhe do imóvel (confirme na etapa 3).")
    else:
        for nome, preenchidas in colunas_com_data.items():
            print(f"  - {nome}: {preenchidas} de {total_linhas} linhas preenchidas")

    print("\nModalidades nos CSVs (quantidade de imóveis):")
    for nome, quantidade in modalidades.most_common(8):
        marca = "  <- é a única que o scraper importa" if nome == MODALIDADE_IMPORTADA else ""
        print(f"  {quantidade:>6}  {nome}{marca}")
    print(
        f"\nO scraper importaria {modalidades.get(MODALIDADE_IMPORTADA, 0)} imóveis desses CSVs "
        "(compare com o total do banco)."
    )


# -------------------------------------------------------------- banco

def abrir_banco(url: str):
    from sqlalchemy import create_engine

    return create_engine(url)


def auditar_banco(url: str) -> None:
    from sqlalchemy import text

    titulo("ETAPA 2: banco de dados (somente leitura)")
    hoje = date.today()
    motor = abrir_banco(url)

    with motor.connect() as conexao:
        if motor.dialect.name == "postgresql":
            conexao.execute(text("SET TRANSACTION READ ONLY"))

        total, sem_data, ativos, menor, maior_1, maior_2, sem_url = conexao.execute(
            text(
                """
                SELECT count(*),
                       count(*) FILTER (WHERE data_primeiro_leilao IS NULL
                                          AND data_segundo_leilao  IS NULL),
                       count(*) FILTER (WHERE data_primeiro_leilao >= :hoje
                                           OR data_segundo_leilao  >= :hoje),
                       min(data_primeiro_leilao),
                       max(data_primeiro_leilao),
                       max(data_segundo_leilao),
                       count(*) FILTER (WHERE url IS NULL)
                FROM imoveis
                """
            ),
            {"hoje": hoje},
        ).one()
        com_data = total - sem_data
        encerrados = com_data - ativos
        maior = max([d for d in (maior_1, maior_2) if d is not None], default=None)

        print(f"Hoje (máquina local): {hoje}")
        print(f"Total de imóveis:            {total}")
        print(f"  sem nenhuma data:          {sem_data}")
        print(f"  com alguma data:           {com_data}")
        print(f"    ativos (leilão >= hoje): {ativos}")
        print(f"    encerrados (só passado): {encerrados}")
        print(f"  sem URL:                   {sem_url}")
        print(f"Menor 1º leilão: {menor} | maior data de leilão: {maior}")

        anomalas = conexao.execute(
            text(
                "SELECT count(*) FROM imoveis "
                "WHERE data_segundo_leilao < data_primeiro_leilao"
            )
        ).scalar()
        print(f"2º leilão ANTES do 1º (suspeito): {anomalas}")

        print("\nModalidades gravadas:")
        for modalidade, quantidade in conexao.execute(
            text("SELECT modalidade, count(*) FROM imoveis GROUP BY 1 ORDER BY 2 DESC LIMIT 6")
        ):
            print(f"  {quantidade:>6}  {modalidade!r}")

        print("\nÚltimas atualizações da Caixa registradas:")
        try:
            registros = conexao.execute(
                text(
                    "SELECT id, status, iniciada_em, concluida_em, imoveis_atualizados, "
                    "imoveis_removidos, estados_baixados FROM atualizacoes_caixa "
                    "ORDER BY id DESC LIMIT 3"
                )
            ).all()
            if not registros:
                print("  (nenhuma: a atualização automática nunca rodou neste banco)")
            for r in registros:
                print(
                    f"  #{r[0]} {r[1]} | início {r[2]} | fim {r[3]} | "
                    f"atualizados {r[4]} | removidos {r[5]} | estados {r[6]}/27"
                )
        except Exception as erro:  # tabela ausente, por exemplo
            print(f"  não foi possível ler: {erro}")


# ------------------------------------------------------ páginas (rede)

def testar_paginas(url_banco: str, quantidade: int, pausa: float) -> None:
    # Esta etapa abre páginas da CAIXA fora do porteiro (lock, espera de
    # bloqueio, lock entre processos). As etapas --csv e --db-url continuam
    # livres; esta só corre com RADAR_PERMITIR_SCRIPT_LEGADO=1 nessa execução.
    if os.getenv("RADAR_PERMITIR_SCRIPT_LEGADO") != "1":
        sys.exit(
            "Script legado desativado: --amostra contorna a protecao de acesso a CAIXA."
        )

    from sqlalchemy import text
    from bs4 import BeautifulSoup

    from app.scrapers.caixa import CaixaScraper
    from app.utils.browser import Browser

    quantidade = max(1, min(quantidade, MAXIMO_AMOSTRA))
    titulo(f"ETAPA 3: {quantidade} páginas de imóveis SEM data no banco (leitura na Caixa)")

    motor = abrir_banco(url_banco)
    with motor.connect() as conexao:
        if motor.dialect.name == "postgresql":
            conexao.execute(text("SET TRANSACTION READ ONLY"))
        amostra = conexao.execute(
            text(
                "SELECT id, url FROM imoveis "
                "WHERE data_primeiro_leilao IS NULL AND data_segundo_leilao IS NULL "
                "AND url IS NOT NULL ORDER BY random() LIMIT :n"
            ),
            {"n": quantidade},
        ).all()

    if not amostra:
        print("Nenhum imóvel sem data e com URL encontrado.")
        return

    resultados: Counter = Counter()
    avisou_formato = False
    navegador = Browser()
    navegador.iniciar()
    try:
        for imovel_id, url in amostra:
            pagina = navegador.pagina
            try:
                pagina.goto(url, wait_until="domcontentloaded", timeout=60000)
                pagina.wait_for_selector("body", timeout=10000)
                pagina.wait_for_timeout(3000)
                html = pagina.content()
            except Exception as erro:
                print(f"#{imovel_id}: ERRO ao abrir a página ({erro})")
                resultados["ERRO"] += 1
                continue

            if CaixaScraper._pagina_bloqueada(html):
                print(f"#{imovel_id}: BLOQUEADO pela Caixa. Parando para não insistir.")
                resultados["BLOQUEADO"] += 1
                break

            sopa = BeautifulSoup(html, "html.parser")
            try:
                primeira, segunda, licitacao, recebidos = separar_datas(
                    CaixaScraper._extrair_datas_da_pagina(sopa)
                )
            except Exception as erro:
                print(f"#{imovel_id}: ERRO_EXTRACAO ao ler as datas ({type(erro).__name__}: {erro})")
                resultados["ERRO_EXTRACAO"] += 1
                time.sleep(pausa)
                continue

            if not avisou_formato:
                print(f"(a função _extrair_datas_da_pagina devolveu {recebidos} valores)")
                avisou_formato = True

            resultado = classificar(primeira, segunda, licitacao)
            resultados[resultado] += 1
            if resultado == "COM_DATA":
                print(
                    f"#{imovel_id}: COM_DATA | 1º={primeira} | 2º={segunda} | "
                    f"licitação aberta={licitacao} | {url}"
                )
            elif resultado == "SO_LICITACAO_ABERTA":
                print(f"#{imovel_id}: SO_LICITACAO_ABERTA | licitação aberta={licitacao} | {url}")
            else:
                texto = re.sub(r"\s+", " ", sopa.get_text(" ", strip=True))
                trechos = [
                    texto[max(0, m.start() - 40): m.end() + 80]
                    for m in list(re.finditer(r"leil", texto, re.IGNORECASE))[:2]
                ]
                print(f"#{imovel_id}: SEM_DATA_NA_PAGINA | {url}")
                for trecho in trechos or ["(a palavra 'leilão' nem aparece na página)"]:
                    print(f"      trecho: ...{trecho}...")
            time.sleep(pausa)
    finally:
        navegador.fechar()

    print("\nResumo:", dict(resultados))


# --------------------------------------------------------------- main

def main() -> None:
    parser = argparse.ArgumentParser(description="Verificação somente leitura das datas de leilão.")
    parser.add_argument("--csv", action="store_true", help="audita os CSVs no disco")
    parser.add_argument("--csv-dir", default=PASTA_CSV_PADRAO, help="pasta dos CSVs")
    parser.add_argument("--db-url", default=os.getenv("DATABASE_URL"), help="URL do Postgres (ou DATABASE_URL)")
    parser.add_argument("--amostra", type=int, default=0, help=f"abre N páginas na Caixa (máx. {MAXIMO_AMOSTRA})")
    parser.add_argument("--pausa", type=float, default=8.0, help="segundos entre páginas")
    args = parser.parse_args()

    if not args.csv and not args.db_url:
        parser.print_help()
        return

    if args.csv:
        auditar_csvs(args.csv_dir)
    if args.db_url:
        auditar_banco(args.db_url)
        if args.amostra > 0:
            testar_paginas(args.db_url, args.amostra, args.pausa)
    elif args.amostra > 0:
        print("--amostra precisa de --db-url (ou DATABASE_URL).")


if __name__ == "__main__":
    main()
