# LegalGuard AI

Agentic contract risk & compliance governance platform. AI recommends;
the lawyer decides — see
[LegalGuard_AI_End_to_End_Implementation_Plan.md](LegalGuard_AI_End_to_End_Implementation_Plan.md)
for the full architecture this implementation follows, and
[CLAUDE.md](.claude/CLAUDE.md) for the working rules (plan-first, no dead code)
this repo is developed under.

This is the foundation slice: a real, working backend covering the
plan's roadmap steps 01–14 (project setup through audit), plus real
accounts and a hand-styled dashboard. Everything runs against a
PostgreSQL database — Aiven in the real deployment, any Postgres for
local dev — with a deterministic mock LLM, so no LLM API key or payment
is required to run or test it. See "What's implemented" and "What's
deferred" below for the exact scope.

## Setup

```
uv pip install -r requirements.txt      # installs into legalenv/
```

Copy `.env.example` to `.env` if you want to override anything — every
setting has a working, zero-setup default, including `DATABASE_URL`
(local SQLite). To use Postgres instead (Aiven or otherwise), set
`DATABASE_URL` to your connection string — for Aiven: console → your
service → Connection information → Service URI, with the scheme swapped
to `postgresql+psycopg://` (Aiven requires TLS, hence `?sslmode=require`).
`.env` is gitignored; the placeholder in `.env.example` is never a real
credential.

There is **no signing secret to configure anywhere** — logins are opaque
session tokens looked up in the database (`users`/`user_sessions`
tables), not JWTs. See `app/services/auth_service.py` for why. A session
lapses after `SESSION_INACTIVITY_MINUTES` (default 180 = 3 hours) with
no requests — every authenticated request slides it forward, so only
genuine idleness logs you out — and the cookie itself has no expiry
date, so closing the browser ends the session too (see
`app/api/deps.py`, `app/api/auth.py`).

## Run

```
python main.py
```

(equivalent to `uvicorn main:app --reload`, just shorter to type.)

Open `http://127.0.0.1:8000/` — the first thing you'll see is the
login/register page (`frontend/`). There are no roles: every account can
upload, analyze, and review a contract — but only *its own* contracts.
Visibility is scoped per account (`Contract.uploaded_by`): a contract ID
that belongs to someone else 404s exactly like one that doesn't exist,
so accounts can't enumerate or peek at each other's data (see
`require_owned_contract` in `app/api/deps.py`). `http://127.0.0.1:8000/docs`
is still there for the raw API (Swagger UI) — it authenticates the same
way the dashboard does, via the session cookie your browser already has
once you're logged in. `/health` is a plain liveness check.

### Typical flow

1. Register (or log in) — any account can do everything below, scoped to
   the contracts it uploads.
2. `POST /contracts/upload`, then `POST /contracts/{id}/analyze` — runs
   the full agent workflow (intake → clauses → risk → deadlines →
   compliance → governance).
3. `GET /contracts/{id}/risks`, `/clauses`, `/deadlines`, `/audit/{id}`.
4. `POST /contracts/{id}/review` or `POST /risks/{id}/approve|reject` —
   the only calls that can set an approved/rejected decision, and
   identity for them comes from the session, not anything the client
   sends; see `app/governance/` for why that's structural, not a
   convention. There's no role gate on *who* can call these — only that
   it's an authenticated human, not the AI, matching the plan's core
   principle (AI recommends, a human decides — RULE-001) — and only on
   a contract the caller owns.

## Test

```
uv run pytest
```

Runs against the **same real database** `DATABASE_URL` points at — no
local SQLite, no separate test database. Every test wraps its work in a
transaction that's always rolled back at the end (SQLAlchemy's
documented `join_transaction_mode="create_savepoint"` pattern — see
`tests/conftest.py`), so nothing persists and real data is never at
risk, but a run does need network access to your database and is slower
than an offline suite would be. Covers document parsing, deadline math,
every governance rule (including the plan's required "AI tries to
approve → BLOCK" style cases), every agent against the mock LLM,
registration/login/logout, and a full upload → analyze → review API
flow authenticated as real accounts.

## What's implemented

FastAPI backend, PostgreSQL via SQLAlchemy (Aiven in production, any
Postgres locally), real email/password accounts with bcrypt-hashed
passwords and database-backed sessions (no JWT, no secret key, no
roles — every account can do everything once logged in, but only to the
contracts it uploaded itself — see the ownership note above), PDF/DOCX text
extraction, all 5 agents (intake, clause, risk, deadline, compliance)
orchestrated by a real `agent_framework` (Microsoft Agent Framework)
workflow, a deterministic governance layer enforcing RULE-001 through
RULE-008, full audit logging (including auth events), review/override
endpoints, the 90/30/7-day deadline-check logic, and a hand-styled
dashboard covering the plan's Lawyer Dashboard (section 21/36) —
login/register, contract list with drag-and-drop upload, a contract
detail view with an animated risk gauge, compliance checklist, and the
approve/reject/request-changes flow, a deadlines view, and an audit
trail.

## What's deferred

Documented in detail in the implementation plan file linked above; in
short — a React rebuild of the frontend (not needed; the current one
covers the same ground), real Microsoft Entra ID auth (real
email/password accounts exist now, but Entra ID specifically, and the
plan's ADMIN/LAWYER/REVIEWER/EMPLOYEE role table, are a deliberate
simplification for this stage — see the "no roles" note above), Azure AI
Search RAG (policies are plain Python data for now), Azure Functions
scheduling (the deadline check logic is real, just triggered manually
via `POST /deadlines/check` instead of on a timer), a real LLM provider
(the mock is the only implementation of the pluggable
`app/llm/client.py` seam today), Docker/CI/CD, Azure deployment, and the
governance-metrics dashboard / 100-contract evaluation harness.

## Project structure

```
main.py                FastAPI app factory (mounts the API, then the frontend)
config.py               environment-driven settings (DATABASE_URL, session inactivity timeout, ...)
app/
├── api/                route handlers (auth, contracts, risks, deadlines, reviews, dashboard)
├── agents/             the 5 MAF agents + shared LLM-call helper
├── workflows/          the agent_framework Workflow chaining them
├── governance/         RULE-001..008, policy definitions, decision evaluator, audit logging
├── llm/                pluggable chat-client factory + the mock implementation
├── services/           document parsing, deadline checks, notification stub, password/session hashing
├── database/           SQLAlchemy models, engine/session, query helpers
├── schemas/            Pydantic request/response models
└── logging_config.py   console + rotating-file logging setup (logs/app.log)
frontend/               the dashboard UI, incl. login/register (static HTML/CSS/JS, no build step)
policies/               human-readable policy documents
tests/                  mirrors the structure of app/
```
