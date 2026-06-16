# NanoTest Backend + Celery Worker - Dev
# Starts uvicorn and celery worker together and shows logs in separate terminal windows.
# - Backend (uvicorn): built-in --reload for hot reload
# - Worker  (celery) : FileSystemWatcher auto-restarts on .py changes

Set-Location $PSScriptRoot

# Activate venv for this script session
& .\.venv\Scripts\Activate.ps1

Clear-Host
Write-Host "NanoTest - Dev: Backend (uvicorn) + Worker (celery + auto-reload)" -ForegroundColor Cyan
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
    "`$Host.UI.RawUI.WindowTitle='$Title'; cd '$PSScriptRoot'; & .\\.venv\\Scripts\\Activate.ps1; $escaped"
  )
}

# ---- Backend window (uvicorn already has --reload) ----
Start-LogWindow -Title 'NanoTest Backend (uvicorn)' -Command @'
python -m alembic upgrade head
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app
'@

# ---- Worker window with auto-reload on .py file changes ----
$workerCmd = @"
`$backendDir = '$PSScriptRoot'
`$workerPath = (Resolve-Path (Join-Path `$backendDir '..\..\apps\worker')).Path
Write-Host '[Auto-Reload] Watching for .py changes in:' -ForegroundColor Cyan
Write-Host "  Backend : `$backendDir" -ForegroundColor DarkGray
Write-Host "  Worker  : `$workerPath" -ForegroundColor DarkGray
Write-Host '  (edit any .py file to trigger worker restart)' -ForegroundColor DarkGray
Write-Host ''

function Start-CeleryWorker {
    `$script:CeleryJob = Start-Process -FilePath 'celery' -ArgumentList @('-A','app.tasks.celery_app','worker','--loglevel=info','--pool=solo') -NoNewWindow -PassThru
    Write-Host "[Auto-Reload] Worker started (PID: `$(`$script:CeleryJob.Id))" -ForegroundColor Green
}

function New-PyWatcher([string]`$dir) {
    `$w = New-Object System.IO.FileSystemWatcher
    `$w.Path = `$dir
    `$w.IncludeSubdirectories = `$true
    `$w.Filter = '*.py'
    `$w.NotifyFilter = [System.IO.NotifyFilters]::LastWrite
    `$w.EnableRaisingEvents = `$true
    return `$w
}

`$watcher1 = New-PyWatcher `$backendDir
`$watcher2 = New-PyWatcher `$workerPath

Start-CeleryWorker
`$lastRestart = [datetime]::MinValue

try {
    while (`$true) {
        `$r1 = `$watcher1.WaitForChanged([System.IO.WatcherChangeTypes]::All, 250)
        `$r2 = `$watcher2.WaitForChanged([System.IO.WatcherChangeTypes]::All, 250)
        `$changed = `$null
        if (-not `$r1.TimedOut) { `$changed = `$r1 }
        elseif (-not `$r2.TimedOut) { `$changed = `$r2 }

        if (`$changed) {
            `$now = [datetime]::Now
            if ((`$now - `$lastRestart).TotalSeconds -gt 2) {
                `$lastRestart = `$now
                `$rel = `$changed.FullPath
                if (`$rel.StartsWith(`$backendDir)) { `$rel = `$rel.Substring(`$backendDir.Length + 1) }
                elseif (`$rel.StartsWith(`$workerPath)) { `$rel = 'worker\' + `$rel.Substring(`$workerPath.Length + 1) }
                Write-Host "[Auto-Reload] Changed: `$rel  -- restarting worker..." -ForegroundColor Yellow
                if (`$script:CeleryJob -and -not `$script:CeleryJob.HasExited) {
                    Stop-Process -Id `$script:CeleryJob.Id -Force -ErrorAction SilentlyContinue
                    Start-Sleep -Seconds 1
                }
                Start-CeleryWorker
            }
        }
    }
} finally {
    `$watcher1.Dispose()
    `$watcher2.Dispose()
    if (`$script:CeleryJob -and -not `$script:CeleryJob.HasExited) {
        Stop-Process -Id `$script:CeleryJob.Id -Force -ErrorAction SilentlyContinue
    }
}
"@

Start-LogWindow -Title 'NanoTest Worker (celery + auto-reload)' -Command $workerCmd

Write-Host "Started." -ForegroundColor Green
Write-Host "- Backend: http://localhost:8000  (hot-reload enabled)" -ForegroundColor Gray
Write-Host "- Worker:  see separate window    (auto-restart on .py changes)" -ForegroundColor Gray
Write-Host ""
Write-Host "Close both windows to stop." -ForegroundColor Yellow
