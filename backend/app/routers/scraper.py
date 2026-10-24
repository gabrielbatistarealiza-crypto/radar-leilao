import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.atualizacao_caixa import AtualizacaoCaixa
from app.models.imovel import Imovel, ImovelImagem
from app.security.auth import usuario_admin
from app.services.scraper_service import ScraperService
from app.services.caixa_worker_lock import CAIXA_COLETA_LOCK
from app.services.caixa_acesso import acesso_caixa_http, registrar_bloqueio_caixa
from app.services.caixa_datas_worker import intervalo_entre_imoveis
from app.models.caixa_data_worker_state import CaixaDataWorkerState


router = APIRouter()


@router.get("/caixa/enriquecer-datas/status")
def status_worker_datas_caixa(
    db: Session = Depends(get_db),
    administrador=Depends(usuario_admin),
):
    estado = db.get(CaixaDataWorkerState, 1)
    habilitado = (
        os.getenv("RADAR_DISABLE_BACKGROUND_JOBS") != "1"
        and os.getenv("RADAR_TEST_DISABLE_BACKGROUND_JOBS") != "1"
        and os.getenv("RADAR_ENABLE_CAIXA_DATE_WORKER", "1") == "1"
    )
    agora = datetime.utcnow()
    aguardando = bool(
        estado and estado.bloqueado_ate and estado.bloqueado_ate > agora
    )
    return {
        "habilitado": habilitado,
        "status": (
            "DESATIVADO" if not habilitado else
            "AGUARDANDO" if aguardando else
            "CONCLUIDO" if estado and not estado.ativo else
            "ATIVO"
        ),
        "cursor_id": estado.cursor_id if estado else None,
        # Ritmo configurado no backend; o ciclo manual do Admin usa o mesmo.
        "intervalo_segundos": intervalo_entre_imoveis(),
        "bloqueado_ate": estado.bloqueado_ate.isoformat()
        + "Z" if estado and estado.bloqueado_ate else None,
        "atualizado_em": estado.atualizado_em.isoformat()
        + "Z" if estado and estado.atualizado_em else None,
    }


@router.post("/caixa")
def executar_scraper_caixa(
    db: Session = Depends(get_db),
    administrador=Depends(usuario_admin),
):
    service = ScraperService(db)
    with CAIXA_COLETA_LOCK:
        return service.executar_scraper_caixa()


@router.post("/caixa/atualizar")
def atualizar_lista_caixa(
    db: Session = Depends(get_db),
    administrador=Depends(usuario_admin),
):
    """Baixa os CSVs atuais da Caixa e atualiza os imóveis no banco."""
    # 409 se outra consulta estiver em curso; 429 durante a espera de bloqueio.
    with acesso_caixa_http(db, "importacao-manual"):
        return ScraperService(db).atualizar_lista_caixa()


@router.post("/caixa/enriquecer-datas")
def enriquecer_datas_caixa(
    limite: int = Query(default=3, ge=1, le=5),
    depois_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    administrador=Depends(usuario_admin),
):
    """Consulta uma leva limitada de páginas da Caixa para preencher datas ausentes."""
    # Porteiro comum: 409 se outra consulta estiver em curso (inclui outros
    # processos em PostgreSQL), 429 durante a espera de bloqueio.
    with acesso_caixa_http(db, "datas-manual"):
        resultado = ScraperService(db).enriquecer_datas_caixa(
            limite=limite,
            depois_id=depois_id,
        )
        if resultado.get("bloqueado"):
            # Mesma espera do worker automático: sem isto, quem chama o
            # endpoint poderia continuar a insistir logo após um bloqueio.
            resultado["horas_espera"] = registrar_bloqueio_caixa(db, "datas-manual")
            resultado["retomar_em"] = db.get(
                CaixaDataWorkerState, 1
            ).bloqueado_ate.isoformat()
        return resultado


@router.get("/caixa/status")
def status_caixa(
    db: Session = Depends(get_db),
    administrador=Depends(usuario_admin),
):
    ultima = (
        db.query(AtualizacaoCaixa)
        .order_by(AtualizacaoCaixa.id.desc())
        .first()
    )

    historico = (
        db.query(AtualizacaoCaixa)
        .order_by(AtualizacaoCaixa.id.desc())
        .limit(5)
        .all()
    )

    total_imoveis = (
        db.query(func.count(Imovel.id))
        .scalar()
        or 0
    )

    imoveis_com_fotos = (
        db.query(
            func.count(
                func.distinct(ImovelImagem.imovel_id)
            )
        )
        .scalar()
        or 0
    )

    resposta = {
        "api": "online",
        "banco": "conectado",
        "imoveis": total_imoveis,
        "imoveis_com_fotos": imoveis_com_fotos,
        "caixa": {
            "status": "SEM_EXECUCAO",
            "iniciada_em": None,
            "concluida_em": None,
            "imoveis_atualizados": 0,
            "imoveis_removidos": 0,
            "fotos_pendentes": 0,
            "estados_baixados": 0,
            "erro": None,
        },
        "historico": [
            {
                "id": item.id,
                "status": item.status,
                "iniciada_em": item.iniciada_em,
                "concluida_em": item.concluida_em,
                "imoveis_atualizados": item.imoveis_atualizados,
                "imoveis_removidos": item.imoveis_removidos,
                "fotos_pendentes": item.fotos_pendentes,
                "estados_baixados": item.estados_baixados,
                "erro": item.erro,
            }
            for item in historico
        ],
    }

    if ultima:
        resposta["caixa"] = {
            "status": ultima.status,
            "iniciada_em": ultima.iniciada_em,
            "concluida_em": ultima.concluida_em,
            "imoveis_atualizados": ultima.imoveis_atualizados,
            "imoveis_removidos": ultima.imoveis_removidos,
            "fotos_pendentes": ultima.fotos_pendentes,
            "estados_baixados": ultima.estados_baixados,
            "erro": ultima.erro,
        }

    return resposta
