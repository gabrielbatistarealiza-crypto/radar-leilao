BEGIN;

ALTER TABLE imoveis
    ADD COLUMN IF NOT EXISTS data_licitacao_aberta DATE;

COMMIT;
