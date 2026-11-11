@echo off
cd /d "%~dp0"
echo A recolher dados da FIP e a enviar para o GitHub...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows\run_fip.ps1"
powershell -NoProfile -Command "Get-Content logs\fip.log -Tail 30 -Encoding UTF8"
pause
