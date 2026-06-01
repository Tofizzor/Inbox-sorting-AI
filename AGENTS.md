# Agent instructions — Shared Engineering Standards

Every agent working on this repository must follow these standards. Phase prompts in `docs/agent_build_plan.md` reference this file instead of repeating them.

## Architecture & safety

- The AI **suggests**; humans **approve** anything that leaves the system (replies, sends, escalation).
- Never trust model output for control flow. `destination`/routing is computed in Python, never read from the model. Validate all LLM JSON against Pydantic before persistence.
- Invalid/failed AI output must set `needs_review` and be logged in `analysis_attempts` — never silently overwrite good data.
- Respect existing module boundaries: `models/` (domain + LLM contract), `schemas/` (HTTP I/O), `services/` (logic), `routers/` (endpoints), `db/` (persistence). Do not collapse them.

## Backend (Python / FastAPI)

- Python 3.11+, full type hints, Pydantic v2.
- Keep functions small and pure where possible; side effects live in `services`/`db`.
- HTTP error contract: `503` when the model provider is unreachable, `422` when analysis fails validation after retries, `404` for missing entities, `400` for bad input.
- Add or update tests for any risky logic you touch. Tests must pass **without a live LLM** (mock it).

## Frontend (React / TypeScript)

- Vite + React + TypeScript + Tailwind CSS. Function components + hooks.
- One typed API client module; no `fetch` scattered across components. Types mirror backend schemas.
- Every data view handles **loading / empty / error** states explicitly. Surface backend `503`/`422` as friendly, actionable messages.
- Make human approval visually central; show AI confidence/reasoning without overwhelming the user.
- Accessible components (labels, focus states, keyboard nav for primary actions).

## Hygiene

- No secrets in code or git. Use `.env` (gitignored) + `.env.example`.
- No narrating comments. Comment only non-obvious intent/trade-offs.
- Conventional commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`). One phase = one branch = one PR.
- Update the relevant README when behaviour or setup changes.
- Run formatters/linters and the test suite before declaring done.
