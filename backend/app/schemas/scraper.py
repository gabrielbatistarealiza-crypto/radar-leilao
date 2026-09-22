from pydantic import BaseModel

class ExecutarScraper(BaseModel):
    fontes: list[str]
