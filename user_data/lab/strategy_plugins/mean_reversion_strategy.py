from __future__ import annotations

from typing import Any

import pandas as pd
from pandas import DataFrame

from .base import EmptySignalPlugin


class MeanReversionStrategy(EmptySignalPlugin):
    """Phase 2 experimental mean-reversion plugin.

    The idea is intentionally different from TrendStrategy: entries wait for
    statistically stretched downside moves around Bollinger Bands, Z-score and
    VWAP, then exits on reversion toward the mean.
    """

    name = "MeanReversionStrategy"

    PARAMETER_SPEC = {
        "bollinger_period": {"default": 24, "min": 10, "max": 80, "type": "int"},
        "bollinger_std": {"default": 2.2, "min": 1.5, "max": 3.5, "type": "decimal"},
        "zscore_period": {"default": 48, "min": 12, "max": 120, "type": "int"},
        "entry_zscore": {"default": -2.0, "min": -4.0, "max": -0.8, "type": "decimal"},
        "exit_zscore": {"default": -0.15, "min": -1.0, "max": 0.8, "type": "decimal"},
        "vwap_period": {"default": 48, "min": 12, "max": 144, "type": "int"},
        "vwap_deviation_min_pct": {"default": 0.45, "min": 0.05, "max": 3.0, "type": "decimal"},
        "rsi_period": {"default": 14, "min": 7, "max": 35, "type": "int"},
        "rsi_oversold": {"default": 34.0, "min": 15.0, "max": 45.0, "type": "decimal"},
        "rsi_exit": {"default": 52.0, "min": 40.0, "max": 70.0, "type": "decimal"},
        "atr_period": {"default": 14, "min": 7, "max": 35, "type": "int"},
        "atr_min_percent": {"default": 0.08, "min": 0.0, "max": 1.0, "type": "decimal"},
        "atr_max_percent": {"default": 3.0, "min": 0.5, "max": 8.0, "type": "decimal"},
        "volume_mean_period": {"default": 30, "min": 10, "max": 120, "type": "int"},
        "volume_min_ratio": {"default": 0.75, "min": 0.2, "max": 2.0, "type": "decimal"},
        "volume_max_ratio": {"default": 4.0, "min": 1.0, "max": 10.0, "type": "decimal"},
        "require_bullish_reclaim": {"default": True, "type": "bool"},
        "reclaim_min_fraction": {"default": 0.55, "min": 0.2, "max": 0.9, "type": "decimal"},
        "allowed_weekdays": {"default": "TUESDAY,FRIDAY", "type": "str"},
        "allowed_hours": {"default": "14,15,16", "type": "str"},
        "allowed_sessions": {"default": "NY", "type": "str"},
        "excluded_pairs": {"default": "BTC/USDT,XRP/USDT", "type": "str"},
        "enable_failure_exit": {"default": True, "type": "bool"},
        "failure_zscore": {"default": -3.4, "min": -6.0, "max": -2.0, "type": "decimal"},
        "roi": {"default": 0.012, "min": 0.002, "max": 0.05, "type": "decimal"},
        "stoploss": {"default": -0.035, "min": -0.12, "max": -0.01, "type": "decimal"},
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

        pair_allowed = self._pair_allowed(metadata, params)
        time_allowed = self._time_allowed(dataframe, params)
        bollinger_stretch = dataframe["mr_close"] <= dataframe["mr_bb_lower"]
        zscore_stretch = dataframe["mr_zscore"] <= params["entry_zscore"]
        vwap_stretch = dataframe["mr_vwap_deviation_pct"] <= -params["vwap_deviation_min_pct"]
        rsi_confirm = dataframe["mr_rsi"] <= params["rsi_oversold"]
        atr_filter = dataframe["mr_atr_percent"].between(
            params["atr_min_percent"],
            params["atr_max_percent"],
        )
        volume_filter = dataframe["mr_volume_ratio"].between(
            params["volume_min_ratio"],
            params["volume_max_ratio"],
        )
        reclaim = self._reclaim_condition(dataframe, params)

        entry = (
            pair_allowed
            & time_allowed
            & (bollinger_stretch | zscore_stretch)
            & vwap_stretch
            & rsi_confirm
            & atr_filter
            & volume_filter
            & reclaim
        )

        dataframe["enter_long"] = entry.fillna(False).astype(int)
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

        middle_reversion = dataframe["mr_close"] >= dataframe["mr_bb_middle"]
        vwap_reversion = dataframe["mr_close"] >= dataframe["mr_vwap"]
        zscore_reversion = dataframe["mr_zscore"] >= params["exit_zscore"]
        rsi_reversion = dataframe["mr_rsi"] >= params["rsi_exit"]
        failure_exit = (
            dataframe["mr_zscore"] <= params["failure_zscore"]
            if params["enable_failure_exit"]
            else pd.Series(False, index=dataframe.index)
        )

        exit_signal = (
            middle_reversion
            | vwap_reversion
            | zscore_reversion
            | rsi_reversion
            | failure_exit
        )
        dataframe["exit_long"] = exit_signal.fillna(False).astype(int)
        dataframe["exit_tag"] = ""
        exit_mask = dataframe["exit_long"] == 1
        if exit_mask.any():
            dataframe.loc[exit_mask, "exit_tag"] = [
                self._exit_reason(row, params)
                for _, row in dataframe.loc[exit_mask].iterrows()
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
            parameter_type = spec.get("type")
            if parameter_type == "int":
                resolved[name] = max(1, int(resolved[name]))
            elif parameter_type == "decimal":
                resolved[name] = float(resolved[name])
            elif parameter_type == "bool":
                resolved[name] = self._bool(resolved[name])
            elif parameter_type == "str":
                resolved[name] = str(resolved[name])

        if resolved["atr_min_percent"] > resolved["atr_max_percent"]:
            resolved["atr_min_percent"], resolved["atr_max_percent"] = (
                resolved["atr_max_percent"],
                resolved["atr_min_percent"],
            )
        if resolved["volume_min_ratio"] > resolved["volume_max_ratio"]:
            resolved["volume_min_ratio"], resolved["volume_max_ratio"] = (
                resolved["volume_max_ratio"],
                resolved["volume_min_ratio"],
            )
        return resolved

    def _ensure_indicators(self, dataframe: DataFrame, params: dict[str, Any]) -> DataFrame:
        dataframe["mr_close"] = dataframe["close"].astype(float)
        dataframe["mr_typical_price"] = (
            dataframe["high"].astype(float)
            + dataframe["low"].astype(float)
            + dataframe["close"].astype(float)
        ) / 3.0
        rolling_mean = dataframe["mr_close"].rolling(
            params["bollinger_period"],
            min_periods=params["bollinger_period"],
        ).mean()
        rolling_std = dataframe["mr_close"].rolling(
            params["bollinger_period"],
            min_periods=params["bollinger_period"],
        ).std(ddof=0)
        dataframe["mr_bb_middle"] = rolling_mean
        dataframe["mr_bb_upper"] = rolling_mean + rolling_std * params["bollinger_std"]
        dataframe["mr_bb_lower"] = rolling_mean - rolling_std * params["bollinger_std"]

        z_mean = dataframe["mr_close"].rolling(
            params["zscore_period"],
            min_periods=params["zscore_period"],
        ).mean()
        z_std = dataframe["mr_close"].rolling(
            params["zscore_period"],
            min_periods=params["zscore_period"],
        ).std(ddof=0)
        dataframe["mr_zscore"] = (dataframe["mr_close"] - z_mean) / z_std.replace(0.0, pd.NA)

        volume = dataframe["volume"].astype(float)
        volume_price = dataframe["mr_typical_price"] * volume
        rolling_volume = volume.rolling(
            params["vwap_period"],
            min_periods=params["vwap_period"],
        ).sum()
        dataframe["mr_vwap"] = volume_price.rolling(
            params["vwap_period"],
            min_periods=params["vwap_period"],
        ).sum() / rolling_volume.replace(0.0, pd.NA)
        dataframe["mr_vwap_deviation_pct"] = (
            (dataframe["mr_close"] - dataframe["mr_vwap"])
            / dataframe["mr_vwap"].replace(0.0, pd.NA)
            * 100.0
        )

        dataframe["mr_rsi"] = self._rsi(dataframe["mr_close"], params["rsi_period"])
        dataframe["mr_atr"] = self._atr(dataframe, params["atr_period"])
        dataframe["mr_atr_percent"] = dataframe["mr_atr"] / dataframe["mr_close"] * 100.0
        dataframe["mr_volume_mean"] = volume.rolling(
            params["volume_mean_period"],
            min_periods=params["volume_mean_period"],
        ).mean()
        dataframe["mr_volume_ratio"] = volume / dataframe["mr_volume_mean"].replace(0.0, pd.NA)
        dataframe["mr_candle_reclaim_fraction"] = (
            (dataframe["close"] - dataframe["low"])
            / (dataframe["high"] - dataframe["low"]).replace(0.0, pd.NA)
        )
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

    def _reclaim_condition(self, dataframe: DataFrame, params: dict[str, Any]) -> pd.Series:
        if not params["require_bullish_reclaim"]:
            return pd.Series(True, index=dataframe.index)
        bullish_close = dataframe["close"] >= dataframe["open"]
        reclaim_fraction = dataframe["mr_candle_reclaim_fraction"] >= params["reclaim_min_fraction"]
        close_improving = dataframe["close"] > dataframe["close"].shift(1)
        return bullish_close & reclaim_fraction & close_improving

    def _pair_allowed(self, metadata: dict[str, Any], params: dict[str, Any]) -> bool:
        pair = str(metadata.get("pair") or "").upper()
        excluded = self._csv_set(params["excluded_pairs"])
        return not pair or pair not in excluded

    def _time_allowed(self, dataframe: DataFrame, params: dict[str, Any]) -> pd.Series:
        dates = self._date_series(dataframe)
        if dates is None:
            return pd.Series(True, index=dataframe.index)
        allowed_weekdays = self._csv_set(params["allowed_weekdays"])
        allowed_hours = self._int_set(params["allowed_hours"])
        allowed_sessions = self._csv_set(params["allowed_sessions"])
        weekday_ok = (
            dates.dt.day_name().str.upper().isin(allowed_weekdays)
            if allowed_weekdays
            else pd.Series(True, index=dataframe.index)
        )
        hour_ok = (
            dates.dt.hour.isin(allowed_hours)
            if allowed_hours
            else pd.Series(True, index=dataframe.index)
        )
        session_ok = (
            dates.dt.hour.map(self._session).isin(allowed_sessions)
            if allowed_sessions
            else pd.Series(True, index=dataframe.index)
        )
        return weekday_ok & hour_ok & session_ok

    def _date_series(self, dataframe: DataFrame) -> pd.Series | None:
        if "date" in dataframe:
            dates = pd.to_datetime(dataframe["date"], utc=True, errors="coerce")
            return pd.Series(dates, index=dataframe.index)
        if isinstance(dataframe.index, pd.DatetimeIndex):
            return pd.Series(pd.to_datetime(dataframe.index, utc=True), index=dataframe.index)
        return None

    def _session(self, hour: int) -> str:
        if 0 <= int(hour) < 7:
            return "ASIA"
        if 7 <= int(hour) < 13:
            return "LONDON"
        if 13 <= int(hour) < 21:
            return "NY"
        return "ASIA"

    def _entry_reason(self, row: pd.Series, params: dict[str, Any]) -> str:
        stretch_reasons: list[str] = []
        if row["mr_close"] <= row["mr_bb_lower"]:
            stretch_reasons.append(
                f"close={row['mr_close']:.6f}<=bb_low({row['mr_bb_lower']:.6f})"
            )
        if row["mr_zscore"] <= params["entry_zscore"]:
            stretch_reasons.append(
                f"z={row['mr_zscore']:.2f}<={params['entry_zscore']:.2f}"
            )
        if not stretch_reasons:
            stretch_reasons.append(
                f"stretch_checked(z={row['mr_zscore']:.2f},bb_low={row['mr_bb_lower']:.6f})"
            )
        return (
            "MeanReversionEntry; "
            + "; ".join(stretch_reasons)
            + f"; vwap_dev={row['mr_vwap_deviation_pct']:.2f}%<=-{params['vwap_deviation_min_pct']:.2f}%"
            + f"; rsi={row['mr_rsi']:.2f}<={params['rsi_oversold']:.2f}"
            + f"; atr={row['mr_atr_percent']:.2f}% in [{params['atr_min_percent']:.2f},{params['atr_max_percent']:.2f}]"
            + f"; vol={row['mr_volume_ratio']:.2f}x"
            + f"; reclaim={row['mr_candle_reclaim_fraction']:.2f}"
        )

    def _exit_reason(self, row: pd.Series, params: dict[str, Any]) -> str:
        reasons: list[str] = []
        if row["mr_close"] >= row["mr_bb_middle"]:
            reasons.append(f"close>=bb_mid({row['mr_bb_middle']:.6f})")
        if row["mr_close"] >= row["mr_vwap"]:
            reasons.append(f"close>=vwap({row['mr_vwap']:.6f})")
        if row["mr_zscore"] >= params["exit_zscore"]:
            reasons.append(f"z={row['mr_zscore']:.2f}>={params['exit_zscore']:.2f}")
        if row["mr_rsi"] >= params["rsi_exit"]:
            reasons.append(f"rsi={row['mr_rsi']:.2f}>={params['rsi_exit']:.2f}")
        if params["enable_failure_exit"] and row["mr_zscore"] <= params["failure_zscore"]:
            reasons.append(f"failure_z={row['mr_zscore']:.2f}<={params['failure_zscore']:.2f}")
        return "MeanReversionExit; " + "; ".join(reasons)

    def _csv_set(self, value: str) -> set[str]:
        return {
            item.strip().upper()
            for item in str(value).split(",")
            if item.strip()
        }

    def _int_set(self, value: str) -> set[int]:
        result: set[int] = set()
        for item in str(value).split(","):
            item = item.strip()
            if not item:
                continue
            try:
                result.add(int(item))
            except ValueError:
                continue
        return result

    def _bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y", "on"}
        return bool(value)
