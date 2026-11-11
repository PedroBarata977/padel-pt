# Corre pela tarefa agendada. Log em logs\fip.log (guarda as ultimas ~2000 linhas).
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$vpy = Join-Path $Root ".venv\Scripts\python.exe"
$log = Join-Path $Root "logs\fip.log"
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
"`n==== $(Get-Date -Format 'yyyy-MM-dd HH:mm') ====" | Add-Content $log
& $vpy -m collector.main fip *>> $log
if ($LASTEXITCODE -eq 0) { & $vpy -m collector.publish *>> $log } else { "recolha falhou (codigo $LASTEXITCODE), nada enviado" | Add-Content $log }
$lines = Get-Content $log; if ($lines.Count -gt 2000) { $lines[-2000..-1] | Set-Content $log }
