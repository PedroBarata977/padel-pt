# Instalador do recolhedor FIP no Windows (corre uma vez).
# Duplo clique em INSTALAR.bat, ou: powershell -ExecutionPolicy Bypass -File windows\setup.ps1
$ErrorActionPreference = "Continue"  # "Stop" faz o PowerShell 5 abortar com qualquer texto em stderr
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
Write-Host "== Padel PT: instalacao em $Root ==" -ForegroundColor Cyan

# 1) Python
$py = $null
foreach ($c in @("py -3", "python")) {
  try { $v = & cmd /c "$c --version" 2>$null; if ($v -match "Python 3\.(\d+)") { if ([int]$Matches[1] -ge 10) { $py = $c; break } } } catch {}
}
if (-not $py) {
  Write-Host "Python 3.10+ nao encontrado. A instalar com winget..." -ForegroundColor Yellow
  winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
  $env:Path = [Environment]::GetEnvironmentVariable("Path","User") + ";" + [Environment]::GetEnvironmentVariable("Path","Machine")
  $py = "py -3"
}
Write-Host "Python: $(& cmd /c "$py --version")"

# 2) Ambiente virtual + bibliotecas
if (-not (Test-Path ".venv\Scripts\python.exe")) { & cmd /c "$py -m venv .venv" }
$vpy = Join-Path $Root ".venv\Scripts\python.exe"
& $vpy -m pip install --quiet --upgrade pip
& $vpy -m pip install --quiet -r requirements.txt
Write-Host "Bibliotecas instaladas." -ForegroundColor Green

# 3) Testes + TESTE REAL: a FIP deixa este PC passar?
& $vpy -m pytest -q
Write-Host "`nA testar o acesso ao padelfip.com a partir deste PC..." -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path logs | Out-Null
& cmd /c "`"$vpy`" -m collector.main fip > logs\primeiro-teste.log 2>&1"
$code = $LASTEXITCODE
Get-Content logs\primeiro-teste.log
if ($code -ne 0) {
  Write-Host "`nFALHOU: a FIP tambem bloqueia este PC (ou o site mudou). Envia o ficheiro logs\primeiro-teste.log ao Claude." -ForegroundColor Red
  Read-Host "Enter para sair"; exit 1
}
Write-Host "`nOK: a FIP respondeu a partir deste PC." -ForegroundColor Green

# 4) Token do GitHub (fica so neste PC, em github_token.txt)
if (-not (Test-Path "github_token.txt")) {
  Write-Host "`nCola o token do GitHub (fine-grained, so o repositorio padel-pt, Contents: Read and write)."
  $sec = Read-Host "Token" -AsSecureString
  $tok = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
  Set-Content -Path github_token.txt -Value $tok.Trim() -NoNewline -Encoding ascii
}
& $vpy -m collector.publish
if ($LASTEXITCODE -ne 0) { Write-Host "Envio para o GitHub falhou (token errado?). Apaga github_token.txt e corre de novo." -ForegroundColor Red; Read-Host "Enter"; exit 1 }

# 5) Tarefa agendada: 07:05, 12:05, 17:05 e 22:05; corre ao ligar se falhou uma hora
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Root\windows\run_fip.ps1`"" -WorkingDirectory $Root
$triggers = @("07:05","12:05","17:05","22:05") | ForEach-Object { New-ScheduledTaskTrigger -Daily -At $_ }
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
Register-ScheduledTask -TaskName "PadelPT - FIP" -Action $action -Trigger $triggers -Settings $settings -Description "Recolhe dados da FIP e envia para o GitHub (padel-pt)" -Force | Out-Null
Write-Host "`nTarefa agendada 'PadelPT - FIP' criada (07:05, 12:05, 17:05, 22:05)." -ForegroundColor Green
Write-Host "Dashboard: https://pedrobarata977.github.io/padel-pt/"
Read-Host "`nFeito. Enter para fechar"
