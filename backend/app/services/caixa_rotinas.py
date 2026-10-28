"""Rotinas automáticas que consultam a CAIXA, todas atrás do porteiro.

Ficam fora de app/main.py para poderem ser testadas sem arrancar a aplicação.
Cada função devolve um dicionário; quando o porteiro recusa, devolve
{"aguardando_bloqueio": True, ...} ou {"ocupado": True} sem contactar a CAIXA.
"""
import logging

from app.services.caixa_acesso import (
    CaixaEmEspera,
    CaixaOcupada,
    acesso_caixa,
    registrar_bloqueio_caixa,
)
from app.services.caixa_datas_worker import processar_lote_datas_caixa

logger = logging.getLogger(__name__)


def _com_acesso(db, origem, funcao):
    try:
        with acesso_caixa(db, origem):
            return funcao()
    except CaixaEmEspera as espera:
        logger.info(
            "%s: espera de bloqueio em vigor (%s s); nada consultado.",
            origem,
            espera.segundos_restantes,
        )
        return {
            "aguardando_bloqueio": True,
            "segundos_restantes": espera.segundos_restantes,
        }
    except CaixaOcupada:
        logger.info("%s: outra consulta à CAIXA em curso; nada consultado.", origem)
        return {"ocupado": True}


def executar_lote_datas(db, max_pedidos: int = 2, pedir=None) -> dict:
    return _com_acesso(
        db,
        "datas-worker",
        lambda: processar_lote_datas_caixa(db, pedir=pedir, max_pedidos=max_pedidos),
    )


def processar_lote_fotos_caixa(db, limite: int) -> dict:
    """Um lote da fila de fotos; um bloqueio grava a espera partilhada."""
    from app.services.scraper_service import ScraperService

    resultado = ScraperService(db).processar_fila_fotos_caixa(limite)
    if resultado.get("bloqueados", 0):
        resultado["horas_espera"] = registrar_bloqueio_caixa(db, "fotos-worker")
    return resultado


def executar_lote_fotos(db, limite: int) -> dict:
    return _com_acesso(db, "fotos-worker", lambda: processar_lote_fotos_caixa(db, limite))


def executar_importacao(db, max_ufs: int | None = None) -> dict:
    from app.services.scraper_service import ScraperService

    return _com_acesso(
        db, "importacao", lambda: ScraperService(db).atualizar_lista_caixa(max_ufs=max_ufs)
    )
