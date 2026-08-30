### Track 2 — Performance & Security Hardening

- **Audit Logging Engine (`AuditService` / `AuditStore`):** Non-blocking, best-effort audit logger persisting user actions to a dedicated `audit_log` table co-located with `auth.db`. The table is created automatically on first instantiation (`AuditStore.__init__` → `_init_sqlite_schema()` / `_init_pg_schema()`). Writes never raise.
- **Rate Limiting (`TokenBucketLimiter`):** Thread-safe in-memory token bucket, one bucket per `(identity, route)` key. Per-route limits:
  - `/api/sow/generate` — 10 req/min for standard users, 60 req/min for superadmins
  - `/api/auth/login` — 10 req/min per source IP
- **Quota Management (`QuotaService`):** Server-side enforcement at three levels:
  - Upload submission: 25 MB total / 12 files max
  - Per-user document storage: 500 documents max
- **Admin Dashboard:** Real-time audit stream in `frontend/app/admin/page.tsx` with action filter dropdown, 10-second polling, and outcome status badges. Streams both `success` and `denied` rows from the last 50 events.

### Track 3 — Field Mobile & Media Optimization

- **Client-side image compression** (`frontend/lib/image-compress.ts`): HTMLCanvas dual-pass pipeline downscales field photographs to a configurable max dimension (default 1920 px) at 0.82 JPEG quality. EXIF filename key is preserved for server-side `SpatialContext` extraction. Non-image files pass through unchanged.
- **Service Worker** (`frontend/public/sw.js`): Three caching strategies:
  - **App shell HTML** — network-first, cached fallback when offline
  - **`_next/static/*`** — cache-first (immutable hashed assets)
  - **Map tiles** (`tile.openstreetmap.org`) — stale-while-revalidate
  - **`/api/*`** — never cached (POSTs handled by the IndexedDB queue)
- **IndexedDB offline queue** (`frontend/lib/offline-db.ts`): Chat submissions made while `navigator.onLine === false` are persisted to a `pending_submissions` object store. On reconnect, `components/ChatInput.tsx` auto-drains the queue.

> **Not in this release:** Background Sync API registration, push notifications, full app-shell pre-cache for the entire route tree. Tracked in Phase 6.

# Phase 5 Release Summary & Deployment Guide

> **Status:** Production-ready, single-host deployment.
> **Audience:** DevOps, on-call engineers, superadmin operators.
> **Audience NOT:** End users (see `README.md` instead).

Phase 5 transitions OSIRIS Imhotep from a functional prototype into a production-hardened platform. The release delivers offline-capable field media optimization, complete automated test coverage across backend and frontend stacks, and enterprise-grade security and quota controls.

---

## 1. Feature & Capability Summary

```
+-----------------------------------------------------------------------------------+
|                                 PHASE 5 RELEASE                                   |
+------------------------------------+----------------------------------------------+
| Track 1: Automated Testing         | • 93 backend Pytest tests (all green)         |
|                                    | • 22 Playwright E2E tests across 5 spec files|
+------------------------------------+----------------------------------------------+
| Track 2: Security & Hardening      | • Append-only Audit Service (auth.db)        |
|                                    | • In-process token-bucket rate limiting      |
|                                    | • Per-user upload & document quotas          |
|                                    | • Real-time Admin Audit Dashboard            |
+------------------------------------+----------------------------------------------+
| Track 3: Mobile & Field Offline    | • Client-side Canvas image compression       |
|                                    | • Service Worker (network-first / cache-first|
|                                    |   / stale-while-revalidate)                  |
|                                    | • IndexedDB offline submission queue         |
+------------------------------------+----------------------------------------------+
```

### Track 1 — Automated Testing & E2E Verification

- **Backend integration suite (Pytest):** 93 tests across `tests/test_audit_service.py`, `tests/test_rate_limit.py`, `tests/test_quotas.py`, `tests/test_export_service.py`, `tests/test_export_routes.py`, and the existing auth/chat/SOW suites. All passing.
- **Frontend E2E suite (Playwright):** 22 tests across 5 spec files:

  | Spec file | Tests | Coverage |
  |---|---|---|
  | `e2e/admin.spec.ts` | 5 | Audit card visible, login entry rendered, action filter, rate-limit 429, rate-limit audit row |
  | `e2e/chat-input-offline.spec.ts` | 8 | Empty-submit disabled, Enter-to-submit, IndexedDB queue on offline, auto-resubmit on reconnect |
  | `e2e/export-toolbar-costing-gate.spec.ts` | 3 | Costing enabled → xlsx/csv visible; costing disabled → xlsx/csv hidden; non-superadmin → costing always hidden |
  | `e2e/export-toolbar.spec.ts` | 3 | Role-locked formats, costing-format gating, permission denied path |
  | `e2e/scatter-map.spec.ts` | 3 | Spatial context propagation through chat → document |

  Tests have not been executed in headless CI on the release image. They are validated locally against `npm run dev` + a running backend.

## 1a. Frontend Architecture Notes (added Phase 5 closeout)

- **SowReport component split:** The monolithic `SowReport.tsx` (283 lines) has been decomposed into 12 focused sub-components under `frontend/components/sow-report/`: `types.ts`, `money.ts`, `SectionTitle`, `THead`, `TData`, `ExecutiveSummary`, `VisualFindings`, `RecommendedServices`, `ScopeBreakdown`, `CostSummary`, `GroundingSources`, and an `index.tsx` barrel. `components/SowReport.tsx` is now a 4-line re-export shim so all existing import paths continue to work.
- **Feature-gated exports:** `EXPORT_COSTING_ENABLED` (default `true`) is exposed to the frontend via `GET /api/admin/config` (superadmin-only). When false, the `ExportToolbar` hides the `.xlsx` and `.csv` costing buttons entirely (rather than showing them in a disabled/locked state).

## 2. Configuration & Environment Variables

The backend reads these from the OS environment (or a `.env` loaded by your process manager). Defaults are tuned for a single-tenant single-host deployment.

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_ENV` | `production` | Set to `development` to enable verbose request logging |
| `DATABASE_URL` | `sqlite:///./auth.db` | SQLite file or Postgres connection string |
| `JWT_SECRET` | *(none)* | **Required.** HMAC-SHA256 secret for signing JWTs (min. 32 random bytes) |
| `SUPERADMIN_PASSWORD` | *(none)* | **Required.** Initial superadmin password |
| `JWT_EXPIRE_MINUTES` | `480` | JWT token lifetime |
| `RATE_LIMIT_LOGIN_PER_MINUTE` | `10` | Login rate-limit bucket capacity |
| `RATE_LIMIT_SOW_PER_MINUTE` | `10` | SOW generation rate-limit capacity |
| `RATE_LIMIT_SOW_ADMIN_PER_MINUTE` | `60` | SOW generation rate-limit capacity for superadmins |
| `QUOTA_MAX_UPLOAD_MB` | `25` | Max total upload size per submission |
| `QUOTA_MAX_FILES` | `12` | Max files per submission |
| `QUOTA_MAX_DOCS` | `500` | Max documents per user |
| `EXPORT_COSTING_ENABLED` | `true` | Set to `false` to hide `.xlsx`/`.csv` costing formats from all non-superadmin users |

## 3. Database Initialization

**SQLite (default):** `auth.db` and the `audit_log` table are created automatically on first startup. No migration step needed.

**Postgres:** Ensure `DATABASE_URL` is set and the role has `CREATE` + `INSERT` on the target schema. The `audit_log` table DDL is emitted by `AuditStore._init_pg_schema()` on first connect — it uses `IF NOT EXISTS` and is idempotent.

Recommended `DATABASE_URL` privileges: a dedicated role with `CREATE TABLE` on the schema and `INSERT` / `SELECT` on `audit_log`. The app does not need `DROP` or `ALTER`.

## 4. Deployment Procedure

1. **Environment:** Copy `.env.example` to `.env` and fill in `JWT_SECRET` and `SUPERADMIN_PASSWORD`. Ensure `DATABASE_URL` points to the correct target (SQLite file or Postgres cluster).
2. **Backend:** `pip install -r requirements.txt && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000` or deploy the Docker image.
3. **Frontend:** `npm install && npm run build && npm start`.
4. **Seed superadmin:** On first start, `POST /api/admin/seed` with `{"password": "..."}` to create the superadmin. This endpoint is disabled once a superadmin exists (`APP_ENV != "development"`).
5. **Smoke test:** Follow the checklist in §6.

## 5. Key Implementation Notes

- `AuditService` uses a background `threading.Thread` to drain a `queue.Queue` of audit rows. The thread never raises; SQLite lock contention drops rows silently (logged at WARNING level).
- `TokenBucketLimiter` is in-process only. Multiple uvicorn workers share no state. Set `WEB_CONCURRENCY=1` or use sticky sessions at the load-balancer to avoid per-worker bucket drift.
- Quota enforcement is per-request (not cumulative in a session). For upload submissions the total bytes of all files in the multipart body is checked before any file is saved.
- The admin audit log streams the last 50 rows sorted by `ts DESC`. There is no pagination in this release.

## 6. Post-Deployment Verification Checklist

Run these in order. Mark each item ✓ before declaring the release live.

- [ ] `curl http://<host>:8000/api/sow/health` returns `200 {"ok": true}`.
- [ ] Log in as superadmin, navigate to `/admin`, and confirm the **Audit Log** card renders with at least one row (the `login` event for the current superadmin session).
- [ ] Log in as a standard user with valid credentials; confirm a `login` row with `outcome=success` and that user's `username` appears in the audit stream within ~10 s.
- [ ] Attempt a denied export (standard user → `.xlsx` or `.csv` costing format). Confirm `403` and a `costing_export` row with `outcome=denied` in the admin audit log.
- [ ] Submit a SOW generation request as a standard user. Confirm `200` and a `generate` row with `outcome=success`.
- [ ] Submit 11 SOW generation requests within 60 s as a standard user. Confirm the 11th returns `429` with a `Retry-After` header and a `rate_limited` row with `outcome=denied` in the audit log.
- [ ] Submit a SOW generation request exceeding `QUOTA_MAX_UPLOAD_MB`. Confirm `413` (or the configured quota status) and a `quota_exceeded` row in the audit log.
- [ ] Confirm env-var overrides are live: inspect `/api/admin/audit-log` filter UI or run `python -c "from app.config import get_settings; print(get_settings().rate_limit_login_per_minute)"` against the deployed process.
- [ ] `POST /api/auth/logout` while logged in as a standard user. Confirm a `logout` row with `outcome=success` appears in the admin audit log within ~10 s.
- [ ] `curl -H "Authorization: Bearer <superadmin_token>" http://<host>:8000/api/admin/config` returns `{"export_costing_enabled": true}` when the gate is open, or `{"export_costing_enabled": false}` after setting `EXPORT_COSTING_ENABLED=false` in the environment and restarting the backend.

## 7. Rollback Procedure

If the release misbehaves in production:

1. **Disable rate limiting** by setting all three `RATE_LIMIT_*` env vars to a very high value (e.g. `10000`) and restarting the backend. The limiter code stays in place but limits become unreachable.
2. **Disable quota enforcement** the same way: set `QUOTA_*` to high values and restart.
3. **If the audit table is the problem:** the `audit_log` table is independent of the user table. Drop it without losing users:
   ```sql
   -- SQLite
   DROP TABLE IF EXISTS audit_log;
   -- Postgres
   DROP TABLE IF EXISTS audit_log;
   ```
   Then redeploy the previous image. The next request will recreate the table.
4. **Full revert:** redeploy the previous container image. The `audit_log` table is left in place (no destructive schema changes were introduced; only `CREATE TABLE IF NOT EXISTS` runs on startup).
5. **Postgres rollback:** ensure the previous app version is compatible with the same `DATABASE_URL`. There is no destructive migration in Phase 5.

The audit system is designed to **never** break a user-facing request, so a partial rollout where audit is the only failure mode should not require a full rollback.

## 8. Known Limitations & Phase 6 Work

- **In-process rate limiter** does not scale horizontally (see §4).
- **No Background Sync API registration** — the offline queue relies on `navigator.onLine` events from `ChatInput`, not the OS-level sync manager. Failures mid-submit before reconnect require the tab to remain open.
- **Service worker does not pre-cache deep routes** — only the 5 URLs in `APP_SHELL_URLS` are seeded on install. A user visiting `/admin` for the first time while offline gets the 503 fallback.
- **Audit log retention is unbounded** — no TTL or archival job. Plan a `DELETE FROM audit_log WHERE ts < now() - interval '90 days'` cron for production.
- **Audit writes are best-effort** — under SQLite lock contention the row is dropped with a `logger.warning`. A future phase can add an async write queue + retry.
