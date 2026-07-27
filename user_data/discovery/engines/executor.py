"""Conservative executor enforcing experiment and advanced-validation budgets."""

from __future__ import annotations

from typing import Callable

from config import MAX_EXPLORATORY_EXPERIMENTS_PER_HYPOTHESIS
from engines.knowledge_base import KnowledgeBase
from models import ExecutionResult, Hypothesis


OfflineRunner = Callable[[Hypothesis, dict], ExecutionResult]


class DiscoveryExecutor:
    def __init__(self, knowledge_base: KnowledgeBase) -> None:
        self.knowledge_base = knowledge_base

    def execute(
        self,
        hypothesis: Hypothesis,
        protocol: dict,
        runner: OfflineRunner | None,
    ) -> ExecutionResult:
        existing = self.knowledge_base.experiment_count(hypothesis.id)
        if existing >= MAX_EXPLORATORY_EXPERIMENTS_PER_HYPOTHESIS:
            return ExecutionResult(
                hypothesis.id,
                "rejected",
                existing,
                {},
                [],
                "Experiment budget exhausted; experiment 501 is forbidden.",
            )
        if not hypothesis.data_available:
            return ExecutionResult(
                hypothesis.id, "paused", existing, {}, [], "Required data unavailable."
            )
        if runner is None:
            return ExecutionResult(
                hypothesis.id,
                "paused",
                existing,
                {},
                [],
                "No preregistered offline runner is attached; implicit backtests/downloads are forbidden.",
            )
        result = runner(hypothesis, protocol)
        if result.experiment_count + existing > MAX_EXPLORATORY_EXPERIMENTS_PER_HYPOTHESIS:
            raise RuntimeError("Runner attempted to exceed the 500-experiment budget.")
        return result

    @staticmethod
    def advanced_validation_allowed(metrics: dict) -> bool:
        return bool(
            metrics.get("positive_net_advantage")
            and metrics.get("economic_effect_nontrivial")
            and metrics.get("initial_robustness")
        )

