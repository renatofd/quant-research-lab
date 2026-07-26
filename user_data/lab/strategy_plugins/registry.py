from __future__ import annotations

from typing import Any

from .base import StrategyPlugin
from .mean_reversion_strategy import MeanReversionStrategy
from .n_of_m_trend_confirmation import NOfMTrendConfirmationStrategy
from .placeholders import (
    BreakoutStrategy,
    MomentumStrategy,
    PullbackStrategy,
    ScalpingStrategy,
    TrendStrategy,
    VolatilityStrategy,
)


PLUGIN_CLASSES: dict[str, type[StrategyPlugin]] = {
    "TrendStrategy": TrendStrategy,
    "PullbackStrategy": PullbackStrategy,
    "BreakoutStrategy": BreakoutStrategy,
    "MeanReversionStrategy": MeanReversionStrategy,
    "ScalpingStrategy": ScalpingStrategy,
    "MomentumStrategy": MomentumStrategy,
    "VolatilityStrategy": VolatilityStrategy,
    "NOfMTrendConfirmationStrategy": NOfMTrendConfirmationStrategy,
}


def available_plugins() -> list[str]:
    return sorted(PLUGIN_CLASSES)


def create_plugin(name: str, parameters: dict[str, Any] | None = None) -> StrategyPlugin:
    plugin_class = PLUGIN_CLASSES.get(name)
    if plugin_class is None:
        available = ", ".join(available_plugins())
        raise ValueError(f"Unknown strategy plugin '{name}'. Available plugins: {available}")
    return plugin_class()
