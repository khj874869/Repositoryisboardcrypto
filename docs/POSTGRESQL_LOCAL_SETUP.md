# Local PostgreSQL Verification

This project now supports `DATABASE_URL` for PostgreSQL and includes Alembic migrations.

## Option 1. Docker

Start a local PostgreSQL container:

```powershell
.\scripts\start-postgres-local.ps1
```

The script prints a ready-to-use `DATABASE_URL`.

Example:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://signalflow:signalflow@127.0.0.1:5432/signal_flow"
```

Run migrations and verify the app:

```powershell
.\scripts\verify-postgres.ps1
```

This will:

- run `alembic upgrade head`
- start the app on `http://127.0.0.1:8010`
- fetch `/api/health`
- fetch `/api/readiness`

## Move Existing SQLite Data

Once PostgreSQL is reachable, copy the local SQLite data set into the target database:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://signalflow:signalflow@127.0.0.1:5432/signal_flow"
.\scripts\migrate-sqlite-to-postgres.ps1
```

Optional source override:

```powershell
$env:SOURCE_DATABASE_URL = "sqlite:///C:/path/to/your/signal_flow.db"
.\scripts\migrate-sqlite-to-postgres.ps1
```

The migration script recreates the application schema if needed, clears target rows, copies all known tables, and resets PostgreSQL sequences so new inserts continue cleanly.

## Option 2. Existing Local PostgreSQL

Set `DATABASE_URL` directly and run:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\run-local.ps1
```

## Expected Health Signals

- `/api/health` should report `database.healthy=true`
- `/api/readiness` should report `status=ready`
- `/api/readiness` should report `database.dialect=postgresql`
