# HTTPS Deployment Guide

This project can now be hosted behind automatic HTTPS with Docker Compose and Caddy.

## Required Environment

Create a production `.env` file or export these variables before deployment:

```env
SIGNAL_FLOW_DOMAIN=signals.example.com
SIGNAL_FLOW_SECRET_KEY=replace-this-with-a-real-secret
DATABASE_URL=postgresql+psycopg://signalflow:password@db-host:5432/signal_flow
SIGNAL_FLOW_ANDROID_PACKAGE_NAME=
SIGNAL_FLOW_ANDROID_SHA256_CERT_FINGERPRINTS=
```

You can start from [`../.env.production.example`](../.env.production.example).

## Deploy

Start the production stack:

```powershell
docker compose -f docker-compose.production.yml up -d --build
```

This stack provides:

- FastAPI app container with startup migrations
- Caddy reverse proxy with automatic HTTPS
- forwarded proxy headers for correct scheme handling

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

## Notes

- Set `SIGNAL_FLOW_CORS_ORIGINS` to the exact hosted web origin.
- The app container runs Alembic migrations on startup by default.
- If you use a managed PostgreSQL service, keep `docker-compose.production.yml` as app plus proxy only and point `DATABASE_URL` at the managed database.
