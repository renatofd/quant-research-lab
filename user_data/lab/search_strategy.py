from __future__ import annotations

from random import Random
from typing import Any, Iterable

try:
    from .parameter_generator import DEFAULT_PARAMETER_SPACE, ParameterGenerator
except ImportError:
    from parameter_generator import DEFAULT_PARAMETER_SPACE, ParameterGenerator


class SearchStrategy:
    def __init__(
        self,
        parameter_space: dict[str, Iterable[Any]] | None = None,
        *,
        seed: int | None = None,
    ) -> None:
        self.parameter_space = {
            key: tuple(values)
            for key, values in (parameter_space or DEFAULT_PARAMETER_SPACE).items()
        }
        self.random = Random(seed)

    def generate(
        self,
        method: str,
        count: int,
        *,
        completed_experiments: list[dict[str, Any]] | None = None,
        optimize_metric: str = "score",
    ) -> list[dict[str, Any]]:
        if method == "random":
            return self.random_search(count)
        if method == "grid":
            return self.grid_search(count)
        if method == "adaptive":
            return self.adaptive_search(
                count,
                completed_experiments=completed_experiments or [],
                optimize_metric=optimize_metric,
            )
        raise ValueError("method must be random, grid, or adaptive.")

    def random_search(self, count: int) -> list[dict[str, Any]]:
        generator = ParameterGenerator(self.parameter_space, seed=self.random.randrange(10**9))
        return generator.generate_random(count)

    def grid_search(self, count: int | None = None) -> list[dict[str, Any]]:
        generator = ParameterGenerator(self.parameter_space)
        return generator.generate_grid(limit=count)

    def adaptive_search(
        self,
        count: int,
        *,
        completed_experiments: list[dict[str, Any]],
        optimize_metric: str = "score",
        top_fraction: float = 0.20,
        neighbor_radius: int = 1,
    ) -> list[dict[str, Any]]:
        completed = [
            experiment
            for experiment in completed_experiments
            if experiment.get("metrics") or experiment.get("score") is not None
        ]
        if not completed:
            return self.random_search(count)

        ranked = sorted(
            completed,
            key=lambda item: self._metric_value(item, optimize_metric),
            reverse=True,
        )
        top_count = max(1, int(len(ranked) * top_fraction))
        adaptive_space = self._adaptive_space(
            ranked[:top_count],
            neighbor_radius=neighbor_radius,
        )
        generator = ParameterGenerator(adaptive_space, seed=self.random.randrange(10**9))
        return generator.generate_random(count)

    def _adaptive_space(
        self,
        top_experiments: list[dict[str, Any]],
        *,
        neighbor_radius: int,
    ) -> dict[str, tuple[Any, ...]]:
        narrowed: dict[str, tuple[Any, ...]] = {}

        for name, values in self.parameter_space.items():
            selected: set[Any] = set()
            top_values = [
                experiment.get("parameters", {}).get(name)
                for experiment in top_experiments
                if name in experiment.get("parameters", {})
            ]

            for value in top_values:
                if value in values:
                    index = values.index(value)
                    start = max(0, index - neighbor_radius)
                    end = min(len(values), index + neighbor_radius + 1)
                    selected.update(values[start:end])
                elif value is not None:
                    selected.add(value)

            narrowed[name] = tuple(value for value in values if value in selected) or values

        return narrowed

    def _metric_value(self, experiment: dict[str, Any], metric_name: str) -> float:
        if metric_name == "score":
            return self._number(experiment.get("score"))
        return self._number(experiment.get("metrics", {}).get(metric_name))

    def _number(self, value: Any) -> float:
        try:
            if value is None:
                return 0.0
            return float(value)
        except (TypeError, ValueError):
            return 0.0
