# OSIRIS Imhotep — Engineering Scope of Work (SOW) Web App

A full-stack engineering AI assistant MVP. Engineers provide **field notes**
and optional site media; **Gemini 2.5 Flash** extracts visual evidence from
photos and sampled video frames, then **DeepSeek** returns a
structured, tabular **Scope of Work** that can be exported to a **styled
Google Doc**.

```
┌───────────────────┐        ┌──────────────────────────────────────────────┐
│   React/Next.js   │  /api  │  FastAPI                                      │
│   chat UI (3000)  │◄──────►│  ├─ media_processor  (images + video frames)  │
│   · notes + media │  proxy │  ├─ gemini_vision    (visual evidence)        │
│   · loading state │        │  ├─ deepseek_service (structured SOW JSON)    │
│   · SOW tables    │        │  ├─ prompt_builder   (modular prompt)         │
│   · loading state │        │  ├─ rag_provider     (RAG plug-in seam)       │
│   · SOW tables    │        │  └─ gdoc_service     (Google Docs export)     │
│   · export button │        └──────────────────────────────────────────────┘
└───────────────────┘
```

---

## 1. Prerequisites

- **Python 3.10+** (developed on 3.12)
- **Node.js 18.17+** (developed on 24)
- A **DeepSeek API key** → <https://platform.deepseek.com/api_keys>
- A **Gemini API key** for vision → <https://aistudio.google.com/apikey>
- (Optional) a **Google Cloud service account** with Docs + Drive scopes for
  the Google Doc export

## 2. Backend setup

Run everything in **Windows PowerShell 5.1+** (PowerShell 7+ also works). Note:
`&&` is **not** a valid separator in Windows PowerShell 5.1 — run the commands
one per line, or join them with `;`.

```powershell
# from the project root
cd backend

python -m venv .venv
.venv\Scripts\activate                 # Windows PowerShell
# source .venv/bin/activate            # macOS / Linux (bash)

pip install -r requirements.txt
copy .env.example .env                 # then add DEEPSEEK_API_KEY and GEMINI_API_KEY

uvicorn app.main:app --reload --port 8000
```

Smoke test (second terminal):

```powershell
curl.exe http://localhost:8000/api/health
# {"status":"ok","model":"deepseek-chat","grounding":false,...}
```

### Backend environment variables (`backend/.env`)

| Variable | Purpose |
| --- | --- |
| `DEEPSEEK_API_KEY` | **Required.** DeepSeek API key |
| `DEEPSEEK_MODEL` | `deepseek-chat` (default) |
| `GEMINI_API_KEY` | Required when analyzing photos or video clips |
| `GEMINI_VISION_MODEL` | `gemini-2.5-flash` (default) |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Path to SA JSON key for Google Docs export |
| `GOOGLE_OAUTH_TOKEN_FILE` | Alternative OAuth user token |
| `GOOGLE_DOCS_IMPERSONATE` | (Domain-wide delegation) email to impersonate |
| `RAG_PROVIDER` / `RAG_ENDPOINT` / `RAG_API_KEY` | Future RAG/vector-DB plug-in (see §5) |

## 3. Frontend setup

In a **second PowerShell terminal** (leave the backend running):

```powershell
cd frontend
npm.cmd install        # .cmd shim avoids the PowerShell execution-policy block
npm.cmd run dev        # http://localhost:3000
```

> **Quick start (no typing):** double-click `dev-backend.cmd` and
> `dev-frontend.cmd` in the project root — each opens its own window with the
> correct working directory and the `npm.cmd` workaround already applied.
>
> **Why `npm.cmd`?** Windows PowerShell 5.1 ships with a default
> `Restricted` execution policy that refuses to run `npm` (a `.ps1` script),
> producing `SecurityError / UnauthorizedAccess`. Using `npm.cmd` skips the
> policy check entirely. To enable plain `npm` commands, run once:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
>
> Also note: `&&` chains from bash-style guides do not work in PowerShell
> 5.1 — use separate lines (`cd frontend` then `npm.cmd run dev`) or `;`.

Next.js proxies `/api/*` → `http://localhost:8000/api/*` (override with
`BACKEND_URL`). The browser only ever talks to the Next origin, so there are
no CORS issues in dev (the backend still sends permissive CORS headers).

## 4. API

### `POST /api/sow/generate` — multipart

| Field | Type | Notes |
| --- | --- | --- |
| `notes` | `string` (form) | Engineer field notes |
| `site` | `string` (form) | Optional site / facility |
| `client` | `string` (form) | Optional client name |
| `files` | file(s) | Optional images (`jpg/png/webp/bmp/tiff`) and clips (`mp4/mov/avi/webm`) analyzed by Gemini Vision |

Returns:

```json
{
  "sow": {
    "project_title": "...",
    "executive_summary": {...},
    "visual_findings": [...],
    "recommended_services": [...],
    "scope_breakdown": [...],
    "cost_breakdown": {...}
  },
  "media_log": [...],
  "model": "deepseek-chat",
  "grounding": false,
  "grounding_sources": [],
  "context_provider": "null",
  "generated_at": "..."
}
```

### `POST /api/sow/export-gdoc` — JSON

```json
{ "sow": { ...SOW payload... }, "owner_email": "engineer@company.com" }
```

Returns `{ "doc_url": "https://docs.google.com/document/d/<id>/edit", "doc_id": "..." }`.

> **Google Docs auth note (MVP):** with a service account the doc is owned by
> the SA. Pass `owner_email` so the doc is shared with the requesting engineer,
> or use domain-wide delegation (`GOOGLE_DOCS_IMPERSONATE`).

## 5. Extensibility / RAG plug-in

The prompt and context pipeline is fully abstracted behind
`app/core/context_provider.py` (`ContextProvider` interface). The MVP ships
the `null` provider; to plug in a private vector DB for company pricing/SOPs:

1. Implement retrieval in `app/services/rag_provider.py`
   (an `HttpRagContextProvider` skeleton is already there).
2. Set `RAG_PROVIDER=vector` + `RAG_ENDPOINT` in `backend/.env`.

No route or UI changes are required — context documents are injected into the
system prompt by `PromptBuilder` and cited in the model output.

## 6. Project layout

```
backend/
  app/
    main.py                  # FastAPI app + CORS + lifespan
    config.py                # pydantic-settings (env / .env)
    api/routes.py            # POST /api/sow/generate, /api/sow/export-gdoc, /health
    models/schemas.py        # Pydantic SOW response models
    core/context_provider.py # ContextProvider interface (RAG seam)
    services/
      media_processor.py     # image normalize + video frame sampling (OpenCV)
      prompt_builder.py      # system/user prompt assembly
      gemini_vision_service.py # Gemini 2.5 Flash visual evidence extraction
      deepseek_service.py    # DeepSeek structured SOW generation
      rag_provider.py        # null + vector RAG providers
      gdoc_service.py        # Google Docs styled export
frontend/
  app/                       # Next.js App Router (page, layout, globals)
  components/                # ChatInput, LoadingIndicator, SowReport, ExportButton, badges
  lib/                       # api client + TS types
```

## 7. Tests

Standalone smoke tests live in `backend/` (run them from `backend/` with the venv):

```powershell
.venv\Scripts\python.exe smoke_test.py       # imports, routes, SOW coercion, prompts
.venv\Scripts\python.exe test_media.py       # image + video frame pipeline (OpenCV)
.venv\Scripts\python.exe test_endpoints.py   # /api/health, 400/502/503 behaviour (TestClient)
```

End-to-end flow (manual): start the backend, then in a second PowerShell
terminal run `cd frontend` followed by `npm.cmd run dev`.

## 8. Deployment (Google Cloud Run + GitHub Actions)

Pushing to `main` triggers a GitHub Actions workflow that tests the backend,
builds both Docker images, pushes them to Artifact Registry, and deploys two
Cloud Run services (FastAPI backend + Next.js frontend) with:

- **Cloud SQL (PostgreSQL)** for persistent logins (SQLite remains the local
  dev default — set `DATABASE_URL` to switch).
- **Secret Manager** for API keys, JWT secret, superadmin password, the DB URL,
  and the Google Docs service-account key.
- **Workload Identity Federation** — GitHub authenticates to GCP without any
  stored service-account keys.

One-time setup (Cloud Shell, ~10 min):

```bash
bash deploy/bootstrap.sh     # or: bash <(curl -s https://raw.githubusercontent.com/rummii/OSIRIS-Imhotep/main/deploy/bootstrap.sh)
```

Then add the 3 printed values as GitHub Actions secrets and push. Full walkthrough,
costs, rollback and troubleshooting: **`deploy/gcp-setup.md`**.

## 9. Notes & limitations

- Gemini Vision supplies evidence only; DeepSeek remains responsible for the
  final structured SOW. Both API keys are required for requests containing media.
- HEIC/RAW images and exotic video codecs are skipped with a manifest note
  (OpenCV can't decode them).
- The generated SOW is an **AI draft** — always review before issuing.
- **OneDrive caveat:** the project lives under OneDrive, whose sync can
  corrupt native binaries (`*.node`) and race with build-artifact churn
  (`node_modules`, `.next`). If `npm install` or `next build` ever fails with
  "not a valid Win32 application" or transient `ENOENT`, run
  `npm cache clean --force` then `npm install` again, and if it persists,
  exclude the project folder from OneDrive sync (or keep it always
  on-device).

