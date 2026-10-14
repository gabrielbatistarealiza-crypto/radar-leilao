# Hospedar a API no Render

Este guia publica apenas a API. A interface web continua hospedada separadamente.

## 1. Criar o PostgreSQL

No Render, crie um banco PostgreSQL pago na mesma região do serviço web e copie a **Internal Database URL**. O endereço do banco e as credenciais devem ser guardados somente nas variáveis do Render.

## 2. Criar o serviço web

Crie um serviço **Web Service** ligado ao repositório e selecione **Docker**. Defina `backend` como Root Directory (contexto) e `Dockerfile` como Dockerfile Path. Configure estas variáveis no painel do Render:

- `DATABASE_URL`: Internal Database URL do banco Render.
- `SECRET_KEY`: segredo aleatório forte, único para este ambiente.
- `BROWSER_HEADLESS`: `true` (a imagem já usa esse padrão).

O comando de inicialização inicia Uvicorn com um worker e usa a porta `PORT` fornecida pelo Render. Configure o health check path como `/health`.

## 3. Manter um único serviço

Mantenha **uma instância** do serviço web e não aumente o número de workers. O lifespan atual inicia a atualização diária da Caixa às 03:00, a fila de fotos e o scheduler de notificações. O scheduler de notificações usa lock PostgreSQL; os outros dois jobs não usam lock distribuído. Várias instâncias repetiriam downloads e scraping. Se precisar escalar a API, será necessário antes mover esses jobs para um worker dedicado e adicionar eleição/locks para eles.

## 4. Limitações operacionais

As tabelas são criadas pela aplicação no startup (`create_all`), sem migrações versionadas. O filesystem do serviço web no Render é efêmero; os CSVs da Caixa serão obtidos de novo após reinícios. Não configure disco persistente sem avaliar o custo e a retenção desejada. O health check confirma que o processo HTTP responde; não verifica conectividade ou estado do banco.

Faça o primeiro deploy e confirme `/health` e `/docs`. Não há URL pública neste guia; ela só existe depois da criação do serviço no Render. Nunca coloque credenciais no repositório.
