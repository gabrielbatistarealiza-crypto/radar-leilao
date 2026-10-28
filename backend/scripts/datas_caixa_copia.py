"""Corre o worker de datas da CAIXA contra a CÓPIA LOCAL, com limite explícito.

Cada volta = 1 imóvel pendente (+ o PDF do seu edital, se ainda não lido):
no máximo 2 pedidos à CAIXA por volta, só com requests (nunca Selenium).
Perante bloqueio ou resposta inesperada o worker PARA até revisão manual e
este comando termina; não há novas tentativas.

Só aceita a base arremata_copia na porta 5433 (confirmado na ligação).
A URL vem de RADAR_COPIA_DB_URL; o ficheiro .env não é usado para a escolher.

Rode a partir da pasta backend/:

  set RADAR_COPIA_DB_URL=postgresql://postgres@localhost:5433/arremata_copia
  python scripts/datas_caixa_copia.py --voltas 3
      ensaio: mostra o estado e o próximo imóvel, NÃO contacta a CAIXA
  python scripts/datas_caixa_copia.py --voltas 3 --confirmo-contactar-caixa
      faz no máximo 3 voltas (até 6 pedidos), com 60 s entre voltas
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
BASE_COPIA = "arremata_copia"
PORTA_COPIA = 5433
MAX_VOLTAS = 20
INTERVALO_MINIMO = 60


def confirmar_copia(motor) -> tuple[bool, str]:
    """True só se a ligação for mesmo à arremata_copia:5433."""
    from sqlalchemy import text

    try:
        with motor.connect() as ligacao:
            base, porta = ligacao.execute(
                text("SELECT current_database(), inet_server_port()")
            ).one()
    except Exception as erro:  # sqlite ou outro motor: recusa
        return False, f"não foi possível confirmar a base ({type(erro).__name__})"
    if (base, porta) != (BASE_COPIA, PORTA_COPIA):
        return False, f"ligado a {base}:{porta}, esperado {BASE_COPIA}:{PORTA_COPIA}"
    return True, f"{base}:{porta}"


def travar_selenium() -> None:
    """Defesa extra: se algum caminho tentar abrir um browser, o comando termina."""
    import selenium.webdriver as webdriver

    def proibido(*args, **kwargs):
        raise SystemExit("ABORTADO: tentativa de abrir um browser.")

    webdriver.Chrome = webdriver.Remote = proibido


def resumo_da_volta(resultado: dict) -> dict:
    chaves = ("imovel_id", "pedidos", "atualizados", "datas_da_pagina", "edital", "estado_edital",
              "membros_na_base", "preenchidos_pelo_edital", "paragem", "destino", "imovel_incoerente",
              "concluido", "aguardando_bloqueio", "paragem_manual", "ocupado", "tem_mais")
    return {k: resultado[k] for k in chaves if k in resultado}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--voltas", type=int, required=True, help=f"máximo de voltas (1 a {MAX_VOLTAS})")
    p.add_argument("--intervalo", type=int, default=INTERVALO_MINIMO,
                   help=f"segundos entre voltas (mínimo {INTERVALO_MINIMO})")
    p.add_argument("--registo", default=None, help="ficheiro .jsonl novo para o progresso")
    p.add_argument("--confirmo-contactar-caixa", action="store_true")
    args = p.parse_args()

    if not 1 <= args.voltas <= MAX_VOLTAS:
        sys.exit(f"Recusado: --voltas tem de estar entre 1 e {MAX_VOLTAS}.")
    if args.intervalo < INTERVALO_MINIMO:
        sys.exit(f"Recusado: --intervalo mínimo é {INTERVALO_MINIMO} s.")
    url = os.environ.get("RADAR_COPIA_DB_URL", "").strip()
    if not url:
        sys.exit("Recusado: defina RADAR_COPIA_DB_URL com a ligação à cópia local.")
    # A app lê DATABASE_URL ao ser importada; aponta-a para a cópia antes disso
    # (load_dotenv não substitui variáveis já definidas).
    os.environ["DATABASE_URL"] = url
    sys.path.insert(0, str(RAIZ_BACKEND))

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    motor = create_engine(url)
    ok, onde = confirmar_copia(motor)
    if not ok:
        sys.exit(f"Recusado: {onde}. Nada foi feito.")
    travar_selenium()

    import app.models  # noqa: F401  (regista os modelos)
    from app.models.caixa_data_worker_state import CaixaDataWorkerState
    from app.models.imovel import Imovel
    from app.services.caixa_datas_edital import filtro_pendentes, numero_do_imovel
    from app.services.caixa_rotinas import executar_lote_datas

    db = sessionmaker(bind=motor, autoflush=False, autocommit=False)()
    try:
        estado = db.get(CaixaDataWorkerState, 1)
        pendentes = db.query(Imovel.id).filter(filtro_pendentes()).count()
        print(f"Base: {onde} | pendentes: {pendentes}")
        if estado:
            print(f"Estado: ativo={estado.ativo} cursor_id={estado.cursor_id} "
                  f"bloqueado_ate={estado.bloqueado_ate}")

        if not args.confirmo_contactar_caixa:
            consulta = db.query(Imovel).filter(filtro_pendentes())
            if estado and estado.cursor_id is not None:
                consulta = consulta.filter(Imovel.id > estado.cursor_id)
            proximo = consulta.order_by(Imovel.id.asc()).first()
            print("ENSAIO: nada foi pedido à CAIXA nem gravado.")
            print(f"  próximo imóvel: {proximo.id if proximo else None} "
                  f"(número {numero_do_imovel(proximo.url) if proximo else None})")
            print(f"  máximo: {args.voltas} voltas, até {2 * args.voltas} pedidos, "
                  f"{args.intervalo} s entre voltas; Selenium: não")
            db.rollback()
            return 0

        momento = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        registo = Path(args.registo or f"registo_datas_caixa_{momento}.jsonl")
        pedidos = 0
        with open(registo, "x", encoding="utf-8") as f:  # nunca sobrescreve
            for volta in range(1, args.voltas + 1):
                resultado = executar_lote_datas(db)
                pedidos += resultado.get("pedidos", 0)
                linha = {"volta": volta, "momento_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         **resumo_da_volta(resultado)}
                f.write(json.dumps(linha, ensure_ascii=False, default=str) + "\n")
                f.flush()
                os.fsync(f.fileno())
                print(json.dumps(linha, ensure_ascii=False, default=str))
                if any(resultado.get(k) for k in ("paragem", "aguardando_bloqueio", "concluido", "ocupado")):
                    break
                if volta < args.voltas:
                    time.sleep(args.intervalo)
        print(f"Fim: {pedidos} pedido(s) à CAIXA. Registo: {registo}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
