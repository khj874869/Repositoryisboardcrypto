# Signal Flow MVP

Real-time market simulator with technical indicators and strategy signals.

## Features
- Simulated price ticks and candles (SQLite)
- RSI / SMA / Bollinger Bands
- Strategy engine (RSI Reversion, Golden Cross, Score Combo)
- WebSocket stream for market updates and signals
- REST API + single-page dashboard

## Tech Stack
- Python 3.13
- FastAPI
- SQLite
- WebSocket
- Vanilla JavaScript

## Quick Start
```bash
cd signal-flow-mvp
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

## Deployment Roadmap
- See [`docs/DEPLOYMENT_ROADMAP.md`](docs/DEPLOYMENT_ROADMAP.md) for the staged plan covering web deployment and app-store mobile deployment.

## API
- `GET /api/health`
- `GET /api/assets`
- `GET /api/market/overview`
- `GET /api/assets/{symbol}/candles`
- `GET /api/assets/{symbol}/signals`
- `GET /api/signals/recent`
- `GET /api/strategies`
- `POST /api/strategies`
- `PATCH /api/strategies/{id}`
- `GET /api/watchlist`
- `POST /api/watchlist`
- `DELETE /api/watchlist/{symbol}`
- `WS /ws/stream`

## Project Structure
```text
signal-flow-mvp/
  app/
    broadcaster.py
    config.py
    db.py
    indicators.py
    main.py
    market_simulator.py
    schemas.py
    strategy_engine.py
  static/
    index.html
  tests/
    test_indicators.py
    test_strategy_engine.py
  requirements.txt
  README.md
```
