import asyncio
import logging
import os
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routers.imoveis import router as imoveis_router
from app.database.database import Base, engine
from app.models.imovel import (
    Imovel,
    ImovelImagem,
    ImovelFotoVerificacao,
)
from app.models.atualizacao_caixa import AtualizacaoCaixa
from app.models.caixa_data_worker_state import CaixaDataWorkerState
from app.routers.usuarios import router as usuarios_router
from app.routers.login import router as login_router
from app.routers.scraper import router as scraper_router
from app.routers.admin import router as admin_router
from app.routers.oportunidades import router as oportunidades_router
from app.routers.negociacoes import router as negociacoes_router
from app.routers.operacoes import router as operacoes_router
from app.routers.corretores import router as corretores_router
from app.routers.anuncios_imoveis import (
    router as anuncios_imoveis_router
)
from app.routers.simulacoes_rentabilidade import router as simulacoes_rentabilidade_router
from app.database.database import SessionLocal
from app.services.scraper_service import ScraperService
from app.models.oportunidade import Oportunidade
from app.models.negociacao import Negociacao
from app.models.operacao import Operacao
from app.models.corretor import Corretor
from app.models.anuncio_imovel import AnuncioImovel
from app.models.anuncio_imagem import AnuncioImagem
from app.models.atividade_oportunidade import AtividadeOportunidade
from app.models.simulacao_rentabilidade import SimulacaoRentabilidade
from app.models.criterio_alerta import CriterioAlerta
from app.models.notificacao import Notificacao
from app.routers.alertas import router as alertas_router
from app.routers.consultoria import criar_router as criar_router_consultoria
from app.security.auth import usuario_atual
from app.services.notificacoes import (
    gerar_notificacoes,
    libertar_lock_scheduler_notificacoes,
    tentar_lock_scheduler_notificacoes,
)
from app.services.caixa_datas_worker import intervalo_entre_imoveis
from app.services.caixa_rotinas import (
    executar_importacao,
    executar_lote_datas,
    executar_lote_fotos,
)

# Outra rotina (deste ou de outro processo) está a usar a CAIXA: tenta depois.
ESPERA_CAIXA_OCUPADA = 60


Base.metadata.create_all(bind=engine)


def configurar_logging_da_app():
    """Mostra as mensagens INFO dos modulos da app (loggers "app.*").

    O uvicorn so configura os seus proprios loggers; sem isto, os da app ficam
    no nivel WARNING por omissao e as mensagens INFO (por exemplo, "rotinas
    desativadas") nao aparecem nos logs. Pode ser chamada varias vezes: so
    acrescenta o handler uma vez.
    """
    logger_app = logging.getLogger("app")
    logger_app.setLevel(logging.INFO)
    if not any(getattr(h, "_radar_logging", False) for h in logger_app.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s: %(message)s"))
        handler._radar_logging = True
        logger_app.addHandler(handler)


configurar_logging_da_app()
logger = logging.getLogger(__name__)


def _atualizar_lista_caixa_agendada():
    db = SessionLocal()
    try:
        # Respeita a espera de bloqueio e o lock entre processos.
        return executar_importacao(db)
    finally:
        db.close()


def _proxima_atualizacao_caixa():
    # Usa o fuso horário local configurado no servidor (Lisboa neste ambiente)
    # sem depender da base tzdata no Windows.
    agora = datetime.now().astimezone()
    proxima = agora.replace(hour=3, minute=0, second=0, microsecond=0)
    if proxima <= agora:
        proxima += timedelta(days=1)
    return proxima


async def _rotina_atualizacao_caixa():
    """Atualiza os CSVs da Caixa diariamente às 03:00 (horário de Lisboa)."""
    while True:
        proxima = _proxima_atualizacao_caixa()
        espera = (proxima - datetime.now().astimezone()).total_seconds()
        logger.info("Próxima atualização automática da Caixa: %s", proxima.isoformat())
        await asyncio.sleep(max(0, espera))

        try:
            resultado = await asyncio.to_thread(_atualizar_lista_caixa_agendada)
            logger.info("Atualização automática da Caixa concluída: %s", resultado)
        except Exception:
            logger.exception("Falha na atualização automática da Caixa")

def _processar_fila_fotos_caixa_agendada(limite: int = 50):
    db = SessionLocal()
    try:
        # O porteiro verifica a espera; um bloqueio grava-a via
        # registrar_bloqueio_caixa (cria a linha de estado se faltar).
        return executar_lote_fotos(db, limite)
    finally:
        db.close()


def _processar_lote_datas_caixa_agendado():
    db = SessionLocal()
    try:
        return executar_lote_datas(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# Fila vazia: volta a olhar de hora a hora. A importação diária reativa a fila.
ESPERA_FILA_DATAS_CONCLUIDA = 3600
# Falha técnica (Chrome, timeouts): dá tempo ao ambiente antes de repetir.
ESPERA_FALHA_TECNICA_DATAS = 300


async def _rotina_enriquecimento_datas_caixa():
    """Preenche datas gradualmente e retoma com espera longa após bloqueio."""
    while True:
        try:
            resultado = await asyncio.to_thread(
                _processar_lote_datas_caixa_agendado
            )
            if resultado.get("ocupado"):
                await asyncio.sleep(ESPERA_CAIXA_OCUPADA)
                continue
            if resultado.get("concluido"):
                # Não termina a tarefa: depois da próxima importação há
                # imóveis novos sem datas para tratar.
                logger.info(
                    "Worker de datas da CAIXA sem pendências na fila; "
                    "nova verificação em %s segundos.",
                    ESPERA_FILA_DATAS_CONCLUIDA,
                )
                await asyncio.sleep(ESPERA_FILA_DATAS_CONCLUIDA)
                continue
            if resultado.get("falha_tecnica"):
                logger.warning(
                    "Worker de datas da CAIXA: falha técnica no imóvel %s "
                    "(tentativa %s); nova volta em %s segundos.",
                    resultado.get("falha_tecnica_id"),
                    resultado.get("tentativas_falha_tecnica"),
                    ESPERA_FALHA_TECNICA_DATAS,
                )
                await asyncio.sleep(ESPERA_FALHA_TECNICA_DATAS)
                continue
            if resultado.get("aguardando_bloqueio"):
                # Paragem manual = espera sem fim: volta só a olhar de 6 em 6 h
                # (sem contactar a CAIXA) até alguém rever e limpar o estado.
                espera = min(max(60, resultado["segundos_restantes"]), 6 * 3600)
                logger.info(
                    "Worker de datas da CAIXA parado (%s); nova verificação do "
                    "estado em %s segundos.",
                    "revisão manual" if resultado.get("paragem_manual") else "bloqueio",
                    espera,
                )
                await asyncio.sleep(espera)
                continue
            if resultado.get("bloqueado"):
                logger.warning(
                    "Worker de datas da CAIXA parado para revisão manual: %s.",
                    resultado.get("paragem"),
                )
                continue
            logger.info(
                "Worker de datas da CAIXA: processados=%s, atualizados=%s.",
                resultado.get("processados", 0),
                resultado.get("atualizados", 0),
            )
            await asyncio.sleep(intervalo_entre_imoveis())
        except Exception:
            logger.exception("Falha no worker automático de datas da CAIXA.")
            await asyncio.sleep(60)

async def _rotina_fila_fotos_caixa():
    """Processa automaticamente a fila de fotos da Caixa."""

    PAUSA_ENTRE_LOTES = 60

    while True:
        try:
            resultado = await asyncio.to_thread(
                _processar_fila_fotos_caixa_agendada,
                5,
            )

            logger.info(
                "Fila de fotos Caixa: %s",
                resultado,
            )

            if resultado.get("ocupado"):
                await asyncio.sleep(ESPERA_CAIXA_OCUPADA)
                continue

            if resultado.get("aguardando_bloqueio"):
                espera = max(60, resultado["segundos_restantes"])
                logger.info(
                    "Worker de fotos aguardará a CAIXA por %s segundos.",
                    espera,
                )
                await asyncio.sleep(espera)
                continue

            if resultado.get("bloqueados", 0) > 0:
                logger.warning(
                    "Caixa bloqueou o acesso. Worker de fotos aguardará %s horas.",
                    resultado.get("horas_espera"),
                )
                continue

            if resultado.get("processados", 0) == 0:
                logger.info(
                    "Fila de fotos Caixa sem imóveis pendentes. "
                    "Nova verificação em 10 minutos."
                )

                await asyncio.sleep(600)
                continue

            await asyncio.sleep(PAUSA_ENTRE_LOTES)

        except Exception:
            logger.exception(
                "Erro no worker da fila de fotos Caixa."
            )

            await asyncio.sleep(60)


def _gerar_notificacoes_agendadas():
    db = SessionLocal()
    try:
        return gerar_notificacoes(db)
    finally:
        db.close()


async def _rotina_notificacoes():
    """Verifica novos critérios correspondentes e prazos a cada 15 minutos."""
    while True:
        db = SessionLocal()
        try:
            if not tentar_lock_scheduler_notificacoes(db):
                db.close()
                await asyncio.sleep(900)
                continue
            break
        except Exception:
            db.close()
            logger.exception("Falha ao eleger worker do scheduler de notificações")
            await asyncio.sleep(900)

    try:
        while True:
            try:
                quantidade = await asyncio.to_thread(_gerar_notificacoes_agendadas)
                logger.info("Verificação de notificações concluída: %s novas", quantidade)
            except Exception:
                # Uma falha pontual não pode encerrar o scheduler para sempre.
                logger.exception("Falha ao gerar notificações de alertas")
            await asyncio.sleep(900)
    finally:
        try:
            libertar_lock_scheduler_notificacoes(db)
        finally:
            db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if (
        os.getenv("RADAR_DISABLE_BACKGROUND_JOBS") == "1"
        or os.getenv("RADAR_TEST_DISABLE_BACKGROUND_JOBS") == "1"
    ):
        logger.info("Rotinas automáticas em segundo plano desativadas por configuração.")
        yield
        return

    tarefa_atualizacao = asyncio.create_task(
        _rotina_atualizacao_caixa()
    )

    tarefa_datas = None
    if os.getenv("RADAR_ENABLE_CAIXA_DATE_WORKER", "1") == "1":
        tarefa_datas = asyncio.create_task(_rotina_enriquecimento_datas_caixa())

    tarefa_fotos = None
    if os.getenv("RADAR_ENABLE_CAIXA_PHOTO_WORKER", "1") == "1":
        tarefa_fotos = asyncio.create_task(_rotina_fila_fotos_caixa())
    else:
        logger.info(
            "Worker automático de fotos da CAIXA pausado. "
            "Defina RADAR_ENABLE_CAIXA_PHOTO_WORKER=1 para reativá-lo."
        )
    tarefa_notificacoes = asyncio.create_task(_rotina_notificacoes())

    try:
        yield
    finally:
        tarefa_atualizacao.cancel()
        if tarefa_datas is not None:
            tarefa_datas.cancel()
        if tarefa_fotos is not None:
            tarefa_fotos.cancel()
        tarefa_notificacoes.cancel()

        with suppress(asyncio.CancelledError):
            await tarefa_atualizacao

        if tarefa_datas is not None:
            with suppress(asyncio.CancelledError):
                await tarefa_datas

        if tarefa_fotos is not None:
            with suppress(asyncio.CancelledError):
                await tarefa_fotos

        with suppress(asyncio.CancelledError):
            await tarefa_notificacoes

# Em produção, defina RADAR_CORS_ORIGINS="https://seusite.com,https://www.seusite.com"
ORIGENS_EXTRAS = [
    origem.strip()
    for origem in os.getenv("RADAR_CORS_ORIGINS", "").split(",")
    if origem.strip()
]


class UTF8JSONResponse(JSONResponse):
    media_type = "application/json; charset=utf-8"

app = FastAPI(
    title="Arremata Patrimonio API",
    description="API com os melhores leilões de imóveis do Brasil",
    version="1.0.0",
    lifespan=lifespan,
    default_response_class=UTF8JSONResponse,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ] + (["http://127.0.0.1:5174"] if os.getenv("RADAR_TEST_DISABLE_BACKGROUND_JOBS") == "1" else []) + ORIGENS_EXTRAS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(imoveis_router)
app.include_router(usuarios_router)
app.include_router(login_router)
app.include_router(scraper_router)
app.include_router(admin_router)
app.include_router(oportunidades_router)
app.include_router(negociacoes_router)
app.include_router(operacoes_router)
app.include_router(corretores_router)
app.include_router(anuncios_imoveis_router)
app.include_router(simulacoes_rentabilidade_router)
app.include_router(alertas_router)
app.include_router(criar_router_consultoria(usuario_atual))

@app.get("/")
def home():
    return {
        "status": "online",
        "app": "Arremata Patrimonio API",
    }


@app.get("/health")
def health():
    return {"status": "ok"}
