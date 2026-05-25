from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    app_name: str = "AI Research Stack"
    environment: str = "development"
    database_url: str = ""
    redis_url: str = "redis://redis:6379/0"
    slack_signing_secret: str = ""
    slack_bot_token: str = ""
    slack_app_token: str = ""
    slack_channel_id: str = ""
    openrouter_api_key: str = ""
    anthropic_api_key: str = ""
    openrouter_worker_model: str = ""
    anthropic_critic_model: str = ""
    github_token: str = ""
    github_search_query: str = "AI agents created:>2026-01-01"
    rss_feed_urls: str = ""
    enable_hacker_news: bool = True
    enable_github_search: bool = True
    enable_rss: bool = True
    enable_paid_search: bool = False
    paid_search_name: str = "paid_search"
    paid_search_endpoint_url: str = ""
    paid_search_api_key: str = ""
    paid_search_query: str = "AI agent workflow complaints"
    paid_search_estimated_cost_usd: float = 0.25
    daily_llm_cap_usd: float = 15.0
    monthly_paid_data_cap_usd: float = 50.0


def load_settings() -> Settings:
    return Settings(
        environment=os.getenv("ENVIRONMENT", "development"),
        database_url=os.getenv("DATABASE_URL", ""),
        redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
        slack_signing_secret=os.getenv("SLACK_SIGNING_SECRET", ""),
        slack_bot_token=os.getenv("SLACK_BOT_TOKEN", ""),
        slack_app_token=os.getenv("SLACK_APP_TOKEN", ""),
        slack_channel_id=os.getenv("SLACK_CHANNEL_ID", ""),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        openrouter_worker_model=os.getenv("OPENROUTER_WORKER_MODEL", ""),
        anthropic_critic_model=os.getenv("ANTHROPIC_CRITIC_MODEL", ""),
        github_token=os.getenv("GITHUB_TOKEN", ""),
        github_search_query=os.getenv("GITHUB_SEARCH_QUERY", "AI agents created:>2026-01-01"),
        rss_feed_urls=os.getenv("RSS_FEED_URLS", ""),
        enable_hacker_news=_env_bool("ENABLE_HACKER_NEWS", True),
        enable_github_search=_env_bool("ENABLE_GITHUB_SEARCH", True),
        enable_rss=_env_bool("ENABLE_RSS", True),
        enable_paid_search=_env_bool("ENABLE_PAID_SEARCH", False),
        paid_search_name=os.getenv("PAID_SEARCH_NAME", "paid_search"),
        paid_search_endpoint_url=os.getenv("PAID_SEARCH_ENDPOINT_URL", ""),
        paid_search_api_key=os.getenv("PAID_SEARCH_API_KEY", ""),
        paid_search_query=os.getenv("PAID_SEARCH_QUERY", "AI agent workflow complaints"),
        paid_search_estimated_cost_usd=float(os.getenv("PAID_SEARCH_ESTIMATED_COST_USD", "0.25")),
        daily_llm_cap_usd=float(os.getenv("DAILY_LLM_CAP_USD", "15")),
        monthly_paid_data_cap_usd=float(os.getenv("MONTHLY_PAID_DATA_CAP_USD", "50")),
    )


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
