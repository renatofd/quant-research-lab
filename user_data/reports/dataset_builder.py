from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
import json
import math
from pathlib import Path
from typing import Any
import zipfile

import pandas as pd
from pandas import DataFrame, concat

from research_dataset import FEATURE_COLUMNS


USER_DATA_DIR = Path(__file__).resolve().parents[1]
REPORTS_DIR = USER_DATA_DIR / "reports"
FEATURE_DIR = REPORTS_DIR / "research_features"
BACKTEST_RESULTS_DIR = USER_DATA_DIR / "backtest_results"
CHANNEL_CONFIG_PATH = USER_DATA_DIR / "channels" / "config.json"


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


def _safe_decimal(value: Any) -> Decimal | None:
    try:
        if value is None:
            return None
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _safe_float(value: Any) -> float | None:
    decimal_value = _safe_decimal(value)
    return float(decimal_value) if decimal_value is not None else None


def _latest_backtest_path() -> Path:
    last_result_path = BACKTEST_RESULTS_DIR / ".last_result.json"
    if last_result_path.exists():
        last_result = json.loads(last_result_path.read_text(encoding="utf-8"))
        latest_name = last_result.get("latest_backtest")
        if latest_name:
            latest_path = BACKTEST_RESULTS_DIR / latest_name
            if latest_path.exists():
                return latest_path

    zip_files = sorted(
        BACKTEST_RESULTS_DIR.glob("*.zip"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not zip_files:
        raise FileNotFoundError("Nenhum resultado oficial de backtest foi encontrado.")

    return zip_files[0]


def _load_backtest_result(backtest_path: Path) -> dict:
    if backtest_path.suffix == ".json":
        return json.loads(backtest_path.read_text(encoding="utf-8"))

    with zipfile.ZipFile(backtest_path) as archive:
        result_names = [
            name
            for name in archive.namelist()
            if name.endswith(".json") and not name.endswith("_config.json")
        ]
        if not result_names:
            raise FileNotFoundError(f"Nenhum JSON de resultado em {backtest_path}.")

        return json.loads(archive.read(result_names[0]))


def _strategy_result(backtest_result: dict, strategy_name: str | None = None) -> dict:
    strategies = backtest_result.get("strategy", {})
    if strategy_name and strategy_name in strategies:
        return strategies[strategy_name]

    if len(strategies) == 1:
        return next(iter(strategies.values()))

    available = ", ".join(strategies.keys())
    raise ValueError(f"Informe uma estratégia. Estratégias disponíveis: {available}")


def _closed_trades(strategy_result: dict) -> list[dict]:
    return [
        trade
        for trade in strategy_result.get("trades", [])
        if not trade.get("is_open", False)
    ]


def _load_features() -> DataFrame:
    feature_files = sorted(FEATURE_DIR.glob("research_features_*.csv"))
    if not feature_files:
        raise FileNotFoundError(
            "Nenhum arquivo de features foi encontrado em user_data/reports/research_features."
        )

    frames = [pd.read_csv(feature_file) for feature_file in feature_files]
    features = concat(frames, ignore_index=True)

    if "date" in features:
        features["_feature_timestamp"] = features["date"].map(_timestamp)
    if "research_time_key" not in features and "date" in features:
        features["research_time_key"] = features["date"].map(_time_key)

    return features


def _match_feature(
    features: DataFrame,
    pair: str,
    entry_time: Any,
) -> tuple[dict[str, Any], str, float | None]:
    pair_features = features[features["pair"] == pair]
    if pair_features.empty:
        return {}, "missing_pair_features", None

    entry_key = _time_key(entry_time)
    exact_match = pair_features[pair_features["research_time_key"] == entry_key]
    if not exact_match.empty:
        return exact_match.iloc[-1].to_dict(), "exact", 0.0

    entry_timestamp = _timestamp(entry_time)
    if entry_timestamp is None or "_feature_timestamp" not in pair_features:
        return {}, "missing_entry_time", None

    valid_rows = pair_features[pair_features["_feature_timestamp"].notna()]
    previous_rows = valid_rows[valid_rows["_feature_timestamp"] <= entry_timestamp]
    if previous_rows.empty:
        return {}, "no_previous_candle", None

    selected = previous_rows.iloc[-1]
    delta = entry_timestamp - selected["_feature_timestamp"]
    return selected.to_dict(), "previous_candle", float(delta.total_seconds() / 60)


def _load_channel_config() -> dict:
    if not CHANNEL_CONFIG_PATH.exists():
        return {}

    return json.loads(CHANNEL_CONFIG_PATH.read_text(encoding="utf-8"))


def _pair_settings(channel_config: dict, pair: str) -> dict:
    defaults = channel_config.get("defaults", {})
    pair_specific = channel_config.get("pairs", {}).get(pair, {})
    return {**defaults, **pair_specific}


def _infer_martingale_level(channel_config: dict, pair: str, stake_amount: Any) -> int | None:
    stake = _safe_decimal(stake_amount)
    settings = _pair_settings(channel_config, pair)
    base_stake = _safe_decimal(settings.get("base_stake"))
    multiplier = _safe_decimal(channel_config.get("martingale", {}).get("multiplier"))
    max_level = channel_config.get("martingale", {}).get("max_level", 0)

    if stake is None or base_stake is None or multiplier is None or multiplier <= 0:
        return None

    try:
        max_level = int(max_level)
    except (TypeError, ValueError):
        max_level = 0

    expected_levels = [
        (level, base_stake * (multiplier ** level))
        for level in range(max_level + 1)
    ]
    level, _ = min(
        expected_levels,
        key=lambda item: abs(item[1] - stake),
    )
    return level


def _trade_entry_time(trade: dict) -> Any:
    if trade.get("open_date"):
        return trade["open_date"]

    open_timestamp = trade.get("open_timestamp")
    if open_timestamp is None:
        return None

    return datetime.fromtimestamp(open_timestamp / 1000, tz=UTC)


def _trade_exit_time(trade: dict) -> Any:
    if trade.get("close_date"):
        return trade["close_date"]

    close_timestamp = trade.get("close_timestamp")
    if close_timestamp is None:
        return None

    return datetime.fromtimestamp(close_timestamp / 1000, tz=UTC)


def _dataset_row(
    trade: dict,
    feature_row: dict[str, Any],
    feature_match: str,
    feature_delta_minutes: float | None,
    channel_config: dict,
) -> dict[str, Any]:
    pair = trade.get("pair")
    profit_ratio = _safe_float(trade.get("profit_ratio"))

    row = {
        "pair": pair,
        "entry_time": _time_key(_trade_entry_time(trade)),
        "exit_time": _time_key(_trade_exit_time(trade)),
        "trade_duration_minutes": trade.get("trade_duration"),
        "exit_reason": trade.get("exit_reason"),
        "open_rate": _safe_float(trade.get("open_rate")),
        "close_rate": _safe_float(trade.get("close_rate")),
        "trade_stake_amount": _safe_float(trade.get("stake_amount")),
        "trade_max_stake_amount": _safe_float(trade.get("max_stake_amount")),
        "trade_amount": _safe_float(trade.get("amount")),
        "profit_ratio": profit_ratio,
        "profit_abs": _safe_float(trade.get("profit_abs")),
        "is_winner": profit_ratio is not None and profit_ratio > 0,
        "entry_martingale_level": _infer_martingale_level(
            channel_config,
            pair,
            trade.get("stake_amount"),
        ),
        "research_feature_match": feature_match,
        "research_feature_delta_minutes": feature_delta_minutes,
    }

    for column in FEATURE_COLUMNS:
        if column == "date":
            row["feature_date"] = feature_row.get(column)
        else:
            value = feature_row.get(column)
            if isinstance(value, float) and math.isnan(value):
                value = None
            row[column] = value

    return row


def build_research_dataset(strategy_name: str | None = None) -> Path:
    backtest_path = _latest_backtest_path()
    backtest_result = _load_backtest_result(backtest_path)
    strategy = _strategy_result(backtest_result, strategy_name)
    trades = _closed_trades(strategy)
    if not trades:
        raise ValueError("O último resultado de backtest não possui trades fechados.")

    features = _load_features()
    channel_config = _load_channel_config()

    rows = []
    for trade in trades:
        feature_row, feature_match, feature_delta_minutes = _match_feature(
            features,
            trade.get("pair"),
            _trade_entry_time(trade),
        )
        rows.append(
            _dataset_row(
                trade,
                feature_row,
                feature_match,
                feature_delta_minutes,
                channel_config,
            )
        )

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    dataset = DataFrame(rows)

    latest_path = REPORTS_DIR / "research_trades_latest.csv"
    timestamped_path = REPORTS_DIR / f"research_trades_{timestamp}.csv"
    dataset.to_csv(latest_path, index=False)
    dataset.to_csv(timestamped_path, index=False)

    return latest_path


def main() -> None:
    output_path = build_research_dataset()
    print(f"Research dataset generated: {output_path}")


if __name__ == "__main__":
    main()
