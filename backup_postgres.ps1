# Backup do Postgres do Radar Leilao.
#
# Por que mudou: o "docker exec ... pg_dump > arquivo" do PowerShell recodifica
# a saida (UTF-16 + pagina de codigo do console) e estraga os acentos
# (por exemplo, "Leilao" virava lixo). Aqui o dump e gerado DENTRO do container, em formato
# binario, e copiado como arquivo, sem passar pelo pipeline de texto.
#
# Restaurar SEMPRE numa base separada primeiro (nunca direto na de producao):
#   1) criar uma base vazia:
#        docker exec aremmata-patrimonio-postgres createdb -U postgres arremata_restauro
#   2) copiar o backup para o container e restaurar nessa base:
#        docker cp .\backups\ARQUIVO.dump aremmata-patrimonio-postgres:/tmp/restaurar.dump
#        docker exec aremmata-patrimonio-postgres pg_restore -U postgres -d arremata_restauro /tmp/restaurar.dump
#        docker exec aremmata-patrimonio-postgres rm -f /tmp/restaurar.dump
#   3) conferir os dados antes de decidir qualquer coisa:
#        docker exec aremmata-patrimonio-postgres psql -U postgres -d arremata_restauro -c "SELECT count(*) FROM imoveis;"
#
# ATENCAO: "pg_restore --clean" apaga e recria os objetos da base indicada. Nunca o use
# em arremata_patrimonio sem antes fazer um backup novo desta mesma base.
#
# Os backups .sql antigos (ate 15/10/2026) foram gravados em UTF-16 pelo metodo
# anterior e nao abrem diretamente no psql; use os .dump (a partir de 21/10/2026).
$ErrorActionPreference = "Stop"

$Container = "aremmata-patrimonio-postgres"
$Database = "arremata_patrimonio"
$User = "postgres"
$BackupDir = Join-Path $PSScriptRoot "backups"
$Temporario = "/tmp/radar_backup.dump"

New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

$Data = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$Arquivo = Join-Path $BackupDir "arremata_patrimonio_$Data.dump"

Write-Host "Iniciando backup..."
Write-Host "Arquivo: $Arquivo"

docker exec $Container pg_dump -U $User -d $Database -Fc -f $Temporario
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao executar o pg_dump."
}

docker cp "${Container}:${Temporario}" $Arquivo
if ($LASTEXITCODE -ne 0) {
    Remove-Item $Arquivo -ErrorAction SilentlyContinue
    throw "Falha ao copiar o backup para fora do container."
}

docker exec $Container rm -f $Temporario | Out-Null

$Tamanho = (Get-Item $Arquivo).Length

if ($Tamanho -lt 100000) {
    throw "Backup criado, mas o arquivo parece pequeno demais: $Tamanho bytes."
}

Write-Host ""
Write-Host "BACKUP CONCLUIDO"
Write-Host "Arquivo: $Arquivo"
Write-Host "Tamanho: $Tamanho bytes"
