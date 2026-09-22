from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.database import get_db  # Ajuste o import do get_db conforme o seu projeto
from app.services.scraper_service import ScraperService

router = APIRouter()

@router.post("/caixa") # ou a rota correspondente ao seu endpoint
def executar_scraper_caixa(db: Session = Depends(get_db)):
    service = ScraperService(db)
    return service.executar_scraper_caixa()


@router.post("/caixa/atualizar")
def atualizar_lista_caixa(db: Session = Depends(get_db)):
    """Baixa os CSVs atuais da Caixa e atualiza os imÃƒÂ³veis no banco."""
    return ScraperService(db).atualizar_lista_caixa()
