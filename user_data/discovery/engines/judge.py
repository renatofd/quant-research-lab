"""Objective fast-discard and promotion gates."""

from __future__ import annotations

from models import ExecutionResult


class ScientificJudge:
    def judge(self, result: ExecutionResult) -> tuple[str, str, dict]:
        if result.status in {"paused", "error"}:
            return "INCONCLUSIVE", result.error or "Execution did not produce valid evidence.", {}
        metrics = result.metrics
        fast_failures = {
            "profit_factor_below_one": metrics.get("profit_factor") is not None and metrics["profit_factor"] < 1.0,
            "negative_expectancy": metrics.get("expectancy") is not None and metrics["expectancy"] < 0.0,
            "null_economic_effect": metrics.get("economic_effect_nontrivial") is False,
            "low_robustness": metrics.get("initial_robustness") is False,
            "no_economic_mechanism": metrics.get("mechanism_valid") is False,
            "statistical_only": metrics.get("statistically_significant") is True and metrics.get("positive_net_advantage") is not True,
        }
        if any(fast_failures.values()):
            failed = [name for name, value in fast_failures.items() if value]
            return "REJECT", "Fast-discard gate failed: " + ", ".join(failed), fast_failures

        promotion = {
            "robust_profit_factor": bool(metrics.get("robust_profit_factor")),
            "positive_net_return": bool(metrics.get("positive_net_advantage")),
            "walk_forward_survival": bool(metrics.get("walk_forward_consistent")),
            "stability": bool(metrics.get("stable")),
            "low_parameter_sensitivity": bool(metrics.get("low_parameter_sensitivity")),
            "reproducible": bool(metrics.get("reproducible")),
            "independent_holdout": bool(metrics.get("independent_holdout")),
        }
        if all(promotion.values()):
            return "ACCEPT", "All mandatory promotion gates passed.", promotion
        return "REJECT", "At least one mandatory continuation/promotion gate is absent.", promotion

