from __future__ import annotations

from math import sqrt
from statistics import mean
from typing import Any

try:
    from .experiment_database import ExperimentDatabase
except ImportError:
    from experiment_database import ExperimentDatabase


DEFAULT_ANALYSIS_METRICS = (
    "profit_factor",
    "expectancy",
    "max_drawdown_abs",
    "profit_total_abs",
    "sharpe",
)


class ParameterSpaceAnalyzer:
    def __init__(
        self,
        database: ExperimentDatabase | None = None,
        *,
        metrics: tuple[str, ...] = DEFAULT_ANALYSIS_METRICS,
    ) -> None:
        self.database = database or ExperimentDatabase()
        self.metrics = metrics

    def analyze(
        self,
        experiments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        experiments = experiments or self.database.list_experiments(status="completed")
        completed = [item for item in experiments if item.get("metrics")]
        parameters = sorted(
            {
                parameter
                for experiment in completed
                for parameter in experiment.get("parameters", {})
            }
        )

        return {
            "experiment_count": len(completed),
            "metrics": list(self.metrics),
            "correlations": self._correlations(completed, parameters),
            "impact": self._impact(completed, parameters),
        }

    def _correlations(
        self,
        experiments: list[dict[str, Any]],
        parameters: list[str],
    ) -> dict[str, dict[str, dict[str, float | None]]]:
        output: dict[str, dict[str, dict[str, float | None]]] = {}
        for parameter in parameters:
            parameter_values = [
                self._number(experiment.get("parameters", {}).get(parameter))
                for experiment in experiments
            ]
            output[parameter] = {}
            for metric in self.metrics:
                metric_values = [
                    self._number(experiment.get("metrics", {}).get(metric))
                    for experiment in experiments
                ]
                output[parameter][metric] = {
                    "pearson": self._pearson(parameter_values, metric_values),
                    "spearman": self._spearman(parameter_values, metric_values),
                }
        return output

    def _impact(
        self,
        experiments: list[dict[str, Any]],
        parameters: list[str],
    ) -> dict[str, dict[str, Any]]:
        output: dict[str, dict[str, Any]] = {}
        for parameter in parameters:
            output[parameter] = {}
            grouped = self._group_by_parameter(experiments, parameter)
            for metric in self.metrics:
                stats = []
                for value, rows in grouped.items():
                    metric_values = [
                        self._number(row.get("metrics", {}).get(metric))
                        for row in rows
                    ]
                    clean_values = [value for value in metric_values if value is not None]
                    if clean_values:
                        stats.append(
                            {
                                "value": value,
                                "count": len(clean_values),
                                "mean": mean(clean_values),
                                "min": min(clean_values),
                                "max": max(clean_values),
                            }
                        )
                stats.sort(key=lambda item: item["mean"], reverse=True)
                means = [item["mean"] for item in stats]
                output[parameter][metric] = {
                    "best_value": stats[0]["value"] if stats else None,
                    "worst_value": stats[-1]["value"] if stats else None,
                    "mean_range": max(means) - min(means) if means else None,
                    "groups": stats,
                }
        return output

    def relative_importance(
        self,
        experiments: list[dict[str, Any]] | None = None,
        *,
        metric: str = "profit_factor",
    ) -> list[dict[str, Any]]:
        analysis = self.analyze(experiments)
        rows = []
        for parameter, metrics in analysis["impact"].items():
            impact = metrics.get(metric, {})
            rows.append(
                {
                    "parameter": parameter,
                    "metric": metric,
                    "importance": impact.get("mean_range") or 0.0,
                    "best_value": impact.get("best_value"),
                    "worst_value": impact.get("worst_value"),
                }
            )
        return sorted(rows, key=lambda item: item["importance"], reverse=True)

    def _group_by_parameter(
        self,
        experiments: list[dict[str, Any]],
        parameter: str,
    ) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for experiment in experiments:
            value = experiment.get("parameters", {}).get(parameter)
            grouped.setdefault(str(value), []).append(experiment)
        return grouped

    def _pearson(
        self,
        left: list[float | None],
        right: list[float | None],
    ) -> float | None:
        pairs = [
            (x, y)
            for x, y in zip(left, right, strict=True)
            if x is not None and y is not None
        ]
        if len(pairs) < 3:
            return None

        xs, ys = zip(*pairs, strict=True)
        mean_x = mean(xs)
        mean_y = mean(ys)
        numerator = sum((x - mean_x) * (y - mean_y) for x, y in pairs)
        denominator = sqrt(
            sum((x - mean_x) ** 2 for x in xs) * sum((y - mean_y) ** 2 for y in ys)
        )
        return numerator / denominator if denominator else None

    def _spearman(
        self,
        left: list[float | None],
        right: list[float | None],
    ) -> float | None:
        pairs = [
            (x, y)
            for x, y in zip(left, right, strict=True)
            if x is not None and y is not None
        ]
        if len(pairs) < 3:
            return None
        left_values, right_values = zip(*pairs, strict=True)
        return self._pearson(self._ranks(list(left_values)), self._ranks(list(right_values)))

    def _ranks(self, values: list[float]) -> list[float]:
        ordered = sorted((value, index) for index, value in enumerate(values))
        ranks = [0.0] * len(values)
        index = 0
        while index < len(ordered):
            end = index
            while end + 1 < len(ordered) and ordered[end + 1][0] == ordered[index][0]:
                end += 1
            rank = (index + end + 2) / 2.0
            for _, original_index in ordered[index : end + 1]:
                ranks[original_index] = rank
            index = end + 1
        return ranks

    def _number(self, value: Any) -> float | None:
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None
