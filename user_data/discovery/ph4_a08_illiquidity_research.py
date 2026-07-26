"""PH4-A08 offline OHLCV illiquidity-proxy research.

This isolated module implements the frozen protocol in PH4_A08_PROTOCOL.md.
Importing it or requesting --help does not read OHLCV or write reports. The
analysis runs only through the explicit ``analyze`` subcommand.
"""

from __future__ import annotations

import argparse
import html
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DISCOVERY_DIR = Path(__file__).resolve().parent
USER_DATA_DIR = DISCOVERY_DIR.parent
PROJECT_ROOT = USER_DATA_DIR.parent
LAB_DIR = USER_DATA_DIR / "lab"
REPORTS_DIR = DISCOVERY_DIR / "reports"
PROTOCOL_FILE = PROJECT_ROOT / "PH4_A08_PROTOCOL.md"

if str(LAB_DIR) not in sys.path:
    sys.path.insert(0, str(LAB_DIR))

import btc_leadership_research as common  # noqa: E402


REPORT_STEM = "ph4_a08_illiquidity_proxy"
REPORT_JSON = REPORTS_DIR / f"{REPORT_STEM}_report.json"
REPORT_MD = REPORTS_DIR / f"{REPORT_STEM}_report.md"
REPORT_HTML = REPORTS_DIR / f"{REPORT_STEM}_report.html"
MATRIX_CSV = REPORTS_DIR / f"{REPORT_STEM}_matrix.csv"
BOOTSTRAP_CSV = REPORTS_DIR / f"{REPORT_STEM}_bootstrap.csv"

HORIZON_CANDLES = 24
TIMEFRAME_MINUTES = 5
BOOTSTRAP_REPS = 1000
RANDOM_SEED = 2026071408
MIN_EVENTS_PER_HALF = 30
MIN_INFORMATIVE_PAIRS = 8
MIN_INFORMATIVE_BLOCKS = 4
MATERIAL_MSE_IMPROVEMENT = 0.05
ALPHA = 0.05

DECISION_DETECTED = (
    "DEVELOPMENT OHLCV ILLIQUIDITY-PROXY RISK SIGNAL DETECTED "
    "\u2014 PROSPECTIVE HOLDOUT REQUIRED"
)
DECISION_REJECTED = "OHLCV ILLIQUIDITY-PROXY HYPOTHESIS REJECTED IN PRIMARY SCOPE"
DECISION_INCONCLUSIVE = "INCONCLUSIVE OHLCV ILLIQUIDITY-PROXY AUDIT"

P1_BASE_FEATURES = ["log_rv_past", "log_qv_past"]
P1_FULL_FEATURES = [*P1_BASE_FEATURES, "log_p1"]
P2_BASE_FEATURES = ["log_rv_past", "log_qv_past", "log_range_past"]
P2_FULL_FEATURES = [*P2_BASE_FEATURES, "log_p2"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "PH4-A08 offline OHLCV illiquidity-proxy audit. Import and help "
            "are data-free; analyze reads existing 5m Feather files and "
            "writes the pre-registered scientific artifacts."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "analyze",
        help="Run the frozen PH4-A08 offline analysis.",
        description=(
            "Run the fixed 24-candle Amihud-OHLCV risk-prediction protocol. "
            "No trading strategy, backtest, grid, or optimization is used."
        ),
    )
    return parser.parse_args()


def _finite(value: Any) -> bool:
    try:
        return value is not None and math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _mean(values: list[Any]) -> float | None:
    valid = [float(value) for value in values if _finite(value)]
    return sum(valid) / len(valid) if valid else None


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    if not _finite(numerator) or not _finite(denominator) or denominator <= 0:
        return None
    return float(numerator / denominator)


def _improvement(reference_loss: float, candidate_loss: float) -> float | None:
    ratio = _safe_ratio(candidate_loss, reference_loss)
    return None if ratio is None else 1.0 - ratio


def _bootstrap_positive_p(values: list[Any]) -> float | None:
    valid = [float(value) for value in values if _finite(value)]
    if not valid:
        return None
    return (1.0 + sum(value <= 0.0 for value in valid)) / (1.0 + len(valid))


def _ci(values: list[Any]) -> list[float | None]:
    return common.ci95([float(value) for value in values if _finite(value)])


def _ci_above_zero(interval: list[float | None]) -> bool:
    return bool(interval and interval[0] is not None and interval[0] > 0.0)


def _ols_fit(frame: Any, features: list[str], target: str = "y") -> dict[str, Any]:
    import numpy as np

    columns = [target, *features]
    matrix = frame[columns].to_numpy(dtype=float)
    matrix = matrix[np.isfinite(matrix).all(axis=1)]
    if len(matrix) <= len(features) + 1:
        raise ValueError("insufficient finite rows for OLS")
    y = matrix[:, 0]
    x = np.column_stack([np.ones(len(matrix)), matrix[:, 1:]])
    coefficients, _, rank, _ = np.linalg.lstsq(x, y, rcond=None)
    if rank < x.shape[1]:
        raise ValueError("rank-deficient OLS design")
    prediction = x @ coefficients
    residual = y - prediction
    sse = float(np.sum(residual**2))
    centered = y - float(np.mean(y))
    sst = float(np.sum(centered**2))
    return {
        "features": list(features),
        "coefficients": coefficients,
        "r2": None if sst <= 0 else 1.0 - sse / sst,
        "n": int(len(y)),
    }


def _ols_predict(frame: Any, model: dict[str, Any], overrides: dict[str, Any] | None = None) -> Any:
    import numpy as np

    values = []
    overrides = overrides or {}
    for feature in model["features"]:
        source = overrides.get(feature, frame[feature])
        values.append(np.asarray(source, dtype=float))
    x = np.column_stack([np.ones(len(frame)), *values])
    return x @ model["coefficients"]


def _losses(actual: Any, predicted: Any) -> dict[str, float]:
    import numpy as np

    residual = np.asarray(actual, dtype=float) - np.asarray(predicted, dtype=float)
    return {
        "mse": float(np.mean(residual**2)),
        "mae": float(np.mean(np.abs(residual))),
    }


def _r2(actual: Any, predicted: Any) -> float | None:
    import numpy as np

    y = np.asarray(actual, dtype=float)
    residual = y - np.asarray(predicted, dtype=float)
    sst = float(np.sum((y - float(np.mean(y))) ** 2))
    return None if sst <= 0 else 1.0 - float(np.sum(residual**2)) / sst


def _partial_correlation(frame: Any, predictor: str, controls: list[str]) -> float | None:
    import numpy as np

    try:
        y_model = _ols_fit(frame.rename(columns={"y": "target_y"}), controls, "target_y")
        x_frame = frame.rename(columns={predictor: "target_x"})
        x_model = _ols_fit(x_frame, controls, "target_x")
    except ValueError:
        return None
    y_residual = frame["y"].to_numpy(dtype=float) - _ols_predict(frame, y_model)
    x_residual = frame[predictor].to_numpy(dtype=float) - _ols_predict(frame, x_model)
    if float(np.std(y_residual)) <= 0 or float(np.std(x_residual)) <= 0:
        return None
    return float(np.corrcoef(x_residual, y_residual)[0, 1])


def _shift(values: Any) -> Any:
    import numpy as np

    array = np.asarray(values, dtype=float)
    if not len(array):
        return array
    offset = max(1, len(array) // 2)
    return np.roll(array, offset)


def _pairing_proxy(frame: Any) -> Any:
    import numpy as np

    count = len(frame)
    if count == 0:
        return np.asarray([], dtype=float)
    offset = max(1, count // 2)
    abs_returns = list(frame["abs_returns"])
    quote_volumes = list(frame["quote_volumes"])
    values: list[float] = []
    for index, returns_vector in enumerate(abs_returns):
        volume_vector = quote_volumes[(index - offset) % count]
        returns_array = np.asarray(returns_vector, dtype=float)
        volume_array = np.asarray(volume_vector, dtype=float)
        if len(returns_array) != HORIZON_CANDLES or len(volume_array) != HORIZON_CANDLES:
            values.append(float("nan"))
            continue
        ratio = returns_array / volume_array
        proxy = float(np.mean(ratio))
        values.append(math.log(proxy) if proxy > 0 and math.isfinite(proxy) else float("nan"))
    return np.asarray(values, dtype=float)


def _validate_ohlcv(frame: Any) -> Any:
    import numpy as np

    numeric = frame[["open", "high", "low", "close", "volume"]].astype(float)
    finite = np.isfinite(numeric.to_numpy(dtype=float)).all(axis=1)
    return (
        ~finite
        | (numeric["open"] <= 0)
        | (numeric["high"] <= 0)
        | (numeric["low"] <= 0)
        | (numeric["close"] <= 0)
        | (numeric["volume"] <= 0)
        | (numeric["high"] < numeric[["open", "close", "low"]].max(axis=1))
        | (numeric["low"] > numeric[["open", "close", "high"]].min(axis=1))
    )


def _load_market_data() -> tuple[dict[str, Any], dict[str, Any]]:
    import pandas as pd

    frames: dict[str, Any] = {}
    file_audit: dict[str, Any] = {}
    for pair in common.ALL_PAIRS:
        path = common.DATA_DIR / common.pair_to_filename(pair)
        if not path.exists():
            file_audit[pair] = {"path": str(path), "exists": False}
            continue
        frame = pd.read_feather(path)
        required = {"date", "open", "high", "low", "close", "volume"}
        missing = sorted(required.difference(frame.columns))
        if missing:
            file_audit[pair] = {
                "path": str(path),
                "exists": True,
                "sha256": common.sha256_file(path),
                "missing_columns": missing,
            }
            continue
        source_timezone = str(frame["date"].dt.tz) if hasattr(frame["date"].dt, "tz") else None
        frame = frame.copy()
        frame["date"] = pd.to_datetime(frame["date"], utc=True)
        frame = frame.sort_values("date", kind="stable").reset_index(drop=True)
        duplicate_count = int(frame["date"].duplicated().sum())
        diffs = frame["date"].diff().dropna()
        invalid = _validate_ohlcv(frame)
        file_audit[pair] = {
            "path": str(path),
            "exists": True,
            "sha256": common.sha256_file(path),
            "rows": int(len(frame)),
            "start": frame["date"].min().isoformat() if len(frame) else None,
            "end": frame["date"].max().isoformat() if len(frame) else None,
            "source_timezone": source_timezone,
            "normalized_timezone": str(frame["date"].dt.tz),
            "strictly_sorted": bool(frame["date"].is_monotonic_increasing),
            "duplicate_timestamps": duplicate_count,
            "non_5m_gaps_full_file": int((diffs != pd.Timedelta(minutes=TIMEFRAME_MINUTES)).sum()),
            "invalid_ohlcv_rows": int(invalid.sum()),
        }
        frames[pair] = frame
    return frames, file_audit


def _build_events() -> tuple[Any, dict[str, Any]]:
    import numpy as np
    import pandas as pd

    windows_payload = common.load_json(common.WINDOWS_FILE)
    windows = windows_payload.get("windows", [])
    frames, file_audit = _load_market_data()
    rows: list[dict[str, Any]] = []
    unit_audit: list[dict[str, Any]] = []
    discarded_total: Counter[str] = Counter()

    for window in windows:
        block_id = int(window["window_index"])
        start = pd.Timestamp(window["start"], tz="UTC")
        end = pd.Timestamp(window["end"], tz="UTC")
        for pair in common.ALL_PAIRS:
            frame = frames.get(pair)
            reasons: Counter[str] = Counter()
            if frame is None:
                unit_audit.append(
                    {
                        "pair": pair,
                        "block": block_id,
                        "timerange": window.get("timerange"),
                        "rows": 0,
                        "eligible_events": 0,
                        "discarded": {"missing_or_invalid_file": 1},
                        "informative": False,
                    }
                )
                discarded_total["missing_or_invalid_file"] += 1
                continue

            block = frame[(frame["date"] >= start) & (frame["date"] < end)].copy()
            block = block.sort_values("date", kind="stable").reset_index(drop=True)
            block_invalid = _validate_ohlcv(block)
            block_diffs = block["date"].diff().dropna()
            event_rows: list[dict[str, Any]] = []
            if len(block) < 2 * HORIZON_CANDLES + 1:
                reasons["block_too_short"] += 1
            else:
                for event_index in range(HORIZON_CANDLES, len(block) - HORIZON_CANDLES, HORIZON_CANDLES):
                    combined_start = event_index - HORIZON_CANDLES
                    combined_end = event_index + HORIZON_CANDLES
                    combined = block.iloc[combined_start : combined_end + 1]
                    expected_span = pd.Timedelta(
                        minutes=TIMEFRAME_MINUTES * (2 * HORIZON_CANDLES)
                    )
                    if (
                        len(combined) != 2 * HORIZON_CANDLES + 1
                        or combined["date"].iloc[-1] - combined["date"].iloc[0] != expected_span
                        or not (combined["date"].diff().dropna() == pd.Timedelta(minutes=TIMEFRAME_MINUTES)).all()
                    ):
                        reasons["gap_in_event_window"] += 1
                        continue
                    if bool(block_invalid.iloc[combined_start : combined_end + 1].any()):
                        reasons["invalid_ohlcv_in_event_window"] += 1
                        continue

                    past_closes = block["close"].iloc[event_index - HORIZON_CANDLES : event_index + 1].to_numpy(dtype=float)
                    past_candles = block.iloc[event_index - HORIZON_CANDLES + 1 : event_index + 1]
                    future_closes = block["close"].iloc[event_index : event_index + HORIZON_CANDLES + 1].to_numpy(dtype=float)
                    past_returns = np.diff(np.log(past_closes))
                    future_returns = np.diff(np.log(future_closes))
                    quote_volumes = (
                        past_candles["close"].to_numpy(dtype=float)
                        * past_candles["volume"].to_numpy(dtype=float)
                    )
                    ranges = np.log(
                        past_candles["high"].to_numpy(dtype=float)
                        / past_candles["low"].to_numpy(dtype=float)
                    )
                    if not (
                        np.isfinite(past_returns).all()
                        and np.isfinite(future_returns).all()
                        and np.isfinite(quote_volumes).all()
                        and np.isfinite(ranges).all()
                        and (quote_volumes > 0).all()
                        and (ranges >= 0).all()
                    ):
                        reasons["nonfinite_or_nonpositive_components"] += 1
                        continue

                    abs_returns = np.abs(past_returns)
                    p1 = float(np.mean(abs_returns / quote_volumes))
                    p2 = float(np.mean(ranges / quote_volumes))
                    rv_past = float(np.sqrt(np.sum(past_returns**2)))
                    rv_future = float(np.sqrt(np.sum(future_returns**2)))
                    qv_past = float(np.sum(quote_volumes))
                    range_past = float(np.mean(ranges))
                    positive_values = [p1, p2, rv_past, rv_future, qv_past, range_past]
                    if not all(value > 0 and math.isfinite(value) for value in positive_values):
                        reasons["zero_or_nonfinite_log_input"] += 1
                        continue

                    timestamp = block["date"].iloc[event_index]
                    event_rows.append(
                        {
                            "pair": pair,
                            "block": block_id,
                            "timerange": window.get("timerange"),
                            "date": timestamp,
                            "day": timestamp.floor("D"),
                            "past_start": block["date"].iloc[event_index - HORIZON_CANDLES],
                            "future_end": block["date"].iloc[event_index + HORIZON_CANDLES],
                            "log_rv_past": math.log(rv_past),
                            "log_qv_past": math.log(qv_past),
                            "log_range_past": math.log(range_past),
                            "log_p1": math.log(p1),
                            "log_p2": math.log(p2),
                            "y": math.log(rv_future),
                            "abs_returns": tuple(float(value) for value in abs_returns),
                            "quote_volumes": tuple(float(value) for value in quote_volumes),
                        }
                    )

            rows.extend(event_rows)
            discarded_total.update(reasons)
            half = len(event_rows) // 2
            informative = half >= MIN_EVENTS_PER_HALF and (len(event_rows) - half) >= MIN_EVENTS_PER_HALF
            event_dates = [row["date"] for row in event_rows]
            minimum_spacing_ok = all(
                later - earlier >= pd.Timedelta(minutes=TIMEFRAME_MINUTES * HORIZON_CANDLES)
                for earlier, later in zip(event_dates, event_dates[1:])
            )
            unit_audit.append(
                {
                    "pair": pair,
                    "block": block_id,
                    "timerange": window.get("timerange"),
                    "rows": int(len(block)),
                    "start": block["date"].min().isoformat() if len(block) else None,
                    "end": block["date"].max().isoformat() if len(block) else None,
                    "duplicate_timestamps": int(block["date"].duplicated().sum()),
                    "non_5m_gaps": int((block_diffs != pd.Timedelta(minutes=TIMEFRAME_MINUTES)).sum()),
                    "invalid_ohlcv_rows": int(block_invalid.sum()),
                    "eligible_events": int(len(event_rows)),
                    "calibration_events": int(half),
                    "evaluation_events": int(len(event_rows) - half),
                    "discarded": dict(reasons),
                    "minimum_event_spacing_ok": minimum_spacing_ok,
                    "informative": informative,
                }
            )

    samples = pd.DataFrame(rows)
    informative_units = [unit for unit in unit_audit if unit["informative"]]
    informative_pairs = sorted({unit["pair"] for unit in informative_units})
    informative_blocks = sorted({unit["block"] for unit in informative_units})
    files_complete = len(frames) == len(common.ALL_PAIRS)
    source_timezone_ok = all(
        audit.get("source_timezone") in {"UTC", "UTC+00:00", "Etc/UTC"}
        for audit in file_audit.values()
        if audit.get("exists") and not audit.get("missing_columns")
    ) and files_complete
    duplicate_free = all(audit.get("duplicate_timestamps", 1) == 0 for audit in file_audit.values())
    labels_nonoverlapping = all(unit.get("minimum_event_spacing_ok", False) for unit in unit_audit if unit["eligible_events"])
    sample_sufficient = (
        len(informative_pairs) >= MIN_INFORMATIVE_PAIRS
        and len(informative_blocks) >= MIN_INFORMATIVE_BLOCKS
    )
    integrity_sufficient = bool(
        PROTOCOL_FILE.exists()
        and common.WINDOWS_FILE.exists()
        and len(windows) == 5
        and files_complete
        and source_timezone_ok
        and duplicate_free
        and labels_nonoverlapping
        and sample_sufficient
    )
    audit = {
        "protocol_file": str(PROTOCOL_FILE),
        "protocol_sha256": common.sha256_file(PROTOCOL_FILE) if PROTOCOL_FILE.exists() else None,
        "windows_file": str(common.WINDOWS_FILE),
        "windows_sha256": common.sha256_file(common.WINDOWS_FILE) if common.WINDOWS_FILE.exists() else None,
        "windows": windows,
        "file_audit": file_audit,
        "unit_audit": unit_audit,
        "discarded_events_by_reason": dict(discarded_total),
        "eligible_events_total": int(len(samples)),
        "informative_units": int(len(informative_units)),
        "informative_pairs": informative_pairs,
        "informative_blocks": informative_blocks,
        "checks": {
            "files_complete": files_complete,
            "five_frozen_windows": len(windows) == 5,
            "source_timezone_utc": source_timezone_ok,
            "duplicate_free": duplicate_free,
            "labels_nonoverlapping": labels_nonoverlapping,
            "lookahead_absent_by_index_construction": True,
            "samples_do_not_cross_block_boundaries": True,
            "sample_sufficient": sample_sufficient,
            "integrity_sufficient": integrity_sufficient,
        },
        "development_consumed": True,
        "holdout_status": "no prospective holdout",
    }
    return samples, audit


def _prepare_units(samples: Any) -> tuple[dict[tuple[str, int], dict[str, Any]], list[dict[str, Any]]]:
    import numpy as np

    states: dict[tuple[str, int], dict[str, Any]] = {}
    failures: list[dict[str, Any]] = []
    if samples.empty:
        return states, failures
    for (pair, block), unit in samples.groupby(["pair", "block"], sort=True):
        unit = unit.sort_values("date", kind="stable").reset_index(drop=True)
        split = len(unit) // 2
        calibration = unit.iloc[:split].copy().reset_index(drop=True)
        evaluation = unit.iloc[split:].copy().reset_index(drop=True)
        if len(calibration) < MIN_EVENTS_PER_HALF or len(evaluation) < MIN_EVENTS_PER_HALF:
            failures.append(
                {
                    "pair": pair,
                    "block": int(block),
                    "reason": "minimum events per chronological half not met",
                    "calibration_events": int(len(calibration)),
                    "evaluation_events": int(len(evaluation)),
                }
            )
            continue
        calibration["log_p1_pairing"] = _pairing_proxy(calibration)
        evaluation["log_p1_pairing"] = _pairing_proxy(evaluation)
        required = ["log_p1_pairing", "y", *P1_FULL_FEATURES, *P2_FULL_FEATURES]
        if not np.isfinite(calibration[required].to_numpy(dtype=float)).all() or not np.isfinite(
            evaluation[required].to_numpy(dtype=float)
        ).all():
            failures.append({"pair": pair, "block": int(block), "reason": "nonfinite prepared design"})
            continue
        try:
            models = {
                "p1_baseline": _ols_fit(calibration, P1_BASE_FEATURES),
                "p1_full": _ols_fit(calibration, P1_FULL_FEATURES),
                "p1_pairing": _ols_fit(
                    calibration.rename(columns={"log_p1_pairing": "log_p1_pseudo"}),
                    [*P1_BASE_FEATURES, "log_p1_pseudo"],
                ),
                "p1_rv_only": _ols_fit(calibration, ["log_rv_past"]),
                "p1_qv_only": _ols_fit(calibration, ["log_qv_past"]),
                "p2_baseline": _ols_fit(calibration, P2_BASE_FEATURES),
                "p2_full": _ols_fit(calibration, P2_FULL_FEATURES),
            }
        except ValueError as exc:
            failures.append({"pair": pair, "block": int(block), "reason": str(exc)})
            continue
        states[(pair, int(block))] = {
            "pair": pair,
            "block": int(block),
            "calibration": calibration,
            "evaluation": evaluation,
            "models": models,
        }
    return states, failures


def _evaluate_unit(state: dict[str, Any], evaluation: Any | None = None) -> dict[str, Any]:
    import numpy as np

    frame = state["evaluation"] if evaluation is None else evaluation
    models = state["models"]
    actual = frame["y"].to_numpy(dtype=float)

    p1_baseline_pred = _ols_predict(frame, models["p1_baseline"])
    p1_full_pred = _ols_predict(frame, models["p1_full"])
    p1_circular_pred = _ols_predict(
        frame,
        models["p1_full"],
        {"log_p1": _shift(frame["log_p1"].to_numpy(dtype=float))},
    )
    pairing_frame = frame.rename(columns={"log_p1_pairing": "log_p1_pseudo"})
    p1_pairing_pred = _ols_predict(pairing_frame, models["p1_pairing"])
    p1_rv_only_pred = _ols_predict(frame, models["p1_rv_only"])
    p1_qv_only_pred = _ols_predict(frame, models["p1_qv_only"])

    p2_baseline_pred = _ols_predict(frame, models["p2_baseline"])
    p2_full_pred = _ols_predict(frame, models["p2_full"])
    p2_circular_pred = _ols_predict(
        frame,
        models["p2_full"],
        {"log_p2": _shift(frame["log_p2"].to_numpy(dtype=float))},
    )

    p1_base_loss = _losses(actual, p1_baseline_pred)
    p1_full_loss = _losses(actual, p1_full_pred)
    p1_circular_loss = _losses(actual, p1_circular_pred)
    p1_pairing_loss = _losses(actual, p1_pairing_pred)
    p2_base_loss = _losses(actual, p2_baseline_pred)
    p2_full_loss = _losses(actual, p2_full_pred)
    p2_circular_loss = _losses(actual, p2_circular_pred)

    p1_eval_model = _ols_fit(frame, P1_FULL_FEATURES)
    p2_eval_model = _ols_fit(frame, P2_FULL_FEATURES)
    p1_beta = float(p1_eval_model["coefficients"][-1])
    p2_beta = float(p2_eval_model["coefficients"][-1])

    return {
        "pair": state["pair"],
        "block": state["block"],
        "calibration_events": int(len(state["calibration"])),
        "evaluation_events": int(len(frame)),
        "p1_beta_eval": p1_beta,
        "p1_partial_correlation": _partial_correlation(frame, "log_p1", P1_BASE_FEATURES),
        "p1_mse_baseline": p1_base_loss["mse"],
        "p1_mse_full": p1_full_loss["mse"],
        "p1_mse_circular": p1_circular_loss["mse"],
        "p1_mse_pairing": p1_pairing_loss["mse"],
        "p1_mse_rv_only": _losses(actual, p1_rv_only_pred)["mse"],
        "p1_mse_qv_only": _losses(actual, p1_qv_only_pred)["mse"],
        "p1_mse_improvement": _improvement(p1_base_loss["mse"], p1_full_loss["mse"]),
        "p1_mae_improvement": _improvement(p1_base_loss["mae"], p1_full_loss["mae"]),
        "p1_circular_loss_reduction": _improvement(p1_circular_loss["mse"], p1_full_loss["mse"]),
        "p1_pairing_loss_reduction": _improvement(p1_pairing_loss["mse"], p1_full_loss["mse"]),
        "p1_r2_baseline": _r2(actual, p1_baseline_pred),
        "p1_r2_full": _r2(actual, p1_full_pred),
        "p1_r2_incremental": (
            None
            if _r2(actual, p1_baseline_pred) is None or _r2(actual, p1_full_pred) is None
            else _r2(actual, p1_full_pred) - _r2(actual, p1_baseline_pred)
        ),
        "p2_beta_eval": p2_beta,
        "p2_partial_correlation": _partial_correlation(frame, "log_p2", P2_BASE_FEATURES),
        "p2_mse_baseline": p2_base_loss["mse"],
        "p2_mse_full": p2_full_loss["mse"],
        "p2_mse_circular": p2_circular_loss["mse"],
        "p2_mse_improvement": _improvement(p2_base_loss["mse"], p2_full_loss["mse"]),
        "p2_mae_improvement": _improvement(p2_base_loss["mae"], p2_full_loss["mae"]),
        "p2_circular_loss_reduction": _improvement(p2_circular_loss["mse"], p2_full_loss["mse"]),
        "p2_r2_baseline": _r2(actual, p2_baseline_pred),
        "p2_r2_full": _r2(actual, p2_full_pred),
        "p2_r2_incremental": (
            None
            if _r2(actual, p2_baseline_pred) is None or _r2(actual, p2_full_pred) is None
            else _r2(actual, p2_full_pred) - _r2(actual, p2_baseline_pred)
        ),
        "event_positive_loss_reduction": np.maximum(
            (actual - p1_baseline_pred) ** 2 - (actual - p1_full_pred) ** 2,
            0.0,
        ),
    }


METRIC_FIELDS = [
    "p1_beta_eval",
    "p1_partial_correlation",
    "p1_mse_baseline",
    "p1_mse_full",
    "p1_mse_circular",
    "p1_mse_pairing",
    "p1_mse_rv_only",
    "p1_mse_qv_only",
    "p1_mse_improvement",
    "p1_mae_improvement",
    "p1_circular_loss_reduction",
    "p1_pairing_loss_reduction",
    "p1_r2_baseline",
    "p1_r2_full",
    "p1_r2_incremental",
    "p2_beta_eval",
    "p2_partial_correlation",
    "p2_mse_baseline",
    "p2_mse_full",
    "p2_mse_circular",
    "p2_mse_improvement",
    "p2_mae_improvement",
    "p2_circular_loss_reduction",
    "p2_r2_baseline",
    "p2_r2_full",
    "p2_r2_incremental",
]


def _aggregate(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "units": int(len(metrics)),
        "calibration_events": int(sum(item.get("calibration_events", 0) for item in metrics)),
        "evaluation_events": int(sum(item.get("evaluation_events", 0) for item in metrics)),
        **{field: _mean([item.get(field) for item in metrics]) for field in METRIC_FIELDS},
    }


def _estimate(states: dict[tuple[str, int], dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]], dict[tuple[str, int], dict[str, Any]]]:
    unit_metrics: dict[tuple[str, int], dict[str, Any]] = {}
    for key, state in states.items():
        unit_metrics[key] = _evaluate_unit(state)

    overall = _aggregate(list(unit_metrics.values()))
    by_pair: dict[str, Any] = {}
    by_block: dict[str, Any] = {}
    for pair in common.ALL_PAIRS:
        values = [metric for (unit_pair, _), metric in unit_metrics.items() if unit_pair == pair]
        if values:
            by_pair[pair] = _aggregate(values)
    for block in sorted({block for _, block in unit_metrics}):
        values = [metric for (_, unit_block), metric in unit_metrics.items() if unit_block == block]
        if values:
            by_block[str(block)] = _aggregate(values)

    matrix: list[dict[str, Any]] = []
    matrix.append({"level": "overall", "pair": None, "block": None, **overall})
    matrix.extend({"level": "pair", "pair": pair, "block": None, **metrics} for pair, metrics in by_pair.items())
    matrix.extend({"level": "block", "pair": None, "block": block, **metrics} for block, metrics in by_block.items())
    for (pair, block), metrics in unit_metrics.items():
        row = {key: value for key, value in metrics.items() if key != "event_positive_loss_reduction"}
        matrix.append({"level": "unit", **row})
    return {"overall": overall, "by_pair": by_pair, "by_block": by_block}, matrix, unit_metrics


def _resample_complete_days(frame: Any, rng: Any) -> Any:
    import pandas as pd

    days = list(frame["day"].drop_duplicates())
    sampled_days = rng.choice(days, size=len(days), replace=True)
    pieces = [frame[frame["day"] == day] for day in sampled_days]
    return pd.concat(pieces, ignore_index=True)


def _bootstrap(states: dict[tuple[str, int], dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    import numpy as np

    rng = np.random.default_rng(RANDOM_SEED)
    rows: list[dict[str, Any]] = []
    pair_mse: dict[str, list[float]] = defaultdict(list)

    for replicate in range(BOOTSTRAP_REPS):
        sampled_metrics: list[dict[str, Any]] = []
        sampled_by_pair: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for key, state in states.items():
            sampled = _resample_complete_days(state["evaluation"], rng)
            try:
                metrics = _evaluate_unit(state, sampled)
            except ValueError:
                continue
            sampled_metrics.append(metrics)
            sampled_by_pair[key[0]].append(metrics)
        aggregate = _aggregate(sampled_metrics)
        row = {"replicate": replicate}
        row.update({field: aggregate.get(field) for field in METRIC_FIELDS})
        rows.append(row)
        for pair, values in sampled_by_pair.items():
            pair_value = _aggregate(values).get("p1_mse_improvement")
            if _finite(pair_value):
                pair_mse[pair].append(float(pair_value))

    p1_fields = {
        "beta": "p1_beta_eval",
        "mse_improvement": "p1_mse_improvement",
        "circular_loss_reduction": "p1_circular_loss_reduction",
        "pairing_loss_reduction": "p1_pairing_loss_reduction",
    }
    p2_fields = {
        "beta": "p2_beta_eval",
        "mse_improvement": "p2_mse_improvement",
        "circular_loss_reduction": "p2_circular_loss_reduction",
    }
    p1_pvalues = {
        name: _bootstrap_positive_p([row.get(field) for row in rows])
        for name, field in p1_fields.items()
    }
    p2_pvalues = {
        name: _bootstrap_positive_p([row.get(field) for row in rows])
        for name, field in p2_fields.items()
    }
    pair_pvalues = {pair: _bootstrap_positive_p(values) for pair, values in pair_mse.items()}
    pair_holm = common.holm_adjust(pair_pvalues)
    pair_diagnostics = {
        pair: {
            "mse_improvement_ci95": _ci(values),
            "p_bootstrap_one_sided": pair_pvalues.get(pair),
            "p_holm": pair_holm.get(pair),
            "holm_significant": bool(pair_holm.get(pair) is not None and pair_holm[pair] <= ALPHA),
        }
        for pair, values in pair_mse.items()
    }
    result = {
        "replicates_requested": BOOTSTRAP_REPS,
        "replicates_completed": int(len(rows)),
        "seed": RANDOM_SEED,
        "resampling_unit": "complete UTC days within each pair/block evaluation half",
        "aggregation": "equal weight across informative pair/block units",
        "p1": {
            **{
                f"{name}_ci95": _ci([row.get(field) for row in rows])
                for name, field in p1_fields.items()
            },
            "p_bootstrap_one_sided": p1_pvalues,
            "p_holm": common.holm_adjust(p1_pvalues),
        },
        "p2_diagnostic": {
            **{
                f"{name}_ci95": _ci([row.get(field) for row in rows])
                for name, field in p2_fields.items()
            },
            "p_bootstrap_one_sided": p2_pvalues,
            "p_holm": common.holm_adjust(p2_pvalues),
        },
        "pair_diagnostic_family": pair_diagnostics,
    }
    return result, rows


def _concentration(states: dict[tuple[str, int], dict[str, Any]], unit_metrics: dict[tuple[str, int], dict[str, Any]]) -> dict[str, Any]:
    contributions: dict[str, defaultdict[str, float]] = {
        "pair": defaultdict(float),
        "block": defaultdict(float),
        "day": defaultdict(float),
    }
    total = 0.0
    for key, metric in unit_metrics.items():
        state = states[key]
        values = metric["event_positive_loss_reduction"]
        evaluation = state["evaluation"]
        unit_size = max(1, len(evaluation))
        for index, value in enumerate(values):
            weighted = float(value) / unit_size
            if weighted <= 0:
                continue
            pair, block = key
            day = str(evaluation["day"].iloc[index].date())
            contributions["pair"][pair] += weighted
            contributions["block"][str(block)] += weighted
            contributions["day"][day] += weighted
            total += weighted

    shares: dict[str, Any] = {}
    for dimension, values in contributions.items():
        dimension_shares = {
            key: (value / total if total > 0 else None)
            for key, value in sorted(values.items())
        }
        finite_shares = [value for value in dimension_shares.values() if _finite(value)]
        shares[dimension] = {
            "shares": dimension_shares,
            "maximum_share": max(finite_shares) if finite_shares else None,
            "maximum_key": max(dimension_shares, key=lambda key: dimension_shares[key] or -1.0) if finite_shares else None,
        }
    return {
        "method": "positive event-level MSE reduction, normalized by evaluation events per unit",
        "positive_reduction_total": total,
        **shares,
    }


def _apply_bootstrap_to_matrix(matrix: list[dict[str, Any]], bootstrap: dict[str, Any]) -> None:
    p1 = bootstrap["p1"]
    p2 = bootstrap["p2_diagnostic"]
    pair_info = bootstrap["pair_diagnostic_family"]
    for row in matrix:
        if row["level"] == "overall":
            row.update(
                {
                    "p1_beta_ci95": p1["beta_ci95"],
                    "p1_mse_improvement_ci95": p1["mse_improvement_ci95"],
                    "p1_circular_ci95": p1["circular_loss_reduction_ci95"],
                    "p1_pairing_ci95": p1["pairing_loss_reduction_ci95"],
                    "p1_beta_p_holm": p1["p_holm"]["beta"],
                    "p1_mse_p_holm": p1["p_holm"]["mse_improvement"],
                    "p1_circular_p_holm": p1["p_holm"]["circular_loss_reduction"],
                    "p1_pairing_p_holm": p1["p_holm"]["pairing_loss_reduction"],
                    "p2_beta_ci95": p2["beta_ci95"],
                    "p2_mse_improvement_ci95": p2["mse_improvement_ci95"],
                    "p2_circular_ci95": p2["circular_loss_reduction_ci95"],
                    "p2_beta_p_holm": p2["p_holm"]["beta"],
                    "p2_mse_p_holm": p2["p_holm"]["mse_improvement"],
                    "p2_circular_p_holm": p2["p_holm"]["circular_loss_reduction"],
                }
            )
        elif row["level"] == "pair" and row.get("pair") in pair_info:
            details = pair_info[row["pair"]]
            row.update(
                {
                    "p1_mse_improvement_ci95": details["mse_improvement_ci95"],
                    "pair_mse_p_bootstrap": details["p_bootstrap_one_sided"],
                    "pair_mse_p_holm": details["p_holm"],
                    "pair_mse_holm_significant": details["holm_significant"],
                }
            )


def _decide(estimates: dict[str, Any], bootstrap: dict[str, Any], audit: dict[str, Any], concentration: dict[str, Any]) -> dict[str, Any]:
    overall = estimates["overall"]
    p1_boot = bootstrap["p1"]
    holm = p1_boot["p_holm"]
    positive_pairs = sum(
        metrics.get("p1_mse_improvement") is not None and metrics["p1_mse_improvement"] > 0
        for metrics in estimates["by_pair"].values()
    )
    positive_blocks = sum(
        metrics.get("p1_mse_improvement") is not None and metrics["p1_mse_improvement"] > 0
        for metrics in estimates["by_block"].values()
    )
    concentration_pass = all(
        concentration[dimension]["maximum_share"] is not None
        and concentration[dimension]["maximum_share"] <= 0.30
        for dimension in ("pair", "block", "day")
    )
    gates = {
        "beta_positive_ci95": (
            overall.get("p1_beta_eval") is not None
            and overall["p1_beta_eval"] > 0
            and _ci_above_zero(p1_boot["beta_ci95"])
        ),
        "mse_improvement_at_least_5pct_with_positive_ci95": (
            overall.get("p1_mse_improvement") is not None
            and overall["p1_mse_improvement"] >= MATERIAL_MSE_IMPROVEMENT
            and _ci_above_zero(p1_boot["mse_improvement_ci95"])
        ),
        "beats_circular_placebo_ci95": _ci_above_zero(p1_boot["circular_loss_reduction_ci95"]),
        "beats_pairing_placebo_ci95": _ci_above_zero(p1_boot["pairing_loss_reduction_ci95"]),
        "all_four_p1_tests_survive_holm": all(
            value is not None and value <= ALPHA for value in holm.values()
        ),
        "positive_in_at_least_4_of_5_blocks": positive_blocks >= 4,
        "positive_in_at_least_7_of_10_pairs": positive_pairs >= 7,
        "no_concentration_above_30pct": concentration_pass,
        "controls_included_and_frozen": True,
        "integrity_and_sample_pass": bool(audit["checks"]["integrity_sufficient"]),
    }
    core_without_concentration = all(
        value for key, value in gates.items() if key != "no_concentration_above_30pct"
    )
    if not audit["checks"]["integrity_sufficient"]:
        decision = DECISION_INCONCLUSIVE
        reason = "Data integrity, frozen-window coverage, or minimum sample prevented a valid contrast."
    elif core_without_concentration and not concentration_pass:
        decision = DECISION_INCONCLUSIVE
        reason = "All core gates passed, but the pre-registered concentration gate failed alone."
    elif all(gates.values()):
        decision = DECISION_DETECTED
        reason = "Every pre-registered P1 development gate passed; prospective holdout remains mandatory."
    else:
        decision = DECISION_REJECTED
        reason = "At least one central economic, placebo, multiplicity, or replication gate failed on valid data."
    return {
        "decision": decision,
        "reason": reason,
        "gates": gates,
        "positive_pairs": int(positive_pairs),
        "positive_blocks": int(positive_blocks),
        "p2_can_rescue_p1": False,
        "scope": "incremental risk prediction by an OHLCV proxy; not liquidity causality or trading profitability",
    }


def _fmt(value: Any) -> str:
    if value is None:
        return "NA"
    if isinstance(value, float):
        return f"{value:.8g}"
    return str(value)


def _render_markdown(report: dict[str, Any]) -> str:
    overall = report["estimates"]["overall"]
    bootstrap = report["bootstrap"]
    decision = report["decision"]
    concentration = report["concentration"]
    lines = [
        "# PH4-A08 - OHLCV Illiquidity-Proxy Risk Forecasting",
        "",
        f"Generated: `{report['generated_at']}`",
        "",
        f"**Decision:** {decision['decision']}",
        "",
        decision["reason"],
        "",
        "## Frozen Design",
        "",
        "- Ten Binance spot USDT pairs, 5m OHLCV, and the five frozen PH3-C03R blocks.",
        "- Fixed 24-candle past and 24-candle future windows; events every 24 candles.",
        "- Chronological calibration/evaluation split inside every pair/block.",
        "- Primary P1 is mean absolute log return per approximate quote volume; P2 is diagnostic only.",
        "- Outcome is log future realized volatility. No trades, fees, strategy, or directional return are modeled.",
        "- All data are development-consumed; there is no prospective holdout.",
        "",
        "## Primary P1 Results",
        "",
        f"- Informative units: `{overall['units']}`",
        f"- Calibration/evaluation events: `{overall['calibration_events']}` / `{overall['evaluation_events']}`",
        f"- Equal-weight beta1_eval: `{_fmt(overall['p1_beta_eval'])}`; CI95 `{bootstrap['p1']['beta_ci95']}`",
        f"- Equal-weight MSE improvement: `{_fmt(overall['p1_mse_improvement'])}`; CI95 `{bootstrap['p1']['mse_improvement_ci95']}`",
        f"- Circular-placebo loss reduction: `{_fmt(overall['p1_circular_loss_reduction'])}`; CI95 `{bootstrap['p1']['circular_loss_reduction_ci95']}`",
        f"- Pairing-placebo loss reduction: `{_fmt(overall['p1_pairing_loss_reduction'])}`; CI95 `{bootstrap['p1']['pairing_loss_reduction_ci95']}`",
        f"- MAE improvement: `{_fmt(overall['p1_mae_improvement'])}`",
        f"- Partial correlation: `{_fmt(overall['p1_partial_correlation'])}`",
        f"- Incremental R2: `{_fmt(overall['p1_r2_incremental'])}`",
        f"- Positive pairs/blocks: `{decision['positive_pairs']}/10`, `{decision['positive_blocks']}/5`",
        "",
        "## Multiplicity",
        "",
        f"- P1 bootstrap p-values: `{bootstrap['p1']['p_bootstrap_one_sided']}`",
        f"- P1 Holm-adjusted p-values: `{bootstrap['p1']['p_holm']}`",
        f"- P2 diagnostic Holm family: `{bootstrap['p2_diagnostic']['p_holm']}`",
        "",
        "## P2 Diagnostic",
        "",
        f"- beta2_eval: `{_fmt(overall['p2_beta_eval'])}`; CI95 `{bootstrap['p2_diagnostic']['beta_ci95']}`",
        f"- MSE improvement: `{_fmt(overall['p2_mse_improvement'])}`; CI95 `{bootstrap['p2_diagnostic']['mse_improvement_ci95']}`",
        f"- Circular-placebo loss reduction: `{_fmt(overall['p2_circular_loss_reduction'])}`",
        "- P2 cannot replace or rescue a failed P1 result.",
        "",
        "## Concentration",
        "",
        f"- Maximum pair share: `{_fmt(concentration['pair']['maximum_share'])}` ({concentration['pair']['maximum_key']})",
        f"- Maximum block share: `{_fmt(concentration['block']['maximum_share'])}` ({concentration['block']['maximum_key']})",
        f"- Maximum UTC-day share: `{_fmt(concentration['day']['maximum_share'])}` ({concentration['day']['maximum_key']})",
        "",
        "## Decision Gates",
        "",
    ]
    lines.extend(f"- `{key}`: `{value}`" for key, value in decision["gates"].items())
    lines.extend(
        [
            "",
            "## Integrity and Limitations",
            "",
            f"- Integrity sufficient: `{report['audit']['checks']['integrity_sufficient']}`",
            f"- Discarded events: `{report['audit']['discarded_events_by_reason']}`",
            "- OHLCV does not observe spread, depth, order direction, realized slippage, or causal price impact.",
            "- A positive result would be predictive association for risk only, never proof of liquidity causality.",
            "- Existing blocks are development-consumed and cannot provide final confirmation.",
            "",
            "## Artifact Inventory",
            "",
            f"- `{REPORT_MD}`",
            f"- `{REPORT_JSON}`",
            f"- `{REPORT_HTML}`",
            f"- `{MATRIX_CSV}`",
            f"- `{BOOTSTRAP_CSV}`",
            "",
        ]
    )
    return "\n".join(lines)


def _matrix_fields(matrix: list[dict[str, Any]]) -> list[str]:
    preferred = [
        "level", "pair", "block", "units", "calibration_events", "evaluation_events",
        *METRIC_FIELDS,
        "p1_beta_ci95", "p1_mse_improvement_ci95", "p1_circular_ci95", "p1_pairing_ci95",
        "p1_beta_p_holm", "p1_mse_p_holm", "p1_circular_p_holm", "p1_pairing_p_holm",
        "pair_mse_p_bootstrap", "pair_mse_p_holm", "pair_mse_holm_significant",
        "p2_beta_ci95", "p2_mse_improvement_ci95", "p2_circular_ci95",
        "p2_beta_p_holm", "p2_mse_p_holm", "p2_circular_p_holm",
    ]
    observed = {key for row in matrix for key in row}
    return [field for field in preferred if field in observed]


def run_analysis() -> int:
    samples, audit = _build_events()
    states, preparation_failures = _prepare_units(samples)
    audit["preparation_failures"] = preparation_failures
    if len(states) == 0:
        estimates = {"overall": _aggregate([]), "by_pair": {}, "by_block": {}}
        matrix: list[dict[str, Any]] = [{"level": "overall", **estimates["overall"]}]
        bootstrap = {
            "replicates_requested": BOOTSTRAP_REPS,
            "replicates_completed": 0,
            "seed": RANDOM_SEED,
            "p1": {
                "beta_ci95": [None, None],
                "mse_improvement_ci95": [None, None],
                "circular_loss_reduction_ci95": [None, None],
                "pairing_loss_reduction_ci95": [None, None],
                "p_bootstrap_one_sided": {},
                "p_holm": {},
            },
            "p2_diagnostic": {
                "beta_ci95": [None, None],
                "mse_improvement_ci95": [None, None],
                "circular_loss_reduction_ci95": [None, None],
                "p_bootstrap_one_sided": {},
                "p_holm": {},
            },
            "pair_diagnostic_family": {},
        }
        bootstrap_rows: list[dict[str, Any]] = []
        concentration = {
            "method": "unavailable",
            "positive_reduction_total": 0.0,
            **{dimension: {"shares": {}, "maximum_share": None, "maximum_key": None} for dimension in ("pair", "block", "day")},
        }
        audit["checks"]["integrity_sufficient"] = False
    else:
        estimates, matrix, unit_metrics = _estimate(states)
        bootstrap, bootstrap_rows = _bootstrap(states)
        concentration = _concentration(states, unit_metrics)
        _apply_bootstrap_to_matrix(matrix, bootstrap)
    decision = _decide(estimates, bootstrap, audit, concentration)
    report = {
        "study": "PH4-A08",
        "title": "OHLCV Illiquidity-Proxy Risk Forecasting",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "protocol": {
            "file": str(PROTOCOL_FILE),
            "sha256": audit.get("protocol_sha256"),
            "primary_proxy": "mean(abs(log return) / (close * base volume)) over 24 candles",
            "secondary_proxy": "mean(log(high / low) / (close * base volume)) over 24 candles",
            "outcome": "log future realized volatility over the next 24 candles",
            "scope": "risk forecasting association, not direction, liquidity causality, execution cost, or trading",
        },
        "mechanics": {
            "timeframe_minutes": TIMEFRAME_MINUTES,
            "past_horizon_candles": HORIZON_CANDLES,
            "future_horizon_candles": HORIZON_CANDLES,
            "event_spacing_candles": HORIZON_CANDLES,
            "bootstrap_replicates": BOOTSTRAP_REPS,
            "bootstrap_seed": RANDOM_SEED,
            "minimum_events_per_half": MIN_EVENTS_PER_HALF,
            "material_mse_improvement": MATERIAL_MSE_IMPROVEMENT,
            "multiple_testing": "Holm, separate P1, P2 diagnostic, and per-pair families",
            "pairing_shift": "floor(events_in_half / 2), minimum 1",
            "temporal_placebo_shift": "floor(evaluation_events / 2), minimum 1",
        },
        "audit": audit,
        "estimates": estimates,
        "bootstrap": bootstrap,
        "concentration": concentration,
        "decision": decision,
        "limitations": [
            "close multiplied by base volume is only approximate quote volume",
            "OHLCV cannot identify spread, depth, aggressor side, or causal price impact",
            "all five blocks are development-consumed",
            "P2 is diagnostic and cannot rescue P1",
        ],
    }
    markdown = _render_markdown(report)
    html_text = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>PH4-A08 Illiquidity Proxy</title>"
        "<style>body{font:15px/1.5 system-ui,sans-serif;max-width:1100px;margin:32px auto;padding:0 20px;color:#202124}"
        "pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f6f8fa;border:1px solid #d0d7de;padding:24px}</style>"
        "</head><body><pre>" + html.escape(markdown) + "</pre></body></html>"
    )
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    common.atomic_write_json(REPORT_JSON, report)
    common.atomic_write_text(REPORT_MD, markdown)
    common.atomic_write_text(REPORT_HTML, html_text)
    common.atomic_write_csv(MATRIX_CSV, matrix, _matrix_fields(matrix))
    bootstrap_fields = ["replicate", *METRIC_FIELDS]
    common.atomic_write_csv(BOOTSTRAP_CSV, bootstrap_rows, bootstrap_fields)
    print(decision["decision"])
    for path in (REPORT_MD, REPORT_JSON, REPORT_HTML, MATRIX_CSV, BOOTSTRAP_CSV):
        print(path)
    return 0


def main() -> int:
    args = parse_args()
    if args.command == "analyze":
        return run_analysis()
    raise AssertionError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
