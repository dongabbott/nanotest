# NanoTest Backend Server - Dev (auto-reload)

Set-Location $PSScriptRoot
& .\.venv\Scripts\Activate.ps1

Clear-Host
Write-Host "NanoTest Backend Server - Dev (Ctrl+C to stop)" -ForegroundColor Cyan
Write-Host ""

function Stop-ListenersOnPort {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Port
    )

    try {
        $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop
    } catch {
        $conns = $null
    }

    $pids = @()

    if ($conns) {
        $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
    } else {
        try {
            $netstat = netstat -ano -p tcp | Select-String -Pattern (":$Port\s+.*LISTENING\s+(\d+)$")
            foreach ($m in $netstat.Matches) {
                $pids += [int]$m.Groups[1].Value
            }
            $pids = $pids | Select-Object -Unique
        } catch {
            Write-Host "Failed to inspect port $Port. Try running PowerShell as Administrator." -ForegroundColor Yellow
            return
        }
    }

    if (-not $pids) {
        return
    }

    foreach ($procId in $pids) {
        try {
            $p = Get-Process -Id $procId -ErrorAction Stop
            Write-Host "Stopping process on port ${Port}: PID=$procId Name=$($p.ProcessName)" -ForegroundColor Yellow
            Stop-Process -Id $procId -Force -ErrorAction Stop
        } catch {
            Write-Host "Failed to stop PID=$procId on port $Port. Try running PowerShell as Administrator." -ForegroundColor Yellow
        }
    }
}

function Stop-ResidualUvicorn {
    try {
        $procs = Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" |
            Where-Object { $_.CommandLine -and $_.CommandLine -match 'uvicorn' }
        foreach ($proc in $procs) {
            try {
                Write-Host "Stopping residual uvicorn: PID=$($proc.ProcessId)" -ForegroundColor Yellow
                Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop
            } catch {
                Write-Host "Failed to stop uvicorn PID=$($proc.ProcessId)." -ForegroundColor Yellow
            }
        }
    } catch {
        Write-Host "Failed to detect residual uvicorn processes." -ForegroundColor Yellow
    }
}

Write-Host "Checking port 8000..." -ForegroundColor Cyan
Stop-ListenersOnPort -Port 8000
Stop-ResidualUvicorn
Write-Host ""

Write-Host "Running database migrations..." -ForegroundColor Cyan
python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Migration failed. Please check the error output above." -ForegroundColor Red
    exit $LASTEXITCODE
}
Write-Host ""

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app
