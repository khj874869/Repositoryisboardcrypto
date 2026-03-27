# Signal Flow Deployment Roadmap

This document describes a staged path to upgrade `signal-flow-mvp` from a local MVP into a deployable web product and a mobile app that can be prepared for app-store release.

## Goals

- Ship a stable web dashboard for real-time signal monitoring
- Extend the same product into a mobile app release track
- Replace the current demo-only user flow with a real user model
- Add the minimum operational features needed for production deployment

## Current State

- Backend: FastAPI
- Frontend: single static HTML page
- Storage: SQLite
- Realtime delivery: WebSocket broadcast
- Data source: simulator-first
- User model: fixed `demo` user

This is enough for a local MVP, but not enough for production deployment.

Main gaps:

- settings are hardcoded in source
- no real authentication or per-user isolation
- no migration workflow
- no production database setup
- no mobile packaging or push-notification flow

## Recommended Delivery Order

1. Make the web app production-ready first.
2. Reuse the same API for mobile.
3. Package mobile as a faster first release path, then expand if needed.

This is the fastest path with the lowest product risk.

## Phase 1. Production Web Foundation

### 1-1. Move config into environment variables

Target:
- separate local, staging, and production settings

Tasks:
- replace hardcoded values in `config.py`
- add `.env.example`
- define `APP_ENV`, `DATABASE_URL`, `CORS_ORIGINS`, `DATA_MODE`, `SECRET_KEY`
- support switching between `demo` mode and `live` mode

Definition of done:
- the app can run in multiple environments without code edits

### 1-2. Replace SQLite for production

Target:
- move to PostgreSQL for deployment stability

Tasks:
- isolate the database layer
- move to SQLAlchemy or `psycopg`
- add Alembic migrations
- convert seed data into explicit setup or migration steps

Definition of done:
- schema changes are versioned and PostgreSQL is the default production database

### 1-3. Add authentication and user isolation

Target:
- remove the fixed `demo` user model

Tasks:
- add email login or social login
- use JWT or session auth
- connect `watchlists`, `strategies`, and `signals` to a real user id
- define basic authorization rules

Definition of done:
- each user sees and manages only their own data

### 1-4. Harden the frontend

Target:
- make the current dashboard usable in a deployed environment

Tasks:
- fix the broken Korean text rendering
- add loading, empty, and error states
- add better WebSocket reconnect UX
- support mobile browser layouts
- support environment-aware API base URLs

Definition of done:
- the app is usable from desktop and mobile browsers with clear failure handling

## Phase 2. Web Features To Add Before Public Deployment

These features will make the product materially more useful at launch.

### Feature 1. Per-user alert rules

Examples:
- alert by symbol
- alert by strategy
- alert by RSI threshold
- alert by price-change threshold

Why it matters:
- turns the dashboard into an actionable product

### Feature 2. Strategy presets

Examples:
- save strategy combinations
- duplicate presets
- enable or disable presets

Why it matters:
- reduces repeated setup work

### Feature 3. Signal history filters

Examples:
- filter by symbol
- filter by strategy
- filter by BUY or SELL
- filter by 1 hour, 24 hours, or 7 days

Why it matters:
- improves analysis and retention

### Feature 4. Expanded watchlist overview

Examples:
- top movers
- highest volatility assets
- most active signal assets

Why it matters:
- improves homepage value immediately

## Phase 3. Production Deployment Setup

### 3-1. Container and runtime

Tasks:
- improve `Dockerfile` for production use
- add `.dockerignore`
- add health checks
- define the production process model

Definition of done:
- the service builds and boots cleanly as a deployable container

### 3-2. Infrastructure

Suggested first deployment:
- API server on Render, Fly.io, Railway, or VPS
- managed PostgreSQL
- static assets on the same app or a CDN

Tasks:
- connect HTTPS
- connect a real domain
- inject environment variables
- set up automatic redeploys

### 3-3. Observability

Tasks:
- structured logs
- exception capture
- readiness checks in addition to `/api/health`
- metrics for WebSocket connections and generated signals

Definition of done:
- failures can be diagnosed without attaching to the server manually

### 3-4. CI/CD

Tasks:
- run tests in GitHub Actions
- build on every main-branch change
- automate deployment after merge

Definition of done:
- deployment does not depend on manual local steps

## Phase 4. Mobile Release Path

There are two realistic options.

### Option A. PWA plus Capacitor

Pros:
- fastest path
- reuses most of the current web code

Cons:
- less native flexibility

Best fit:
- when time to first mobile release matters most

### Option B. React Native or Flutter

Pros:
- better native UX
- better long-term mobile foundation

Cons:
- higher implementation cost

Best fit:
- when mobile is expected to become a major product channel

Given the current codebase, Option A is the better first release path.

## Phase 5. Mobile Features Required For App-Store Value

Shipping the web dashboard inside a mobile shell is not enough. Add these first.

### Feature 1. Push notifications

Examples:
- signal alerts for watchlist assets
- sharp-move alerts
- user-defined alert conditions

Why it matters:
- this is the main reason users keep a market app installed

### Feature 2. Persistent login and device sessions

Examples:
- automatic sign-in
- multi-device session tracking
- token invalidation on logout

Why it matters:
- basic trust and usability requirement for store apps

### Feature 3. Mobile-first home screen

Examples:
- compact summary cards
- live signal feed
- watchlist tab
- strategy tab

Why it matters:
- shrinking the desktop table view is not enough for a good app experience

### Feature 4. Notification history

Examples:
- in-app view of past alerts
- read-state tracking
- symbol-specific alert review

Why it matters:
- gives the mobile app value even after a push is missed

## Phase 6. App-Store Submission Checklist

### Common

- product description
- privacy-policy URL
- terms-of-service URL
- support email
- app icon
- screenshots
- release notes

### iOS

- Apple Developer account
- bundle identifier
- APNs or push setup
- review whether Sign in with Apple is required

### Android

- Google Play Console account
- signing-key management
- notification-permission handling
- target SDK policy compliance

## Recommended Priority

1. move config to environment variables
2. switch to PostgreSQL
3. add authentication
4. fix the frontend and text rendering
5. add alert rules
6. add push notifications
7. package for mobile
8. prepare store-submission assets

## Suggested Timeline

### Week 1

- config refactor
- deployment setup cleanup
- Docker improvements

### Week 2

- PostgreSQL migration
- user model
- authentication first pass

### Week 3

- frontend cleanup
- alert settings
- signal filtering

### Week 4

- web deployment
- logging and error capture
- domain and HTTPS

### Week 5

- PWA or Capacitor setup
- mobile layout tuning
- push-notification integration

### Week 6

- store assets
- internal testing
- submission

## Recommended Immediate Implementation Scope

If work starts from the current repository right now, the best first batch is:

1. `.env`-based config refactor
2. simulator and live-data mode split
3. frontend text rendering fix
4. production Docker cleanup
5. auth-ready user data model

These five items are the right bridge from MVP to deployable web app.
