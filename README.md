# Signal Flow Live

Upbit 실데이터 기반 주식/코인 시그널 분석 데모입니다. 기본 모드는 Upbit 실데이터 연동이며, 초기 네트워크 연결이 실패하면 시뮬레이터로 자동 전환할 수 있습니다.

## 이번 버전에서 추가된 것
- Upbit REST 캔들 bootstrap
- Upbit WebSocket ticker + candle 실시간 스트림
- 실시간/스냅샷 소스 상태 확인 API (`/api/source-status`)
- UI 상단에 데이터 소스 상태 표시
- Windows PowerShell 실행 스크립트 (`run-local.ps1`)
- Windows CMD 실행 스크립트 (`run-local.bat`)
- 기존 최신 캔들 조회 로직 수정 (최근 120개 기준)

## 권장 실행 방법

### Windows PowerShell
압축을 푼 폴더까지 **정확한 전체 경로**로 이동해야 합니다.

예시:
```powershell
cd "C:\Users\S-P-041\Downloads\signal-flow-mvp"
```

기존 에러 원인:
- `cd signal-flow-mvp` 는 현재 위치에 해당 폴더가 없으면 실패합니다.
- `source .venv/bin/activate` 는 Linux/macOS 방식이라 PowerShell에서 동작하지 않습니다.

가장 쉬운 실행:
```powershell
cd "C:\Users\S-P-041\Downloads\signal-flow-mvp"
.\run-local.ps1
```

직접 실행:
```powershell
cd "C:\Users\S-P-041\Downloads\signal-flow-mvp"
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:SIGNAL_FLOW_DATA_SOURCE = "upbit"
$env:SIGNAL_FLOW_UPBIT_MARKETS = "KRW-BTC,KRW-ETH,KRW-XRP"
$env:SIGNAL_FLOW_UPBIT_INTERVAL = "1s"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

### Windows CMD
```bat
cd /d C:\Users\S-P-041\Downloads\signal-flow-mvp
run-local.bat
```

### macOS / Linux
```bash
cd signal-flow-mvp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export SIGNAL_FLOW_DATA_SOURCE=upbit
export SIGNAL_FLOW_UPBIT_MARKETS=KRW-BTC,KRW-ETH,KRW-XRP
export SIGNAL_FLOW_UPBIT_INTERVAL=1s
uvicorn app.main:app --reload
```

## 접속
```text
http://127.0.0.1:8000
```

## 기본 계정
- username: `demo`
- password: `demo1234`

## 주요 환경변수
- `SIGNAL_FLOW_DATA_SOURCE=upbit|simulator`
- `SIGNAL_FLOW_UPBIT_MARKETS=KRW-BTC,KRW-ETH,KRW-XRP`
- `SIGNAL_FLOW_UPBIT_INTERVAL=1s|1m|3m|5m|10m|15m|30m|60m|240m`
- `SIGNAL_FLOW_UPBIT_BOOTSTRAP_COUNT=120`
- `SIGNAL_FLOW_SOURCE_FALLBACK_TO_SIMULATOR=true`

## API
- `GET /api/health`
- `GET /api/source-status`
- `GET /api/market/overview`
- `GET /api/signals/recent`
- `POST /api/auth/login`
- `GET /api/watchlist`
- `GET /api/notifications`
- `WS /ws/stream`

## 테스트
```bash
pytest -q
```
