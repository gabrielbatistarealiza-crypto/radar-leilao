-- GRAVA: igual ao marcar_0001_ENSAIO.sql, mas termina em COMMIT.
-- Correr só depois de o ensaio mostrar "17 tabelas: ok" e "versao: 0001".
-- Para desfazer: DROP TABLE alembic_version;
\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
  IF (SELECT count(*) FROM information_schema.tables
      WHERE table_schema = 'public' AND table_name IN (
        'anuncio_imagens', 'anuncios_imoveis', 'atividades_oportunidade', 'atualizacoes_caixa',
        'caixa_data_worker_state', 'caixa_pedidos_dia', 'corretores', 'criterios_alerta', 'imoveis',
        'imovel_foto_verificacoes', 'imovel_imagens', 'negociacoes', 'notificacoes', 'operacoes',
        'oportunidades', 'simulacoes_rentabilidade', 'usuarios')) <> 17 THEN
    RAISE EXCEPTION 'Faltam tabelas da migração 0001: nada foi gravado.';
  END IF;
END $$;

CREATE TABLE alembic_version (
  version_num VARCHAR(32) NOT NULL,
  CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
INSERT INTO alembic_version (version_num) VALUES ('0001');

SELECT 'versao: ' || version_num AS resultado FROM alembic_version;

COMMIT;
