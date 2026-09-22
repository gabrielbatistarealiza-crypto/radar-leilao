$ErrorActionPreference = "Stop"

$Container = "aremmata-patrimonio-postgres"
$Database = "arremata_patrimonio"
$User = "postgres"
$BackupDir = Join-Path $PSScriptRoot "backups"

New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

$Data = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$Arquivo = Join-Path $BackupDir "arremata_patrimonio_$Data.sql"

Write-Host "Iniciando backup..."
Write-Host "Arquivo: $Arquivo"

docker exec $Container pg_dump -U $User -d $Database > $Arquivo

if ($LASTEXITCODE -ne 0) {
    Remove-Item $Arquivo -ErrorAction SilentlyContinue
    throw "Falha ao executar o pg_dump."
}

$Tamanho = (Get-Item $Arquivo).Length

if ($Tamanho -lt 100000) {
    throw "Backup criado, mas o arquivo parece pequeno demais: $Tamanho bytes."
}

Write-Host ""
Write-Host "BACKUP CONCLUIDO"
Write-Host "Arquivo: $Arquivo"
Write-Host "Tamanho: $Tamanho bytes"
