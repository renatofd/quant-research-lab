from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class SchedulerGoals:
    target_experiments: int | None = None
    min_profit_factor: float | None = None
    max_drawdown: float | None = None
    max_runtime_seconds: int | None = None
    cpu_limit_percent: float | None = None


class ExperimentScheduler:
    def __init__(self, goals: SchedulerGoals | dict[str, Any] | None = None) -> None:
        if isinstance(goals, SchedulerGoals):
            self.goals = goals
        else:
            self.goals = SchedulerGoals(**(goals or {}))

    def evaluate(
        self,
        *,
        session: dict[str, Any],
        experiments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        completed = [item for item in experiments if item["status"] == "completed"]
        reasons = []

        if (
            self.goals.target_experiments is not None
            and len(experiments) >= self.goals.target_experiments
        ):
            reasons.append("target_experiments_reached")

        if self.goals.min_profit_factor is not None:
            best_profit_factor = max(
                (self._metric(item, "profit_factor") for item in completed),
                default=0.0,
            )
            if best_profit_factor >= self.goals.min_profit_factor:
                reasons.append("min_profit_factor_reached")

        if self.goals.max_drawdown is not None:
            latest_drawdown = self._latest_metric(completed, "max_drawdown_abs")
            if latest_drawdown is not None and latest_drawdown > self.goals.max_drawdown:
                reasons.append("max_drawdown_exceeded")

        if self.goals.max_runtime_seconds is not None:
            runtime_seconds = self._runtime_seconds(session)
            if runtime_seconds is not None and runtime_seconds >= self.goals.max_runtime_seconds:
                reasons.append("max_runtime_reached")

        return {
            "should_stop": bool(reasons),
            "reasons": reasons,
            "completed": len(completed),
            "pending": len([item for item in experiments if item["status"] == "pending"]),
            "running": len([item for item in experiments if item["status"] == "running"]),
            "cpu_limit_percent": self.goals.cpu_limit_percent,
        }

    def next_batch_size(
        self,
        *,
        current_total: int,
        default_batch_size: int,
    ) -> int:
        if self.goals.target_experiments is None:
            return default_batch_size
        remaining = max(0, self.goals.target_experiments - current_total)
        return min(default_batch_size, remaining)

    def _metric(self, experiment: dict[str, Any], metric_name: str) -> float:
        try:
            return float(experiment.get("metrics", {}).get(metric_name) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _latest_metric(
        self,
        experiments: list[dict[str, Any]],
        metric_name: str,
    ) -> float | None:
        if not experiments:
            return None
        return self._metric(experiments[-1], metric_name)

    def _runtime_seconds(self, session: dict[str, Any]) -> float | None:
        started_at = session.get("started_at") or session.get("created_at")
        if not started_at:
            return None
        start = datetime.fromisoformat(started_at)
        return (datetime.now(UTC) - start).total_seconds()
