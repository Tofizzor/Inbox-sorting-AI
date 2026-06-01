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

**Phase 2 (planned):** draft reply, approve/edit, mock send  
**Phase 3 (planned):** email listener / IMAP → same ingest pipeline

## Tests

```bash
pytest
```

Unit tests use `mock` or `httpx` monkeypatches — no live LLM or network required.

## Troubleshooting

- **503 Cannot reach provider** — for Ollama, run `ollama serve`; for cloud providers, check network and `LLM_API_KEY`.
- **422 Analysis failed after N attempts** — model returned invalid JSON; check `analysis_attempts` via audit endpoint or DB.
- Switch model: set `LLM_MODEL=mistral` (or any pulled model) in `.env`.
