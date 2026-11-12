# Corre pela tarefa agendada. Log em logs\recolha.log (UTF-8, guarda as ultimas ~2000 linhas).
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$env:PYTHONIOENCODING = "utf-8"
$vpy = Join-Path $Root ".venv\Scripts\python.exe"
$log = Join-Path $Root "logs\recolha.log"
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
"`r`n==== $(Get-Date -Format 'yyyy-MM-dd HH:mm') ====" | Out-File -FilePath $log -Append -Encoding utf8
& cmd /c "`"$vpy`" -m collector.main fip >> `"$log`" 2>&1"
if ($LASTEXITCODE -eq 0) {
  & cmd /c "`"$vpy`" -m collector.publish >> `"$log`" 2>&1"
  if ($LASTEXITCODE -ne 0) { "ENVIO PARA O GITHUB FALHOU (codigo $LASTEXITCODE)" | Out-File -FilePath $log -Append -Encoding utf8 }
} else { "RECOLHA FALHOU (codigo $LASTEXITCODE), nada enviado" | Out-File -FilePath $log -Append -Encoding utf8 }
$lines = Get-Content $log -Encoding UTF8; if ($lines.Count -gt 2000) { $lines[-2000..-1] | Set-Content $log -Encoding UTF8 }
