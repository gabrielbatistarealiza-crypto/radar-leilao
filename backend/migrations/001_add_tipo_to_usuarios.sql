BEGIN;

-- Adiciona a coluna sem remover ou recriar os usuários existentes.
ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS tipo VARCHAR(20);

-- Preenche usuários já existentes (e eventuais valores nulos) como clientes.
UPDATE usuarios
SET tipo = 'cliente'
WHERE tipo IS NULL;

-- Mantém o mesmo padrão para novos registros e impede valores nulos.
ALTER TABLE usuarios
    ALTER COLUMN tipo SET DEFAULT 'cliente',
    ALTER COLUMN tipo SET NOT NULL;

COMMIT;
