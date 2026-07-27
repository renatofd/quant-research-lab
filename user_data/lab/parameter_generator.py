from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from random import Random
from typing import Any, Iterable

try:
    from .strategy_plugins import create_plugin
except ImportError:
    from strategy_plugins import create_plugin


@dataclass(frozen=True)
class ParameterSpec:
    name: str
    values: tuple[Any, ...]


DEFAULT_PARAMETER_SPACE: dict[str, Iterable[Any]] = {
    "buy_ema_fast": range(5, 13, 2),
    "buy_ema_slow": range(18, 36, 4),
    "buy_ema_trend": (150, 200, 250),
    "buy_rsi_min": (40, 45, 50),
    "buy_rsi_max": (55, 58, 62),
    "buy_volume_mult": (1.2, 1.5, 1.8, 2.0),
    "roi": (0.004, 0.006, 0.008, 0.01),
    "stoploss": (-0.03, -0.04, -0.05, -0.06),
    "martingale_multiplier": (1.2, 1.5, 1.8),
    "max_martingale_level": (2, 3, 4),
    "reset_after_losses": (3, 4, 5),
}

DEFAULT_STRATEGY_PLUGINS = (
    "TrendStrategy",
    "PullbackStrategy",
    "BreakoutStrategy",
    "MeanReversionStrategy",
    "ScalpingStrategy",
    "MomentumStrategy",
    "VolatilityStrategy",
)


class ParameterGenerator:
    def __init__(
        self,
        parameter_space: dict[str, Iterable[Any]] | None = None,
        *,
        seed: int | None = None,
        strategy_plugins: Iterable[str] | None = None,
    ) -> None:
        self.parameter_space = {
            key: tuple(values)
            for key, values in (parameter_space or DEFAULT_PARAMETER_SPACE).items()
        }
        self.random = Random(seed)
        self.strategy_plugins = tuple(strategy_plugins or DEFAULT_STRATEGY_PLUGINS)

    def generate_grid(self, limit: int | None = None) -> list[dict[str, Any]]:
        keys = list(self.parameter_space.keys())
        experiments = []

        for values in product(*(self.parameter_space[key] for key in keys)):
            params = dict(zip(keys, values, strict=True))
            if self._is_valid(params):
                experiments.append(params)
                if limit and len(experiments) >= limit:
                    break

        return experiments

    def generate_random(self, count: int) -> list[dict[str, Any]]:
        experiments = []
        attempts = 0
        max_attempts = count * 100

        while len(experiments) < count and attempts < max_attempts:
            attempts += 1
            params = {
                key: self.random.choice(values)
                for key, values in self.parameter_space.items()
            }
            if self._is_valid(params):
                experiments.append(params)

        return experiments

    def generate_plugin_grid(
        self,
        *,
        strategy_plugins: Iterable[str] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        experiments = []
        plugins = self.strategy_plugins if strategy_plugins is None else tuple(strategy_plugins)
        for strategy_plugin in plugins:
            parameter_space = self._parameter_space_for_plugin(strategy_plugin)
            remaining = None if limit is None else limit - len(experiments)
            for parameters in self._generate_grid_from_space(parameter_space, remaining):
                experiments.append(
                    self._plugin_experiment(strategy_plugin, parameters)
                )
                if limit and len(experiments) >= limit:
                    return experiments
        return experiments

    def generate_plugin_random(
        self,
        count: int,
        *,
        strategy_plugins: Iterable[str] | None = None,
    ) -> list[dict[str, Any]]:
        plugins = self.strategy_plugins if strategy_plugins is None else tuple(strategy_plugins)
        if not plugins:
            raise ValueError("At least one strategy plugin is required.")

        experiments = []
        attempts = 0
        max_attempts = count * 100

        while len(experiments) < count and attempts < max_attempts:
            attempts += 1
            strategy_plugin = self.random.choice(plugins)
            parameters = self._random_parameters_for_plugin(strategy_plugin)
            if self._is_valid(parameters):
                experiments.append(
                    self._plugin_experiment(
                        strategy_plugin,
                        parameters,
                    )
                )

        return experiments

    def _is_valid(self, params: dict[str, Any]) -> bool:
        fast = params.get("buy_ema_fast")
        slow = params.get("buy_ema_slow")
        trend = params.get("buy_ema_trend")
        rsi_min = params.get("buy_rsi_min")
        rsi_max = params.get("buy_rsi_max")

        if fast is not None and slow is not None and fast >= slow:
            return False
        if slow is not None and trend is not None and slow >= trend:
            return False
        if rsi_min is not None and rsi_max is not None and rsi_min >= rsi_max:
            return False

        return True

    def _parameter_space_for_plugin(self, strategy_plugin: str) -> dict[str, tuple[Any, ...]]:
        spec = self._plugin_parameter_spec(strategy_plugin)
        if not spec:
            return dict(self.parameter_space)

        parameter_space: dict[str, tuple[Any, ...]] = {}
        for name, parameter_spec in spec.items():
            parameter_space[name] = self._grid_values_from_spec(parameter_spec)
        return parameter_space

    def _random_parameters_for_plugin(self, strategy_plugin: str) -> dict[str, Any]:
        spec = self._plugin_parameter_spec(strategy_plugin)
        if not spec:
            return {
                key: self.random.choice(values)
                for key, values in self.parameter_space.items()
            }

        return {
            name: self._random_value_from_spec(parameter_spec)
            for name, parameter_spec in spec.items()
        }

    def _plugin_parameter_spec(self, strategy_plugin: str) -> dict[str, Any]:
        try:
            plugin = create_plugin(strategy_plugin)
            spec = plugin.get_parameters()
        except Exception:
            return {}
        return dict(spec) if isinstance(spec, dict) else {}

    def _generate_grid_from_space(
        self,
        parameter_space: dict[str, Iterable[Any]],
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        keys = list(parameter_space.keys())
        experiments = []
        for values in product(*(tuple(parameter_space[key]) for key in keys)):
            params = dict(zip(keys, values, strict=True))
            if self._is_valid(params):
                experiments.append(params)
                if limit and len(experiments) >= limit:
                    break
        return experiments

    def _grid_values_from_spec(self, parameter_spec: dict[str, Any]) -> tuple[Any, ...]:
        parameter_type = parameter_spec.get("type")
        default = parameter_spec.get("default")
        if parameter_type == "bool":
            return (False, True)
        if parameter_type == "str":
            return (str(default or ""),)

        if parameter_type in {"int", "decimal"}:
            low = parameter_spec.get("min", default)
            high = parameter_spec.get("max", default)
            values = (low, default, high)
            normalized = []
            for value in values:
                if value is None:
                    continue
                cast = self._cast_spec_value(value, parameter_type)
                if cast not in normalized:
                    normalized.append(cast)
            return tuple(normalized)

        return (default,)

    def _random_value_from_spec(self, parameter_spec: dict[str, Any]) -> Any:
        parameter_type = parameter_spec.get("type")
        default = parameter_spec.get("default")
        if parameter_type == "bool":
            return self.random.choice((False, True))
        if parameter_type == "str":
            return str(default or "")
        if parameter_type == "int":
            low = int(parameter_spec.get("min", default))
            high = int(parameter_spec.get("max", default))
            return self.random.randint(low, high)
        if parameter_type == "decimal":
            low = float(parameter_spec.get("min", default))
            high = float(parameter_spec.get("max", default))
            return round(self.random.uniform(low, high), 4)
        return default

    def _cast_spec_value(self, value: Any, parameter_type: str) -> Any:
        if parameter_type == "int":
            return int(round(float(value)))
        if parameter_type == "decimal":
            return round(float(value), 4)
        return value

    def _plugin_experiment(
        self,
        strategy_plugin: str,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "experiment_type": "strategy_plugin",
            "strategy_plugin": strategy_plugin,
            "plugin_parameters": parameters,
        }
