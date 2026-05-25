from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelConfig:
    name: str
    model_id: str
    role: str
    cost_per_million_input: float
    cost_per_million_output: float
    active: bool

    @property
    def blended_cost(self) -> float:
        return self.cost_per_million_input + self.cost_per_million_output


class ModelRegistry:
    def __init__(self, models: list[ModelConfig]) -> None:
        self.models = models

    def select(self, role: str) -> ModelConfig | None:
        active = [model for model in self.models if model.role == role and model.active]
        if not active:
            return None
        return min(active, key=lambda model: model.blended_cost)

