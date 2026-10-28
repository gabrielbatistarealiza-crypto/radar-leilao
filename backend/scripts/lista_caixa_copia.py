"""Corre a atualização da lista de imóveis da CAIXA contra a CÓPIA LOCAL.

Descarrega no máximo --max-ufs listas (1 GET por UF, só com requests, nunca
Selenium, pausa mínima de 60 s entre UFs) e importa os CSV de
app/scrapers/dados para a cópia. Com menos de 27 UFs nada é removido.
Perante bloqueio ou resposta inesperada a descarga PARA, nenhuma UF seguinte é
pedida e as consultas à CAIXA ficam paradas até revisão manual. Antes de
contactar a CAIXA é gravada a marca de "pedido em curso": um processo
interrompido a meio nunca leva a repetir pedidos.

Só aceita a base arremata_copia na porta 5433 (confirmado na ligação); a URL
vem de RADAR_COPIA_DB_URL.

Rode a partir da pasta backend/:

  set RADAR_COPIA_DB_URL=postgresql://postgres@localhost:5433/arremata_copia
  python scripts/lista_caixa_copia.py --max-ufs 1
      ensaio: mostra o estado, as listas no disco e o que seria pedido
  python scripts/lista_caixa_copia.py --max-ufs 1 --confirmo-contactar-caixa
      1 pedido (lista do AC) e importação dos CSV para a cópia
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ_BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from datas_caixa_copia import confirmar_copia, travar_selenium  # noqa: E402

MAX_UFS = 27
INTERVALO_MINIMO = 60


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--max-ufs", type=int, required=True, help=f"UFs a descarregar (1 a {MAX_UFS})")
    p.add_argument("--intervalo", type=int, default=INTERVALO_MINIMO,
                   help=f"segundos entre UFs (mínimo {INTERVALO_MINIMO})")
    p.add_argument("--registo", default=None, help="ficheiro .json novo com o resultado")
    p.add_argument("--confirmo-contactar-caixa", action="store_true")
    args = p.parse_args()

    if not 1 <= args.max_ufs <= MAX_UFS:
        sys.exit(f"Recusado: --max-ufs tem de estar entre 1 e {MAX_UFS}.")
    if args.intervalo < INTERVALO_MINIMO:
        sys.exit(f"Recusado: --intervalo mínimo é {INTERVALO_MINIMO} s.")
    url = os.environ.get("RADAR_COPIA_DB_URL", "").strip()
    if not url:
        sys.exit("Recusado: defina RADAR_COPIA_DB_URL com a ligação à cópia local.")
    os.environ["DATABASE_URL"] = url
    os.environ["RADAR_CAIXA_LISTA_INTERVALO_SEGUNDOS"] = str(args.intervalo)
    sys.path.insert(0, str(RAIZ_BACKEND))

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    motor = create_engine(url)
    ok, onde = confirmar_copia(motor)
    if not ok:
        sys.exit(f"Recusado: {onde}. Nada foi feito.")
    travar_selenium()

    import app.models  # noqa: F401
    from app.models.caixa_data_worker_state import CaixaDataWorkerState
    from app.models.imovel import Imovel
    from app.services.caixa_lista_segura import URL_LISTA, CaixaListaSegura, data_de_geracao
    from app.services.caixa_rotinas import executar_importacao

    db = sessionmaker(bind=motor, autoflush=False, autocommit=False)()
    try:
        estado = db.get(CaixaDataWorkerState, 1)
        caixa = db.query(Imovel.id).filter(Imovel.fonte.ilike("%caixa%")).count()
        print(f"Base: {onde} | imóveis Caixa: {caixa}")
        if estado:
            print(f"Estado: ativo={estado.ativo} cursor_id={estado.cursor_id} "
                  f"bloqueado_ate={estado.bloqueado_ate}")
        pasta = CaixaListaSegura(intervalo=args.intervalo).pasta_dados
        ufs = CaixaListaSegura.UFS[:args.max_ufs]

        if not args.confirmo_contactar_caixa:
            print("ENSAIO: nada foi pedido à CAIXA nem gravado.")
            for uf in ufs:
                f = pasta / f"Lista_imoveis_{uf}.csv"
                geracao = data_de_geracao(f.read_bytes()) if f.exists() else None
                print(f"  {uf}: GET {URL_LISTA.format(uf=uf)} | no disco: "
                      f"{'geração ' + geracao.isoformat() if geracao else 'sem lista válida'}")
            print(f"  máximo: {len(ufs)} pedidos, {args.intervalo} s entre UFs; Selenium: não; "
                  f"remoções: {'só se as 27 UFs vierem novas' if len(ufs) == MAX_UFS else 'nenhuma'}")
            db.rollback()
            return 0

        momento = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        registo = Path(args.registo or f"registo_lista_caixa_{momento}_{os.getpid()}.json")
        with open(registo, "x", encoding="utf-8") as f:  # nunca sobrescreve
            resultado = executar_importacao(db, max_ufs=args.max_ufs)
            resumo = {"momento_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                      "download": resultado.get("download"),
                      **{k: resultado[k] for k in ("imoveis_atualizados", "imoveis_removidos",
                                                   "remocao_recusada", "aguardando_bloqueio",
                                                   "ocupado") if k in resultado}}
            f.write(json.dumps(resumo, ensure_ascii=False, indent=2, default=str))
        print(json.dumps(resumo, ensure_ascii=False, indent=2, default=str))
        print(f"Fim: {(resultado.get('download') or {}).get('pedidos', 0)} pedido(s) à CAIXA. "
              f"Registo: {registo}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
