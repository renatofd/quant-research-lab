from __future__ import annotations

from typing import Any

try:
    from .experiment_database import ExperimentDatabase
except ImportError:
    from experiment_database import ExperimentDatabase


DEFAULT_SCORE_WEIGHTS = {
    "profit_factor": 0.40,
    "expectancy": 0.20,
    "profit_total_abs": 0.20,
    "sharpe": 0.10,
    "max_drawdown_abs": -0.10,
}


class RankingEngine:
    def __init__(
        self,
        database: ExperimentDatabase | None = None,
        *,
        score_weights: dict[str, float] | None = None,
    ) -> None:
        self.database = database or ExperimentDatabase()
        self.score_weights = score_weights or DEFAULT_SCORE_WEIGHTS

    def composite_score(self, metrics: dict[str, Any]) -> float:
        score = 0.0
        for metric_name, weight in self.score_weights.items():
            score += self._number(metrics.get(metric_name)) * weight
        return score

    def rank(
        self,
        *,
        order_by: str = "score",
        descending: bool = True,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        experiments = [
            experiment
            for experiment in self.database.list_experiments(status="completed")
            if experiment.get("metrics")
        ]

        for experiment in experiments:
            experiment["computed_score"] = self.composite_score(experiment["metrics"])
            experiment["strategy_plugin"] = self.strategy_plugin_name(experiment)

        key_func = (
            (lambda item: item.get("computed_score", 0.0))
            if order_by == "score"
            else (lambda item: self._number(item.get("metrics", {}).get(order_by)))
        )

        return sorted(experiments, key=key_func, reverse=descending)[:limit]

    def strategy_rankings(
        self,
        *,
        order_by: str = "score",
        descending: bool = True,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for experiment in self.rank(limit=10_000):
            grouped.setdefault(self.strategy_plugin_name(experiment), []).append(experiment)

        rows = []
        for strategy_plugin, experiments in grouped.items():
            best = sorted(
                experiments,
                key=lambda item: self._rank_value(item, order_by),
                reverse=descending,
            )[0]
            metrics = best.get("metrics", {})
            rows.append(
                {
                    "strategy_plugin": strategy_plugin,
                    "best_experiment_id": best["id"],
                    "best_parameters": best.get("parameters", {}),
                    "score": best.get("computed_score", best.get("score")),
                    "profit_factor": self._number(metrics.get("profit_factor")),
                    "drawdown": self._number(metrics.get("max_drawdown_abs")),
                    "winrate": self._number(metrics.get("winrate")),
                    "expectancy": self._number(metrics.get("expectancy")),
                    "sharpe": self._number(metrics.get("sharpe")),
                    "total_trades": self._number(metrics.get("total_trades")),
                    "experiments": len(experiments),
                }
            )

        return sorted(
            rows,
            key=lambda item: self._number(item.get(order_by if order_by != "score" else "score")),
            reverse=descending,
        )[:limit]

    def strategy_plugin_name(self, experiment: dict[str, Any]) -> str:
        parameters = experiment.get("parameters", {})
        return (
            experiment.get("strategy_plugin")
            or parameters.get("strategy_plugin")
            or experiment.get("strategy_name")
            or "UNKNOWN"
        )

    def _rank_value(self, experiment: dict[str, Any], order_by: str) -> float:
        if order_by == "score":
            return self._number(experiment.get("computed_score", experiment.get("score")))
        return self._number(experiment.get("metrics", {}).get(order_by))

    def _number(self, value: Any) -> float:
        try:
            if value is None:
                return 0.0
            return float(value)
        except (TypeError, ValueError):
            return 0.0
