# Signal Flow Live

[Korean Portfolio Overview](README.ko.md)

Signal Flow Live is a real-time market signal platform MVP built with FastAPI, SQLite/PostgreSQL, WebSocket streaming, and a shared client contract for web, PWA, and app-style clients.

This project is positioned as a portfolio piece around one core idea:

- one backend
- one product contract
- multiple client surfaces
- resilient market data ingestion with graceful fallback behavior

## Project Summary

Signal Flow Live combines live crypto market streaming with scanner-mode watchlists for stocks and ETFs. It exposes a shared API surface that allows a browser dashboard, installable PWA shell, and future mobile/desktop clients to boot from the same backend contract.

The product is designed to show:

- real-time data handling with WebSocket and bootstrap REST flows
- fallback-safe runtime behavior when an upstream source is unavailable
- shared client payload design instead of fragmented endpoint sprawl
- user-level signal preferences, watchlists, notifications, and auth flows
- operational thinking around migrations, release readiness, and deployment docs

## Why This Project Stands Out

- Shared client architecture: `bootstrap`, `dashboard`, and `asset detail` endpoints are intentionally shaped so web and app clients can use the same startup and display contract.
- Runtime resilience: live Upbit mode can fall back to a simulator, and scanner providers can fall back to synthetic data when external data is unavailable.
- Multi-market model: crypto runs in real time, while watch-only equities and ETFs run in scanner mode with runtime metadata such as session state and delayed-feed flags.
- Delivery-aware signals: signals now carry richer delivery semantics such as `notified`, `suppressed`, or `no_subscribers`, with reasons that explain why a user was not alerted.
- Production-minded foundation: Alembic migrations, PostgreSQL support, deployment docs, PWA support, and CI are already part of the repository.

## Key Features

- Upbit REST bootstrap for recent candles
- Upbit WebSocket ticker and candle streaming
- automatic fallback to simulator mode if Upbit startup fails
- scanner runtime for watch-only stocks and ETFs
- pluggable scanner providers with synthetic default and Yahoo adapter support
- scanner audit flow for delayed or out-of-session instruments
- access plus refresh token auth with session rotation
- password reset and email verification foundations
- per-user watchlists and notification settings
- notification inbox with read state
- static web dashboard consuming shared client APIs
- installable PWA shell for Android-first delivery paths
- SQLite by default with PostgreSQL-ready migration support

## Architecture

```text
                +----------------------+
                |  Web / PWA / App UI  |
                +----------+-----------+
                           |
                           v
                +----------------------+
                | FastAPI Backend      |
                | - shared client APIs |
                | - auth/session flows |
                | - signals/watchlist  |
                +----+------------+----+
                     |            |
          realtime   |            | scanner
                     v            v
           +----------------+   +----------------------+
           | Upbit stream   |   | Scanner providers    |
           | REST + WS      |   | synthetic / Yahoo    |
           +--------+-------+   +----------+-----------+
                    |                      |
                    +----------+-----------+
                               v
                    +----------------------+
                    | DB + runtime state   |
                    | SQLite / PostgreSQL  |
                    +----------------------+
```

## Shared Client Contract

The most important product APIs are:

- `GET /api/client/bootstrap`
- `GET /api/client/dashboard`
- `GET /api/client/assets/{symbol}`

These endpoints provide:

- application metadata and environment info
- source and runtime status
- shared endpoint discovery
- asset catalog and supported intervals
- dashboard state including signals, notifications, watchlist, and counts
- asset detail state including candles, recent signals, and computed indicators

This keeps the frontend thin and makes client expansion easier.

## Tech Stack

- Backend: FastAPI
- Data access: SQLAlchemy
- Database migrations: Alembic
- Storage: SQLite by default, PostgreSQL-ready
- Streaming: WebSocket + Upbit market feed
- HTTP client: httpx
- Testing: pytest
- Client shell: static HTML, JS, and PWA assets

## Local Run

### Windows PowerShell

```powershell
cd "C:\Users\S-P-041\Downloads\signal-flow-mvp"
.\run-local.ps1
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
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

## Demo Account

- username: `demo`
- password: `demo1234`

## Quality and Verification

Run tests with:

```bash
pytest -q
```

Latest local verification in this repository:

- `58 passed`

## Core API Surface

- `GET /api/health`
- `GET /api/readiness`
- `GET /api/source-status`
- `POST /api/auth/signup`
- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`
- `POST /api/auth/email-verification/request`
- `POST /api/auth/email-verification/confirm`
- `POST /api/auth/password-reset/request`
- `POST /api/auth/password-reset/confirm`
- `GET /api/auth/me`
- `GET /api/auth/sessions`
- `DELETE /api/auth/sessions/{session_id}`
- `GET /api/assets`
- `GET /api/assets/{symbol}/candles`
- `GET /api/assets/{symbol}/signals`
- `GET /api/signals/recent`
- `GET /api/market/overview`
- `GET /api/watchlist`
- `POST /api/watchlist`
- `DELETE /api/watchlist/{symbol}`
- `GET /api/notifications`
- `PATCH /api/notifications/{notification_id}/read`
- `GET /api/notification-settings`
- `PATCH /api/notification-settings`
- `WS /ws/stream`

## Environment

The full reference lives in [`.env.example`](.env.example). Key settings include:

- `SIGNAL_FLOW_APP_ENV=development|staging|production`
- `SIGNAL_FLOW_DATA_SOURCE=upbit|simulator`
- `SIGNAL_FLOW_SOURCE_FALLBACK_TO_SIMULATOR=true`
- `SIGNAL_FLOW_SCANNER_PROVIDER=synthetic|yahoo`
- `SIGNAL_FLOW_SCANNER_PROVIDER_FALLBACK_TO_SYNTHETIC=true`
- `SIGNAL_FLOW_SCANNER_ALERT_ALLOWED_SESSIONS=regular`
- `SIGNAL_FLOW_SCANNER_ALERT_ALLOW_DELAYED=false`
- `SIGNAL_FLOW_AUTH_EMAIL_DELIVERY_MODE=preview|smtp`
- `SIGNAL_FLOW_PUBLIC_WEB_BASE_URL=https://signals.example.com`
- `SIGNAL_FLOW_PUBLIC_API_BASE_URL=https://api.example.com`
- `SIGNAL_FLOW_PUBLIC_WS_BASE_URL=wss://api.example.com/ws/stream`
- `SIGNAL_FLOW_ENABLE_DEMO_SEED=true|false`
- `SIGNAL_FLOW_STRICT_STARTUP_VALIDATION=true|false`

## Migrations and Database

The repository includes:

- `DATABASE_URL` support for SQLite or PostgreSQL
- SQLAlchemy-based database access
- Alembic configuration and versioned migrations
- a SQLite-to-PostgreSQL migration helper for release cutovers

Examples:

```bash
alembic upgrade head
```

```bash
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/signal_flow alembic upgrade head
```

Windows migration helper:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://signalflow:signalflow@127.0.0.1:5432/signal_flow"
.\scripts\migrate-sqlite-to-postgres.ps1
```

## Release and Deployment References

- PWA release guide: [`docs/PWA_RELEASE_GUIDE.md`](docs/PWA_RELEASE_GUIDE.md)
- HTTPS deployment guide: [`docs/HTTPS_DEPLOYMENT_GUIDE.md`](docs/HTTPS_DEPLOYMENT_GUIDE.md)
- PostgreSQL local setup: [`docs/POSTGRESQL_LOCAL_SETUP.md`](docs/POSTGRESQL_LOCAL_SETUP.md)
- deployment roadmap: [`docs/DEPLOYMENT_ROADMAP.md`](docs/DEPLOYMENT_ROADMAP.md)
- production compose stack: [`docker-compose.production.yml`](docker-compose.production.yml)
- production env generator: [`scripts/generate-production-env.ps1`](scripts/generate-production-env.ps1)
- CI workflow: [`.github/workflows/ci.yml`](.github/workflows/ci.yml)

## Repository Focus

If you are reviewing this project as a portfolio artifact, the most important things to inspect are:

- shared API contract design in `app/client_api.py`
- runtime orchestration in `app/runtime.py` and `app/scanner_runtime.py`
- signal delivery policy in `app/signal_service.py`
- database evolution in `alembic/`
- product shell and operator UX in `static/index.html`
