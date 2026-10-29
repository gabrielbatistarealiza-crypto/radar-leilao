FROM mcr.microsoft.com/playwright/python:v1.62.0-noble

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BROWSER_HEADLESS=true

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic.ini ./alembic.ini
COPY migrations ./migrations

EXPOSE 8000

# Primeiro as migrações; se falharem, a API não arranca (o Render mantém a versão anterior).
CMD ["sh", "-c", "python -m app.migrar && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
