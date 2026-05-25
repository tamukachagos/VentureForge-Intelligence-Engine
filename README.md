# AI Research Stack

V1 is a 24/7 AI opportunity research control plane. It tracks frontier AI signals, requires demand witnesses before promotion, scores opportunities, controls LLM/data spend, and sends founder-facing dossiers and approvals through Slack.

## What V1 Includes

- Custom Python orchestrator shape with Postgres-owned tasks and leases.
- Redis-ready deployment topology, with Redis used only as a wake-up bus.
- Demand-witness hard gate.
- Weighted opportunity scoring.
- Express lane eligibility for direct-witness frontier opportunities.
- Per-day and per-opportunity budget governor.
- Slack signature verification, `/ask-tracker` handling, and action parsing.
- Outbound Slack posting for daily digests and promotion dossiers.
- Slack approval actions persisted into `approvals` and `events`.
- Monitoring-first web dashboard at `/`.
- Docker Compose stack for Hetzner.
- Deterministic development agent handlers so the stack runs before live API keys are connected.
- Live runtime switching to OpenRouter and Anthropic when model IDs and API keys are configured.
- Result persistence from completed agent tasks into signals, opportunities, witnesses, evidence, scores, budget events, and event logs.
- Scheduled source ingestion from Hacker News, GitHub search, and RSS/Atom AI feeds into frontier-tracker tasks.

## Local Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
python -m pytest tests -q
uvicorn ai_research_stack.api:app --reload
```

Open `http://127.0.0.1:8000`.

## Docker Compose

```bash
copy .env.example .env
docker compose up --build
```

Open `http://SERVER_IP:8000`.

The scheduler enqueues frontier-tracker and daily-digest tasks. The worker processes them and persists completed results into Postgres. In deterministic mode, the frontier tracker creates a development opportunity so the dashboard can be verified before live LLM keys are configured.

## Source Ingestion

The scheduler runs enabled source connectors and stores deduplicated findings as `ai_direction_signals`. It then enqueues `frontier_tracker` with the latest findings in the task payload.

Source controls:

```bash
ENABLE_HACKER_NEWS=true
ENABLE_GITHUB_SEARCH=true
ENABLE_RSS=true
GITHUB_TOKEN=
GITHUB_SEARCH_QUERY=AI agents created:>2026-01-01
RSS_FEED_URLS=https://openai.com/news/rss.xml,https://www.anthropic.com/news/rss.xml,https://huggingface.co/blog/feed.xml
```

RSS ingestion supports both RSS `<item>` feeds and Atom `<entry>` feeds.

Paid search can be enabled with a generic JSON search endpoint. It is guarded by the `MONTHLY_PAID_DATA_CAP_USD` budget and skipped with an event log entry if the next request would exceed the cap.

```bash
ENABLE_PAID_SEARCH=false
PAID_SEARCH_NAME=paid_search
PAID_SEARCH_ENDPOINT_URL=
PAID_SEARCH_API_KEY=
PAID_SEARCH_QUERY=AI agent workflow complaints
PAID_SEARCH_ESTIMATED_COST_USD=0.25
```

The endpoint is expected to accept `POST {"query": "..."}` and return one of `results`, `items`, or `data` arrays with fields such as `title`, `url`, `content`, or `snippet`.

## Slack App Setup

Create a Slack app with:

- slash command: `/ask-tracker`
- command URL: `https://YOUR_DOMAIN/slack/commands`
- interactivity URL: `https://YOUR_DOMAIN/slack/actions`
- signing secret in `SLACK_SIGNING_SECRET`
- bot token in `SLACK_BOT_TOKEN`
- channel id in `SLACK_CHANNEL_ID`

V1 verifies signed Slack requests when a signing secret is configured.

Workers post Slack messages when `SLACK_BOT_TOKEN` and `SLACK_CHANNEL_ID` are configured:

- `daily_digest` task results post a Daily Intelligence Digest.
- promoted `claude_critic` results post a Promotion Dossier with Approve, Reject, Deeper Research, Snooze, and Halt buttons.
- Slack button clicks are persisted as approval records and event log entries.

## Production Operation Rules

- LLM spend cap defaults to 15 USD/day.
- Paid data cap defaults to 50 USD/month.
- `/ask-tracker` is capped at 0.10 USD per query and 1.50 USD/day.
- An opportunity can auto-spend up to 3 USD before owner approval is required.
- Legal and builder-fit failures are hard stops.
- Saturation and novelty are review signals, not kill gates.
- V1 does not deploy products, send outreach, buy domains, or run generated-code sandboxes.

## Live Model Configuration

To enable live LLM work immediately, set `OPENROUTER_API_KEY`, `OPENROUTER_WORKER_MODEL`, `ANTHROPIC_API_KEY`, and `ANTHROPIC_CRITIC_MODEL` in `.env`. Without those values, workers use deterministic zero-cost handlers for local verification.

## Next Build Step

Add dashboard views for source quality, connector failures, paid-data spend, and source-to-opportunity conversion.
