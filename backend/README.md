# AI Inbox Triage — Backend

Phase 1 backend: ingest emails, triage with **Ollama** (local LLM), extract structured fields, persist in **SQLite**, expose REST API for the frontend.

## Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com/) installed and running

```bash
ollama pull llama3.2
ollama serve
```

## Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
copy .env.example .env
```

## Run API

```bash
uvicorn main:app --reload
```

Open http://127.0.0.1:8000/docs for interactive API documentation.

## Example flow

```bash
# Create a message
curl -X POST http://127.0.0.1:8000/messages ^
  -H "Content-Type: application/json" ^
  -d "{\"email\":{\"subject\":\"VOD.L stock stopped trading\",\"body\":\"POV order PUKOID3234234234 stopped\"}}"

# Analyze (calls Ollama — replace {id} with UUID from previous response)
curl -X POST http://127.0.0.1:8000/messages/{id}/analyze

# Fetch message + analysis
curl http://127.0.0.1:8000/messages/{id}

# List inbox
curl http://127.0.0.1:8000/messages

# Get / update triage guide (JSON)
curl http://127.0.0.1:8000/guide
```

## Configuration (.env)

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `ollama` | `ollama` \| `openai` \| `anthropic` \| `mock` |
| `LLM_MODEL` | `llama3.2` | Model id for the selected provider |
| `LLM_API_KEY` | _(empty)_ | Required for `openai` and `anthropic`; not used for `ollama` or `mock` |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama API base (`LLM_PROVIDER=ollama`) |
| `OLLAMA_TIMEOUT_SECONDS` | `120` | HTTP timeout for all LLM providers |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible API base |
| `ANTHROPIC_BASE_URL` | `https://api.anthropic.com` | Anthropic API base |
| `ANTHROPIC_VERSION` | `2023-06-01` | Anthropic API version header |
| `MAX_LLM_RETRIES` | `2` | Retries on invalid JSON |
| `DATABASE_URL` | `sqlite:///./data/inbox.db` | SQLite path |

**Providers**

- **ollama** — local dev default; run `ollama serve` and `ollama pull` for `LLM_MODEL`.
- **openai** — Chat Completions via `httpx`; set `LLM_API_KEY` and a chat model (e.g. `gpt-4o-mini`).
- **anthropic** — Messages API via `httpx`; set `LLM_API_KEY` and a Claude model id.
- **mock** — deterministic keyword-based JSON for tests and offline demos; no API key and no network.

Switch provider by changing `LLM_PROVIDER` only; the classifier and API routes stay the same.

## Architecture

```
POST /messages          → save raw email
POST /messages/{id}/analyze → preprocessor + guide + Ollama → validate → SQLite
GET  /messages/{id}     → raw + latest analysis
GET  /guide / PUT /guide → editable triage policy (JSON in DB)
```

**Phase 3 (planned):** email listener / IMAP → same ingest pipeline

## Replies (Phase 2) — AI draft, human approval, mock send

The AI **drafts** a customer-facing reply; a human **edits/approves**, and only an
**approved** reply can be (mock) **sent**. This is a second, independent LLM call from
triage, so each is testable in isolation. Reply generation returns JSON `{"reply": "..."}`,
which is validated (non-empty, length-bounded) before anything is persisted.

### State machine

```
              POST /draft-reply (requires analysis)
                 │
                 ▼
   (none) ─▶ [draft] ──PATCH──▶ [edited] ──approve──▶ [approved] ──send(mock)──▶ [sent]
                 │  approve (as-is) ▲    │ edit re-opens (clears approved_by)        ▲
                 └──────────────────┘    └────────────────────────────────────────────
        send is rejected with 409 from any status other than `approved`
        regenerating (POST /draft-reply again) creates a NEW draft row → must be re-approved
```

Safety invariant: **nothing is sent without explicit human approval.** Sending a reply
that is not `approved` returns **409 Conflict**; editing an approved reply clears the
approval so it must be re-approved before it can be sent.

### Endpoints

| Method | Path | Purpose | Notable status codes |
|--------|------|---------|----------------------|
| `POST`  | `/messages/{id}/draft-reply` | Generate + store a draft (body: optional `{"tone": "professional"}`) | `201`; `409` if not analyzed; `422` generation failed; `503` provider down |
| `GET`   | `/messages/{id}/reply` | Latest reply for the message | `200`; `404` if none |
| `PATCH` | `/messages/{id}/reply` | Save a human edit (body: `{"edited_text": "...", "editor": "user"}`) → `edited` | `200`; `404`; `409` if already sent |
| `POST`  | `/messages/{id}/reply/approve` | Approve (body: optional `{"approved_by": "user"}`) → `approved` | `200`; `404`; `409` if already sent |
| `POST`  | `/messages/{id}/reply/send` | **Mock** send (body: optional `{"actor": "user"}`) → `sent` | `200`; **`409` unless `approved`**; `404` |

On failed generation the latest analysis is flagged `needs_review`, each attempt is logged
to `reply_attempts`, and no draft is persisted. Every transition writes an audit event
(`draft_created`, `reply_edited`, `reply_approved`, `reply_sent`) visible via
`GET /messages/{id}/audit`. **No real SMTP is integrated; "send" is a mock that only marks state + audits.**

### Example flow

```bash
# 1. Draft a reply (message must already be analyzed)
curl -X POST http://127.0.0.1:8000/messages/{id}/draft-reply

# 2. (optional) Edit it
curl -X PATCH http://127.0.0.1:8000/messages/{id}/reply ^
  -H "Content-Type: application/json" -d "{\"edited_text\":\"Thanks, we're on it.\"}"

# 3. Sending before approval is blocked (409)
curl -X POST http://127.0.0.1:8000/messages/{id}/reply/send   # -> 409 Conflict

# 4. Approve, then send (mock)
curl -X POST http://127.0.0.1:8000/messages/{id}/reply/approve -d "{\"approved_by\":\"alice\"}"
curl -X POST http://127.0.0.1:8000/messages/{id}/reply/send    -d "{\"actor\":\"alice\"}"
```

Run the whole flow offline with `LLM_PROVIDER=mock` (no GPU, no keys, no network).

## Tests

```bash
pytest
```

Unit tests use `mock` or `httpx` monkeypatches — no live LLM or network required.

## Troubleshooting

- **503 Cannot reach provider** — for Ollama, run `ollama serve`; for cloud providers, check network and `LLM_API_KEY`.
- **422 Analysis failed after N attempts** — model returned invalid JSON; check `analysis_attempts` via audit endpoint or DB.
- Switch model: set `LLM_MODEL=mistral` (or any pulled model) in `.env`.
