# Signal Flow Live

Signal Flow Live is a real-time market signal MVP built on FastAPI and SQLite.

The backend now exposes a shared client surface for both:

- a browser-based web dashboard
- a mobile or desktop app client
- an installable PWA shell for Android-first release paths

That shared surface is centered around:

- `GET /api/client/bootstrap`
- `GET /api/client/dashboard`
- `GET /api/client/assets/{symbol}`

These endpoints give web and app clients the same startup metadata, dashboard payload, and asset detail contract.

## Current Features

- Upbit REST bootstrap for recent candles
- Upbit WebSocket ticker and candle streaming
- automatic fallback to simulator mode if Upbit startup fails
- access plus refresh token auth with session rotation, password reset, and email verification foundations
- per-user watchlist and notification settings
- notification inbox with read state
- shared dashboard and asset detail APIs for web and app clients
- static web dashboard consuming the same shared client APIs
- PWA manifest, service worker, and install flow foundation

## Quick Start

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

## Shared Client APIs

### Bootstrap

`GET /api/client/bootstrap`

Returns:

- app metadata
- current session state
- source status
- available assets
- supported intervals
- shared endpoint map
- web/app connection info including WebSocket URL

### Dashboard

`GET /api/client/dashboard`

Returns a single aggregated payload for clients:

- market overview
- recent signals
- watchlist
- notifications
- notification settings
- top-level counts

### Asset Detail

`GET /api/client/assets/{symbol}`

Returns:

- asset metadata
- recent candles
- recent signals
- computed indicator snapshot

## Core APIs

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

## Environment Variables

- `SIGNAL_FLOW_APP_ENV=development|staging|production`
- `SIGNAL_FLOW_DATA_SOURCE=upbit|simulator`
- `SIGNAL_FLOW_UPBIT_MARKETS=KRW-BTC,KRW-ETH,KRW-XRP`
- `SIGNAL_FLOW_UPBIT_INTERVAL=1s|1m|3m|5m|10m|15m|30m|60m|240m`
- `SIGNAL_FLOW_UPBIT_BOOTSTRAP_COUNT=120`
- `SIGNAL_FLOW_SOURCE_FALLBACK_TO_SIMULATOR=true`
- `SIGNAL_FLOW_REFRESH_TOKEN_EXPIRE_DAYS=30`
- `SIGNAL_FLOW_PASSWORD_RESET_TOKEN_EXPIRE_MINUTES=30`
- `SIGNAL_FLOW_EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS=24`
- `SIGNAL_FLOW_AUTH_TOKEN_PREVIEW_ENABLED=true`
- `SIGNAL_FLOW_AUTH_EMAIL_DELIVERY_MODE=preview|smtp`
- `SIGNAL_FLOW_AUTH_EMAIL_FROM_ADDRESS=alerts@example.com`
- `SIGNAL_FLOW_AUTH_EMAIL_FROM_NAME=Signal Flow Live`
- `SIGNAL_FLOW_AUTH_SMTP_HOST=smtp.example.com`
- `SIGNAL_FLOW_AUTH_SMTP_PORT=587`
- `SIGNAL_FLOW_AUTH_SMTP_USERNAME=alerts@example.com`
- `SIGNAL_FLOW_AUTH_SMTP_PASSWORD=app-password`
- `SIGNAL_FLOW_AUTH_SMTP_USE_SSL=false`
- `SIGNAL_FLOW_AUTH_SMTP_USE_STARTTLS=true`
- `SIGNAL_FLOW_PUBLIC_WEB_BASE_URL=https://signals.example.com`
- `SIGNAL_FLOW_PUBLIC_API_BASE_URL=https://api.example.com`
- `SIGNAL_FLOW_PUBLIC_WS_BASE_URL=wss://api.example.com/ws/stream`
- `SIGNAL_FLOW_CORS_ORIGINS=https://web.example.com,capacitor://localhost`
- `SIGNAL_FLOW_ANDROID_PACKAGE_NAME=com.signalflow.live`
- `SIGNAL_FLOW_ANDROID_SHA256_CERT_FINGERPRINTS=AA:BB:CC,...`
- `SIGNAL_FLOW_ENABLE_DEMO_SEED=false`
- `SIGNAL_FLOW_STRICT_STARTUP_VALIDATION=true`

## Tests

```bash
pytest -q
```

## Release Path

- PWA release guide: [`docs/PWA_RELEASE_GUIDE.md`](docs/PWA_RELEASE_GUIDE.md)
- HTTPS deployment guide: [`docs/HTTPS_DEPLOYMENT_GUIDE.md`](docs/HTTPS_DEPLOYMENT_GUIDE.md)
- Production compose stack: [`docker-compose.production.yml`](docker-compose.production.yml)
- Production env generator: [`scripts/generate-production-env.ps1`](scripts/generate-production-env.ps1)
- GitHub Actions CI: [`.github/workflows/ci.yml`](.github/workflows/ci.yml)

## Database Migration Foundation

The project now includes:

- `DATABASE_URL` support for SQLite or PostgreSQL
- SQLAlchemy-based database access
- Alembic configuration and an initial migration
- a SQLite to PostgreSQL copy utility for release cutovers

Examples:

```bash
alembic upgrade head
```

```bash
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/signal_flow alembic upgrade head
```

- Windows migration helper:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://signalflow:signalflow@127.0.0.1:5432/signal_flow"
.\scripts\migrate-sqlite-to-postgres.ps1
```

- PostgreSQL local setup guide: [`docs/POSTGRESQL_LOCAL_SETUP.md`](docs/POSTGRESQL_LOCAL_SETUP.md)
