# NanoTest Backend + Celery Worker - Dev
# Starts uvicorn and celery worker together and shows logs in separate terminal windows.

Set-Location $PSScriptRoot

# Activate venv for this script session
& .\.venv\Scripts\Activate.ps1

Clear-Host
Write-Host "NanoTest - Dev: Backend (uvicorn) + Worker (celery)" -ForegroundColor Cyan
Write-Host ""

# Helper: start a new PowerShell window running a command, keeping it open for logs
function Start-LogWindow {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Title,
    [Parameter(Mandatory = $true)]
    [string]$Command
  )

  $escaped = $Command.Replace('"', '\"')
  Start-Process powershell -ArgumentList @(
    '-NoExit',
    '-Command',
    "$Host.UI.RawUI.WindowTitle='$Title'; cd '$PSScriptRoot'; & .\\.venv\\Scripts\\Activate.ps1; $escaped"
  )
}

# Backend window
Start-LogWindow -Title 'NanoTest Backend (uvicorn)' -Command @'
python -m alembic upgrade head
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app
'@

# Worker window (Windows uses solo pool)
Start-LogWindow -Title 'NanoTest Worker (celery)' -Command @'
celery -A app.tasks.celery_app worker --loglevel=info --pool=solo
'@

Write-Host "Started." -ForegroundColor Green
Write-Host "- Backend: http://localhost:8000" -ForegroundColor Gray
Write-Host "- Worker:  see separate window" -ForegroundColor Gray
Write-Host ""
Write-Host "Close both windows to stop." -ForegroundColor Yellow
