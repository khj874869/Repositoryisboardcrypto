$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

if (-not $env:DATABASE_URL) {
    throw 'DATABASE_URL is required'
}

& '.\.venv\Scripts\python.exe' -m alembic upgrade head

$stdout = Join-Path $projectRoot 'uvicorn.postgres.stdout.log'
$stderr = Join-Path $projectRoot 'uvicorn.postgres.stderr.log'
if (Test-Path $stdout) { Remove-Item -LiteralPath $stdout -Force }
if (Test-Path $stderr) { Remove-Item -LiteralPath $stderr -Force }

$process = Start-Process -FilePath '.\.venv\Scripts\python.exe' `
    -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8010') `
    -WorkingDirectory $projectRoot `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr `
    -PassThru

try {
    Start-Sleep -Seconds 5
    $health = Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8010/api/health | Select-Object -ExpandProperty Content
    $readiness = Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8010/api/readiness | Select-Object -ExpandProperty Content
    Write-Output "PID=$($process.Id)"
    Write-Output $health
    Write-Output $readiness
}
finally {
    if (-not $process.HasExited) {
        Stop-Process -Id $process.Id -Force
    }
}
