import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.imoveis import router as imoveis_router
from app.database.database import Base, engine
from app.models.imovel import Imovel, ImovelImagem
from app.routers.usuarios import router as usuarios_router
from app.routers.login import router as login_router
from app.routers.scraper import router as scraper_router
from app.database.database import SessionLocal
from app.services.scraper_service import ScraperService

Base.metadata.create_all(bind=engine)

logger = logging.getLogger(__name__)


def _atualizar_lista_caixa_agendada():
    db = SessionLocal()
    try:
        return ScraperService(db).atualizar_lista_caixa()
    finally:
        db.close()


def _proxima_atualizacao_caixa():
    # Usa o fuso horÃƒÂ¡rio local configurado no servidor (Lisboa neste ambiente)
    # sem depender da base tzdata no Windows.
    agora = datetime.now().astimezone()
    proxima = agora.replace(hour=3, minute=0, second=0, microsecond=0)
    if proxima <= agora:
        proxima += timedelta(days=1)
    return proxima


async def _rotina_atualizacao_caixa():
    """Atualiza os CSVs da Caixa diariamente ÃƒÂ s 03:00 (horÃƒÂ¡rio de Lisboa)."""
    while True:
        proxima = _proxima_atualizacao_caixa()
        espera = (proxima - datetime.now().astimezone()).total_seconds()
        logger.info("PrÃƒÂ³xima atualizaÃƒÂ§ÃƒÂ£o automÃƒÂ¡tica da Caixa: %s", proxima.isoformat())
        await asyncio.sleep(max(0, espera))

        try:
            resultado = await asyncio.to_thread(_atualizar_lista_caixa_agendada)
            logger.info("AtualizaÃƒÂ§ÃƒÂ£o automÃƒÂ¡tica da Caixa concluÃƒÂ­da: %s", resultado)
        except Exception:
            logger.exception("Falha na atualizaÃƒÂ§ÃƒÂ£o automÃƒÂ¡tica da Caixa")

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
                    "Fila de fotos Caixa sem imÃƒÂ³veis pendentes. "
                    "Nova verificaÃƒÂ§ÃƒÂ£o em 10 minutos."
                )

                await asyncio.sleep(600)
                continue

            await asyncio.sleep(PAUSA_ENTRE_LOTES)

        except Exception:
            logger.exception(
                "Erro no worker da fila de fotos Caixa."
            )

            await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    tarefa_atualizacao = asyncio.create_task(
        _rotina_atualizacao_caixa()
    )

    yield

    tarefa_atualizacao.cancel()

    with suppress(asyncio.CancelledError):
        await tarefa_atualizacao

app = FastAPI(
    title="Arremata Patrimonio API",
    description="API com os melhores leilÃƒÂµes de imÃƒÂ³veis do Brasil",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(imoveis_router)
app.include_router(usuarios_router)
app.include_router(login_router)
app.include_router(scraper_router)

@app.get("/")
def home():
    return {
        "status": "online",
        "app": "Arremata Patrimonio API",
    }
