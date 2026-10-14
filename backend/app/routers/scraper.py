from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.atualizacao_caixa import AtualizacaoCaixa
from app.models.imovel import Imovel, ImovelImagem
from app.security.auth import usuario_admin
from app.services.scraper_service import ScraperService


router = APIRouter()


@router.post("/caixa")
def executar_scraper_caixa(
    db: Session = Depends(get_db),
    administrador=Depends(usuario_admin),
):
    service = ScraperService(db)
    return service.executar_scraper_caixa()


@router.post("/caixa/atualizar")
def atualizar_lista_caixa(
    db: Session = Depends(get_db),
    administrador=Depends(usuario_admin),
):
    """Baixa os CSVs atuais da Caixa e atualiza os imóveis no banco."""
    return ScraperService(db).atualizar_lista_caixa()


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
