"""Fila automática de datas da CAIXA (um imóvel por volta).

Fica fora de app/main.py para poder ser testada sem arrancar a aplicação.
Quem chama deve segurar CAIXA_COLETA_LOCK.
"""
import logging
import os
from datetime import datetime, timedelta

from app.models.caixa_data_worker_state import CaixaDataWorkerState

logger = logging.getLogger(__name__)

# Quantas vezes seguidas o mesmo imóvel pode falhar por motivo técnico
# (Chrome indisponível, timeouts) antes de a fila seguir em frente.
MAX_FALHAS_TECNICAS_POR_IMOVEL = 3

# Contagem em memória: recomeça se o processo reiniciar, o que só dá mais
# tentativas a esse imóvel. Não precisa de coluna nova na base de dados.
_falhas_tecnicas: dict[int, int] = {}

# Pausa entre dois imóveis consultados pelo worker. Configurável por
# RADAR_CAIXA_DATAS_INTERVALO_SEGUNDOS; abaixo do mínimo usa o mínimo.
INTERVALO_PADRAO_SEGUNDOS = 60
INTERVALO_MINIMO_SEGUNDOS = 10


def intervalo_entre_imoveis() -> int:
    valor = os.getenv("RADAR_CAIXA_DATAS_INTERVALO_SEGUNDOS", "").strip()
    if not valor:
        return INTERVALO_PADRAO_SEGUNDOS
    try:
        segundos = int(float(valor))
    except ValueError:
        logger.warning(
            "RADAR_CAIXA_DATAS_INTERVALO_SEGUNDOS inválido (%r); a usar %s s.",
            valor,
            INTERVALO_PADRAO_SEGUNDOS,
        )
        return INTERVALO_PADRAO_SEGUNDOS
    return max(INTERVALO_MINIMO_SEGUNDOS, segundos)


def registrar_bloqueio(estado, agora: datetime) -> int:
    """Aplica a espera progressiva após um bloqueio da CAIXA (12h, 24h, 48h, 72h).

    Para gravar a espera a partir de qualquer rotina, use
    app.services.caixa_acesso.registrar_bloqueio_caixa (cria a linha e faz commit).
    """
    estado.bloqueios_consecutivos = (estado.bloqueios_consecutivos or 0) + 1
    horas_espera = min(
        12 * (2 ** (estado.bloqueios_consecutivos - 1)),
        72,
    )
    estado.bloqueado_ate = agora + timedelta(hours=horas_espera)
    estado.atualizado_em = agora
    return horas_espera


def _obter_estado(db):
    estado = db.get(CaixaDataWorkerState, 1)
    if estado is None:
        estado = CaixaDataWorkerState(id=1, ativo=True)
        db.add(estado)
        db.flush()
    return estado


def reativar_worker_datas_caixa(db) -> None:
    """Põe a fila a correr outra vez desde o início, sem fazer commit.

    Usado depois de cada importação da lista: os imóveis novos chegam sem datas
    e os que ficaram sem datas na volta anterior voltam a ser tentados.
    Um bloqueio ainda em vigor (bloqueado_ate) é respeitado.
    """
    estado = _obter_estado(db)
    estado.ativo = True
    estado.cursor_id = None
    estado.atualizado_em = datetime.utcnow()
    _falhas_tecnicas.clear()


def processar_lote_datas_caixa(db, agora: datetime | None = None) -> dict:
    """Consulta o próximo imóvel pendente e avança o cursor da fila."""
    from app.services.scraper_service import ScraperService

    estado = db.get(CaixaDataWorkerState, 1)
    if estado is None:
        estado = CaixaDataWorkerState(id=1, ativo=True)
        db.add(estado)
        db.commit()
        db.refresh(estado)

    agora = agora or datetime.utcnow()
    if not estado.ativo:
        return {"concluido": True}
    if estado.bloqueado_ate and estado.bloqueado_ate > agora:
        return {
            "aguardando_bloqueio": True,
            "segundos_restantes": int(
                (estado.bloqueado_ate - agora).total_seconds()
            ),
        }

    resultado = ScraperService(db).enriquecer_datas_caixa(
        limite=1,
        depois_id=estado.cursor_id,
    )

    if resultado.get("bloqueado"):
        item_bloqueado = next(
            (
                item
                for item in resultado.get("resultados", [])
                if item.get("status") == "BLOQUEADO_CAIXA"
            ),
            None,
        )
        if item_bloqueado:
            estado.cursor_id = max(0, int(item_bloqueado["id"]) - 1)
        horas_espera = registrar_bloqueio(estado, agora)
        resultado["retomar_em"] = estado.bloqueado_ate.isoformat()
        resultado["horas_espera"] = horas_espera

    elif resultado.get("falha_tecnica"):
        imovel_id = int(resultado["falha_tecnica_id"])
        tentativas = _falhas_tecnicas.get(imovel_id, 0) + 1
        resultado["tentativas_falha_tecnica"] = tentativas
        if tentativas < MAX_FALHAS_TECNICAS_POR_IMOVEL:
            # Fica no mesmo imóvel para a próxima volta.
            _falhas_tecnicas[imovel_id] = tentativas
            estado.cursor_id = max(0, imovel_id - 1)
            resultado["tentar_novamente"] = True
        else:
            # Desiste deste imóvel nesta volta; a próxima importação reativa
            # a fila e ele volta a ser tentado.
            _falhas_tecnicas.pop(imovel_id, None)
            logger.warning(
                "Imóvel %s falhou %s vezes por motivo técnico; a fila segue.",
                imovel_id,
                tentativas,
            )
            _avancar_cursor(estado, resultado)

    else:
        estado.bloqueios_consecutivos = 0
        estado.bloqueado_ate = None
        for item in resultado.get("resultados", []):
            _falhas_tecnicas.pop(item.get("id"), None)
        _avancar_cursor(estado, resultado)

    estado.atualizado_em = agora
    db.commit()
    return resultado


def _avancar_cursor(estado, resultado) -> None:
    if resultado.get("tem_mais"):
        estado.cursor_id = resultado.get("proximo_depois_id")
    else:
        estado.cursor_id = None
        estado.ativo = False
        resultado["concluido"] = True
