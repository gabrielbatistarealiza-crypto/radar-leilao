# Radar Leilão: estado atual, decisões em aberto e deploy

_Atualizado em 28/10/2026. Em produção: API no commit `0e84870` (PR #5) e site no
`8463dee` (PR #7), com as rotinas automáticas da Caixa desligadas (secção 7). O branch
local `feat/worker-datas-edital` (sem push) tem o worker novo da Caixa e as correções das
decisões 2, 3, 5 e 6 (secções 2, 3 e 9)._

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

No branch `feat/worker-datas-edital` (ainda não em produção):

- Todas as rotinas e endpoints que contactam a Caixa passam por
  `app/services/caixa_acesso.py`: lock do processo, lock consultivo PostgreSQL entre
  processos e espera guardada em `caixa_data_worker_state.bloqueado_ate`.
- **Só `requests`, nunca browser.** Um GET por URL, sem novas tentativas, sem seguir
  redirecionamentos, sem proxy do ambiente; o estado HTTP decide antes do corpo (3xx, 403
  e 429 param sem o ler). CAPTCHA/Radware só se detetam no conteúdo, depois de o ler.
- **Paragem manual.** Qualquer bloqueio ou resposta inesperada grava
  `bloqueado_ate = 9999-12-31`: todas as rotinas da Caixa (datas, lista, fotos, endpoints)
  ficam paradas até alguém rever. Antes de cada pedido essa marca é gravada (com commit) e
  só é retirada depois de gravar o resultado: um processo que morra a meio nunca leva a
  repetir o pedido. Para retomar, depois de rever: `bloqueado_ate = NULL` e `ativo = true`
  na linha 1 de `caixa_data_worker_state`.
- **Worker de datas** (`caixa_datas_worker.py` + `caixa_datas_edital.py`): em cada volta
  lê a página de um imóvel pendente e grava as datas e as **fotos da galeria** que ela
  mostra; se o edital dessa página ainda não foi lido, descarrega o PDF e preenche os
  imóveis à venda do Anexo II (números de 8 a 13 dígitos; lotes `ANULADO`/`Arrematado`
  não recebem datas). Só aplica o edital se tudo conferir.
- **Limite diário** de pedidos de datas (UTC), contado antes de cada pedido na tabela
  `caixa_pedidos_dia`, partilhado pelo worker e pelo endpoint manual do Admin.
- **Lista de imóveis** (`caixa_lista_segura.py`): 1 GET por UF a
  `listaweb/Lista_imoveis_{UF}.csv`, pausa entre UFs, o CSV anterior fica em
  `dados/_anterior/`. A remoção de imóveis ausentes só corre com as 27 UFs da mesma data
  de geração e nunca acima de max(50, 5 %) de uma vez.
- Os endpoints de fotos com browser (`/imoveis/manutencao/...`) respondem **410** salvo
  `RADAR_PERMITIR_SELENIUM_CAIXA=1`. O worker de fotos antigo só corre com
  `RADAR_ENABLE_CAIXA_PHOTO_WORKER=1`.
- Comandos só para a cópia local (`arremata_copia:5433`, confirmada na ligação):
  `scripts/datas_caixa_copia.py` e `scripts/lista_caixa_copia.py` (ensaio por omissão).
- Os scripts soltos em `backend/` que contactam a Caixa estão desativados por uma guarda.
  Só correm com `RADAR_PERMITIR_SCRIPT_LEGADO=1` definido nessa execução (nunca no `.env`).

O histórico dos pedidos reais feitos à Caixa e os seus resultados está na secção 9.

## 3. Decisões em aberto (confirmadas no código em 24/10/2026)

1. **Ocupação e FGTS sem fonte.** O CSV só traz Financiamento. Ficam `NULL` e a app não
   os mostra.
2. **Resolvida no branch (28/10/2026): transições de negociação.** Uma negociação
   `aceita`, `recusada` ou `cancelada` já não muda de estado (400). Para negociar de novo
   abre-se outra negociação.
3. **Resolvida no branch (28/10/2026): papel de quem altera a negociação.**
   `PATCH /negociacoes/{id}/status` só é aceite do corretor responsável ou do
   administrador (403 para o cliente), como o site já mostrava ("modo de consulta"). O
   cliente continua a poder abrir e ver negociações.
4. **Resolvida a 26/10/2026 (PR #5, `0e84870`): limite de tentativas de login.** O
   `POST /login` bloqueia um e-mail depois de 5 tentativas falhadas em 15 minutos (429 com
   `Retry-After`, a mesma resposta exista ou não a conta), procura a conta sem distinguir
   maiúsculas e já não tem o `print("LOGIN OK")`. Validado em produção com um e-mail
   inventado (cinco 401 e depois 429) e com o login normal pelo site, numa conta real,
   confirmado pelo utilizador. Limitações: o contador é em memória e volta a zero
   em cada deploy ou reinício da API; quem conheça um e-mail pode bloqueá-lo até 15
   minutos; o registo de contas ainda guarda o e-mail como foi escrito.
5. **Resolvida no branch (28/10/2026): alerta de prazo.** Só vale para imóveis dentro dos
   filtros do critério (estado, cidade, preço, desconto); o ROI não conta aqui. As
   notificações de prazo seguem a mesma regra.
6. **Resolvida no branch (28/10/2026): rótulo da modalidade.** A importação continua a
   trazer só "Leilão SFI - Edital Único", mas a comparação ignora acentos, maiúsculas,
   travessões e espaços, e grava sempre o rótulo canónico. Com os 27 CSV de 21/10 o
   número de imóveis lidos não mudou (4.054).
7. **O texto jurídico da consultoria** (`SYSTEM_BASE` em `consultoria_core.py`) ainda tem
   de ser revisto por um advogado de direito imobiliário.
8. **O limite de uso da consultoria** (20 perguntas a cada 10 min por pessoa) é em
   memória e conta à parte em cada processo.
9. **A consultoria envia o histórico** (últimas 10 mensagens) mas não os dados do imóvel.
   É uma decisão já tomada; o custo por pergunta é maior.
10. **Código sem uso:** `consultoria_edital.py` (local, não commitado; o `pypdf` de que
    precisa já está no `requirements.txt` do branch, porque o worker lê os editais) e os
    componentes `AnunciosCorretor.jsx` e `AnunciosPublicos.jsx` (commitados, mas não
    ligados à interface). No backend, o caminho antigo das datas com Selenium
    (`ScraperService.enriquecer_datas_caixa`) e o `CaixaDownloader` com Selenium ficaram
    sem uso na aplicação; só os testes os chamam.

## 4. Variáveis de ambiente

| Variável | Valor por omissão | Uso |
|---|---|---|
| `DATABASE_URL` | obrigatória | base de dados |
| `SECRET_KEY` | obrigatória | assinatura dos tokens |
| `RADAR_CORS_ORIGINS` | vazio | origens extra, separadas por vírgulas (o `localhost:5173` já é aceite); no Render: `https://radar-leilao-web.onrender.com` |
| `RADAR_DISABLE_BACKGROUND_JOBS` | não definida | `1` desliga a importação das 03:00, os workers de datas e de fotos e as notificações |
| `RADAR_ENABLE_CAIXA_DATE_WORKER` | `1` | worker de datas (e fotos da mesma página) |
| `RADAR_ENABLE_CAIXA_PHOTO_WORKER` | `0` no branch (`1` antes) | worker de fotos antigo, com browser |
| `RADAR_CAIXA_DATAS_INTERVALO_SEGUNDOS` | `600` (mínimo 60) no branch; `60` (mínimo 10) antes | pausa entre imóveis no worker de datas |
| `RADAR_CAIXA_DATAS_MAX_PEDIDOS_DIA` | `20` (0 a 1000), só no branch | pedidos de datas por dia UTC (worker + Admin) |
| `RADAR_CAIXA_LISTA_INTERVALO_SEGUNDOS` | `60` (mínimo 30), só no branch | pausa entre UFs na descarga das listas |
| `RADAR_PERMITIR_SELENIUM_CAIXA` | não definida, só no branch | `1` reativa os endpoints de fotos com browser (410 sem ela) |
| `RADAR_CAIXA_FOTOS_INTERVALO_SEGUNDOS` | `30` (mínimo 5) | pausa entre imóveis nas fotos (worker antigo) |
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

- Por omissão usa SQLite em memória. No branch `feat/worker-datas-edital` (28/10/2026):
  513 passam e 6 são ignorados (só correm em PostgreSQL); já não há `xfail`. Os testes de
  logging deixaram de precisar de um PostgreSQL local a correr. Nenhum teste contacta a
  Caixa (confirmado com a rede externa bloqueada durante a execução).
- Com PostgreSQL de teste: cria uma base vazia (por exemplo `radar_test`) e define
  `$env:TEST_DATABASE_URL = "postgresql://<utilizador>:<senha>@localhost:5432/radar_test"`
  só nessa sessão. Passam 386 e há 2 `xfail`, incluindo os testes do lock entre processos.
- Os testes da consultoria usam um fornecedor falso e não dependem do `.env`.

**Frontend** (a partir de `frontend/`): `npx vitest run` (37 testes no branch) e `npx vite build`.

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
partir de `main`, mas **cada um só quando o commit altera a sua pasta** (Root Directory):
a API em `backend/` e o site em `frontend`. Uma alteração só em `docs/`, por exemplo,
não faz deploy de nenhum. As Pull Request Previews estão desligadas em ambos.

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

**Estado observado em 26/10/2026**
- API "Live" no commit `40bbb95` (PR #2) desde as 00:59. Os logs do arranque mostram
  `INFO: app.main: Rotinas automáticas em segundo plano desativadas por configuração.` e
  não têm linhas `[BROWSER]` nem `[GALERIA]`. As três variáveis da Caixa continuam
  `1`/`0`/`0`.
- Site "Live" no commit `f17d4a0` (PR #3) desde as 02:45, construído com o vite 8.2.4 e
  sem vulnerabilidades no `npm audit`. Serve o mesmo `index-B3LJp9uO.js` de antes. O merge
  do PR #3 não fez deploy da API.
- API "Live" no commit `0e84870` (PR #5) desde as 03:29, com a mesma mensagem de rotinas
  desativadas no arranque e sem atividade da Caixa. Com um e-mail inventado, `POST /login`
  deu 401 cinco vezes e depois 429 com `Retry-After: 899`; o aviso no log não inclui o
  e-mail. O merge do PR #5 não fez deploy do site.
- O login normal pelo site, com uma conta real, funciona depois do PR #5 (confirmado pelo
  utilizador).

**Feito**
- Logging da app em INFO: PR #2, em produção desde 26/10/2026 (`40bbb95`).
- Aviso do `npm audit` (vite 8.2.4 e source-map-js 1.2.2): PR #3, em produção desde
  26/10/2026 (`f17d4a0`).
- Limite de tentativas de login (decisão 4): PR #5, em produção desde 26/10/2026
  (`0e84870`).

**Por investigar ou por fazer**
- A causa de "galeria não encontrada" (secção 8).
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
  desativadas por configuração.") **não apareciam nos logs**. Foi confirmado localmente:
  com a configuração de logging do uvicorn, o logger da app ficava em WARNING. Corrigido
  no PR #2, em produção desde 26/10/2026 (`40bbb95`): a mensagem aparece agora no
  arranque. Outras provas de que as rotinas estão desligadas:
  `GET /caixa/enriquecer-datas/status` (`"habilitado": false`) e a ausência de linhas
  `[BROWSER]`/`[GALERIA]` nos logs.
- Não acordar a instância (nem com `/health`) antes de confirmar que as variáveis estão
  ativas.

## 9. Recuperação das datas e worker novo (26 a 28/10/2026)

**Pedidos reais à Caixa (todos do IP local, NordVPN desligada, rota pela Wi-Fi, cada um
com autorização explícita).** Nenhum foi repetido.

| Momento (UTC) | Pedido | Resultado |
|---|---|---|
| 26/10 12:58 | página do imóvel 9217 | 200, datas no HTML (20/10 e 26/10) |
| 27/10 01:44 | lote: páginas 9222 e 9225, 62 s entre elas | 9222 OK; 9225 → 302 para `validate.perfdrive.com` (desafio Radware); lote parado |
| 28/10 00:36 | PDF do edital EL00490226CPARE | 200, PDF válido; datas únicas do edital e 613 números no Anexo II |
| 28/10 01:47 | worker novo, 1 pedido (página do 10182) | 200, datas gravadas na cópia, edital adiado pelo limite |
| 28/10 02:18 | lista do AC (`listaweb/`) | 200, CSV válido (geração 27/10); confirma o endereço direto |

**Factos**
- A página de cada imóvel indica o edital (`/editais/<código>.PDF`) e traz as fotos da
  galeria em HTML estático (`/fotos/...`).
- Um PDF de edital dá as datas de centenas de imóveis num só pedido. No EL00490226CPARE:
  557 lotes à venda (9 com números de 8 dígitos) e 35 `ANULADO`/`Arrematado`.
- Na cópia local (`arremata_copia`), 201 imóveis receberam datas a partir destes pedidos
  (199 do edital, 9222 e 10182 das páginas). O 12678, lote anulado, recebeu datas por
  engano e foi revertido.
- Para a produção foi preparado um SQL que copia essas 201 datas por URL, só onde as três
  datas estão a NULL (verificar, aplicar com ensaio por omissão, desfazer). Na produção,
  a verificação e o ensaio deram 201 / 201 / 201 / 0 / 0 e `UPDATE 201` com `ROLLBACK`.
  A aplicação com `COMMIT` estava, à data desta nota, nas mãos do utilizador.

**Hipóteses (não confirmadas)**
- O desafio de 27/10 terá vindo de pedidos seguidos às páginas `detalhe-imovel.asp`;
  PDFs e listas pareceram menos vigiados, mas há só 1 pedido de cada.
- O IP do Render pode continuar marcado desde 24/10 (secção 8).

**Para pôr o worker em produção (cada passo com autorização)**
1. Push do branch, PR e merge; o deploy da API cria a tabela `caixa_pedidos_dia`.
   Manter `RADAR_DISABLE_BACKGROUND_JOBS=1` neste deploy.
2. O plano Free adormece a API sem tráfego (secção 7): o ciclo em segundo plano e a
   importação das 03:00 só correm com a instância acordada. É preciso decidir como a
   manter acordada ou de onde correr as rotinas (por exemplo, um serviço externo que
   chame `/health` a cada 10 min, ou um plano pago, ou um *cron job*).
3. Ligar as rotinas com `RADAR_ENABLE_CAIXA_PHOTO_WORKER=0`, o limite diário baixo e
   acompanhar os logs do primeiro dia; subir o ritmo só depois de uma semana sem
   bloqueios.
