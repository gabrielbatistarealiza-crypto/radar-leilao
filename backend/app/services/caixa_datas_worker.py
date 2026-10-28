"""Fila automática de datas da CAIXA (um imóvel, e o seu edital, por volta).

Fica fora de app/main.py para poder ser testada sem arrancar a aplicação.
Quem chama deve segurar CAIXA_COLETA_LOCK (ver caixa_acesso.acesso_caixa).

Cada volta usa só requests (sem Selenium) e faz no máximo 2 pedidos: a página
do imóvel e, se ainda não foi lido, o PDF do edital (ver caixa_datas_edital).
Perante qualquer bloqueio ou resposta inesperada o worker PARA até revisão
manual: nunca repete o pedido nem retoma sozinho. Antes de cada GET grava a
paragem manual como marca de "pedido em curso" e só a retira depois de gravar
o resultado; um processo interrompido a meio deixa o worker parado.
"""
import logging
import os
from datetime import datetime, timedelta

from app.models.caixa_data_worker_state import CaixaDataWorkerState
from app.models.imovel import Imovel
from app.services.caixa_datas_edital import (
    PARAGEM_MANUAL,
    e_paragem_manual,
    filtro_pendentes,
    processar_passo,
)

logger = logging.getLogger(__name__)

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


def registrar_paragem_manual(estado, agora: datetime, imovel_id: int | None = None) -> None:
    """Para o worker até alguém rever: espera sem fim, fila inativa.

    O cursor recua para que, depois da revisão, o mesmo imóvel seja o próximo.
    Para retomar: bloqueado_ate = NULL e ativo = true (à mão, depois de rever).
    """
    estado.bloqueios_consecutivos = (estado.bloqueios_consecutivos or 0) + 1
    estado.bloqueado_ate = PARAGEM_MANUAL
    estado.ativo = False
    if imovel_id is not None:
        estado.cursor_id = max(0, int(imovel_id) - 1)
    estado.atualizado_em = agora


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
    Um bloqueio ou uma paragem manual ainda em vigor (bloqueado_ate) é respeitado.
    """
    estado = _obter_estado(db)
    estado.ativo = True
    estado.cursor_id = None
    estado.atualizado_em = datetime.utcnow()


def processar_lote_datas_caixa(
    db, agora: datetime | None = None, pedir=None, max_pedidos: int = 2
) -> dict:
    """Uma volta: o próximo imóvel pendente (e o seu edital); avança o cursor.

    `pedir` substitui o pedido HTTP (testes). `max_pedidos` (1 ou 2) limita os
    GET desta volta; com 1, o edital fica para uma volta seguinte.
    """
    estado = db.get(CaixaDataWorkerState, 1)
    if estado is None:
        estado = CaixaDataWorkerState(id=1, ativo=True)
        db.add(estado)
        db.commit()
        db.refresh(estado)

    agora = agora or datetime.utcnow()
    if not estado.ativo:
        return {"concluido": True, "pedidos": 0}
    if estado.bloqueado_ate and estado.bloqueado_ate > agora:
        return {
            "aguardando_bloqueio": True,
            "paragem_manual": e_paragem_manual(estado.bloqueado_ate),
            "segundos_restantes": int(
                (estado.bloqueado_ate - agora).total_seconds()
            ),
            "pedidos": 0,
        }

    def marcar_pedido_em_curso(imovel_id: int) -> None:
        # Gravada (commit) ANTES de cada GET e só retirada depois de gravar o
        # resultado: se o processo morrer a meio, a próxima execução encontra a
        # paragem manual e não repete o pedido.
        estado.bloqueado_ate = PARAGEM_MANUAL
        estado.atualizado_em = agora
        db.commit()

    try:
        resultado = processar_passo(
            db, estado, pedir=pedir, max_pedidos=max_pedidos,
            antes_de_pedir=marcar_pedido_em_curso,
        )
    except Exception:
        # Resultado desconhecido: a marca (se já gravada) fica e o worker
        # permanece parado até revisão manual.
        db.rollback()
        raise

    if "paragem" in resultado:
        # As datas lidas da própria página (se houver) ficam; do edital nada foi
        # gravado. O worker fica parado até revisão manual.
        registrar_paragem_manual(estado, agora, resultado.get("imovel_id"))
        resultado.update(bloqueado=True, paragem_manual=True)
        logger.warning(
            "Worker de datas da CAIXA PARADO para revisão manual: %s (imóvel %s).",
            resultado["paragem"],
            resultado.get("imovel_id"),
        )
    elif resultado.get("concluido"):
        estado.cursor_id = None
        estado.ativo = False
    else:
        estado.bloqueios_consecutivos = 0
        estado.bloqueado_ate = None  # retira a marca de pedido em curso
        estado.cursor_id = resultado["imovel_id"]
        resultado["tem_mais"] = bool(
            db.query(Imovel.id)
            .filter(filtro_pendentes(), Imovel.id > estado.cursor_id)
            .first()
        )
        resultado["proximo_depois_id"] = estado.cursor_id

    estado.atualizado_em = agora
    db.commit()
    return resultado
