# AI Research Stack V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable v1 AI research stack with Postgres-owned orchestration, demand-witness scoring, budget control, Slack approvals, and a monitoring dashboard.

**Architecture:** Python services own the control plane. Postgres stores authoritative state, Redis acts as wake-up bus, workers execute typed agent tasks, and FastAPI serves Slack endpoints plus a lightweight dashboard.

**Tech Stack:** Python 3.11, FastAPI, psycopg, Redis, Postgres, Docker Compose, pytest, ruff, OpenRouter HTTP API, Anthropic HTTP API, Slack signed requests.

---

## File Structure

- `src/ai_research_stack/domain.py`: enums and dataclasses for opportunities, scores, witnesses, tasks, and budget records.
- `src/ai_research_stack/scoring.py`: demand gate, weighted scores, confidence computation, express lane eligibility.
- `src/ai_research_stack/budget.py`: per-day, per-month, per-task, and per-opportunity budget decisions.
- `src/ai_research_stack/tasks.py`: task leasing, result recording, retry decisions, and idempotency helpers.
- `src/ai_research_stack/repository.py`: repository interface plus in-memory implementation for tests.
- `src/ai_research_stack/postgres.py`: Postgres SQL repository implementation.
- `src/ai_research_stack/schema.sql`: production Postgres schema.
- `src/ai_research_stack/models.py`: model registry and role selection.
- `src/ai_research_stack/prompts.py`: high-leverage agent prompts.
- `src/ai_research_stack/agents.py`: typed stateless agent handlers and local deterministic development handlers.
- `src/ai_research_stack/orchestrator.py`: stage transitions and task creation.
- `src/ai_research_stack/slack.py`: Slack signature verification, command handling, and action parsing.
- `src/ai_research_stack/api.py`: FastAPI app, health checks, dashboard JSON endpoints, Slack endpoints.
- `src/ai_research_stack/dashboard.py`: code-native operator console HTML.
- `src/ai_research_stack/worker.py`: worker loop that leases tasks and executes handlers.
- `src/ai_research_stack/scheduler.py`: periodic frontier tracker and daily digest task creation.
- `tests/`: focused tests for scoring, budget, task leasing, Slack signatures, and prompt contracts.
- `docker-compose.yml`: Postgres, Redis, API, worker, and scheduler services.
- `Dockerfile`: Python service image.
- `.env.example`: required configuration keys and caps.

## Tasks

### Task 1: Core Scoring and Budget Tests

- [ ] Write tests for demand witness gate, weighted score, express lane exclusion for proxy witnesses, computed confidence, and opportunity budget thresholds.
- [ ] Run `python -m pytest tests -q` and confirm the tests fail because modules are missing.
- [ ] Implement `domain.py`, `scoring.py`, and `budget.py`.
- [ ] Run `python -m pytest tests -q` and confirm these tests pass.

### Task 2: Task Leasing and Repository

- [ ] Write tests proving task leases are exclusive, expired leases can be reclaimed, idempotency keys prevent duplicate open tasks, and retry caps stop failed tasks.
- [ ] Run the task tests and confirm failure from missing repository/task code.
- [ ] Implement `repository.py` and `tasks.py` with an in-memory repository.
- [ ] Run the tests and confirm pass.

### Task 3: Prompts and Model Registry

- [ ] Write tests checking the frontier tracker, saturation checker, obvious-wrapper detector, and Claude critic prompts contain the required output fields and legal constraints.
- [ ] Write tests for model role selection and inactive model exclusion.
- [ ] Implement `prompts.py` and `models.py`.
- [ ] Run tests and confirm pass.

### Task 4: Orchestrator

- [ ] Write tests for watchlist routing, normal research routing, express lane routing, and hard-stop legal/builder-fit routing.
- [ ] Implement `orchestrator.py` using repository events and task creation.
- [ ] Run tests and confirm pass.

### Task 5: Slack Interface

- [ ] Write tests for Slack signature verification, `/ask-tracker` budget policy, and button action parsing.
- [ ] Implement `slack.py`.
- [ ] Run tests and confirm pass.

### Task 6: API and Dashboard

- [ ] Implement `api.py` with `/health`, `/api/opportunities`, `/api/tasks`, `/api/budget`, `/slack/commands`, `/slack/actions`, and `/`.
- [ ] Implement `dashboard.py` with a monitoring-first operator console.
- [ ] Add basic API tests using FastAPI's test client if dependencies are available.

### Task 7: Production Adapters and Deployment Files

- [ ] Implement `schema.sql` and `postgres.py` with Postgres task leases using `FOR UPDATE SKIP LOCKED`.
- [ ] Add `.env.example`, `Dockerfile`, and `docker-compose.yml`.
- [ ] Add `README.md` with local setup, production setup, Slack app setup, and operating rules.

### Task 8: Verification

- [ ] Run `python -m pytest tests -q`.
- [ ] Run `python -m compileall src tests`.
- [ ] Run `python -m ruff check .` if ruff is installed.
- [ ] Record any commands that cannot run because dependencies are unavailable.
