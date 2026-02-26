# NanoTest Celery Worker - Dev

Set-Location $PSScriptRoot
& .\.venv\Scripts\Activate.ps1

Clear-Host
Write-Host "NanoTest Celery Worker - Dev (Ctrl+C to stop)" -ForegroundColor Cyan
Write-Host ""
Write-Host "Broker:  $env:CELERY_BROKER_URL  (default: redis://localhost:6379/1)" -ForegroundColor Gray
Write-Host "Pool:    solo (Windows)" -ForegroundColor Gray
Write-Host ""

celery -A app.tasks.celery_app worker --loglevel=info --pool=solo
