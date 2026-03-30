@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv" (
    python -m venv .venv || py -m venv .venv
)
call ".venv\Scripts\python.exe" -m pip install --upgrade pip
call ".venv\Scripts\python.exe" -m pip install -r requirements.txt
if "%SIGNAL_FLOW_DATA_SOURCE%"=="" set SIGNAL_FLOW_DATA_SOURCE=upbit
if "%SIGNAL_FLOW_UPBIT_MARKETS%"=="" set SIGNAL_FLOW_UPBIT_MARKETS=KRW-BTC,KRW-ETH,KRW-XRP
if "%SIGNAL_FLOW_UPBIT_INTERVAL%"=="" set SIGNAL_FLOW_UPBIT_INTERVAL=1s
if "%SIGNAL_FLOW_SOURCE_FALLBACK_TO_SIMULATOR%"=="" set SIGNAL_FLOW_SOURCE_FALLBACK_TO_SIMULATOR=true
call ".venv\Scripts\python.exe" -m uvicorn app.main:app --reload
endlocal
