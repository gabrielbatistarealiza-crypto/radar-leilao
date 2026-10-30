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

from types import SimpleNamespace

from app.models.caixa_data_worker_state import CaixaDataWorkerState
from app.models.caixa_pedidos_dia import CaixaPedidosDia
from app.models.imovel import Imovel
from app.services.caixa_datas_edital import (
    PARAGEM_MANUAL,
    e_paragem_manual,
    filtro_pendentes,
    processar_edital_pendente,
    processar_passo,
)

logger = logging.getLogger(__name__)

# Pausa entre dois imóveis consultados pelo worker. Configurável por
# RADAR_CAIXA_DATAS_INTERVALO_SEGUNDOS; abaixo do mínimo usa o mínimo.
# Em produção a página de imóvel foi travada pelo Radware com 62 s entre
# pedidos: o padrão é lento de propósito.
INTERVALO_PADRAO_SEGUNDOS = 600
INTERVALO_MINIMO_SEGUNDOS = 60

# Máximo de pedidos (páginas + editais) por dia UTC, para o worker e o
# endpoint manual juntos. Configurável por RADAR_CAIXA_DATAS_MAX_PEDIDOS_DIA.
MAX_PEDIDOS_DIA_PADRAO = 20
MAX_PEDIDOS_DIA_TETO = 1000


def limite_diario_pedidos() -> int:
    valor = os.getenv("RADAR_CAIXA_DATAS_MAX_PEDIDOS_DIA", "").strip()
    if not valor:
        return MAX_PEDIDOS_DIA_PADRAO
    try:
        return min(MAX_PEDIDOS_DIA_TETO, max(0, int(float(valor))))
    except ValueError:
        logger.warning(
            "RADAR_CAIXA_DATAS_MAX_PEDIDOS_DIA inválido (%r); a usar %s.",
            valor,
            MAX_PEDIDOS_DIA_PADRAO,
        )
        return MAX_PEDIDOS_DIA_PADRAO


def pedidos_hoje(db, agora: datetime) -> int:
    linha = db.get(CaixaPedidosDia, agora.date())
    return (linha.pedidos or 0) if linha else 0


def _contar_pedido(db, agora: datetime) -> None:
    """Soma 1 ao dia (sem commit: quem chama faz commit ANTES do pedido)."""
    linha = db.get(CaixaPedidosDia, agora.date())
    if linha is None:
        linha = CaixaPedidosDia(dia=agora.date(), pedidos=0)
        db.add(linha)
    linha.pedidos = (linha.pedidos or 0) + 1


def _segundos_ate_amanha(agora: datetime) -> int:
    amanha = datetime.combine(agora.date() + timedelta(days=1), datetime.min.time())
    return max(1, int((amanha - agora).total_seconds()))


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


def _executar_passo(db, estado, cursor, agora, pedir, max_pedidos, recuar_cursor_na_paragem,
                    edital_pendente: dict | None = None, excluir_ufs=None):
    """Passo comum ao worker e ao endpoint manual.

    `cursor` é o estado do worker ou um cursor próprio do endpoint manual.
    Aplica o limite diário, conta cada pedido e grava a marca de "pedido em
    curso" (com commit) ANTES de cada GET, e trata a paragem manual.
    """
    restantes = limite_diario_pedidos() - pedidos_hoje(db, agora)
    if restantes <= 0:
        return {"limite_diario_atingido": True, "pedidos": 0,
                "segundos_restantes": _segundos_ate_amanha(agora)}

    def marcar_pedido_em_curso(imovel_id: int) -> None:
        # Gravada (commit) ANTES de cada GET e só retirada depois de gravar o
        # resultado: se o processo morrer a meio, a próxima execução encontra a
        # paragem manual e não repete o pedido. O pedido fica já contado.
        _contar_pedido(db, agora)
        estado.bloqueado_ate = PARAGEM_MANUAL
        estado.atualizado_em = agora
        db.commit()

    try:
        if edital_pendente:
            # Só o edital adiado numa volta anterior: 1 pedido, sem ler página.
            resultado = processar_edital_pendente(
                db, edital_pendente["imovel_id"], edital_pendente["link"], pedir=pedir,
                antes_de_pedir=marcar_pedido_em_curso,
            )
        else:
            resultado = processar_passo(
                db, cursor, pedir=pedir, max_pedidos=min(max_pedidos, restantes),
                antes_de_pedir=marcar_pedido_em_curso, excluir_ufs=excluir_ufs,
            )
    except Exception:
        # Resultado desconhecido: a marca (se já gravada) fica e tudo
        # permanece parado até revisão manual.
        db.rollback()
        raise

    if "paragem" in resultado:
        # As datas lidas da própria página (se houver) ficam; do edital nada foi
        # gravado. Tudo fica parado até revisão manual.
        registrar_paragem_manual(
            estado, agora, resultado.get("imovel_id") if recuar_cursor_na_paragem else None
        )
        resultado.update(bloqueado=True, paragem_manual=True)
        logger.warning(
            "Datas da CAIXA PARADAS para revisão manual: %s (imóvel %s).",
            resultado["paragem"],
            resultado.get("imovel_id"),
        )
    elif not resultado.get("concluido"):
        estado.bloqueios_consecutivos = 0
        estado.bloqueado_ate = None  # retira a marca de pedido em curso
    return resultado


def passo_manual_datas(db, depois_id: int | None = None, pedir=None,
                       agora: datetime | None = None) -> dict:
    """Um imóvel a partir de `depois_id`, para o ciclo manual do painel Admin.

    Usa o mesmo passo do worker (só requests, limite diário, marca antes de
    cada pedido, paragem manual), sem mexer no cursor do worker. Devolve o
    formato antigo do endpoint (processados, atualizados, tem_mais, ...).
    """
    agora = agora or datetime.utcnow()
    estado = _obter_estado(db)
    db.commit()
    cursor = SimpleNamespace(cursor_id=depois_id)
    r = _executar_passo(db, estado, cursor, agora, pedir, 2, recuar_cursor_na_paragem=False)
    if r.get("limite_diario_atingido"):
        return r

    imovel_id = r.get("imovel_id")
    tem_mais = bool(
        imovel_id is not None and "paragem" not in r
        and db.query(Imovel.id).filter(filtro_pendentes(), Imovel.id > imovel_id).first()
    )
    if "paragem" in r:
        status = "BLOQUEADO_CAIXA"
    else:
        status = "ATUALIZADO" if r.get("atualizados") else "SEM_DATAS_NOVAS"
    estado.atualizado_em = agora
    db.commit()
    return {
        "processados": r.get("processados", 0),
        "atualizados": r.get("atualizados", 0),
        "sem_dados_novos": int(bool(imovel_id) and not r.get("atualizados") and "paragem" not in r),
        "erros": 0,
        "falhas_tecnicas": 0,
        "falha_tecnica": False,
        "falha_tecnica_id": None,
        "bloqueado": "paragem" in r,
        "paragem": r.get("paragem"),
        "pedidos": r.get("pedidos", 0),
        "tem_mais": tem_mais,
        "proximo_depois_id": imovel_id if tem_mais else None,
        "resultados": [{"id": imovel_id, "status": status}] if imovel_id else [],
    }


def processar_lote_datas_caixa(
    db, agora: datetime | None = None, pedir=None, max_pedidos: int = 2,
    edital_pendente: dict | None = None,
    excluir_ufs=None,
) -> dict:
    """Uma volta: o próximo imóvel pendente (e o seu edital); avança o cursor.

    `pedir` substitui o pedido HTTP (testes). `max_pedidos` (1 ou 2) limita os
    GET desta volta; com 1, o edital fica para uma volta seguinte, que o pede
    passando `edital_pendente={"imovel_id": ..., "link": ...}`.
    `excluir_ufs` (conjunto): modo "um imóvel por estado"; não mexe no cursor
    nem desativa a fila quando os estados se esgotam.
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

    por_uf = excluir_ufs is not None
    resultado = _executar_passo(db, estado, estado, agora, pedir, max_pedidos,
                                recuar_cursor_na_paragem=not por_uf,
                                edital_pendente=edital_pendente, excluir_ufs=excluir_ufs)
    if resultado.get("limite_diario_atingido"):
        return resultado

    if "paragem" in resultado:
        pass  # paragem manual já gravada por _executar_passo
    elif por_uf or resultado.get("ufs_esgotadas"):
        pass  # o cursor da ordem normal fica onde estava
    elif resultado.get("concluido"):
        estado.cursor_id = None
        estado.ativo = False
    else:
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
