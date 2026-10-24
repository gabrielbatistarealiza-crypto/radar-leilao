# Backup da base de PRODUCAO do Radar Leilao (Render, PostgreSQL 18).
#
# O backup_postgres.ps1 copia so a base local de desenvolvimento (contentor
# aremmata-patrimonio-postgres). Este script copia o Render.
#
# Como funciona: usa o pg_dump 18 instalado no Windows
# (C:\Program Files\PostgreSQL\18\bin), em formato binario (-Fc), valida o
# indice do dump com pg_restore --list e grava tudo em .\backups. O pg_dump so
# le; nao altera nada no Render.
#
# A ligacao vem da variavel RADAR_RENDER_DB_URL, definida so nesta sessao do
# terminal (nunca no .env nem no script). O script separa-a nas variaveis
# PGHOST/PGPORT/PGUSER/PGPASSWORD/PGDATABASE so durante o backup, por isso a
# senha nao aparece na linha de comando do pg_dump; no fim apaga-as.
#
# Uso (na pasta do projeto):
#   $s = Read-Host "URL externa do Render" -AsSecureString
#   $env:RADAR_RENDER_DB_URL = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))
#   .\backup_render.ps1
#   Remove-Item Env:RADAR_RENDER_DB_URL
#
# Restaurar: NUNCA no Render diretamente. Restaura primeiro numa base separada
# (ver o cabecalho do backup_postgres.ps1) e confere os dados.
$ErrorActionPreference = "Stop"

if (-not $env:RADAR_RENDER_DB_URL) {
    throw "Defina RADAR_RENDER_DB_URL nesta sessao do terminal (ver o cabecalho)."
}

$Bin = "C:\Program Files\PostgreSQL\18\bin"
$PgDump = Join-Path $Bin "pg_dump.exe"
$PgRestore = Join-Path $Bin "pg_restore.exe"
foreach ($Exe in $PgDump, $PgRestore) {
    if (-not (Test-Path $Exe)) { throw "Nao encontrei $Exe (precisa do PostgreSQL 18)." }
}
$Versao = & $PgDump --version
if ($Versao -notmatch "PostgreSQL\) 18\.") {
    throw "O pg_dump tem de ser da versao 18 (encontrado: $Versao)."
}

$BackupDir = Join-Path $PSScriptRoot "backups"
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
$Data = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$Arquivo = Join-Path $BackupDir "render_$Data.dump"
$Indice = Join-Path $BackupDir "render_$Data.toc.txt"

# Separa o endereco postgresql://utilizador:senha@servidor:porta/base.
$Uri = [Uri]$env:RADAR_RENDER_DB_URL
if ($Uri.Scheme -notin "postgres", "postgresql") { throw "RADAR_RENDER_DB_URL nao e um endereco postgresql://." }
$Utilizador, $Senha = $Uri.UserInfo.Split(":", 2)
$Variaveis = @{
    PGHOST     = $Uri.Host
    PGPORT     = $(if ($Uri.Port -gt 0) { "$($Uri.Port)" } else { "5432" })
    PGUSER     = [Uri]::UnescapeDataString($Utilizador)
    PGPASSWORD = [Uri]::UnescapeDataString($Senha)
    PGDATABASE = [Uri]::UnescapeDataString($Uri.AbsolutePath.TrimStart("/"))
    PGSSLMODE  = "require"
}

Write-Host "Usando $Versao"
Write-Host "Iniciando backup do Render..."
try {
    foreach ($Nome in $Variaveis.Keys) { Set-Item "Env:$Nome" $Variaveis[$Nome] }

    & $PgDump -Fc -f $Arquivo
    if ($LASTEXITCODE -ne 0) {
        Remove-Item $Arquivo -ErrorAction SilentlyContinue
        throw "Falha no pg_dump."
    }
}
finally {
    foreach ($Nome in $Variaveis.Keys) { Remove-Item "Env:$Nome" -ErrorAction SilentlyContinue }
}

# A validacao le so o ficheiro local; nao liga ao Render.
& $PgRestore --list $Arquivo | Out-File $Indice -Encoding utf8
if ($LASTEXITCODE -ne 0) { throw "O pg_restore nao conseguiu ler o indice do dump." }

$Tamanho = (Get-Item $Arquivo).Length
if ($Tamanho -lt 100000) {
    throw "Dump criado, mas parece pequeno demais: $Tamanho bytes."
}
$Toc = Get-Content $Indice
foreach ($Tabela in "imoveis", "usuarios", "imovel_imagens") {
    if (-not ($Toc -match "TABLE DATA public $Tabela ")) {
        throw "O dump nao contem os dados da tabela $Tabela."
    }
}

Write-Host ""
Write-Host "BACKUP DO RENDER CONCLUIDO"
Write-Host "Arquivo: $Arquivo"
Write-Host "Tamanho: $Tamanho bytes"
Write-Host "Entradas no indice: $($Toc.Count)"
$Toc | Select-Object -First 14 | ForEach-Object { Write-Host "  $_" }
