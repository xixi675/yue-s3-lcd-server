$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\main\xiaoyue-server"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
Write-Host "Starting xiaoyue server"
Write-Host "OTA URL:   http://172.20.10.3:8003/xiaoyue/ota/"
Write-Host "WebSocket: ws://172.20.10.3:8000/xiaoyue/v1/"
& ".\.venv\Scripts\python.exe" app.py