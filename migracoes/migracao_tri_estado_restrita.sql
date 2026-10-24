-- Radar Leilao: "nao informado" passa a ser NULL em ocupado e aceita_fgts.
--
-- Versao restrita da migracao_tri_estado.sql, para o Render (24/10/2026):
--   - So mexe em ocupado e aceita_fgts. Nenhum codigo grava estas colunas (nao ha
--     fonte), por isso todo o false que la esta e o antigo valor padrao, nao um
--     "Nao" real. Por isso pode ser repetida sem perder dados.
--   - NAO mexe em aceita_financiamento: esse valor vem da coluna Financiamento do
--     CSV da Caixa (4.026 Nao e 33 Sim a 24/10) e e real.
--
-- Por omissao corre em ENSAIO: mostra as contagens antes e depois e termina com
-- ROLLBACK (nada fica gravado). So grava com -v confirmar=1.
--
-- Precisa do psql (usa \if). Com o psql 18 instalado no Windows e a ligacao em
-- RADAR_RENDER_DB_URL (ver backup_render.ps1), na pasta do projeto:
--
--   1) backup:  .\backup_render.ps1
--   2) ensaio:  .\executar_sql_render.ps1 .\migracoes\migracao_tri_estado_restrita.sql
--   3) gravar (so depois de conferir o ensaio):
--               .\executar_sql_render.ps1 .\migracoes\migracao_tri_estado_restrita.sql -Confirmar
\set ON_ERROR_STOP on

BEGIN;

\echo '== antes'
SELECT count(*)                                              AS total,
       count(*) FILTER (WHERE ocupado = false)               AS ocupado_false,
       count(*) FILTER (WHERE ocupado = true)                AS ocupado_true,
       count(*) FILTER (WHERE aceita_fgts = false)           AS fgts_false,
       count(*) FILTER (WHERE aceita_fgts = true)            AS fgts_true,
       count(*) FILTER (WHERE aceita_financiamento = false)  AS financiamento_false,
       count(*) FILTER (WHERE aceita_financiamento = true)   AS financiamento_true
FROM imoveis;

-- No Render os defaults ja nao existem; isto so garante o mesmo numa base antiga.
ALTER TABLE imoveis ALTER COLUMN ocupado DROP DEFAULT;
ALTER TABLE imoveis ALTER COLUMN aceita_fgts DROP DEFAULT;

UPDATE imoveis SET ocupado = NULL WHERE ocupado = false;
UPDATE imoveis SET aceita_fgts = NULL WHERE aceita_fgts = false;

\echo '== depois (financiamento tem de ficar igual)'
SELECT count(*)                                              AS total,
       count(*) FILTER (WHERE ocupado = false)               AS ocupado_false,
       count(*) FILTER (WHERE aceita_fgts = false)           AS fgts_false,
       count(*) FILTER (WHERE aceita_financiamento = false)  AS financiamento_false,
       count(*) FILTER (WHERE aceita_financiamento = true)   AS financiamento_true
FROM imoveis;

\if :{?confirmar}
COMMIT;
\echo '== GRAVADO'
\else
ROLLBACK;
\echo '== ENSAIO: nada foi gravado. Para gravar, repetir com -v confirmar=1'
\endif
