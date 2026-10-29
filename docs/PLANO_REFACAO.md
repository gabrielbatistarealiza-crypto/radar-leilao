# Plano de refação por fases

Decidido a 29/10/2026: refazer o projeto **por fases**, sem parar o site e sem
perder dados, cada fase num PR com testes. Alojamento: **continua no Render**
por agora (sem custos novos); o código fica preparado para mudar mais tarde.

Regras que se mantêm em todas as fases: nada de contactos com a Caixa, alterações
à produção, push, merge ou deploy sem autorização explícita; SQL na produção
sempre primeiro em ensaio (ROLLBACK) e corrido pelo dono do projeto.

## Fases

| Fase | O quê | Estado |
|---|---|---|
| 1 | Fundações: Alembic com a migração inicial, teste que impede modelos sem migração, CI no GitHub (pytest em PostgreSQL + vitest + build) | este ramo |
| 2 | Migrações a correr no arranque (`alembic upgrade head` antes do uvicorn) e fim do `create_all` | depois da marcação na produção |
| 3 | Imóveis: número da Caixa único, nunca apagar (marcar "saiu da lista"), histórico de preços e datas, importação com upsert | |
| 4 | Utilizadores: um só campo de papel (hoje `admin` e `tipo`), token pelo id e não pelo e-mail, recuperação de senha por e-mail | precisa de escolher serviço de e-mail |
| 5 | Frontend: rotas a sério, páginas separadas (o `App.jsx` tem mais de 3000 linhas), um só cliente da API | |
| 6 | Recolha da Caixa: guardar sempre os ficheiros originais e reprocessar offline; uma só porta para todas as rotinas | |
| 7 | Alojamento: API e base na mesma região (São Paulo) | quando decidires |

## Fase 1: o que muda e o que não muda

- **Não muda nada na produção.** O arranque continua a usar `create_all`; o
  Alembic só fica disponível.
- `backend/migrations/versions/0001_esquema_inicial.py` descreve as 17 tabelas
  atuais. Foi comparada com a cópia local da produção: 156 colunas, 58 índices e
  129 restrições iguais; o downgrade também foi testado.
- `app/models/__init__.py` passa a importar **todos** os modelos (faltavam
  `notificacoes` e `simulacoes_rentabilidade`, que só existiam porque os
  routers os importavam antes do `create_all`).
- `tests/test_migracoes.py` falha se um modelo mudar sem migração (testado com
  uma coluna acrescentada de propósito).
- `.github/workflows/testes.yml` corre em cada PR, sem segredos: PostgreSQL
  descartável, pytest, `alembic upgrade head` + `alembic check`, lint, vitest e
  build do frontend.

## Passo único na produção (antes da fase 2)

A produção já tem as tabelas, por isso **não** se corre a migração 0001: marca-se
só a versão. No mesmo terminal onde já usaste o psql com `RADAR_RENDER_DB_URL`:

1. Ensaio (não grava nada, termina em ROLLBACK):
   `psql "$env:RADAR_RENDER_DB_URL" -f backend/migrations/producao/marcar_0001_ENSAIO.sql`
2. Se o ensaio mostrar `17 tabelas` e `versao: 0001`, gravar:
   `psql "$env:RADAR_RENDER_DB_URL" -f backend/migrations/producao/marcar_0001_COMMIT.sql`

Isto só cria a pequena tabela `alembic_version` com uma linha. Para desfazer:
`DROP TABLE alembic_version;`.

## Ramos abertos e ordem de junção

- `feat/registo-utilizadores` acrescenta a tabela `pedidos_corretor`. Se entrar
  no `main` antes deste ramo, este ramo precisa de uma migração `0002` para essa
  tabela (o teste de migrações avisa). Se entrar depois, é esse PR que leva a `0002`.
- `feat/rotina-caixa-local` (só local) não mexe em modelos.
