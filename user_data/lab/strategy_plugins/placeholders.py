from __future__ import annotations

from typing import Any

import pandas as pd
from pandas import DataFrame

from .base import EmptySignalPlugin


class TrendStrategy(EmptySignalPlugin):
    name = "TrendStrategy"

    PARAMETER_SPEC = {
        "ema_fast_period": {"default": 12, "min": 5, "max": 30, "type": "int"},
        "ema_slow_period": {"default": 34, "min": 16, "max": 80, "type": "int"},
        "ema_trend_period": {"default": 200, "min": 100, "max": 300, "type": "int"},
        "adx_period": {"default": 14, "min": 7, "max": 35, "type": "int"},
        "atr_period": {"default": 14, "min": 7, "max": 35, "type": "int"},
        "rsi_period": {"default": 14, "min": 7, "max": 35, "type": "int"},
        "volume_mean_period": {"default": 20, "min": 10, "max": 60, "type": "int"},
        "adx_entry_threshold": {"default": 22.0, "min": 12.0, "max": 45.0, "type": "decimal"},
        "adx_exit_threshold": {"default": 18.0, "min": 8.0, "max": 35.0, "type": "decimal"},
        "rsi_min": {"default": 45.0, "min": 30.0, "max": 60.0, "type": "decimal"},
        "rsi_max": {"default": 68.0, "min": 50.0, "max": 80.0, "type": "decimal"},
        "volume_multiplier": {"default": 1.2, "min": 1.0, "max": 3.0, "type": "decimal"},
        "atr_min_percent": {"default": 0.25, "min": 0.05, "max": 2.0, "type": "decimal"},
        "entry_score_threshold": {"default": 7.0, "min": 1.0, "max": 14.0, "type": "decimal"},
        "ema_fast_slow_weight": {"default": 2.0, "min": 0.0, "max": 5.0, "type": "decimal"},
        "ema_slow_trend_weight": {"default": 2.0, "min": 0.0, "max": 5.0, "type": "decimal"},
        "adx_weight": {"default": 2.0, "min": 0.0, "max": 5.0, "type": "decimal"},
        "rsi_weight": {"default": 1.0, "min": 0.0, "max": 5.0, "type": "decimal"},
        "volume_weight": {"default": 1.0, "min": 0.0, "max": 5.0, "type": "decimal"},
        "atr_weight": {"default": 1.0, "min": 0.0, "max": 5.0, "type": "decimal"},
        "breakout_weight": {"default": 1.0, "min": 0.0, "max": 5.0, "type": "decimal"},
        "trend_loss_exit_weight": {"default": 1.0, "min": 0.0, "max": 5.0, "type": "decimal"},
        "adx_loss_exit_weight": {"default": 1.0, "min": 0.0, "max": 5.0, "type": "decimal"},
        "exit_score_threshold": {"default": 1.0, "min": 1.0, "max": 2.0, "type": "decimal"},
        "roi": {"default": 0.01, "min": 0.002, "max": 0.03, "type": "decimal"},
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

        score = pd.Series(0.0, index=dataframe.index)
        ema_fast_slow = dataframe["trend_ema_fast"] > dataframe["trend_ema_slow"]
        ema_slow_trend = dataframe["trend_ema_slow"] > dataframe["trend_ema_trend"]
        adx_strong = dataframe["trend_adx"] > params["adx_entry_threshold"]
        rsi_healthy = dataframe["trend_rsi"].between(params["rsi_min"], params["rsi_max"])
        volume_expanded = (
            dataframe["volume"]
            > dataframe["trend_volume_mean"] * params["volume_multiplier"]
        )
        atr_active = dataframe["trend_atr_percent"] > params["atr_min_percent"]
        candle_breakout = dataframe["close"] > dataframe["high"].shift(1)

        score += ema_fast_slow.astype(float) * params["ema_fast_slow_weight"]
        score += ema_slow_trend.astype(float) * params["ema_slow_trend_weight"]
        score += adx_strong.astype(float) * params["adx_weight"]
        score += rsi_healthy.astype(float) * params["rsi_weight"]
        score += volume_expanded.astype(float) * params["volume_weight"]
        score += atr_active.astype(float) * params["atr_weight"]
        score += candle_breakout.astype(float) * params["breakout_weight"]

        dataframe["trend_entry_score"] = score
        dataframe["enter_long"] = (
            score >= params["entry_score_threshold"]
        ).astype(int)
        dataframe["enter_tag"] = ""

        entry_mask = dataframe["enter_long"] == 1
        if entry_mask.any():
            dataframe.loc[entry_mask, "enter_tag"] = [
                self._entry_reason(row, params)
                for _, row in dataframe.loc[entry_mask].iterrows()
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

        trend_lost = dataframe["trend_ema_fast"] < dataframe["trend_ema_slow"]
        adx_lost = dataframe["trend_adx"] < params["adx_exit_threshold"]
        exit_score = (
            trend_lost.astype(float) * params["trend_loss_exit_weight"]
            + adx_lost.astype(float) * params["adx_loss_exit_weight"]
        )

        dataframe["trend_exit_score"] = exit_score
        dataframe["exit_long"] = (
            exit_score >= params["exit_score_threshold"]
        ).astype(int)
        dataframe["exit_tag"] = ""

        exit_mask = dataframe["exit_long"] == 1
        if exit_mask.any():
            dataframe.loc[exit_mask, "exit_tag"] = [
                self._exit_reason(row, params)
                for _, row in dataframe.loc[exit_mask].iterrows()
            ]

        return dataframe

    def _parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        defaults = {
            name: spec["default"]
            for name, spec in self.PARAMETER_SPEC.items()
        }
        aliases = {
            "ema_fast_period": "buy_ema_fast",
            "ema_slow_period": "buy_ema_slow",
            "ema_trend_period": "buy_ema_trend",
            "rsi_min": "buy_rsi_min",
            "rsi_max": "buy_rsi_max",
            "volume_multiplier": "buy_volume_mult",
        }

        resolved = defaults.copy()
        for name in resolved:
            if name in parameters:
                resolved[name] = parameters[name]
            elif aliases.get(name) in parameters:
                resolved[name] = parameters[aliases[name]]

        for name, spec in self.PARAMETER_SPEC.items():
            if spec["type"] == "int":
                resolved[name] = int(resolved[name])
            else:
                resolved[name] = float(resolved[name])

        return resolved

    def _ensure_indicators(self, dataframe: DataFrame, params: dict[str, Any]) -> DataFrame:
        dataframe["trend_ema_fast"] = dataframe["close"].ewm(
            span=params["ema_fast_period"],
            adjust=False,
        ).mean()
        dataframe["trend_ema_slow"] = dataframe["close"].ewm(
            span=params["ema_slow_period"],
            adjust=False,
        ).mean()
        dataframe["trend_ema_trend"] = dataframe["close"].ewm(
            span=params["ema_trend_period"],
            adjust=False,
        ).mean()
        dataframe["trend_rsi"] = self._rsi(dataframe["close"], params["rsi_period"])
        dataframe["trend_atr"] = self._atr(dataframe, params["atr_period"])
        dataframe["trend_atr_percent"] = (
            dataframe["trend_atr"] / dataframe["close"] * 100.0
        )
        dataframe["trend_adx"] = self._adx(dataframe, params["adx_period"])
        dataframe["trend_volume_mean"] = dataframe["volume"].rolling(
            params["volume_mean_period"],
            min_periods=params["volume_mean_period"],
        ).mean()
        dataframe["trend_previous_high"] = dataframe["high"].shift(1)

        return dataframe

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

    def _entry_reason(self, row: pd.Series, params: dict[str, Any]) -> str:
        volume_ratio = row["volume"] / row["trend_volume_mean"]
        previous_high = row["trend_previous_high"]
        reasons = [
            self._reason(
                row["trend_ema_fast"] > row["trend_ema_slow"],
                "EMA fast above slow",
                params["ema_fast_slow_weight"],
            ),
            self._reason(
                row["trend_ema_slow"] > row["trend_ema_trend"],
                "EMA slow above trend",
                params["ema_slow_trend_weight"],
            ),
            self._reason(
                row["trend_adx"] > params["adx_entry_threshold"],
                f"ADX={row['trend_adx']:.2f}>{params['adx_entry_threshold']:.2f}",
                params["adx_weight"],
            ),
            self._reason(
                params["rsi_min"] <= row["trend_rsi"] <= params["rsi_max"],
                f"RSI={row['trend_rsi']:.2f} in healthy range",
                params["rsi_weight"],
            ),
            self._reason(
                volume_ratio > params["volume_multiplier"],
                f"Volume={volume_ratio:.2f}x mean",
                params["volume_weight"],
            ),
            self._reason(
                row["trend_atr_percent"] > params["atr_min_percent"],
                f"ATR={row['trend_atr_percent']:.2f}% active",
                params["atr_weight"],
            ),
            self._reason(
                row["close"] > previous_high,
                f"Close={row['close']:.6f}>{previous_high:.6f}",
                params["breakout_weight"],
            ),
        ]
        details = [reason for reason in reasons if reason]
        return f"TrendScore={row['trend_entry_score']:.2f}; " + "; ".join(details)

    def _exit_reason(self, row: pd.Series, params: dict[str, Any]) -> str:
        reasons = [
            self._reason(
                row["trend_ema_fast"] < row["trend_ema_slow"],
                "EMA fast below slow",
                params["trend_loss_exit_weight"],
            ),
            self._reason(
                row["trend_adx"] < params["adx_exit_threshold"],
                f"ADX={row['trend_adx']:.2f}<{params['adx_exit_threshold']:.2f}",
                params["adx_loss_exit_weight"],
            ),
        ]
        details = [reason for reason in reasons if reason]
        return f"TrendExitScore={row['trend_exit_score']:.2f}; " + "; ".join(details)

    def _reason(self, passed: bool, text: str, weight: float) -> str:
        return f"{text} (+{weight:g})" if passed else ""


class PullbackStrategy(EmptySignalPlugin):
    name = "PullbackStrategy"

    PARAMETER_SPEC = {
        "ema_fast_period": {"default": 21, "min": 5, "max": 50, "type": "int"},
        "ema_slow_period": {"default": 55, "min": 20, "max": 120, "type": "int"},
        "ema_trend_period": {"default": 200, "min": 100, "max": 300, "type": "int"},
        "rsi_period": {"default": 14, "min": 7, "max": 35, "type": "int"},
        "atr_period": {"default": 14, "min": 7, "max": 35, "type": "int"},
        "volume_mean_period": {"default": 20, "min": 10, "max": 80, "type": "int"},
        "pullback_lookback": {"default": 5, "min": 2, "max": 20, "type": "int"},
        "trend_buffer_percent": {"default": 0.0, "min": 0.0, "max": 2.0, "type": "decimal"},
        "pullback_tolerance_percent": {"default": 0.35, "min": 0.05, "max": 2.0, "type": "decimal"},
        "max_pullback_depth_percent": {"default": 3.0, "min": 0.5, "max": 8.0, "type": "decimal"},
        "recovery_close_percent": {"default": 0.05, "min": 0.0, "max": 1.0, "type": "decimal"},
        "rsi_min": {"default": 38.0, "min": 25.0, "max": 55.0, "type": "decimal"},
        "rsi_max": {"default": 68.0, "min": 50.0, "max": 82.0, "type": "decimal"},
        "volume_multiplier": {"default": 1.15, "min": 0.8, "max": 3.0, "type": "decimal"},
        "atr_min_percent": {"default": 0.20, "min": 0.0, "max": 2.0, "type": "decimal"},
        "entry_score_threshold": {"default": 7.0, "min": 1.0, "max": 16.0, "type": "decimal"},
        "trend_weight": {"default": 2.0, "min": 0.0, "max": 5.0, "type": "decimal"},
        "pullback_touch_weight": {"default": 2.0, "min": 0.0, "max": 5.0, "type": "decimal"},
        "pullback_control_weight": {"default": 1.5, "min": 0.0, "max": 5.0, "type": "decimal"},
        "reclaim_ema_weight": {"default": 2.0, "min": 0.0, "max": 5.0, "type": "decimal"},
        "confirmation_weight": {"default": 2.0, "min": 0.0, "max": 5.0, "type": "decimal"},
        "rsi_weight": {"default": 1.0, "min": 0.0, "max": 5.0, "type": "decimal"},
        "volume_weight": {"default": 1.0, "min": 0.0, "max": 5.0, "type": "decimal"},
        "atr_weight": {"default": 1.0, "min": 0.0, "max": 5.0, "type": "decimal"},
        "exit_score_threshold": {"default": 2.0, "min": 1.0, "max": 8.0, "type": "decimal"},
        "ema_fast_loss_weight": {"default": 1.5, "min": 0.0, "max": 5.0, "type": "decimal"},
        "ema_slow_loss_weight": {"default": 2.0, "min": 0.0, "max": 5.0, "type": "decimal"},
        "trend_loss_weight": {"default": 2.0, "min": 0.0, "max": 5.0, "type": "decimal"},
        "momentum_loss_weight": {"default": 1.0, "min": 0.0, "max": 5.0, "type": "decimal"},
        "roi": {"default": 0.012, "min": 0.002, "max": 0.04, "type": "decimal"},
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

        score = pd.Series(0.0, index=dataframe.index)
        main_trend = (
            (dataframe["pullback_ema_fast"] > dataframe["pullback_ema_slow"])
            & (dataframe["pullback_ema_slow"] > dataframe["pullback_ema_trend"])
            & (
                dataframe["close"]
                > dataframe["pullback_ema_trend"]
                * (1.0 + params["trend_buffer_percent"] / 100.0)
            )
        )
        pullback_touch = dataframe["pullback_recent_touch"]
        pullback_controlled = dataframe["pullback_controlled"]
        reclaim_ema = dataframe["close"] > dataframe["pullback_ema_fast"]
        resume_confirmation = (
            (dataframe["close"] > dataframe["open"])
            & (dataframe["close"] > dataframe["high"].shift(1))
            & (
                dataframe["close"]
                > dataframe["close"].shift(1)
                * (1.0 + params["recovery_close_percent"] / 100.0)
            )
        )
        rsi_healthy = dataframe["pullback_rsi"].between(params["rsi_min"], params["rsi_max"])
        volume_expanded = (
            dataframe["volume"]
            > dataframe["pullback_volume_mean"] * params["volume_multiplier"]
        )
        atr_active = dataframe["pullback_atr_percent"] > params["atr_min_percent"]

        score += main_trend.astype(float) * params["trend_weight"]
        score += pullback_touch.astype(float) * params["pullback_touch_weight"]
        score += pullback_controlled.astype(float) * params["pullback_control_weight"]
        score += reclaim_ema.astype(float) * params["reclaim_ema_weight"]
        score += resume_confirmation.astype(float) * params["confirmation_weight"]
        score += rsi_healthy.astype(float) * params["rsi_weight"]
        score += volume_expanded.astype(float) * params["volume_weight"]
        score += atr_active.astype(float) * params["atr_weight"]

        dataframe["pullback_entry_score"] = score
        dataframe["enter_long"] = (
            score >= params["entry_score_threshold"]
        ).astype(int)
        dataframe["enter_tag"] = ""

        entry_mask = dataframe["enter_long"] == 1
        if entry_mask.any():
            dataframe.loc[entry_mask, "enter_tag"] = [
                self._entry_reason(row, params)
                for _, row in dataframe.loc[entry_mask].iterrows()
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

        lost_fast_ema = dataframe["close"] < dataframe["pullback_ema_fast"]
        lost_slow_ema = dataframe["close"] < dataframe["pullback_ema_slow"]
        trend_lost = dataframe["pullback_ema_fast"] < dataframe["pullback_ema_slow"]
        momentum_lost = dataframe["close"] < dataframe["low"].shift(1)

        exit_score = (
            lost_fast_ema.astype(float) * params["ema_fast_loss_weight"]
            + lost_slow_ema.astype(float) * params["ema_slow_loss_weight"]
            + trend_lost.astype(float) * params["trend_loss_weight"]
            + momentum_lost.astype(float) * params["momentum_loss_weight"]
        )

        dataframe["pullback_exit_score"] = exit_score
        dataframe["exit_long"] = (
            exit_score >= params["exit_score_threshold"]
        ).astype(int)
        dataframe["exit_tag"] = ""

        exit_mask = dataframe["exit_long"] == 1
        if exit_mask.any():
            dataframe.loc[exit_mask, "exit_tag"] = [
                self._exit_reason(row, params)
                for _, row in dataframe.loc[exit_mask].iterrows()
            ]

        return dataframe

    def _parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        defaults = {
            name: spec["default"]
            for name, spec in self.PARAMETER_SPEC.items()
        }
        aliases = {
            "ema_fast_period": "buy_ema_fast",
            "ema_slow_period": "buy_ema_slow",
            "ema_trend_period": "buy_ema_trend",
            "rsi_min": "buy_rsi_min",
            "rsi_max": "buy_rsi_max",
            "volume_multiplier": "buy_volume_mult",
        }

        resolved = defaults.copy()
        for name in resolved:
            if name in parameters:
                resolved[name] = parameters[name]
            elif aliases.get(name) in parameters:
                resolved[name] = parameters[aliases[name]]

        for name, spec in self.PARAMETER_SPEC.items():
            if spec["type"] == "int":
                resolved[name] = int(resolved[name])
            else:
                resolved[name] = float(resolved[name])

        if resolved["ema_fast_period"] >= resolved["ema_slow_period"]:
            resolved["ema_slow_period"] = resolved["ema_fast_period"] + 1
        if resolved["ema_slow_period"] >= resolved["ema_trend_period"]:
            resolved["ema_trend_period"] = resolved["ema_slow_period"] + 1
        if resolved["rsi_min"] >= resolved["rsi_max"]:
            resolved["rsi_max"] = resolved["rsi_min"] + 1.0

        return resolved

    def _ensure_indicators(self, dataframe: DataFrame, params: dict[str, Any]) -> DataFrame:
        dataframe["pullback_ema_fast"] = dataframe["close"].ewm(
            span=params["ema_fast_period"],
            adjust=False,
        ).mean()
        dataframe["pullback_ema_slow"] = dataframe["close"].ewm(
            span=params["ema_slow_period"],
            adjust=False,
        ).mean()
        dataframe["pullback_ema_trend"] = dataframe["close"].ewm(
            span=params["ema_trend_period"],
            adjust=False,
        ).mean()
        dataframe["pullback_rsi"] = self._rsi(dataframe["close"], params["rsi_period"])
        dataframe["pullback_atr"] = self._atr(dataframe, params["atr_period"])
        dataframe["pullback_atr_percent"] = (
            dataframe["pullback_atr"] / dataframe["close"] * 100.0
        )
        dataframe["pullback_volume_mean"] = dataframe["volume"].rolling(
            params["volume_mean_period"],
            min_periods=params["volume_mean_period"],
        ).mean()

        fast_ema = dataframe["pullback_ema_fast"]
        tolerance = params["pullback_tolerance_percent"] / 100.0
        max_depth = params["max_pullback_depth_percent"] / 100.0
        pullback_near_fast = (
            (dataframe["low"] <= fast_ema * (1.0 + tolerance))
            & (dataframe["low"] >= fast_ema * (1.0 - max_depth))
        )
        dataframe["pullback_recent_touch"] = (
            pullback_near_fast.astype(int)
            .rolling(params["pullback_lookback"], min_periods=1)
            .max()
            .astype(bool)
        )
        recent_min_low = dataframe["low"].rolling(
            params["pullback_lookback"],
            min_periods=1,
        ).min()
        dataframe["pullback_controlled"] = recent_min_low >= (
            fast_ema * (1.0 - max_depth)
        )
        dataframe["pullback_previous_high"] = dataframe["high"].shift(1)
        dataframe["pullback_previous_low"] = dataframe["low"].shift(1)

        return dataframe

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

    def _entry_reason(self, row: pd.Series, params: dict[str, Any]) -> str:
        volume_ratio = row["volume"] / row["pullback_volume_mean"]
        reasons = [
            self._reason(
                (
                    row["pullback_ema_fast"] > row["pullback_ema_slow"]
                    and row["pullback_ema_slow"] > row["pullback_ema_trend"]
                    and row["close"]
                    > row["pullback_ema_trend"]
                    * (1.0 + params["trend_buffer_percent"] / 100.0)
                ),
                "Main trend above long EMA",
                params["trend_weight"],
            ),
            self._reason(
                bool(row["pullback_recent_touch"]),
                f"Recent pullback touched EMA fast={row['pullback_ema_fast']:.6f}",
                params["pullback_touch_weight"],
            ),
            self._reason(
                bool(row["pullback_controlled"]),
                f"Pullback depth within {params['max_pullback_depth_percent']:.2f}%",
                params["pullback_control_weight"],
            ),
            self._reason(
                row["close"] > row["pullback_ema_fast"],
                f"Close reclaimed EMA fast ({row['close']:.6f}>{row['pullback_ema_fast']:.6f})",
                params["reclaim_ema_weight"],
            ),
            self._reason(
                row["close"] > row["open"]
                and row["close"] > row["pullback_previous_high"],
                f"Retake candle close>{row['pullback_previous_high']:.6f}",
                params["confirmation_weight"],
            ),
            self._reason(
                params["rsi_min"] <= row["pullback_rsi"] <= params["rsi_max"],
                f"RSI={row['pullback_rsi']:.2f} not overbought",
                params["rsi_weight"],
            ),
            self._reason(
                volume_ratio > params["volume_multiplier"],
                f"Volume={volume_ratio:.2f}x mean",
                params["volume_weight"],
            ),
            self._reason(
                row["pullback_atr_percent"] > params["atr_min_percent"],
                f"ATR={row['pullback_atr_percent']:.2f}% active",
                params["atr_weight"],
            ),
        ]
        details = [reason for reason in reasons if reason]
        return f"PullbackScore={row['pullback_entry_score']:.2f}; " + "; ".join(details)

    def _exit_reason(self, row: pd.Series, params: dict[str, Any]) -> str:
        reasons = [
            self._reason(
                row["close"] < row["pullback_ema_fast"],
                f"Close lost EMA fast ({row['close']:.6f}<{row['pullback_ema_fast']:.6f})",
                params["ema_fast_loss_weight"],
            ),
            self._reason(
                row["close"] < row["pullback_ema_slow"],
                f"Close lost EMA slow ({row['close']:.6f}<{row['pullback_ema_slow']:.6f})",
                params["ema_slow_loss_weight"],
            ),
            self._reason(
                row["pullback_ema_fast"] < row["pullback_ema_slow"],
                "EMA fast below EMA slow",
                params["trend_loss_weight"],
            ),
            self._reason(
                row["close"] < row["pullback_previous_low"],
                f"Close below previous low ({row['close']:.6f}<{row['pullback_previous_low']:.6f})",
                params["momentum_loss_weight"],
            ),
        ]
        details = [reason for reason in reasons if reason]
        return f"PullbackExitScore={row['pullback_exit_score']:.2f}; " + "; ".join(details)

    def _reason(self, passed: bool, text: str, weight: float) -> str:
        return f"{text} (+{weight:g})" if passed else ""


class BreakoutStrategy(EmptySignalPlugin):
    name = "BreakoutStrategy"


class MeanReversionStrategy(EmptySignalPlugin):
    name = "MeanReversionStrategy"


class ScalpingStrategy(EmptySignalPlugin):
    name = "ScalpingStrategy"


class MomentumStrategy(EmptySignalPlugin):
    name = "MomentumStrategy"


class VolatilityStrategy(EmptySignalPlugin):
    name = "VolatilityStrategy"
