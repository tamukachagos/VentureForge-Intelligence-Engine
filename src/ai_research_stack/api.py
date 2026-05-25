from __future__ import annotations

from datetime import datetime, timezone

from urllib.parse import parse_qs

from fastapi import FastAPI, Header, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse

from ai_research_stack.budget import BudgetPolicy, BudgetSnapshot, BudgetGovernor
from ai_research_stack.config import Settings, load_settings
from ai_research_stack.dashboard import render_dashboard
from ai_research_stack.postgres import PostgresRepository
from ai_research_stack.repository import InMemoryRepository
from ai_research_stack.slack import parse_slack_action, verify_slack_signature
from ai_research_stack.slack_actions import record_slack_action


def create_app(
    settings: Settings | None = None,
    repository: InMemoryRepository | PostgresRepository | None = None,
) -> FastAPI:
    settings = settings or load_settings()
    if repository is None and settings.database_url:
        repository = PostgresRepository(settings.database_url)
    repository = repository or InMemoryRepository()
    policy = BudgetPolicy(
        daily_llm_cap=settings.daily_llm_cap_usd,
        monthly_data_cap=settings.monthly_paid_data_cap_usd,
    )
    governor = BudgetGovernor(policy)

    app = FastAPI(title=settings.app_name)

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> str:
        return render_dashboard()

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "environment": settings.environment}

    @app.get("/api/opportunities")
    def opportunities() -> dict:
        return {"opportunities": repository.list_opportunities()}

    @app.get("/api/tasks")
    def tasks() -> dict:
        return {"tasks": repository.list_tasks()}

    @app.get("/api/budget")
    def budget() -> dict:
        return {
            "daily_llm_cap": policy.daily_llm_cap,
            "monthly_paid_data_cap": policy.monthly_data_cap,
            "ask_tracker_query_cap": policy.ask_tracker_query_cap,
            "ask_tracker_daily_cap": policy.ask_tracker_daily_cap,
        }

    @app.post("/slack/commands")
    async def slack_commands(
        request: Request,
        x_slack_request_timestamp: str | None = Header(default=None),
        x_slack_signature: str | None = Header(default=None),
    ) -> Response:
        body = await request.body()
        if settings.slack_signing_secret and not verify_slack_signature(
            signing_secret=settings.slack_signing_secret,
            timestamp=x_slack_request_timestamp or "",
            body=body,
            signature=x_slack_signature or "",
            now=datetime.now(timezone.utc),
        ):
            return JSONResponse({"text": "Invalid Slack signature"}, status_code=401)

        parsed = parse_qs(body.decode("utf-8"))
        command = parsed.get("command", [""])[0]
        text = parsed.get("text", [""])[0]

        if command == "/ask-tracker":
            decision = governor.authorize_ask_tracker(
                BudgetSnapshot(
                    daily_llm_spend=0.0,
                    monthly_data_spend=0.0,
                    ask_tracker_daily_spend=0.0,
                ),
                estimated_cost=0.10,
            )
            if not decision.allowed:
                return JSONResponse({"response_type": "ephemeral", "text": decision.reason})
            return JSONResponse(
                {
                    "response_type": "ephemeral",
                    "text": f"Tracker question queued: {text or 'latest frontier changes'}",
                }
            )
        return JSONResponse({"response_type": "ephemeral", "text": "Unsupported command"})

    @app.post("/slack/actions")
    async def slack_actions(request: Request) -> Response:
        body = await request.body()
        parsed = parse_qs(body.decode("utf-8"))
        value = parsed.get("payload", [body.decode("utf-8")])[0]
        action = parse_slack_action(value)
        if action is None:
            return JSONResponse({"text": "Unsupported action"}, status_code=400)
        user_id = action.user_id or parsed.get("user_id", ["slack-owner"])[0]
        record_slack_action(repository, action, user_id, datetime.now(timezone.utc))
        return JSONResponse(
            {
                "response_type": "ephemeral",
                "text": f"Recorded {action.action} for {action.opportunity_id}",
            }
        )

    return app


app = create_app()
