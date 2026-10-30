<#
Corre a rotina diária da CAIXA a partir deste computador, contra a base de produção.
Pensado para o Agendador de Tarefas do Windows (uma vez por dia).

Antes de agendar:
  1. No Render, a API não pode correr as rotinas da CAIXA:
     RADAR_DISABLE_BACKGROUND_JOBS=1 (o IP do Render recebe 403).
  2. A ligação à base vem da variável de utilizador RADAR_RENDER_DB_URL
     (External Database URL do radar-leilao-db). Fica guardada no perfil do
     Windows deste utilizador; não a escrevas neste ficheiro nem no Git.
  3. A paragem manual na produção tem de ter sido revista e limpa
     (producao_datas\05_retomar_caixa.sql), senão a rotina termina sem pedidos.

O que faz:
  - recusa correr com a NordVPN ligada (o pedido tem de sair pelo IP de casa);
  - lista das 27 UFs (60 s entre UFs) e até 10 pedidos de datas (600 s entre voltas);
  - registo em backend\registos_caixa\ (um ficheiro por execução);
  - código de saída: 0 normal, 2 parou (paragem manual, espera, limite), outro = erro.
#>
$ErrorActionPreference = 'Stop'
$backend = Split-Path -Parent $PSScriptRoot
Set-Location $backend

$vpn = Get-NetAdapter -Name 'NordLynx' -ErrorAction SilentlyContinue | Where-Object Status -eq 'Up'
if ($vpn) { Write-Output 'Recusado: a NordVPN está ligada. Nada foi pedido à CAIXA.'; exit 3 }

if (-not $env:RADAR_RENDER_DB_URL) {
    $env:RADAR_RENDER_DB_URL = [Environment]::GetEnvironmentVariable('RADAR_RENDER_DB_URL', 'User')
}
if (-not $env:RADAR_RENDER_DB_URL) { Write-Output 'Recusado: RADAR_RENDER_DB_URL não definida.'; exit 4 }

$pasta = Join-Path $backend 'registos_caixa'
New-Item -ItemType Directory -Force $pasta | Out-Null
$registo = Join-Path $pasta ("rotina_{0}.jsonl" -f (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ'))
$saida = Join-Path $pasta ("rotina_{0}.log" -f (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ'))

& (Join-Path $backend '.venv\Scripts\python.exe') (Join-Path $backend 'scripts\rotina_caixa.py') `
    --base producao --lista --max-pedidos-datas 10 --confirmo-contactar-caixa --registo $registo *>> $saida
exit $LASTEXITCODE
