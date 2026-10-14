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
from app.services.notificacoes import (
    gerar_notificacoes,
    libertar_lock_scheduler_notificacoes,
    tentar_lock_scheduler_notificacoes,
)


Base.metadata.create_all(bind=engine)

logger = logging.getLogger(__name__)


def _atualizar_lista_caixa_agendada():
    db = SessionLocal()
    try:
        return ScraperService(db).atualizar_lista_caixa()
    finally:
        db.close()


def _proxima_atualizacao_caixa():
    # Usa o fuso horÃ¡rio local configurado no servidor (Lisboa neste ambiente)
    # sem depender da base tzdata no Windows.
    agora = datetime.now().astimezone()
    proxima = agora.replace(hour=3, minute=0, second=0, microsecond=0)
    if proxima <= agora:
        proxima += timedelta(days=1)
    return proxima


async def _rotina_atualizacao_caixa():
    """Atualiza os CSVs da Caixa diariamente Ã s 03:00 (horÃ¡rio de Lisboa)."""
    while True:
        proxima = _proxima_atualizacao_caixa()
        espera = (proxima - datetime.now().astimezone()).total_seconds()
        logger.info("PrÃ³xima atualizaÃ§Ã£o automÃ¡tica da Caixa: %s", proxima.isoformat())
        await asyncio.sleep(max(0, espera))

        try:
            resultado = await asyncio.to_thread(_atualizar_lista_caixa_agendada)
            logger.info("AtualizaÃ§Ã£o automÃ¡tica da Caixa concluÃ­da: %s", resultado)
        except Exception:
            logger.exception("Falha na atualizaÃ§Ã£o automÃ¡tica da Caixa")

def _processar_fila_fotos_caixa_agendada(limite: int = 50):
    db = SessionLocal()
    try:
        return ScraperService(db).processar_fila_fotos_caixa(limite)
    finally:
        db.close()

async def _rotina_fila_fotos_caixa():
    """Processa automaticamente a fila de fotos da Caixa."""

    PAUSA_ENTRE_LOTES = 30

    while True:
        try:
            resultado = await asyncio.to_thread(
                _processar_fila_fotos_caixa_agendada,
                50,
            )

            logger.info(
                "Fila de fotos Caixa: %s",
                resultado,
            )

            if resultado.get("bloqueados", 0) > 0:
                logger.warning(
                    "Caixa bloqueou o acesso. "
                    "Worker de fotos encerrado para evitar novas tentativas."
                )
                return

            if resultado.get("processados", 0) == 0:
                logger.info(
                    "Fila de fotos Caixa sem imÃ³veis pendentes. "
                    "Nova verificaÃ§Ã£o em 10 minutos."
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
            quantidade = await asyncio.to_thread(_gerar_notificacoes_agendadas)
            logger.info("Verificação de notificações concluída: %s novas", quantidade)
            await asyncio.sleep(900)
    except Exception:
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

    tarefa_fotos = asyncio.create_task(
        _rotina_fila_fotos_caixa()
    )
    tarefa_notificacoes = asyncio.create_task(_rotina_notificacoes())

    try:
        yield
    finally:
        tarefa_atualizacao.cancel()
        tarefa_fotos.cancel()
        tarefa_notificacoes.cancel()

        with suppress(asyncio.CancelledError):
            await tarefa_atualizacao

        with suppress(asyncio.CancelledError):
            await tarefa_fotos

        with suppress(asyncio.CancelledError):
            await tarefa_notificacoes
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
    ] + (["http://127.0.0.1:5174"] if os.getenv("RADAR_TEST_DISABLE_BACKGROUND_JOBS") == "1" else []),
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

@app.get("/")
def home():
    return {
        "status": "online",
        "app": "Arremata Patrimonio API",
    }


@app.get("/health")
def health():
    return {"status": "ok"}
