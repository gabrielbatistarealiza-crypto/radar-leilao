# Radar Leilão: estado atual, decisões em aberto e deploy

_Atualizado em 24/10/2026. Em produção: `main` no commit `8126830` (merge do PR #1),
com as rotinas automáticas da Caixa desligadas (secção 7)._

Este documento substitui o `LEIA-ME-PRIMEIRO.md` e o `INTEGRACAO.md`, que eram notas de
entrega de um pacote antigo. **Não sigas as instruções de "copiar por cima" desses
ficheiros**: substituiriam o código atual por versões antigas.

## 1. Ordem para publicar

A produção é a base PostgreSQL 18 do **Render**. O contentor local
(`aremmata-patrimonio-postgres`, PostgreSQL 16) é só de desenvolvimento.

1. Faz um backup do Render: `.\backup_render.ps1`. Usa o `pg_dump` 18 instalado no
   Windows (`C:\Program Files\PostgreSQL\18\bin`) e valida o dump com
   `pg_restore --list`. A ligação vem de `RADAR_RENDER_DB_URL`, definida só nessa
   sessão do terminal (instruções no cabeçalho); a senha não aparece na linha de
   comando. O `backup_postgres.ps1` e a tarefa agendada das 02:00 copiam **só a base
   local**.
2. Esquema: no Render já existem `usuarios.tipo`, `imoveis.data_licitacao_aberta` e
   `caixa_data_worker_state` (confirmado em 24/10/2026, só leitura). As migrações de
   `backend/migrations/` (`001`, `002`) só são precisas numa base que ainda não as tenha;
   podem ser repetidas.
3. Executa `migracoes/migracao_tri_estado_restrita.sql`: converte `false` em `NULL` em
   `ocupado` e `aceita_fgts` (2.284 imóveis cada em 24/10/2026). Não mexe em
   `aceita_financiamento`, que vem do CSV e é real. Corre primeiro em ensaio (termina com
   `ROLLBACK`) e só grava com `.\executar_sql_render.ps1 <ficheiro> -Confirmar`;
   instruções no cabeçalho. A
   `migracao_tri_estado.sql` original fica só para bases antigas e corre **uma única vez**.
   **Estado: aplicada no Render em 24/10/2026**, depois do backup
   `render_2026-10-24_05-16-30.dump` e de um ensaio. Saída: `UPDATE 2284` em `ocupado`
   e em `aceita_fgts`, financiamento sem alteração (4.026 Não, 33 Sim), `COMMIT`. Não é
   preciso voltar a corrê-la no Render; repeti-la não perde dados.
4. Configura as variáveis (secção 4) e publica o código. No Render, grava as variáveis
   com **"Save, rebuild, and deploy"**: o "Restart service" volta a usar as variáveis do
   último deploy e **não aplica** as que foram gravadas depois (secção 8).
5. Faz a primeira importação: às 03:00 ou com `POST /caixa/atualizar`. Os CSVs da Caixa não estão
   no Git; são descarregados nessa altura. Ambas contactam a Caixa: **só depois da
   validação da secção 2**.

Notas:
- O `create_all` cria tabelas novas (por exemplo `caixa_data_worker_state`), mas **não
  acrescenta colunas** a tabelas que já existem. Por isso as migrações são necessárias.
- Mantém uma só instância (o `Dockerfile` já usa `--workers 1`). Mesmo com mais
  processos, o acesso à Caixa fica protegido pelo lock consultivo do PostgreSQL.

## 2. Acesso à Caixa (porteiro)

- Todas as rotinas e endpoints que contactam a Caixa passam por
  `app/services/caixa_acesso.py`: lock do processo, lock consultivo PostgreSQL entre
  processos e espera de bloqueio guardada na tabela `caixa_data_worker_state`.
- Ao primeiro CAPTCHA, a espera é gravada (12 h, 24 h, 48 h, até 72 h) e nada mais é
  consultado até ela expirar. Os endpoints respondem 409 (outra consulta em curso) ou
  429 (em espera); sem login respondem 401/403.
- O download das listas pára ao primeiro CAPTCHA e repõe o CSV anterior de cada UF.
- Estado do worker de datas: `GET /caixa/enriquecer-datas/status` (admin).
- Os scripts soltos em `backend/` que contactam a Caixa estão desativados por uma guarda.
  Só correm com `RADAR_PERMITIR_SCRIPT_LEGADO=1` definido nessa execução (nunca no `.env`).

Próximos passos (por fazer):
1. Repouso sem pedidos à Caixa a partir do IP local e do IP do Render. O do Render pode
   estar marcado desde 24/10/2026, 06:00 (Lisboa): o worker de fotos antigo abriu 46
   páginas da Caixa nesse dia (secção 8).
2. Sonda única de leitura: uma página de detalhe e a página de download, guardando o
   HTML desta para validar a deteção de CAPTCHA contra a página real.
3. Teste de tolerância: 1 pedido de 15 em 15 min, no máximo 4, parando ao primeiro CAPTCHA.
4. Primeira execução numa cópia da base, antes de atualizar os cerca de 3.700 imóveis sem datas.

## 3. Decisões em aberto (confirmadas no código em 24/10/2026)

1. **Ocupação e FGTS sem fonte.** O CSV só traz Financiamento. Ficam `NULL` e a app não
   os mostra.
2. **Negociação sem regras de transição.** É possível recusar ou reabrir uma negociação
   aceite. Teste `xfail`: `test_negociacao_aceita_nao_deveria_voltar_para_recusada`.
3. **O cliente pode aceitar a própria negociação.** `PATCH /negociacoes/{id}/status` só
   verifica o acesso à oportunidade, não o papel de quem altera.
4. **Login sem limite de tentativas** e com `print("LOGIN OK")` em `routers/login.py`.
5. **O alerta de prazo dispara fora dos filtros do critério** (estado, desconto, etc.).
   Teste `xfail`: `test_prazo_proximo_nao_deveria_alertar_imovel_fora_dos_filtros`.
6. **A importação só traz "Leilão SFI - Edital Único"**, comparando o texto exato. Se a
   Caixa mudar o rótulo, passa a trazer 0 imóveis (a limpeza não apaga nada nesse caso).
7. **O texto jurídico da consultoria** (`SYSTEM_BASE` em `consultoria_core.py`) ainda tem
   de ser revisto por um advogado de direito imobiliário.
8. **O limite de uso da consultoria** (20 perguntas a cada 10 min por pessoa) é em
   memória e conta à parte em cada processo.
9. **A consultoria envia o histórico** (últimas 10 mensagens) mas não os dados do imóvel.
   É uma decisão já tomada; o custo por pergunta é maior.
10. **Código sem uso:** `consultoria_edital.py` (precisa de `pypdf`; nenhum dos dois está
    commitado) e os componentes `AnunciosCorretor.jsx` e `AnunciosPublicos.jsx`
    (commitados, mas não ligados à interface).

## 4. Variáveis de ambiente

| Variável | Valor por omissão | Uso |
|---|---|---|
| `DATABASE_URL` | obrigatória | base de dados |
| `SECRET_KEY` | obrigatória | assinatura dos tokens |
| `RADAR_CORS_ORIGINS` | vazio | origens extra, separadas por vírgulas (o `localhost:5173` já é aceite); no Render: `https://radar-leilao-web.onrender.com` |
| `RADAR_DISABLE_BACKGROUND_JOBS` | não definida | `1` desliga a importação das 03:00, os workers de datas e de fotos e as notificações |
| `RADAR_ENABLE_CAIXA_DATE_WORKER` | `1` | worker de datas |
| `RADAR_ENABLE_CAIXA_PHOTO_WORKER` | `1` | worker de fotos |
| `RADAR_CAIXA_DATAS_INTERVALO_SEGUNDOS` | `60` (mínimo 10) | pausa entre imóveis no worker de datas |
| `RADAR_CAIXA_FOTOS_INTERVALO_SEGUNDOS` | `30` (mínimo 5) | pausa entre imóveis nas fotos |
| `BROWSER_HEADLESS` | `false` no Playwright e no downloader; `true` no scraper de datas | o `Dockerfile` define `true` |
| `CONSULTORIA_PROVEDOR` | `anthropic` | `anthropic` ou `ollama` |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` | obrigatória / `claude-sonnet-5-5` | consultoria |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | se o provedor for `ollama` |
| `CONSULTORIA_MODO_SIMULADO` | não definida | `1` responde sem chamar o modelo |
| `VITE_API_URL` (frontend) | `http://127.0.0.1:8000` | endereço da API, fixado no build; no Render: `https://radar-leilao-1zn7.onrender.com` |
| `TEST_DATABASE_URL` (testes) | SQLite em memória | PostgreSQL de teste; o nome da base tem de conter "test" (as tabelas são apagadas) |
| `RADAR_PERMITIR_SCRIPT_LEGADO` | não definida | `1` só para correr um script solto de forma consciente |

## 5. Testes

**Backend** (a partir de `backend/`):

```powershell
$env:RADAR_DISABLE_BACKGROUND_JOBS = "1"
.\.venv\Scripts\python.exe -m pytest -q
```

- Por omissão usa SQLite em memória: 380 passam, 6 são ignorados (só correm em
  PostgreSQL) e 2 são `xfail` (decisões 2 e 5).
- Com PostgreSQL de teste: cria uma base vazia (por exemplo `radar_test`) e define
  `$env:TEST_DATABASE_URL = "postgresql://<utilizador>:<senha>@localhost:5432/radar_test"`
  só nessa sessão. Passam 386 e há 2 `xfail`, incluindo os testes do lock entre processos.
- Os testes da consultoria usam um fornecedor falso e não dependem do `.env`.

**Frontend** (a partir de `frontend/`): `npx vitest run` (31 testes) e `npx vite build`.

**App móvel** (a partir de `app_flutter/`):

```powershell
flutter pub get --enforce-lockfile
flutter analyze
flutter test test
```

São 4 testes unitários. O teste de integração precisa do emulador: ver `backend/MOBILE_TESTING.md`.

## 6. O que não está no Git (de propósito)

- As listas CSV da Caixa (`backend/app/scrapers/dados/*.csv`): geradas pelo download diário.
- Os dumps da base (`backups/` e `*.sql` fora das pastas de migrações).
- O `.env` e as cópias de segurança locais (`*.bak`, `app_backup_encoding*/`).

## 7. Produção no Render (24/10/2026)

Projeto "My project", ambiente Production. Os dois serviços fazem deploy automático a
cada commit em `main`; as Pull Request Previews estão desligadas em ambos.

| Serviço | Tipo | Endereço |
|---|---|---|
| `radar-leilao` | Web Service (Docker, plano Free) | `https://radar-leilao-1zn7.onrender.com` |
| `radar-leilao-web` | Static Site | `https://radar-leilao-web.onrender.com` |
| `radar-leilao-db` | PostgreSQL 18 | só acessível pelas variáveis do Render |

- **API:** variáveis definidas: `DATABASE_URL`, `SECRET_KEY`, `ANTHROPIC_API_KEY`,
  `BROWSER_HEADLESS`, `RADAR_CORS_ORIGINS` e as três da Caixa:
  `RADAR_DISABLE_BACKGROUND_JOBS=1`, `RADAR_ENABLE_CAIXA_DATE_WORKER=0`,
  `RADAR_ENABLE_CAIXA_PHOTO_WORKER=0`. Com isto ficam desligadas a importação das 03:00,
  os workers de datas e de fotos e as notificações. A página de Admin mostra "Worker
  automático desativado". Os botões de Admin que contactam a Caixa continuam
  disponíveis; não os usar antes da validação da secção 2.
- **Site:** Root Directory `frontend`, build `npm ci && npm run build`, publicação `dist`,
  variáveis `VITE_API_URL=https://radar-leilao-1zn7.onrender.com` e `NODE_VERSION=24`, e
  a regra `/*` → `/index.html` (Rewrite) para que `/admin` abra diretamente.
- O plano Free adormece a API sem tráfego; o primeiro pedido pode demorar cerca de 50 s.
  Ao acordar, o processo arranca de novo e lê as variáveis do último deploy.
- **Ao alterar variáveis da API**, o formulário de edição mostra os valores secretos
  vazios até se carregar em "Show secret". Antes de gravar, confirmar que nenhum valor
  ficou vazio.

**Estado observado em 24/10/2026**
- A API está "Live" no commit `8126830`. `GET /health` responde `ok`, e
  `GET /caixa/enriquecer-datas/status` (admin) devolve `"habilitado": false`.
- O site está publicado. O login, a listagem, os detalhes de um imóvel e a página
  `/admin` funcionam a partir dele.
- O CORS aceita o site e recusa outras origens.
- Os logs da API não mostram atividade da Caixa desde o deploy das 06:00.

**Por investigar ou por fazer**
- A causa de "galeria não encontrada" (secção 8).
- A configuração do logging da app, para as mensagens INFO aparecerem.
- O aviso do `npm audit` no build do site.
- A validação da Caixa e a recuperação das datas (secção 2).

## 8. Registo de 24/10/2026: worker de fotos antigo no Render

**Factos confirmados**
- As variáveis da Caixa foram gravadas no Render e o serviço foi reiniciado com "Restart
  service" (05:55, Lisboa). O valor de `RADAR_DISABLE_BACKGROUND_JOBS` estava exatamente
  `"1"` e o código em produção (`e8381e8`) testava-o corretamente, mas o processo
  arrancou sem as variáveis novas.
- Um pedido `GET /health` acordou a instância às 05:57. O worker de fotos antigo correu
  de 04:57:36 a 05:00:26 UTC, um imóvel a cada ~4 s, e registou "#galeria-imagens não
  encontrada" em todos.
- Parou com o deploy manual do mesmo commit (06:00), que aplicou as variáveis. Desde
  então não houve atividade da Caixa nos logs.
- Impacto: 46 linhas de `imovel_foto_verificacoes` (imóveis 12132 a 12177) passaram de
  `PENDENTE` para `SEM_FOTOS`. As imagens (1.908) e os `COM_FOTOS` não mudaram. O código
  antigo não deteta bloqueios, por isso nada ficou gravado em `caixa_data_worker_state`.
- Correção: os 46 registos foram repostos com o `resultado` e o `verificado_em` exatos
  do backup `render_2026-10-24_05-16-30.dump`. O script tinha duas guardas (exatamente 46
  linhas alteradas e totais finais conferidos antes do `COMMIT`). Antes de gravar houve
  um ensaio com `ROLLBACK`. Resultado: `UPDATE 46`, `COMMIT`.
- Estado final: 1.889 `COM_FOTOS`, 1.966 `PENDENTE`, 204 `SEM_FOTOS`, 0 registos com
  `verificado_em` posterior ao backup (iguais ao backup).
- O script de correção e as consultas de auditoria não estão no Git: foram usados uma
  vez, a partir de uma pasta temporária.

**Hipótese (não confirmada)**
- A galeria não foi encontrada porque a Caixa devolveu uma página de bloqueio (CAPTCHA)
  ao IP do Render. Também é possível que essas páginas não tivessem galeria. Não foi
  guardado nenhum HTML que permita distinguir os dois casos.

**Lições**
- Variáveis novas no Render só ficam ativas com "Save, rebuild, and deploy" ou com um
  deploy manual; o "Restart" não chega. Confirmar sempre um evento de deploy posterior à
  gravação.
- As mensagens `logger.info` da app (por exemplo "Rotinas automáticas em segundo plano
  desativadas por configuração.") **não aparecem nos logs**. Foi confirmado localmente:
  com a configuração de logging do uvicorn, o logger da app fica em WARNING. Por fazer:
  configurar o logging da app para mostrar INFO. Até lá, a prova de que as rotinas estão
  desligadas é `GET /caixa/enriquecer-datas/status` (`"habilitado": false`) e a ausência
  de linhas `[BROWSER]`/`[GALERIA]` nos logs.
- Não acordar a instância (nem com `/health`) antes de confirmar que as variáveis estão
  ativas.
