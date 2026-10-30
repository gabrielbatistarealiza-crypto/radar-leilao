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
| 1 | Fundações: Alembic com a migração inicial, teste que impede modelos sem migração, CI no GitHub (pytest em PostgreSQL + vitest + build) | no `main` (PR #9) |
| 2 | Migrações a correr no arranque (`python -m app.migrar` antes do uvicorn) e fim do `create_all` | no `main` (PR #12); produção na 0003 desde 30/10 |
| 3 | Imóveis: nunca apagar (marcar "saiu da lista"), histórico (entrou, saiu, voltou, preço), importação em lotes e só das UFs descarregadas. Falta: número da Caixa único | no `main` (PRs #12 a #16) |
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

## Fases 2 e 3: ordem obrigatória para publicar

A fase 3 acrescenta colunas a `imoveis`. O `create_all` não acrescenta colunas a
tabelas existentes, por isso as migrações têm de correr no arranque (fase 2) e
a produção tem de estar marcada em 0001 **antes** do deploy:

1. Marcar a produção em 0001 (passo único acima: ensaio, depois COMMIT).
2. Merge do PR das fases 2 e 3. No arranque, `app.migrar` aplica a 0002 (a
   tabela `pedidos_corretor` já existe: só avança a versão) e a 0003 (3 colunas
   e a tabela `imovel_eventos`; só acrescenta).
3. Se o passo 1 tiver sido esquecido, o arranque recusa (`BaseSemVersao`), o
   deploy falha e o Render mantém a versão anterior no ar. Nada é alterado.
4. Só depois deste deploy correr a rotina local (`scripts/rotina_caixa.py`) a
   partir deste código: ela já usa as colunas novas.

Validado numa cópia temporária da cópia local da produção (estado de 21/10) com
os 27 CSV de 28/10: base sem versão recusada sem alterações; base marcada sobe a
0003 sem diferenças (`alembic check`); importação com 1149 entradas, **587 fora
da lista (os mesmos 587 ausentes da produção a 29/10), nenhum apagado**; segunda
importação sem efeitos.

Limite de segurança: numa importação completa não se tiram da lista mais de
max(50, 20%) dos imóveis Caixa na lista; acima disso nada é marcado e o
resultado mostra `remocao_recusada`.

## Ramos abertos e ordem de junção

- Ordem: primeiro `refactor/fase1-fundacoes`, depois `feat/registo-utilizadores`.
- `feat/registo-utilizadores` já inclui a fase 1 e a migração `0002`
  (`pedidos_corretor`). Enquanto o arranque usar `create_all`, a produção pode
  já ter a tabela quando a `0002` correr: a migração deteta isso e só avança a
  versão (testado: base vazia, produção marcada em 0001, e produção com a
  tabela já criada).
- `feat/fase3-imoveis` contém `feat/rotina-caixa-local` (rotina local, importação
  em lotes e só das UFs descarregadas) mais o `main` e as fases 2 e 3: um único
  PR leva tudo.
