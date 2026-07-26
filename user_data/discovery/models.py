"""Typed contracts used by the isolated Discovery Engine."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


TERMINAL_STATUSES = {
    "approved",
    "rejected",
    "closed",
    "inconclusive_sample",
    "blocked_data",
}


@dataclass(frozen=True)
class Hypothesis:
    id: str
    family_key: str
    description: str
    economic_hypothesis: str
    assumptions: list[str]
    required_data: list[str]
    protocol: str
    success_criteria: list[str]
    rejection_criteria: list[str]
    pause_criteria: list[str]
    computational_cost: str
    dependencies: list[str]
    state: str
    priority: int
    data_available: bool
    estimated_success_probability: float
    origin: str
    literature: list[str] = field(default_factory=list)
    result: str | None = None
    overfitting_risk: str = "medium"
    rejection_reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PlanDecision:
    action: str
    reason_code: str
    reason: str
    hypothesis_id: str | None
    tested_count: int
    registered_count: int
    actionable_count: int
    blocked_count: int
    expected_success_probability: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionResult:
    hypothesis_id: str
    status: str
    experiment_count: int
    metrics: dict[str, Any]
    evidence: list[dict[str, Any]]
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

