# PWA And Android Release Guide

This project is currently best shipped in two steps.

## Step 1. Ship The Web App As A PWA

The current codebase already fits a PWA-first release path:

- FastAPI serves the full web shell
- the dashboard is mobile-friendly
- the app now exposes a web manifest
- the app now exposes a service worker
- the web client can be installed from supported browsers

### PWA Checklist

- deploy behind HTTPS
- set `SIGNAL_FLOW_PUBLIC_API_BASE_URL`
- set `SIGNAL_FLOW_PUBLIC_WS_BASE_URL`
- set `SIGNAL_FLOW_CORS_ORIGINS`
- verify `/manifest.webmanifest`
- verify `/sw.js`
- verify install prompt from Chrome on Android

## Step 2. Package For Google Play

There are two realistic Android release paths.

### Option A. Trusted Web Activity

Best when:

- the web app stays primary
- release speed matters most
- native device integration is minimal

Recommended stack:

- Bubblewrap
- Trusted Web Activity
- Play Store deployment from the hosted PWA

Requirements:

- production HTTPS domain
- Lighthouse PWA readiness
- Android package name
- signing key
- Digital Asset Links on the production domain

### Option B. Capacitor Wrapper

Best when:

- you want push notifications sooner
- you need deeper Android APIs
- you expect more mobile-specific UI work

Recommended when the next milestone includes:

- native push notifications
- device storage integration
- app-specific auth/session handling

## Recommended Order

1. Deploy the hosted PWA.
2. Validate mobile browser usage and install flow.
3. Add push-notification infrastructure.
4. Choose TWA or Capacitor based on how much native control is needed.

## Next Engineering Targets

- replace demo-only auth with production auth
- move SQLite to PostgreSQL for hosted deployment
- add background alert delivery beyond the in-app inbox
- add analytics and crash reporting
- add release environments for local, staging, and production
