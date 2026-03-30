# HTTPS Deployment Guide

This project can now be hosted behind automatic HTTPS with Docker Compose and Caddy.

## Required Environment

Create a production `.env` file or export these variables before deployment:

```env
SIGNAL_FLOW_DOMAIN=signals.example.com
SIGNAL_FLOW_SECRET_KEY=replace-this-with-a-real-secret
DATABASE_URL=postgresql+psycopg://signalflow:password@db-host:5432/signal_flow
SIGNAL_FLOW_AUTH_TOKEN_PREVIEW_ENABLED=false
SIGNAL_FLOW_AUTH_EMAIL_DELIVERY_MODE=smtp
SIGNAL_FLOW_AUTH_EMAIL_FROM_ADDRESS=alerts@example.com
SIGNAL_FLOW_AUTH_SMTP_HOST=smtp.example.com
SIGNAL_FLOW_AUTH_SMTP_PORT=587
SIGNAL_FLOW_AUTH_SMTP_USERNAME=alerts@example.com
SIGNAL_FLOW_AUTH_SMTP_PASSWORD=app-password
SIGNAL_FLOW_ANDROID_PACKAGE_NAME=
SIGNAL_FLOW_ANDROID_SHA256_CERT_FINGERPRINTS=
```

You can start from [`../.env.production.example`](../.env.production.example).

## Generate `.env.production`

If you already know the public domain and the production PostgreSQL URL, generate a ready-to-use file:

```powershell
.\scripts\generate-production-env.ps1 `
  -Domain signals.example.com `
  -DatabaseUrl "postgresql+psycopg://signalflow:password@db-host:5432/signal_flow"
```

The generator will:

- create `.env.production`
- generate a strong `SIGNAL_FLOW_SECRET_KEY`
- derive `SIGNAL_FLOW_PUBLIC_WEB_BASE_URL`
- derive `SIGNAL_FLOW_PUBLIC_API_BASE_URL`
- derive `SIGNAL_FLOW_PUBLIC_WS_BASE_URL`
- derive a default Android package name from the domain

If you already have a package name or signing fingerprints:

```powershell
.\scripts\generate-production-env.ps1 `
  -Domain signals.example.com `
  -DatabaseUrl "postgresql+psycopg://signalflow:password@db-host:5432/signal_flow" `
  -AndroidPackageName com.example.signals.signalflow `
  -AndroidSha256CertFingerprints "AA:BB:CC:DD"
```

## Deploy

Start the production stack:

```powershell
docker compose --env-file .env.production -f docker-compose.production.yml up -d --build
```

This stack provides:

- FastAPI app container with startup migrations
- Caddy reverse proxy with automatic HTTPS
- forwarded proxy headers for correct scheme handling
- SMTP auth email settings loaded from `.env.production`

## Verify

Check the hosted readiness endpoints:

```powershell
curl https://signals.example.com/api/health
curl https://signals.example.com/api/readiness
curl https://signals.example.com/api/release-status
```

Expected results:

- `/api/health` returns `status=ok`
- `/api/readiness` returns `status=ready`
- `/api/release-status` returns `ready_for_hosted_pwa=true`
- `/api/release-status` returns `auth.email_delivery_mode=smtp`
- `/api/release-status` returns `auth.email_delivery_ready=true`

## Notes

- Set `SIGNAL_FLOW_CORS_ORIGINS` to the exact hosted web origin.
- The app container runs Alembic migrations on startup by default.
- If you use a managed PostgreSQL service, keep `docker-compose.production.yml` as app plus proxy only and point `DATABASE_URL` at the managed database.
