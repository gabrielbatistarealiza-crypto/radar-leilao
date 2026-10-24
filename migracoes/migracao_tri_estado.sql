-- Radar Leilao: "nao informado" passa a ser diferente de "nao".
--
-- Ate hoje ocupado, aceita_fgts e aceita_financiamento valiam false em todos os
-- imoveis, porque false era o valor padrao e o scraper nunca os preenchia. O app
-- mostraria "Desocupado" e "Nao aceita FGTS" para tudo. Com NULL = desconhecido,
-- o frontend simplesmente esconde o campo ate existir um dado real.
--
-- ORDEM:
--   1) faca um backup (backup_postgres.ps1)
--   2) rode este arquivo UMA vez, ANTES de publicar o codigo novo:
--        docker cp .\migracao_tri_estado.sql aremmata-patrimonio-postgres:/tmp/migracao.sql
--        docker exec aremmata-patrimonio-postgres psql -U postgres -d arremata_patrimonio -f /tmp/migracao.sql
--   3) publique o codigo novo
--   4) execute POST /caixa/atualizar (ou espere as 03:00): a coluna Financiamento
--      do CSV da Caixa passa a preencher aceita_financiamento com Sim/Nao reais.
BEGIN;

ALTER TABLE imoveis ALTER COLUMN ocupado DROP DEFAULT;
ALTER TABLE imoveis ALTER COLUMN aceita_fgts DROP DEFAULT;
ALTER TABLE imoveis ALTER COLUMN aceita_financiamento DROP DEFAULT;

UPDATE imoveis SET ocupado = NULL WHERE ocupado = false;
UPDATE imoveis SET aceita_fgts = NULL WHERE aceita_fgts = false;
UPDATE imoveis SET aceita_financiamento = NULL WHERE aceita_financiamento = false;

COMMIT;
