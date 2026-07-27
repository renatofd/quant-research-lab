from pathlib import Path
import sys

from pandas import DataFrame

from freqtrade.strategy import IStrategy


USER_DATA_DIR = Path(__file__).resolve().parents[1]
if str(USER_DATA_DIR) not in sys.path:
    sys.path.append(str(USER_DATA_DIR))

from indicators.momentum import add_momentum_indicators  # noqa: E402
from indicators.trend import add_trend_indicators  # noqa: E402
from indicators.volatility import add_volatility_indicators  # noqa: E402


class BaseStrategy(IStrategy):
    def _runmode_name(self) -> str:
        runmode = self.config.get("runmode") if hasattr(self, "config") else None
        return str(getattr(runmode, "value", runmode) or "").lower().replace("-", "_")

    def _is_hyperopt_mode(self) -> bool:
        return self._runmode_name() == "hyperopt"

    def _is_backtest_mode(self) -> bool:
        return self._runmode_name() == "backtest"

    def _parameter_range(self, name: str, default: int):
        parameter = getattr(self, name, None)

        if parameter is None:
            return [default]

        if self._is_hyperopt_mode():
            return getattr(parameter, "range", [default])

        return [int(getattr(parameter, "value", default))]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = add_trend_indicators(
            dataframe,
            fast_periods=self._parameter_range("buy_ema_fast", 9),
            slow_periods=self._parameter_range("buy_ema_slow", 21),
            trend_periods=self._parameter_range("buy_ema_trend", 200),
        )
        dataframe = add_momentum_indicators(dataframe)
        dataframe = add_volatility_indicators(dataframe)

        if self._is_backtest_mode():
            from indicators.decision_engine import add_passive_decision
            from indicators.regime import add_market_regime
            from indicators.signal_score import add_signal_score

            dataframe = add_market_regime(dataframe)
            dataframe = add_signal_score(dataframe)
            dataframe = add_passive_decision(dataframe)

        return dataframe
