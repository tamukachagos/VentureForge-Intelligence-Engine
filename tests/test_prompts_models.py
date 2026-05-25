from ai_research_stack.models import ModelConfig, ModelRegistry
from ai_research_stack.prompts import (
    obvious_wrapper_detector_prompt,
    saturation_checker_prompt,
    frontier_tracker_prompt,
    claude_critic_prompt,
)


def test_high_leverage_prompts_include_required_fields_and_constraints():
    prompts = [
        frontier_tracker_prompt(),
        saturation_checker_prompt(),
        obvious_wrapper_detector_prompt(),
        claude_critic_prompt(),
    ]

    required_terms = [
        "legal",
        "demand",
        "source",
        "uncertainty",
        "output JSON",
    ]

    for prompt in prompts:
        for term in required_terms:
            assert term in prompt

    assert "capability shift" in frontier_tracker_prompt()
    assert "funded companies" in saturation_checker_prompt()
    assert "AI for" in obvious_wrapper_detector_prompt()
    assert "fatal flaws" in claude_critic_prompt()


def test_model_registry_selects_active_lowest_cost_model_by_role():
    registry = ModelRegistry(
        [
            ModelConfig("expensive", "openrouter/foo", "extraction", 1.0, 2.0, True),
            ModelConfig("cheap", "openrouter/bar", "extraction", 0.1, 0.2, True),
            ModelConfig("inactive", "openrouter/baz", "extraction", 0.01, 0.01, False),
            ModelConfig("critic", "anthropic/claude-sonnet", "critic", 3.0, 15.0, True),
        ]
    )

    assert registry.select("extraction").name == "cheap"
    assert registry.select("critic").model_id == "anthropic/claude-sonnet"
    assert registry.select("unknown") is None
