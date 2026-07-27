from datetime import UTC, datetime
import json
from pathlib import Path
import re
from typing import Any

import pandas as pd
from pandas import DataFrame


FEATURE_COLUMNS = [
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "ema_9",
    "ema_21",
    "ema_200",
    "rsi",
    "volume_mean_20",
    "regime_adx",
    "regime_atr",
    "regime_ema_200_slope",
    "regime_volatility",
    "market_regime",
    "score_trend",
    "score_momentum",
    "score_volume",
    "score_volatility",
    "score_regime",
    "signal_score",
    "passive_decision",
    "decision_confidence",
    "decision_reasons",
    "shadow_real_decision",
    "shadow_engine_decision",
    "shadow_confidence",
    "shadow_regime",
    "shadow_signal_score",
    "enter_long",
    "exit_long",
]

_FEATURE_EXPORT_INITIALIZED = False


def _is_backtest(config: dict) -> bool:
    runmode = config.get("runmode")
    return getattr(runmode, "value", runmode) == "backtest"


def _user_data_dir(config: dict) -> Path:
    return Path(config.get("user_data_dir", Path.cwd() / "user_data"))


def _feature_dir(config: dict) -> Path:
    return _user_data_dir(config) / "reports" / "research_features"


def _timestamp(value: Any) -> pd.Timestamp | None:
    if value is None:
        return None

    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp):
        return None

    if timestamp.tzinfo is None:
        return timestamp.tz_localize(UTC)

    return timestamp.tz_convert(UTC)


def _time_key(value: Any) -> str:
    timestamp = _timestamp(value)
    if timestamp is None:
        return ""

    return timestamp.isoformat()


def _safe_value(value: Any) -> Any:
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if isinstance(value, (list, dict, tuple)):
        return json.dumps(value, ensure_ascii=False)

    if isinstance(value, pd.Timestamp):
        return value.isoformat()

    if isinstance(value, datetime):
        timestamp = _timestamp(value)
        return timestamp.isoformat() if timestamp is not None else None

    return value


def _pair_slug(pair: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", pair).strip("_")


def _initialize_feature_export(config: dict) -> None:
    global _FEATURE_EXPORT_INITIALIZED

    if _FEATURE_EXPORT_INITIALIZED:
        return

    feature_dir = _feature_dir(config)
    feature_dir.mkdir(parents=True, exist_ok=True)

    for feature_file in feature_dir.glob("research_features_*.csv"):
        feature_file.unlink()

    _FEATURE_EXPORT_INITIALIZED = True


def record_research_feature_frame(
    dataframe: DataFrame,
    metadata: dict,
    config: dict,
) -> DataFrame:
    if not _is_backtest(config):
        return dataframe

    pair = metadata.get("pair", "UNKNOWN")
    available_columns = [column for column in FEATURE_COLUMNS if column in dataframe]
    feature_frame = dataframe[available_columns].copy()

    feature_frame["pair"] = pair
    if "date" in feature_frame:
        feature_frame["research_time_key"] = feature_frame["date"].map(_time_key)

    for column in feature_frame.columns:
        feature_frame[column] = feature_frame[column].map(_safe_value)

    _initialize_feature_export(config)
    feature_path = _feature_dir(config) / f"research_features_{_pair_slug(pair)}.csv"
    feature_frame.to_csv(feature_path, index=False)

    return dataframe
