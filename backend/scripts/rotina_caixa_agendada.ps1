<#
Atualiza as listas da CAIXA a partir deste computador, contra a base de produção,
e deixa um lembrete dos editais. Pensado para o Agendador de Tarefas do Windows.

Antes de agendar:
  1. No Render a API não corre as rotinas da CAIXA (RADAR_DISABLE_BACKGROUND_JOBS=1):
     o IP do Render recebe 403.
  2. A ligação à base vem da variável de UTILIZADOR RADAR_RENDER_DB_URL (External
     Database URL). Fica no perfil do Windows; nunca neste ficheiro nem no Git.
  3. A paragem manual na produção tem de estar limpa (05_retomar_caixa.sql); se estiver
     ligada, a rotina termina sem pedidos (código 2).
  4. A descarga usa um browser real (Chrome): a tarefa tem de correr com a sessão do
     utilizador iniciada ("Executar apenas quando o utilizador tiver sessão iniciada").

O que faz:
  - recusa correr com a NordVPN ligada (os pedidos têm de sair pelo IP de casa);
  - recusa começar entre as 23:45 e as 02:30 UTC: a CAIXA gera as listas novas por volta
    da 01:00 UTC e uma descarga que atravesse essa hora mistura gerações;
  - descarrega as 27 listas com o browser (90 s entre UFs), importa e tira da lista os
    imóveis ausentes (nunca apaga; limite de segurança max(50, 20%));
  - NÃO pede datas à CAIXA (os pedidos automáticos são redirecionados): no fim escreve o
    resumo dos editais (pendentes, próximo edital a experimentar, PDFs por aplicar) em
    registos_caixa\ultimo_resumo.txt;
  - com -Ensaio faz tudo em ensaio: nada é pedido à CAIXA nem gravado.

Código de saída: 0 normal, 2 parou (paragem manual, bloqueio, outra rotina), 3 VPN,
4 sem ligação à base, 5 fora do horário, outro = erro.
#>
param([switch]$Ensaio)

$ErrorActionPreference = 'Stop'
$backend = Split-Path -Parent $PSScriptRoot
Set-Location $backend

$vpn = Get-NetAdapter -Name 'NordLynx' -ErrorAction SilentlyContinue | Where-Object Status -eq 'Up'
if ($vpn) { Write-Output 'Recusado: a NordVPN está ligada. Nada foi pedido à CAIXA.'; exit 3 }

if (-not $env:RADAR_RENDER_DB_URL) {
    $env:RADAR_RENDER_DB_URL = [Environment]::GetEnvironmentVariable('RADAR_RENDER_DB_URL', 'User')
}
if (-not $env:RADAR_RENDER_DB_URL) { Write-Output 'Recusado: RADAR_RENDER_DB_URL não definida.'; exit 4 }

$agora = (Get-Date).ToUniversalTime()
$minutos = $agora.Hour * 60 + $agora.Minute
if (-not $Ensaio -and ($minutos -ge (23 * 60 + 45) -or $minutos -lt (2 * 60 + 30))) {
    Write-Output ("Recusado: {0:HH:mm} UTC está perto da geração das listas (~01:00 UTC)." -f $agora)
    exit 5
}

$pasta = Join-Path $backend 'registos_caixa'
New-Item -ItemType Directory -Force $pasta | Out-Null
$marca = $agora.ToString('yyyyMMddTHHmmssZ')
$registo = Join-Path $pasta "rotina_$marca.jsonl"
$saida = Join-Path $pasta "rotina_$marca.log"
$python = Join-Path $backend '.venv\Scripts\python.exe'
$rotina = Join-Path $backend 'scripts\rotina_caixa.py'

$argumentos = @('--base', 'producao', '--lista-com-browser', '--intervalo-lista', '90')
if (-not $Ensaio) { $argumentos += @('--confirmo-contactar-caixa', '--registo', $registo) }
# No PowerShell 5.1, com 'Stop', qualquer linha do Python no stderr (até um aviso)
# terminaria o script: daqui para a frente decide só o código de saída do Python.
$ErrorActionPreference = 'Continue'
$env:PYTHONWARNINGS = 'ignore'
$env:PYTHONIOENCODING = 'utf-8'
& $python $rotina @argumentos 2>&1 | ForEach-Object { "$_" } | Out-File -Encoding utf8 -Append $saida
$codigo = $LASTEXITCODE

# Lembrete dos editais (só lê a base; não contacta a CAIXA).
$resumo = & $python $rotina --base producao --resumo-editais 2>&1
$resumo | Out-File -Encoding utf8 (Join-Path $pasta 'ultimo_resumo.txt')
$resumo | Out-File -Encoding utf8 -Append $saida
Write-Output $resumo
exit $codigo
