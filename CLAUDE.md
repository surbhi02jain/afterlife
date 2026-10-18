# Virasat — find and claim what your loved one left behind (hackathon project)

Virasat helps a grieving Indian family find and claim the deceased's financial assets.
The family uploads whatever documents they have (statement photos, SMS/UPI screenshots,
policy receipts). Virasat (1) extracts structured data, (2) infers assets that probably exist
but weren't uploaded, (3) builds a per-institution action plan, and (4) drafts claim letters.

Built for the Google Cloud AI Builder Cup. ~36 hours total; the 3-minute demo path must be rock solid.

## Non-negotiable constraints
- **All AI goes through Google Gemini via the official `google-genai` Python SDK.** No other LLM providers.
  - API key from env `GEMINI_API_KEY`.
  - Model IDs from env `EXTRACTION_MODEL` (default `gemini-3.8-flash`) and `REASONING_MODEL`
    (default `gemini-4-argon`). Defaults were checked against https://ai.google.dev/gemini-api/docs/models
    on 2026-10-16. Re-check the docs before changing them; never guess model IDs.
  - Use `client.models.generate_content` with `response_json_schema=<PydanticModel>.model_json_schema()`
    and validate the reply with Pydantic. Created in one place: `backend/app/gemini.py`; always call
    through `gemini.generate()` (per-model RPM throttle via `GEMINI_RPM`, honours 429 retry delays). The one
    exception is the agent: Google ADK makes its model calls, with the same throttle applied in a before-model callback.
  - **Quota (found 2026-10-16):** the free tier allows ~5 RPM and **20 requests/day per model**, and
    `gemini-4-argon` has a free-tier limit of **0**. Local `.env` therefore sets `REASONING_MODEL=gemini-3.6-flash`
    until billing is enabled (a different free model from extraction, so each gets its own daily quota; free models
    per the pricing page on 2026-10-17: 3.8-flash, 3.6-flash, 3.5-flash-lite, 3.1-flash-lite, 3-flash-preview). Don't burn quota: use `--replay` / `--missing` flags and recorded fixtures.
- **Deployable to Google Cloud Run** as ONE container: a multi-stage Dockerfile builds the frontend and FastAPI serves it.
- **No real personal data anywhere.** Demo data is synthetic, uses fictional institutions, and is watermarked.
- **No silent fallbacks.** If a Gemini call fails or a response doesn't validate, surface the error and fix the
  root cause. Never substitute fake data.
- Out of scope: real bank/insurer integrations, payments, e-signing, legal filings.

## Product guardrails (enforce in prompts AND code)
- Inferred ("probable") assets are never presented as facts. They always carry evidence + confidence.
- Legal/succession topics: "guidance, not legal advice".
- Refuse any request to use the deceased's cards, PINs, passwords or credentials.
- Procedures come only from `backend/kb/procedures.json` and cite `source_name`; if nothing is found,
  say "please confirm with the institution".
- Warm, simple language; English or Hindi per the case's `language`.
- Deterministic code (not the model) for totals, date/deadline arithmetic, identifier masking (last 4 only)
  and identifier format validation.

## Stack
- Backend: Python 3.11+ (local venv uses 3.14; Docker uses 3.12), FastAPI, Pydantic v2, uvicorn.
- Frontend: React + Vite + Tailwind in `/frontend`, built to static files served by FastAPI.
- Storage: interface in `backend/storage/base.py`, chosen by `STORAGE_BACKEND=local|gcp`.
  `local` = JSON files + uploads under `LOCAL_DATA_DIR` (default `./data`); `gcp` = Firestore (cases) +
  Cloud Storage (uploads, auto-deleted after 24h by a bucket lifecycle rule).
- Tests: pytest. **Tests never call the live Gemini API.** They use real Gemini replies recorded in
  `demo/recorded/` or a fake client.

## Repo layout
```
backend/
  app/        FastAPI app (main.py), config.py, models.py (all Pydantic models), gemini.py (client)
  tools/      model-backed + deterministic tools (extraction.py, ...)
  agent/      Virasat agent on Google ADK (Agent Development Kit), tools, guardrails
  kb/         procedures.json knowledge base (Phase 3)
  storage/    base.py interface, local.py, gcp.py
  tests/      pytest (no network)
frontend/     React + Vite + Tailwind (Phase 4)
scripts/      make_demo_docs.py, run_extraction.py, deploy.sh (Phase 5)
demo/         synthetic demo docs/, recorded/ real Gemini replies for them, README of what is planted
Dockerfile, README.md, DEMO.md, CLAUDE.md
```

## Commands (run from repo root)
```bash
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements-dev.txt   # setup
cp .env.example .env    # then put your GEMINI_API_KEY in .env

.venv/bin/pytest backend                                   # tests (no network)
(cd frontend && npm install && npm run build)              # build UI into frontend/dist (served by FastAPI)
(cd frontend && npm run dev)                               # UI dev server on :5173, proxies /api to :8000
docker build -t afterlife . && docker run -p 8080:8080 -e STORAGE_BACKEND=local -e LOCAL_DATA_DIR=/tmp/data afterlife
GEMINI_API_KEY=... ./scripts/deploy.sh                     # Cloud Run deploy (user runs it after gcloud auth)
# GcpStorage against emulators: see the docstring in backend/tests/test_gcp_storage.py
.venv/bin/uvicorn app.main:app --app-dir backend --reload  # API on http://localhost:8000
.venv/bin/python scripts/make_demo_docs.py                 # regenerate demo/docs/*.png
.venv/bin/python scripts/run_extraction.py                 # live extraction on demo docs (needs key)
.venv/bin/python scripts/run_extraction.py --record        # ...and save responses as test fixtures
.venv/bin/python scripts/run_extraction.py --record --missing   # ...only docs without a fixture
.venv/bin/python scripts/record_samples.py --record   # record replies for the voice memo, sample replies, name check
.venv/bin/python scripts/run_demo_case.py --replay         # full demo case: recorded extraction + live inference,
                                                           # then checks both planted assets are found (exit 1 if not)
.venv/bin/python scripts/run_agent_demo.py                 # Phase 3: live agent on the demo case; prints activity
                                                           # log, plan, a letter (add --hi for Hindi)
```

## Conventions
- Keep code simple and readable; prefer working over clever. Sync FastAPI endpoints are fine.
- All Pydantic models live in `backend/app/models.py`. They are the API contract and the Gemini schemas.
- Dates are ISO `YYYY-MM-DD` strings in model output; amounts are plain numbers in INR.
- Case mutations go through `storage.update_case(case_id, fn)`, which is atomic per backend (lock or Firestore
  transaction). Do slow Gemini calls *outside* that function.
- Work in phases. Finish each phase, run it, show real output, then make one commit per phase.
- Imports are rooted at `backend/` (`from app.models import ...`, `from storage import ...`).
- Agent (`agent/loop.py`): Google ADK `LlmAgent` + `InMemoryRunner` over Gemini, max 10 model calls (`RunConfig.max_llm_calls`), tools in `agent/tools.py` dispatch to
  `app/services.py`, which writes every activity-log entry (en + hi). Guardrails in `agent/guardrails.py` run in
  code: credential requests are refused before any model call; legal topics get "guidance, not legal advice".
- Plan (`tools/plan.py`), letters (`tools/letters.py`) and procedure lookup (`kb/`) are deterministic. Procedural
  text comes only from `backend/kb/procedures.json` (all `verified: false` placeholders for now).
- Frontend (`frontend/src`): React + Tailwind v4, hash routes `#/case/<id>/<screen>`, every
  string in `i18n.js` (en + hi), 18px base font, one primary action per screen (`PrimaryBar`). The API returns
  `case_view()` (no raw extractions or storage keys). If the npm cache errors with EACCES, set `npm_config_cache`
  to a writable folder.
- Demo cases replay the REAL recorded extraction for byte-identical demo docs (`app/demo.py`,
  `DEMO_REPLAY_EXTRACTION`), logged as a "saved reading". Real uploads always go live. The same holds for the sample
  voice memo, the two sample replies (`demo/samples/`) and the demo name check: `demo.recorded(kind, input_bytes)`
  replays `demo/recorded/{memory,replies,names}/*.json`, written by `scripts/record_samples.py --record`.
- Memories (`tools/memories.py`), name check (`tools/names.py`), institution replies (`tools/replies.py`): Gemini
  reads/listens/compares; code decides. Memory confidence comes from matched transactions (none = low); name findings
  must quote names exactly as on the cited document; a reply with any scam signal (`guardrails.scam_signals`, plus
  Gemini's red flags) changes nothing in the case. Recordings and reply files are read once and never stored.
- Evidence descriptions mask any 6+ digit run to the last 4 (`Evidence.mask_numbers`).
- Asset map (`tools/asset_map.py`): confirmed items come deterministically from extracted documents; inferred items
  (`tools/inference.py`) are only ever `probable`, must cite real transaction ids, and merge through the same
  `upsert()` dedup path. `decided_by_user` items are never changed by rebuilds. Items store only the masked
  identifier; full numbers stay in the document extraction.
