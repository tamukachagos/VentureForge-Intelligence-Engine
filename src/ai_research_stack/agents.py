from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Any

from ai_research_stack.config import Settings
from ai_research_stack.prompts import (
    claude_critic_prompt,
    frontier_tracker_prompt,
    obvious_wrapper_detector_prompt,
    saturation_checker_prompt,
)
from ai_research_stack.providers import AnthropicClient, LLMResponse, OpenRouterClient


@dataclass(frozen=True)
class AgentResult:
    status: str
    output: dict[str, Any]
    cost_usd: float
    input_tokens: int
    output_tokens: int
    model_used: str
    warnings: tuple[str, ...] = ()


Handler = Callable[[dict[str, Any]], AgentResult]


class AgentRuntime:
    def __init__(self, handlers: dict[str, Handler] | None = None) -> None:
        self.handlers = handlers or default_handlers()

    def run(self, task_type: str, payload: dict[str, Any]) -> AgentResult:
        handler = self.handlers.get(task_type)
        if handler is None:
            return AgentResult(
                status="failed",
                output={"error": f"No handler registered for {task_type}"},
                cost_usd=0.0,
                input_tokens=0,
                output_tokens=0,
                model_used="none",
                warnings=("missing_handler",),
            )
        return handler(payload)


def default_handlers() -> dict[str, Handler]:
    return {
        "frontier_tracker": deterministic_frontier_tracker,
        "full_research": deterministic_research,
        "saturation_check": deterministic_saturation_check,
        "wrapper_check": deterministic_wrapper_check,
        "claude_critic": deterministic_critic,
        "daily_digest": deterministic_daily_digest,
    }


def runtime_from_settings(settings: Settings) -> AgentRuntime:
    handlers = default_handlers()

    if settings.openrouter_api_key and settings.openrouter_worker_model:
        openrouter = OpenRouterClient(settings.openrouter_api_key)
        handlers.update(
            {
                "frontier_tracker": _openrouter_handler(
                    openrouter,
                    settings.openrouter_worker_model,
                    frontier_tracker_prompt(),
                ),
                "full_research": _openrouter_handler(
                    openrouter,
                    settings.openrouter_worker_model,
                    "Research the opportunity. Extract demand witnesses, evidence, sources, risks, and uncertainty.",
                ),
                "saturation_check": _openrouter_handler(
                    openrouter,
                    settings.openrouter_worker_model,
                    saturation_checker_prompt(),
                ),
                "wrapper_check": _openrouter_handler(
                    openrouter,
                    settings.openrouter_worker_model,
                    obvious_wrapper_detector_prompt(),
                ),
            }
        )

    if settings.anthropic_api_key and settings.anthropic_critic_model:
        anthropic = AnthropicClient(settings.anthropic_api_key)
        handlers["claude_critic"] = _anthropic_handler(
            anthropic,
            settings.anthropic_critic_model,
            claude_critic_prompt(),
        )

    return AgentRuntime(handlers)


def _openrouter_handler(client: OpenRouterClient, model: str, system_prompt: str) -> Handler:
    def run(payload: dict[str, Any]) -> AgentResult:
        response = client.complete(model=model, system=system_prompt, user=str(payload))
        return _llm_result(response)

    return run


def _anthropic_handler(client: AnthropicClient, model: str, system_prompt: str) -> Handler:
    def run(payload: dict[str, Any]) -> AgentResult:
        response = client.complete(model=model, system=system_prompt, user=str(payload))
        return _llm_result(response)

    return run


def _llm_result(response: LLMResponse) -> AgentResult:
    return AgentResult(
        status="complete",
        output={"raw_text": response.text},
        cost_usd=response.cost_usd,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        model_used=response.model_used,
    )


def deterministic_frontier_tracker(payload: dict[str, Any]) -> AgentResult:
    return AgentResult(
        status="complete",
        output={
            "prompt": frontier_tracker_prompt(),
            "signals": [
                {
                    "signal_id": "dev-signal-agent-spreadsheets",
                    "source": "deterministic-dev",
                    "title": "Tool-use agents can inspect spreadsheet workflows",
                    "url": "https://example.com/dev-signal-agent-spreadsheets",
                    "summary": (
                        "A frontier signal indicating agents can inspect and reason over "
                        "messy spreadsheet workflows for finance and operations teams."
                    ),
                    "opportunities": [
                        {
                            "opportunity_id": "dev-opp-spreadsheet-qa",
                            "title": "Spreadsheet QA copilot for finance operators",
                            "thesis": (
                                "Finance teams spend repeated review cycles checking linked "
                                "spreadsheets, broken formulas, and control evidence."
                            ),
                            "stage": "first_pass",
                        }
                    ],
                }
            ],
            "source_batch": payload.get("source_batch", "default"),
        },
        cost_usd=0.0,
        input_tokens=0,
        output_tokens=0,
        model_used="deterministic-dev",
    )


def deterministic_research(payload: dict[str, Any]) -> AgentResult:
    return AgentResult(
        status="complete",
        output={
            "opportunity_id": payload.get("opportunity_id"),
            "findings": [],
            "demand_witnesses": [],
            "warnings": ["deterministic handler did not call external sources"],
        },
        cost_usd=0.0,
        input_tokens=0,
        output_tokens=0,
        model_used="deterministic-dev",
    )


def deterministic_saturation_check(payload: dict[str, Any]) -> AgentResult:
    return AgentResult(
        status="complete",
        output={
            "prompt": saturation_checker_prompt(),
            "opportunity_id": payload.get("opportunity_id"),
            "crowdedness": "unknown",
            "competitors": [],
        },
        cost_usd=0.0,
        input_tokens=0,
        output_tokens=0,
        model_used="deterministic-dev",
    )


def deterministic_wrapper_check(payload: dict[str, Any]) -> AgentResult:
    return AgentResult(
        status="complete",
        output={
            "prompt": obvious_wrapper_detector_prompt(),
            "opportunity_id": payload.get("opportunity_id"),
            "wrapper_verdict": "unknown",
        },
        cost_usd=0.0,
        input_tokens=0,
        output_tokens=0,
        model_used="deterministic-dev",
    )


def deterministic_critic(payload: dict[str, Any]) -> AgentResult:
    return AgentResult(
        status="complete",
        output={
            "prompt": claude_critic_prompt(),
            "opportunity_id": payload.get("opportunity_id"),
            "recommendation": "research_more",
            "fatal_flaws": [],
        },
        cost_usd=0.0,
        input_tokens=0,
        output_tokens=0,
        model_used="deterministic-dev",
    )


def deterministic_daily_digest(payload: dict[str, Any]) -> AgentResult:
    return AgentResult(
        status="complete",
        output={
            "digest": "No live opportunities yet.",
            "window": payload.get("window", "daily"),
        },
        cost_usd=0.0,
        input_tokens=0,
        output_tokens=0,
        model_used="deterministic-dev",
    )
