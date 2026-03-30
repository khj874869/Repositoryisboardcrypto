$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

function New-ProjectVenv {
    if (Get-Command python -ErrorAction SilentlyContinue) {
        & python -m venv .venv
        return
    }
    & py -m venv .venv
}

if (-not (Test-Path '.venv')) {
    New-ProjectVenv
}

& '.\.venv\Scripts\python.exe' -m pip install --upgrade pip
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt

if (-not $env:SIGNAL_FLOW_DATA_SOURCE) { $env:SIGNAL_FLOW_DATA_SOURCE = 'upbit' }
if (-not $env:SIGNAL_FLOW_UPBIT_MARKETS) { $env:SIGNAL_FLOW_UPBIT_MARKETS = 'KRW-BTC,KRW-ETH,KRW-XRP' }
if (-not $env:SIGNAL_FLOW_UPBIT_INTERVAL) { $env:SIGNAL_FLOW_UPBIT_INTERVAL = '1s' }
if (-not $env:SIGNAL_FLOW_SOURCE_FALLBACK_TO_SIMULATOR) { $env:SIGNAL_FLOW_SOURCE_FALLBACK_TO_SIMULATOR = 'true' }

& '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --reload
