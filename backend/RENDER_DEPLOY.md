# Hospedar a API no Render

Este guia publica apenas a API. A interface web continua hospedada separadamente.

## 1. Criar o PostgreSQL

No Render, crie um banco PostgreSQL pago na mesma região do serviço web e copie a **Internal Database URL**. O endereço do banco e as credenciais devem ser guardados somente nas variáveis do Render.

## 2. Criar o serviço web

Crie um serviço **Web Service** ligado ao repositório e selecione **Docker**. Defina `backend` como Root Directory (contexto) e `Dockerfile` como Dockerfile Path. Configure estas variáveis no painel do Render:

- `DATABASE_URL`: Internal Database URL do banco Render.
- `SECRET_KEY`: segredo aleatório forte, único para este ambiente.
- `BROWSER_HEADLESS`: `true` (a imagem já usa esse padrão).
- `RADAR_DISABLE_BACKGROUND_JOBS`: defina como `1` para desativar no lifespan as três rotinas em segundo plano: atualização Caixa das 03:00, processamento automático da fila de fotos e notificações. A criação das tabelas (`create_all`) continua ocorrendo no startup. Remova a variável ou use outro valor para reativar as rotinas. Isso exige reinício/redeploy do serviço; nenhuma configuração de produção é alterada por este repositório.

O comando de inicialização inicia Uvicorn com um worker e usa a porta `PORT` fornecida pelo Render. Configure o health check path como `/health`.

## 3. Manter um único serviço

Mantenha **uma instância** do serviço web e não aumente o número de workers. O lifespan atual inicia a atualização diária da Caixa às 03:00, a fila de fotos e o scheduler de notificações. O scheduler de notificações usa lock PostgreSQL; os outros dois jobs não usam lock distribuído. Várias instâncias repetiriam downloads e scraping. Se precisar escalar a API, será necessário antes mover esses jobs para um worker dedicado e adicionar eleição/locks para eles.

## 4. Limitações operacionais

As tabelas são criadas pela aplicação no startup (`create_all`), sem migrações versionadas. O filesystem do serviço web no Render é efêmero; os CSVs da Caixa serão obtidos de novo após reinícios. Não configure disco persistente sem avaliar o custo e a retenção desejada. O health check confirma que o processo HTTP responde; não verifica conectividade ou estado do banco.

Faça o primeiro deploy e confirme `/health` e `/docs`. Não há URL pública neste guia; ela só existe depois da criação do serviço no Render. Nunca coloque credenciais no repositório.

## Criar o primeiro administrador

O bootstrap é um comando de execução única e não cria uma rota pública. `DATABASE_URL` precisa ser definida explicitamente no ambiente do processo; o comando recusa seleção implícita pelo `.env`. Primeiro, ele exibe o dialeto, o host e o nome do banco, sem credenciais. Em seguida, pede confirmação do alvo exibido; digite `SIM` para continuar. Qualquer outra resposta, EOF ou interrupção cancela o comando antes de pedir credenciais, importar o engine do banco ou abrir conexão. PostgreSQL exige a opção `--allow-production` na linha de comando, além da confirmação interativa após conferir o alvo. SQLite também exige a confirmação interativa, mas não a opção. Outros dialetos são recusados.

No PowerShell, a partir de `backend`:

```powershell
$env:DATABASE_URL = "<URL do banco escolhido>"
python -m scripts.bootstrap_admin --allow-production
# Confira dialeto, host e banco exibidos; digite SIM apenas se forem o alvo pretendido.
```

Para testar em SQLite, defina também `DATABASE_URL` explicitamente com o caminho do banco local e execute `python -m scripts.bootstrap_admin` sem `--allow-production`; confira o alvo e digite `SIM` no prompt para continuar.

O comando pede nome e e-mail e lê a senha sem exibi-la (com confirmação). Também aceita `BOOTSTRAP_ADMIN_NAME`, `BOOTSTRAP_ADMIN_EMAIL` e `BOOTSTRAP_ADMIN_PASSWORD` no ambiente; evite fornecer a senha na linha de comando ou gravá-la em arquivos. O comando bloqueia tentativas concorrentes durante a verificação, só cria o usuário quando `usuarios` está vazia, define `admin=true` e `tipo=admin`, e aborta sem alterações se já houver qualquer usuário. Nunca configure essas credenciais como variáveis permanentes do serviço web.
