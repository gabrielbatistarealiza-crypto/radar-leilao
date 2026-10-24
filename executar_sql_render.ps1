# Corre um ficheiro SQL na base de PRODUCAO (Render) com o psql 18 instalado no
# Windows (C:\Program Files\PostgreSQL\18\bin).
#
# A ligacao vem de RADAR_RENDER_DB_URL, definida so nesta sessao do terminal
# (ver o cabecalho do backup_render.ps1). Tal como no backup, o endereco e
# separado nas variaveis PGHOST/PGPORT/PGUSER/PGPASSWORD/PGDATABASE so durante a
# execucao, por isso a senha nao aparece na linha de comando; no fim sao apagadas.
#
# Sem -Confirmar, o psql recebe so o ficheiro: na migracao_tri_estado_restrita.sql
# isso e o ENSAIO (termina com ROLLBACK). Com -Confirmar passa "-v confirmar=1".
#
# Uso (na pasta do projeto, depois do backup):
#   .\executar_sql_render.ps1 .\migracoes\migracao_tri_estado_restrita.sql
#   .\executar_sql_render.ps1 .\migracoes\migracao_tri_estado_restrita.sql -Confirmar
param(
    [Parameter(Mandatory = $true)][string]$Ficheiro,
    [switch]$Confirmar
)
$ErrorActionPreference = "Stop"

if (-not $env:RADAR_RENDER_DB_URL) {
    throw "Defina RADAR_RENDER_DB_URL nesta sessao do terminal (ver o backup_render.ps1)."
}
$Caminho = (Resolve-Path $Ficheiro).Path

$Psql = "C:\Program Files\PostgreSQL\18\bin\psql.exe"
if (-not (Test-Path $Psql)) { throw "Nao encontrei $Psql (precisa do PostgreSQL 18)." }

$Uri = [Uri]$env:RADAR_RENDER_DB_URL
if ($Uri.Scheme -notin "postgres", "postgresql") { throw "RADAR_RENDER_DB_URL nao e um endereco postgresql://." }
$Utilizador, $Senha = $Uri.UserInfo.Split(":", 2)
$Variaveis = @{
    PGHOST            = $Uri.Host
    PGPORT            = $(if ($Uri.Port -gt 0) { "$($Uri.Port)" } else { "5432" })
    PGUSER            = [Uri]::UnescapeDataString($Utilizador)
    PGPASSWORD        = [Uri]::UnescapeDataString($Senha)
    PGDATABASE        = [Uri]::UnescapeDataString($Uri.AbsolutePath.TrimStart("/"))
    PGSSLMODE         = "require"
    PGCLIENTENCODING  = "UTF8"
}

# -X ignora o psqlrc; ON_ERROR_STOP para ao primeiro erro.
$Argumentos = @("-X", "-v", "ON_ERROR_STOP=1", "-f", $Caminho)
if ($Confirmar) { $Argumentos += @("-v", "confirmar=1") }

Write-Host ("Ficheiro: {0}  Modo: {1}" -f $Caminho, $(if ($Confirmar) { "GRAVAR" } else { "ensaio" }))
try {
    foreach ($Nome in $Variaveis.Keys) { Set-Item "Env:$Nome" $Variaveis[$Nome] }
    & $Psql @Argumentos
    if ($LASTEXITCODE -ne 0) { throw "O psql terminou com erro (codigo $LASTEXITCODE)." }
}
finally {
    foreach ($Nome in $Variaveis.Keys) { Remove-Item "Env:$Nome" -ErrorAction SilentlyContinue }
}
