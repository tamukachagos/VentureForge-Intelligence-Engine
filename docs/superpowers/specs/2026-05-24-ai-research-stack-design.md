# AI Research Stack V1 Design

## Goal

Build a 24/7 cloud-based AI research engine that finds frontier AI startup opportunities, proves there is demand, benchmarks the market, scores opportunities, and sends promotion-ready dossiers to the founder through Slack.

V1 stops at research dossiers and approval workflows. The builder pipeline is intentionally designed but not executed in V1.

## Operating Constraints

- LLM budget: 15 USD per day.
- Paid search/data budget: 50 USD per month.
- Cloud target: Hetzner CPX41 using Docker Compose.
- Model strategy: cheap OpenRouter workers for extraction, clustering, scoring drafts, and research; Claude Sonnet for critic and dossier synthesis; Claude Opus only for rare arbitration.
- Local embeddings: BGE/FastEmbed-style local embedding adapter, with deterministic fallback for development and tests.
- Legal limits: no private data scraping, no access-control bypasses, no autonomous outreach, no paid signups, no domain purchases, and no copied protected code or content.

## Core Architecture

The system uses a custom Python orchestrator with Postgres as the source of truth.

Postgres owns tasks, leases, opportunity state, budget events, approvals, demand witnesses, evidence, scores, model registry entries, learned founder preferences, and the append-only event log. Redis is only a wake-up bus. If Redis fails, tasks are still safe in Postgres and workers resume by polling.

Only the orchestrator can change an opportunity stage. Agents append findings through typed outputs and never mutate the state machine directly.

## V1 Pipeline

1. Frontier tracker collects AI capability shifts from configured sources.
2. Discovery agents convert raw signals into candidate opportunities.
3. Deduplication clusters similar opportunities instead of deleting them.
4. Demand-witness gate blocks opportunities with no direct or proxy demand witness.
5. Cheap first-pass scoring ranks demand strength, timing, speed, distribution, defensibility window, wedge-to-platform, cash-flow path, and novelty.
6. Full research runs automatically up to 3 USD lifetime spend per opportunity.
7. Slack notifies the founder when an opportunity crosses 1 USD of lifetime spend.
8. Claude critic produces dossiers only for opportunities with demand evidence and acceptable legal/builder fit.
9. Slack sends promotion dossiers with approve, reject, deeper research, snooze, and halt actions.
10. The daily digest reports funnel state, AI direction shifts, budget, top opportunities, killed opportunities, and system health.

## Demand Witness Gate

No opportunity advances to Claude critic without at least one demand witness.

Direct witnesses include buyer complaints, paid incumbents, job posting patterns, regulatory deadlines, visible budget owners, or measurable workflow costs.

Proxy witnesses include adjacent category spend, analogous workflow budgets, role-based need, or nearby willingness-to-pay. Proxy witnesses can enter the normal funnel when timing and novelty are strong, but cannot use the express lane.

Opportunities with no witness enter the watchlist only.

## Express Lane

An opportunity can receive a 6-24 hour dossier SLA only when it has:

- direct demand witness,
- high capability timing,
- high novelty,
- acceptable legal/compliance risk,
- available budget.

Proxy witnesses are excluded from the express lane.

## Scoring

Composite scoring uses these weights:

- demand-witness strength: 0.20
- capability timing: 0.18
- speed-to-MVP: 0.13
- distribution edge: 0.13
- defensibility window: 0.10
- wedge-to-platform: 0.09
- cash-flow path: 0.09
- novelty: 0.08

Legal and builder-fit failures are hard stops. Saturation and novelty are review signals, not hard kill gates.

Confidence is computed from source diversity, freshness, contradiction count, evidence strength, and repeatability. Model self-reported confidence is logged but not used for routing.

## Agents

Agents are stateless functions with formal task/result contracts:

- task id,
- task type,
- input payload,
- budget ceiling,
- timeout,
- model role hint,
- idempotency key,
- typed output,
- cost,
- tokens,
- warnings,
- model used.

Persisted research sessions can hold scratch context across multiple stateless calls.

## Slack and Dashboard

Slack is the primary command surface for the solo founder.

V1 supports:

- daily digest,
- weekly digest hooks,
- promotion dossiers,
- slash command `/ask-tracker`,
- action buttons for approve, reject, deeper research, snooze, and halt,
- notifications at 1 USD lifetime opportunity spend,
- approvals for budget exceptions and later build gates.

The dashboard is a monitoring console. It shows opportunities, scores, tasks, budgets, approvals, model registry entries, and recent events. It is not a full editing workspace.

## Budget Controls

The budget governor tracks:

- daily LLM spend,
- monthly paid data spend,
- per-opportunity lifetime spend,
- per-task budget ceiling,
- `/ask-tracker` per-query cap of 0.10 USD,
- `/ask-tracker` daily cap of 1.50 USD,
- express lane reserved spend.

Work degrades or pauses when caps are reached.

## Data Model

Core tables:

- ai_direction_signals
- opportunities
- demand_witnesses
- evidence
- scores
- competitors_found
- tasks
- budget_events
- approvals
- builder_profile
- learned_preferences
- model_registry
- eval_set
- events
- outbox

## V1 Preconditions

Before production operation, the founder should provide:

- builder profile,
- at least 15 eval examples with rationale,
- Anthropic key,
- OpenRouter key,
- GitHub PAT,
- Slack bot token/signing secret/channel id,
- Hetzner CPX41 host with Docker Compose.

The eval set grows to 50 during the first month and is used to tune prompts, scoring, and gates.

## Non-Goals

V1 does not automatically deploy live products, send outreach, buy domains, use paid services beyond configured caps, or run generated build sandboxes. The V2 builder pipeline produces validated prototypes plus smoke-test kits after explicit founder approval.
