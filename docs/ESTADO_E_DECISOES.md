# Radar Leilão: estado atual, decisões em aberto e deploy

_Atualizado em 24/10/2026, no branch `fix/worker-datas-caixa`._

Este documento substitui o `LEIA-ME-PRIMEIRO.md` e o `INTEGRACAO.md`, que eram notas de
entrega de um pacote antigo. **Não sigas as instruções de "copiar por cima" desses
ficheiros**: substituiriam o código atual por versões antigas.

## 1. Ordem para publicar

1. Faz um backup da base de produção: `.\backup_postgres.ps1` (gera um `.dump` dentro do contentor).
2. Aplica as migrações de esquema em `backend/migrations/` (podem ser repetidas):
   - `001_add_tipo_to_usuarios.sql`
   - `002_add_data_licitacao_aberta_to_imoveis.sql`
3. Executa `migracoes/migracao_tri_estado.sql` **uma única vez**, antes do código novo.
   Converte `false` em `NULL` em `ocupado`, `aceita_fgts` e `aceita_financiamento`.
   Uma segunda execução apagaria os "Não" reais de financiamento até à importação
   seguinte. As instruções estão no cabeçalho do ficheiro.
4. Configura as variáveis (secção 4) e publica o código.
5. Faz a primeira importação: às 03:00 ou com `POST /caixa/atualizar`. Os CSVs da Caixa não estão
   no Git; são descarregados nessa altura.

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
1. Repouso sem pedidos à Caixa a partir deste IP.
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
| `RADAR_CORS_ORIGINS` | vazio | origens extra, separadas por vírgulas |
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
| `VITE_API_URL` (frontend) | `http://127.0.0.1:8000` | endereço da API |
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
