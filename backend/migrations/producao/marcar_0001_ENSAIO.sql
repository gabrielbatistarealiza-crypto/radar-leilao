-- ENSAIO: marca a base como estando na migração 0001, sem alterar nenhuma tabela
-- existente. Termina em ROLLBACK: não grava nada.
\set ON_ERROR_STOP on
BEGIN;

-- 1. As 17 tabelas da migração 0001 têm de existir todas.
SELECT count(*) AS tabelas_encontradas,
       CASE WHEN count(*) = 17 THEN '17 tabelas: ok' ELSE 'FALTAM TABELAS: parar' END AS verificacao
FROM information_schema.tables
WHERE table_schema = 'public' AND table_name IN (
  'anuncio_imagens', 'anuncios_imoveis', 'atividades_oportunidade', 'atualizacoes_caixa',
  'caixa_data_worker_state', 'caixa_pedidos_dia', 'corretores', 'criterios_alerta', 'imoveis',
  'imovel_foto_verificacoes', 'imovel_imagens', 'negociacoes', 'notificacoes', 'operacoes',
  'oportunidades', 'simulacoes_rentabilidade', 'usuarios');

-- 2. Falha (e para) se a base já tiver sido marcada.
CREATE TABLE alembic_version (
  version_num VARCHAR(32) NOT NULL,
  CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
INSERT INTO alembic_version (version_num) VALUES ('0001');

SELECT 'versao: ' || version_num AS resultado FROM alembic_version;

ROLLBACK;
