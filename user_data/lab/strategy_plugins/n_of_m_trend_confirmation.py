from __future__ import annotations

from typing import Any

import pandas as pd
from pandas import DataFrame

from .base import EmptySignalPlugin


class NOfMTrendConfirmationStrategy(EmptySignalPlugin):
    name = "NOfMTrendConfirmationStrategy"

    PARAMETER_SPEC = {
        "ema_fast_period": {"default": 12, "min": 5, "max": 30, "type": "int"},
        "ema_slow_period": {"default": 34, "min": 16, "max": 80, "type": "int"},
        "ema_trend_period": {"default": 200, "min": 100, "max": 300, "type": "int"},
        "adx_period": {"default": 14, "min": 7, "max": 35, "type": "int"},
        "atr_period": {"default": 14, "min": 7, "max": 35, "type": "int"},
        "rsi_period": {"default": 14, "min": 7, "max": 35, "type": "int"},
        "volume_mean_period": {"default": 20, "min": 10, "max": 80, "type": "int"},
        "n_required": {"default": 4, "min": 2, "max": 6, "type": "int"},
        "exit_confirmation_floor": {"default": 2, "min": 0, "max": 5, "type": "int"},
        "require_ema_trend": {"default": True, "type": "bool"},
        "require_price_above_trend": {"default": False, "type": "bool"},
        "adx_entry_threshold": {"default": 22.0, "min": 10.0, "max": 45.0, "type": "decimal"},
        "adx_exit_threshold": {"default": 18.0, "min": 8.0, "max": 35.0, "type": "decimal"},
        "rsi_min": {"default": 42.0, "min": 25.0, "max": 60.0, "type": "decimal"},
        "rsi_max": {"default": 70.0, "min": 50.0, "max": 85.0, "type": "decimal"},
        "volume_multiplier": {"default": 1.1, "min": 0.8, "max": 3.0, "type": "decimal"},
        "atr_min_percent": {"default": 0.20, "min": 0.0, "max": 2.0, "type": "decimal"},
        "breakout_lookback": {"default": 1, "min": 1, "max": 8, "type": "int"},
        "roi": {"default": 0.01, "min": 0.002, "max": 0.04, "type": "decimal"},
        "stoploss": {"default": -0.04, "min": -0.12, "max": -0.01, "type": "decimal"},
    }

    def get_parameters(self) -> dict[str, Any]:
        return self.PARAMETER_SPEC

    def populate_entry(
        self,
        dataframe: DataFrame,
        metadata: dict[str, Any],
        parameters: dict[str, Any],
    ) -> DataFrame:
        params = self._parameters(parameters)
        dataframe = self._ensure_indicators(dataframe, params)

        confirmations = self._confirmation_frame(dataframe, params)
        count = confirmations.sum(axis=1)

        trend_gate = pd.Series(True, index=dataframe.index)
        if params["require_ema_trend"]:
            trend_gate &= confirmations["ema_fast_slow"] & confirmations["ema_slow_trend"]
        if params["require_price_above_trend"]:
            trend_gate &= dataframe["close"] > dataframe["nom_ema_trend"]

        dataframe["nom_confirmation_count"] = count
        dataframe["enter_long"] = ((count >= params["n_required"]) & trend_gate).astype(int)
        dataframe["enter_tag"] = ""

        entry_mask = dataframe["enter_long"] == 1
        if entry_mask.any():
            dataframe.loc[entry_mask, "enter_tag"] = [
                self._entry_reason(row, confirmations.loc[index], params)
                for index, row in dataframe.loc[entry_mask].iterrows()
            ]
        return dataframe

    def populate_exit(
        self,
        dataframe: DataFrame,
        metadata: dict[str, Any],
        parameters: dict[str, Any],
    ) -> DataFrame:
        params = self._parameters(parameters)
        dataframe = self._ensure_indicators(dataframe, params)
        confirmations = self._confirmation_frame(dataframe, params)
        count = confirmations.sum(axis=1)

        trend_lost = dataframe["nom_ema_fast"] < dataframe["nom_ema_slow"]
        momentum_lost = dataframe["nom_adx"] < params["adx_exit_threshold"]
        confirmation_lost = count <= params["exit_confirmation_floor"]

        dataframe["nom_exit_confirmation_count"] = count
        dataframe["exit_long"] = (trend_lost | momentum_lost | confirmation_lost).astype(int)
        dataframe["exit_tag"] = ""

        exit_mask = dataframe["exit_long"] == 1
        if exit_mask.any():
            dataframe.loc[exit_mask, "exit_tag"] = [
                self._exit_reason(row, confirmations.loc[index], params)
                for index, row in dataframe.loc[exit_mask].iterrows()
            ]
        return dataframe

    def _parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        resolved = {
            name: spec["default"]
            for name, spec in self.PARAMETER_SPEC.items()
        }
        for name in resolved:
            if name in parameters:
                resolved[name] = parameters[name]

        for name, spec in self.PARAMETER_SPEC.items():
            if spec.get("type") == "int":
                resolved[name] = int(resolved[name])
            elif spec.get("type") == "decimal":
                resolved[name] = float(resolved[name])
            elif spec.get("type") == "bool":
                resolved[name] = bool(resolved[name])

        resolved["n_required"] = max(1, min(6, int(resolved["n_required"])))
        resolved["exit_confirmation_floor"] = max(0, min(5, int(resolved["exit_confirmation_floor"])))
        return resolved

    def _ensure_indicators(self, dataframe: DataFrame, params: dict[str, Any]) -> DataFrame:
        dataframe["nom_ema_fast"] = dataframe["close"].ewm(
            span=params["ema_fast_period"],
            adjust=False,
        ).mean()
        dataframe["nom_ema_slow"] = dataframe["close"].ewm(
            span=params["ema_slow_period"],
            adjust=False,
        ).mean()
        dataframe["nom_ema_trend"] = dataframe["close"].ewm(
            span=params["ema_trend_period"],
            adjust=False,
        ).mean()
        dataframe["nom_rsi"] = self._rsi(dataframe["close"], params["rsi_period"])
        dataframe["nom_atr"] = self._atr(dataframe, params["atr_period"])
        dataframe["nom_atr_percent"] = dataframe["nom_atr"] / dataframe["close"] * 100.0
        dataframe["nom_adx"] = self._adx(dataframe, params["adx_period"])
        dataframe["nom_volume_mean"] = dataframe["volume"].rolling(
            params["volume_mean_period"],
            min_periods=params["volume_mean_period"],
        ).mean()
        return dataframe

    def _confirmation_frame(self, dataframe: DataFrame, params: dict[str, Any]) -> DataFrame:
        previous_high = dataframe["high"].shift(params["breakout_lookback"]).rolling(
            params["breakout_lookback"],
            min_periods=1,
        ).max()
        return pd.DataFrame(
            {
                "ema_fast_slow": dataframe["nom_ema_fast"] > dataframe["nom_ema_slow"],
                "ema_slow_trend": dataframe["nom_ema_slow"] > dataframe["nom_ema_trend"],
                "adx": dataframe["nom_adx"] > params["adx_entry_threshold"],
                "rsi": dataframe["nom_rsi"].between(params["rsi_min"], params["rsi_max"]),
                "volume": dataframe["volume"] > dataframe["nom_volume_mean"] * params["volume_multiplier"],
                "atr": dataframe["nom_atr_percent"] > params["atr_min_percent"],
                "breakout": dataframe["close"] > previous_high,
            },
            index=dataframe.index,
        ).fillna(False)

    def _rsi(self, close: pd.Series, period: int) -> pd.Series:
        delta = close.diff()
        gain = delta.clip(lower=0.0)
        loss = -delta.clip(upper=0.0)
        avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        relative_strength = avg_gain / avg_loss.where(avg_loss != 0.0)
        return 100.0 - (100.0 / (1.0 + relative_strength))

    def _atr(self, dataframe: DataFrame, period: int) -> pd.Series:
        previous_close = dataframe["close"].shift(1)
        true_range = pd.concat(
            [
                dataframe["high"] - dataframe["low"],
                (dataframe["high"] - previous_close).abs(),
                (dataframe["low"] - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        return true_range.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    def _adx(self, dataframe: DataFrame, period: int) -> pd.Series:
        up_move = dataframe["high"].diff()
        down_move = -dataframe["low"].diff()
        plus_dm = up_move.where((up_move > down_move) & (up_move > 0.0), 0.0)
        minus_dm = down_move.where((down_move > up_move) & (down_move > 0.0), 0.0)
        atr = self._atr(dataframe, period)
        plus_di = 100.0 * plus_dm.ewm(
            alpha=1 / period,
            min_periods=period,
            adjust=False,
        ).mean() / atr
        minus_di = 100.0 * minus_dm.ewm(
            alpha=1 / period,
            min_periods=period,
            adjust=False,
        ).mean() / atr
        dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di)
        return dx.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    def _entry_reason(
        self,
        row: pd.Series,
        confirmations: pd.Series,
        params: dict[str, Any],
    ) -> str:
        active = [name for name, passed in confirmations.items() if passed]
        return (
            f"NOfM={int(row['nom_confirmation_count'])}/{params['n_required']}; "
            + ",".join(active)
        )

    def _exit_reason(
        self,
        row: pd.Series,
        confirmations: pd.Series,
        params: dict[str, Any],
    ) -> str:
        active = [name for name, passed in confirmations.items() if passed]
        return (
            f"NOfMExit={int(row['nom_exit_confirmation_count'])}"
            f"<=floor({params['exit_confirmation_floor']}); active="
            + ",".join(active)
        )
