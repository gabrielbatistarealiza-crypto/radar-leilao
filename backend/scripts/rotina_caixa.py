"""Rotina diária da CAIXA a partir DESTE computador (lista + datas), numa base escolhida.

Porquê: a CAIXA recusa (HTTP 403) os pedidos feitos a partir do IP do Render
(29/10/2026). Este comando corre as mesmas rotinas da API, com as mesmas
proteções, a partir do IP de casa, e grava diretamente na base escolhida.

Proteções (as mesmas do worker em produção):
  - só requests, nunca browser; um GET por URL, sem repetições;
  - qualquer bloqueio ou resposta inesperada grava a paragem manual
    (bloqueado_ate = 9999-12-31) na base: tudo pára até revisão, aqui e na API;
  - marca de "pedido em curso" gravada antes de cada GET;
  - limite diário de pedidos de datas (RADAR_CAIXA_DATAS_MAX_PEDIDOS_DIA, padrão
    20) contado na base, mais o limite --max-pedidos-datas desta execução;
  - lock entre processos no PostgreSQL: nunca corre ao mesmo tempo que a API;
  - sem --confirmo-contactar-caixa faz só um ensaio (lê a base, não pede nada).

Bases aceites (confirmadas na ligação):
  --base copia      RADAR_COPIA_DB_URL; só arremata_copia na porta 5433
  --base producao   RADAR_RENDER_DB_URL; só um servidor *.render.com, com as
                    tabelas do worker (caixa_pedidos_dia criada pelo deploy)

Antes de usar em produção, a API no Render NÃO pode correr as rotinas da CAIXA
(RADAR_DISABLE_BACKGROUND_JOBS=1), senão volta a tentar e a levar 403.

Rode a partir da pasta backend/ (exemplos):

  python scripts/rotina_caixa.py --base producao --lista --max-pedidos-datas 10
      ensaio: mostra o estado e o que seria feito
  python scripts/rotina_caixa.py --base producao --lista --max-pedidos-datas 10 --confirmo-contactar-caixa
      lista das 27 UFs (60 s entre UFs) e até 10 pedidos de datas (600 s entre voltas)

Código de saída: 0 terminou normalmente; 2 parou (paragem manual, espera,
outra consulta em curso ou limite diário); outros valores = recusado/erro.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

RAIZ_BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from datas_caixa_copia import confirmar_copia, travar_selenium  # noqa: E402

VARIAVEL_URL = {"copia": "RADAR_COPIA_DB_URL", "producao": "RADAR_RENDER_DB_URL"}
MAX_UFS = 27
MAX_PEDIDOS_DATAS = 40
INTERVALO_DATAS_MINIMO = 60
INTERVALO_DATAS_PADRAO = 600
INTERVALO_LISTA_MINIMO = 30
INTERVALO_LISTA_PADRAO = 60
TABELAS_EXIGIDAS = ("imoveis", "caixa_data_worker_state", "caixa_pedidos_dia")
SAIDA_PAROU = 2
# Páginas seguidas que a CAIXA serve sem datas, fotos nem edital (por exemplo, imóvel já
# vendido ou página genérica): ao fim destas, grava a paragem manual para revisão.
MAX_PAGINAS_VAZIAS_PADRAO = 3


def pagina_vazia(resultado: dict) -> bool:
    """Volta em que a página foi lida (sem bloqueio) mas não trouxe datas, fotos nem edital."""
    return bool(
        resultado.get("imovel_id")
        and "paragem" not in resultado
        and not any(resultado.get("datas_da_pagina") or [])
        and not resultado.get("fotos")
        and resultado.get("estado_edital") == "SEM_EDITAL_NA_PAGINA"
    )


def guardar_respostas(pedir_real, pasta: Path, guardados: list):
    """Envolve o pedido HTTP: guarda o corpo de cada página lida (nunca sobrescreve)."""
    import re

    def pedir(url, tipo):
        resposta = pedir_real(url, tipo)
        if tipo == "pagina" and resposta.corpo is not None:
            pasta.mkdir(parents=True, exist_ok=True)
            numero = (re.search(r"hdnimovel=(\d+)", url) or [None, "sem_numero"])[1]
            momento = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            ficheiro = pasta / f"{momento}_{numero}.html"
            with open(ficheiro, "xb") as f:
                f.write(resposta.corpo)
            guardados.append(ficheiro.name)
        return resposta

    return pedir


def confirmar_producao(motor, url: str) -> tuple[bool, str]:
    """True só para um servidor *.render.com com as tabelas do worker (e que não seja a cópia)."""
    from sqlalchemy import text
    from sqlalchemy.engine import make_url

    try:
        host = (make_url(url).host or "").lower()
    except Exception:
        return False, "URL da base inválido"
    if not host.endswith(".render.com"):
        return False, "o servidor não é do Render (*.render.com)"
    try:
        with motor.connect() as ligacao:
            base = ligacao.execute(text("SELECT current_database()")).scalar()
            faltam = [t for t in TABELAS_EXIGIDAS
                      if ligacao.execute(text("SELECT to_regclass(:t)"), {"t": f"public.{t}"}).scalar() is None]
    except Exception as erro:
        return False, f"não foi possível confirmar a base ({type(erro).__name__})"
    if base == "arremata_copia":
        return False, "a base é a cópia local"
    if faltam:
        return False, f"faltam tabelas do worker: {faltam} (o deploy novo já correu?)"
    return True, f"{base} (Render)"


def linha_registo(f, etapa: str, dados: dict) -> dict:
    linha = {"etapa": etapa, "momento_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), **dados}
    f.write(json.dumps(linha, ensure_ascii=False, default=str) + "\n")
    f.flush()
    os.fsync(f.fileno())
    print(json.dumps(linha, ensure_ascii=False, default=str), flush=True)
    return linha


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base", choices=sorted(VARIAVEL_URL), required=True)
    p.add_argument("--lista", action="store_true", help="descarrega e importa as listas das UFs")
    p.add_argument("--max-ufs", type=int, default=MAX_UFS, help=f"UFs a descarregar (1 a {MAX_UFS})")
    p.add_argument("--lista-com-browser", action="store_true",
                   help="descarrega as listas com um browser real (Selenium), 1 tentativa por UF; "
                        "só neste computador (decisão de 29/10/2026)")
    p.add_argument("--sem-remocoes", action="store_true",
                   help="importa a lista sem apagar imóveis ausentes (só os conta)")
    p.add_argument("--intervalo-lista", type=int, default=INTERVALO_LISTA_PADRAO,
                   help=f"segundos entre UFs (mínimo {INTERVALO_LISTA_MINIMO})")
    p.add_argument("--max-pedidos-datas", type=int, default=0,
                   help=f"pedidos de datas nesta execução (0 a {MAX_PEDIDOS_DATAS}; 0 = não corre)")
    p.add_argument("--intervalo-datas", type=int, default=INTERVALO_DATAS_PADRAO,
                   help=f"segundos entre voltas de datas (mínimo {INTERVALO_DATAS_MINIMO})")
    p.add_argument("--max-paginas-vazias", type=int, default=MAX_PAGINAS_VAZIAS_PADRAO,
                   help="páginas seguidas sem datas, fotos nem edital antes de parar (1 a 10)")
    p.add_argument("--pasta-paginas", default=None,
                   help="onde guardar o HTML das páginas pedidas (padrão: paginas_caixa ao lado do registo)")
    p.add_argument("--registo", default=None, help="ficheiro .jsonl novo para o resultado")
    p.add_argument("--confirmo-contactar-caixa", action="store_true")
    args = p.parse_args()
    if args.lista_com_browser:
        args.lista = True

    if not args.lista and args.max_pedidos_datas == 0:
        sys.exit("Recusado: indique --lista e/ou --max-pedidos-datas N.")
    if not 1 <= args.max_ufs <= MAX_UFS:
        sys.exit(f"Recusado: --max-ufs tem de estar entre 1 e {MAX_UFS}.")
    if not 0 <= args.max_pedidos_datas <= MAX_PEDIDOS_DATAS:
        sys.exit(f"Recusado: --max-pedidos-datas tem de estar entre 0 e {MAX_PEDIDOS_DATAS}.")
    if args.intervalo_datas < INTERVALO_DATAS_MINIMO:
        sys.exit(f"Recusado: --intervalo-datas mínimo é {INTERVALO_DATAS_MINIMO} s.")
    if args.intervalo_lista < INTERVALO_LISTA_MINIMO:
        sys.exit(f"Recusado: --intervalo-lista mínimo é {INTERVALO_LISTA_MINIMO} s.")
    if not 1 <= args.max_paginas_vazias <= 10:
        sys.exit("Recusado: --max-paginas-vazias tem de estar entre 1 e 10.")

    variavel = VARIAVEL_URL[args.base]
    url = os.environ.get(variavel, "").strip()
    if not url:
        sys.exit(f"Recusado: defina {variavel} com a ligação à base ({args.base}).")
    # A app lê DATABASE_URL ao ser importada; aponta-a para a base escolhida antes.
    os.environ["DATABASE_URL"] = url
    os.environ["RADAR_CAIXA_LISTA_INTERVALO_SEGUNDOS"] = str(args.intervalo_lista)
    sys.path.insert(0, str(RAIZ_BACKEND))

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # A base do Render fica longe: avisa e não espera para sempre pela ligação.
    print(f"A ligar à base ({args.base})...", flush=True)
    motor = create_engine(url, connect_args={"connect_timeout": 30}, use_native_hstore=False)
    ok, onde = confirmar_copia(motor) if args.base == "copia" else confirmar_producao(motor, url)
    if not ok:
        sys.exit(f"Recusado: {onde}. Nada foi feito.")
    if not args.lista_com_browser:
        travar_selenium()  # sem --lista-com-browser, nenhum caminho pode abrir um browser

    import app.models  # noqa: F401
    from app.models.caixa_data_worker_state import CaixaDataWorkerState
    from app.models.caixa_pedidos_dia import CaixaPedidosDia
    from app.models.imovel import Imovel
    from app.services.caixa_datas_edital import e_paragem_manual, filtro_pendentes, pedir_caixa
    from app.services.caixa_datas_worker import (
        limite_diario_pedidos,
        pedidos_hoje,
        registrar_paragem_manual,
    )
    from app.services.caixa_rotinas import executar_importacao, executar_lote_datas

    if args.base == "copia" and args.confirmo_contactar_caixa:
        CaixaPedidosDia.__table__.create(bind=motor, checkfirst=True)

    db = sessionmaker(bind=motor, autoflush=False, autocommit=False)()
    try:
        estado = db.get(CaixaDataWorkerState, 1)
        pendentes = db.query(Imovel.id).filter(filtro_pendentes()).count()
        parado = bool(estado and e_paragem_manual(estado.bloqueado_ate))
        print(f"Base: {onde} | pendentes de datas: {pendentes}")
        if estado:
            print(f"Estado: ativo={estado.ativo} cursor_id={estado.cursor_id} "
                  f"bloqueado_ate={estado.bloqueado_ate}{' (PARAGEM MANUAL)' if parado else ''}")

        if not args.confirmo_contactar_caixa:
            from sqlalchemy import inspect

            usados = (pedidos_hoje(db, datetime.utcnow())
                      if inspect(motor).has_table("caixa_pedidos_dia") else 0)
            print("ENSAIO: nada foi pedido à CAIXA nem gravado.")
            if args.lista:
                remocoes = ("desligadas (só conta os ausentes)" if args.sem_remocoes
                            else "só com as 27 UFs da mesma geração e até max(50, 5%)")
                modo = "browser (Selenium), 1 tentativa por UF" if args.lista_com_browser else "requests"
                print(f"  lista: {args.max_ufs} UF(s), {args.intervalo_lista} s entre UFs, {modo}; "
                      f"remoções: {remocoes}")
            if args.max_pedidos_datas:
                print(f"  datas: até {args.max_pedidos_datas} pedido(s), {args.intervalo_datas} s entre voltas; "
                      f"hoje já {usados} de {limite_diario_pedidos()} (limite diário)")
            if parado:
                print("  ATENÇÃO: a paragem manual está gravada; nada seria pedido até ser revista e limpa.")
            db.rollback()
            return 0

        momento = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        registo = Path(args.registo or f"registo_rotina_caixa_{args.base}_{momento}_{os.getpid()}.jsonl")
        parou = False
        with open(registo, "x", encoding="utf-8") as f:  # nunca sobrescreve
            if args.lista:
                r = executar_importacao(db, max_ufs=args.max_ufs, remover=not args.sem_remocoes,
                                        com_browser=args.lista_com_browser)
                download = r.get("download") or {}
                linha_registo(f, "lista", {
                    "pedidos": download.get("pedidos", 0), "ufs_ok": len(download.get("sucesso", [])),
                    "paragem": download.get("paragem"), "uf_bloqueada": download.get("uf_bloqueada"),
                    "ufs_importadas": r.get("ufs_importadas"),
                    "imoveis_atualizados": r.get("imoveis_atualizados"),
                    "imoveis_removidos": r.get("imoveis_removidos"),
                    "remocao_recusada": r.get("remocao_recusada"),
                    "ausentes_da_lista": r.get("ausentes_da_lista"),
                    "remocoes_desligadas": args.sem_remocoes,
                    "com_browser": args.lista_com_browser,
                    "aguardando_bloqueio": r.get("aguardando_bloqueio"), "ocupado": r.get("ocupado"),
                })
                parou = bool(download.get("bloqueado") or r.get("aguardando_bloqueio") or r.get("ocupado"))

            pasta_paginas = Path(args.pasta_paginas) if args.pasta_paginas else registo.parent / "paginas_caixa"
            guardados: list[str] = []
            pedir = guardar_respostas(pedir_caixa, pasta_paginas, guardados)
            pedidos = 0
            volta = 0
            vazias_seguidas = 0
            while not parou and pedidos < args.max_pedidos_datas:
                if volta:
                    time.sleep(args.intervalo_datas)
                volta += 1
                antes = len(guardados)
                r = executar_lote_datas(db, max_pedidos=min(2, args.max_pedidos_datas - pedidos), pedir=pedir)
                pedidos += r.get("pedidos", 0)
                chaves = ("imovel_id", "pedidos", "atualizados", "datas_da_pagina", "fotos", "fotos_novas",
                          "estado_edital", "preenchidos_pelo_edital", "paragem", "concluido",
                          "aguardando_bloqueio", "ocupado", "limite_diario_atingido")
                dados = {k: r[k] for k in chaves if k in r}
                dados["html_guardado"] = guardados[antes:]
                vazias_seguidas = vazias_seguidas + 1 if pagina_vazia(r) else 0
                dados["paginas_vazias_seguidas"] = vazias_seguidas
                linha_registo(f, f"datas {volta}", dados)
                if r.get("paragem") or r.get("aguardando_bloqueio") or r.get("ocupado") \
                        or r.get("limite_diario_atingido"):
                    parou = True
                elif vazias_seguidas >= args.max_paginas_vazias:
                    # Não é um bloqueio, mas a CAIXA está a servir páginas sem dados: pára
                    # tudo (aqui e na API) até alguém ver o HTML guardado.
                    estado = db.get(CaixaDataWorkerState, 1)
                    registrar_paragem_manual(estado, datetime.utcnow())
                    db.commit()
                    linha_registo(f, "paragem", {"paragem": "PAGINAS_SEM_DADOS",
                                                 "paginas_vazias_seguidas": vazias_seguidas,
                                                 "pasta_paginas": str(pasta_paginas)})
                    parou = True
                if r.get("concluido"):
                    break
        print(f"Fim. Registo: {registo}")
        return SAIDA_PAROU if parou else 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
