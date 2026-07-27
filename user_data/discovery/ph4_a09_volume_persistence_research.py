"""PH4-A09 offline OHLCV volume-persistence research.

The module implements the frozen PH4_A09_PROTOCOL.md. Importing it or asking
for --help does not load OHLCV or write artifacts. Analysis runs only through
the explicit ``analyze`` subcommand.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import NormalDist
from typing import Any


DISCOVERY_DIR = Path(__file__).resolve().parent
USER_DATA_DIR = DISCOVERY_DIR.parent
PROJECT_ROOT = USER_DATA_DIR.parent
LAB_DIR = USER_DATA_DIR / "lab"
REPORTS_DIR = DISCOVERY_DIR / "reports"
PROTOCOL_FILE = PROJECT_ROOT / "PH4_A09_PROTOCOL.md"

if str(LAB_DIR) not in sys.path:
    sys.path.insert(0, str(LAB_DIR))

import btc_leadership_research as common  # noqa: E402


REPORT_STEM = "ph4_a09_volume_persistence"
REPORT_JSON = REPORTS_DIR / f"{REPORT_STEM}_report.json"
REPORT_MD = REPORTS_DIR / f"{REPORT_STEM}_report.md"
REPORT_HTML = REPORTS_DIR / f"{REPORT_STEM}_report.html"
MATRIX_CSV = REPORTS_DIR / f"{REPORT_STEM}_matrix.csv"
BOOTSTRAP_CSV = REPORTS_DIR / f"{REPORT_STEM}_bootstrap.csv"

HORIZON_CANDLES = 12
TIMEFRAME_MINUTES = 5
TRAIN_FRACTION = 0.60
EMBARGO_CANDLES = 12
BOOTSTRAP_REPS = 1000
RANDOM_SEED = 2026071409
MIN_EVALUATION_EVENTS = 30
MIN_INFORMATIVE_PAIRS = 8
MIN_INFORMATIVE_BLOCKS = 4
MATERIAL_IMPROVEMENT = 0.05
ALPHA = 0.05
HOUR_CATEGORIES = 168

DECISION_OPERATIONAL = "VOLUME-ACTIVITY PROXY CONFIRMED \u2014 RISK OPERATIONAL EXPERIMENT JUSTIFIED"
DECISION_ACTIVITY = "VOLUME-ACTIVITY PROXY CONFIRMED \u2014 NO OPERATIONAL BOT JUSTIFIED"
DECISION_REJECTED = "OHLCV VOLUME-PERSISTENCE HYPOTHESIS REJECTED IN PRIMARY SCOPE"
DECISION_INCONCLUSIVE = "INCONCLUSIVE OHLCV VOLUME-PERSISTENCE AUDIT"

BASE_FEATURES = ["l_prev", "current_risk", "market_activity", "market_risk"]
FULL_FEATURES = [*BASE_FEATURES, "x"]
CONTROL_COLUMNS = {
    "circular": "x_circular",
    "day_permutation": "x_day_permuted",
    "cross_asset": "market_activity",
    "reverse_time": "x_reverse",
}
OUTCOMES = {"activity": "y_activity", "risk": "y_risk"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "PH4-A09 offline volume-persistence audit. Import and help are "
            "data-free; analyze reads existing synchronized 5m OHLCV and "
            "writes only the frozen scientific artifacts."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "analyze",
        help="Run the frozen PH4-A09 offline analysis.",
        description=(
            "Run one fixed 60-minute volume-innovation protocol with no "
            "strategy, threshold, grid, Hyperopt, or trading execution."
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


def _improvement(reference: float, candidate: float) -> float | None:
    if not _finite(reference) or not _finite(candidate) or reference <= 0:
        return None
    return 1.0 - float(candidate) / float(reference)


def _ci(values: list[Any]) -> list[float | None]:
    return common.ci95([float(value) for value in values if _finite(value)])


def _ci_positive(interval: list[float | None]) -> bool:
    return bool(interval and interval[0] is not None and interval[0] > 0.0)


def _bootstrap_positive_p(values: list[Any]) -> float | None:
    valid = [float(value) for value in values if _finite(value)]
    if not valid:
        return None
    return (1.0 + sum(value <= 0.0 for value in valid)) / (1.0 + len(valid))


def _stable_seed(*parts: Any) -> int:
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    return RANDOM_SEED + int.from_bytes(digest[:4], "big")


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


def _fit_hour_fixed_effects(frame: Any, target: str, features: list[str]) -> dict[str, Any]:
    import numpy as np

    columns = [target, "hour_of_week", *features]
    values = frame[columns].to_numpy(dtype=float)
    values = values[np.isfinite(values).all(axis=1)]
    if len(values) <= len(features) + HOUR_CATEGORIES:
        raise ValueError("insufficient finite rows for fixed-effects OLS")
    y = values[:, 0]
    hours = values[:, 1].astype(int)
    x = values[:, 2:]
    if (hours < 0).any() or (hours >= HOUR_CATEGORIES).any():
        raise ValueError("hour_of_week outside 0..167")

    counts = np.bincount(hours, minlength=HOUR_CATEGORIES).astype(float)
    if (counts == 0).any():
        raise ValueError("training split does not cover every hour-of-week category")
    y_means = np.bincount(hours, weights=y, minlength=HOUR_CATEGORIES) / counts
    x_means = np.column_stack(
        [np.bincount(hours, weights=x[:, index], minlength=HOUR_CATEGORIES) / counts for index in range(x.shape[1])]
    )
    y_within = y - y_means[hours]
    x_within = x - x_means[hours]
    slopes, _, rank, _ = np.linalg.lstsq(x_within, y_within, rcond=None)
    if rank < x.shape[1]:
        raise ValueError("rank-deficient continuous fixed-effects design")
    hour_intercepts = y_means - x_means @ slopes
    fitted = hour_intercepts[hours] + x @ slopes
    residual = y - fitted
    degrees_freedom = len(y) - int(rank) - int(np.count_nonzero(counts))
    if degrees_freedom <= 0:
        raise ValueError("non-positive fixed-effects residual degrees of freedom")
    sigma2 = float(np.sum(residual**2)) / degrees_freedom
    covariance = sigma2 * np.linalg.pinv(x_within.T @ x_within)
    standard_errors = np.sqrt(np.maximum(np.diag(covariance), 0.0))
    return {
        "target": target,
        "features": list(features),
        "slopes": slopes,
        "standard_errors": standard_errors,
        "hour_intercepts": hour_intercepts,
        "n": int(len(y)),
        "rank": int(rank),
        "degrees_freedom": int(degrees_freedom),
    }


def _predict_hour_fixed_effects(frame: Any, model: dict[str, Any], overrides: dict[str, Any] | None = None) -> Any:
    import numpy as np

    overrides = overrides or {}
    hours = frame["hour_of_week"].to_numpy(dtype=int)
    feature_values = []
    for feature in model["features"]:
        feature_values.append(np.asarray(overrides.get(feature, frame[feature]), dtype=float))
    x = np.column_stack(feature_values)
    return model["hour_intercepts"][hours] + x @ model["slopes"]


def _beta_summary(model: dict[str, Any], feature: str = "x") -> dict[str, Any]:
    index = model["features"].index(feature)
    beta = float(model["slopes"][index])
    standard_error = float(model["standard_errors"][index])
    if standard_error <= 0:
        pvalue = None
        interval = [beta, beta]
    else:
        z_value = beta / standard_error
        pvalue = 2.0 * (1.0 - NormalDist().cdf(abs(z_value)))
        interval = [beta - 1.959963984540054 * standard_error, beta + 1.959963984540054 * standard_error]
    return {"beta": beta, "se": standard_error, "p_two_sided": pvalue, "ci95": interval}


def _partial_correlation(frame: Any, target: str) -> float | None:
    import numpy as np

    try:
        y_model = _fit_hour_fixed_effects(frame, target, BASE_FEATURES)
        x_frame = frame.copy()
        x_frame["target_x"] = x_frame["x"]
        x_model = _fit_hour_fixed_effects(x_frame, "target_x", BASE_FEATURES)
    except ValueError:
        return None
    y_residual = frame[target].to_numpy(dtype=float) - _predict_hour_fixed_effects(frame, y_model)
    x_residual = frame["x"].to_numpy(dtype=float) - _predict_hour_fixed_effects(x_frame, x_model)
    if float(np.std(y_residual)) <= 0 or float(np.std(x_residual)) <= 0:
        return None
    return float(np.corrcoef(x_residual, y_residual)[0, 1])


def _circular_shift(values: Any) -> Any:
    import numpy as np

    array = np.asarray(values, dtype=float)
    return np.roll(array, max(1, len(array) // 2)) if len(array) else array


def _permute_complete_days(frame: Any, column: str, seed: int) -> Any:
    import numpy as np

    result = frame[column].to_numpy(dtype=float).copy()
    groups: dict[int, list[tuple[Any, Any]]] = defaultdict(list)
    for day, group in frame.groupby("day", sort=True):
        groups[len(group)].append((day, group.index.to_numpy(dtype=int)))
    rng = np.random.default_rng(seed)
    source = frame[column].to_numpy(dtype=float)
    for same_length_days in groups.values():
        if len(same_length_days) < 2:
            continue
        permutation = rng.permutation(len(same_length_days))
        for target_index, donor_index in enumerate(permutation):
            target_rows = same_length_days[target_index][1]
            donor_rows = same_length_days[int(donor_index)][1]
            result[target_rows] = source[donor_rows]
    return result


def _invalid_ohlcv(frame: Any) -> Any:
    import numpy as np

    values = frame[["open", "high", "low", "close", "volume"]].astype(float)
    finite = np.isfinite(values.to_numpy(dtype=float)).all(axis=1)
    return (
        ~finite
        | (values["open"] <= 0)
        | (values["high"] <= 0)
        | (values["low"] <= 0)
        | (values["close"] <= 0)
        | (values["volume"] < 0)
        | (values["high"] < values[["open", "close", "low"]].max(axis=1))
        | (values["low"] > values[["open", "close", "high"]].min(axis=1))
    )


def _load_and_synchronize() -> tuple[dict[int, Any], dict[str, Any]]:
    import pandas as pd

    windows_payload = common.load_json(common.WINDOWS_FILE)
    windows = windows_payload.get("windows", [])
    pair_frames: dict[str, Any] = {}
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
        source_timezone = str(frame["date"].dt.tz)
        frame = frame.copy()
        frame["date"] = pd.to_datetime(frame["date"], utc=True)
        frame = frame.sort_values("date", kind="stable").reset_index(drop=True)
        diffs = frame["date"].diff().dropna()
        invalid = _invalid_ohlcv(frame)
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
            "duplicate_timestamps": int(frame["date"].duplicated().sum()),
            "non_5m_gaps_full_file": int((diffs != pd.Timedelta(minutes=TIMEFRAME_MINUTES)).sum()),
            "invalid_ohlcv_rows": int(invalid.sum()),
        }
        pair_frames[pair] = frame

    synchronized: dict[int, Any] = {}
    block_audit: list[dict[str, Any]] = []
    for window in windows:
        block_id = int(window["window_index"])
        start = pd.Timestamp(window["start"], tz="UTC")
        end = pd.Timestamp(window["end"], tz="UTC")
        merged = None
        pre_sync_counts: dict[str, int] = {}
        for pair in common.ALL_PAIRS:
            frame = pair_frames.get(pair)
            if frame is None:
                continue
            block = frame[(frame["date"] >= start) & (frame["date"] < end)].copy()
            pre_sync_counts[pair] = int(len(block))
            prefix = pair.replace("/", "_")
            selected = block[["date", "close", "volume"]].rename(
                columns={"close": f"{prefix}__close", "volume": f"{prefix}__volume"}
            )
            merged = selected if merged is None else merged.merge(selected, on="date", how="inner")
        if merged is None:
            block_audit.append({"block": block_id, "rows_after_sync": 0, "valid": False})
            continue
        merged = merged.sort_values("date", kind="stable").reset_index(drop=True)
        diffs = merged["date"].diff().dropna()
        synchronized[block_id] = merged
        block_audit.append(
            {
                "block": block_id,
                "timerange": window.get("timerange"),
                "pre_sync_counts": pre_sync_counts,
                "rows_after_sync": int(len(merged)),
                "rows_removed_by_sync": {
                    pair: pre_sync_counts[pair] - len(merged) for pair in pre_sync_counts
                },
                "start": merged["date"].min().isoformat() if len(merged) else None,
                "end": merged["date"].max().isoformat() if len(merged) else None,
                "duplicate_timestamps": int(merged["date"].duplicated().sum()),
                "non_5m_gaps": int((diffs != pd.Timedelta(minutes=TIMEFRAME_MINUTES)).sum()),
                "valid": bool(len(merged) > 2 * HORIZON_CANDLES),
            }
        )
    audit = {
        "protocol_file": str(PROTOCOL_FILE),
        "protocol_sha256": common.sha256_file(PROTOCOL_FILE) if PROTOCOL_FILE.exists() else None,
        "windows_file": str(common.WINDOWS_FILE),
        "windows_sha256": common.sha256_file(common.WINDOWS_FILE) if common.WINDOWS_FILE.exists() else None,
        "windows": windows,
        "file_audit": file_audit,
        "block_audit": block_audit,
    }
    return synchronized, audit


def _build_samples() -> tuple[Any, dict[str, Any]]:
    import numpy as np
    import pandas as pd

    blocks, audit = _load_and_synchronize()
    all_rows: list[Any] = []
    unit_audit: list[dict[str, Any]] = []
    discarded_total: Counter[str] = Counter()

    for block_id, merged in blocks.items():
        derived: dict[str, Any] = {}
        for pair in common.ALL_PAIRS:
            prefix = pair.replace("/", "_")
            close = merged[f"{prefix}__close"].astype(float)
            volume = merged[f"{prefix}__volume"].astype(float)
            log_volume = np.log1p(volume)
            x = log_volume - log_volume.shift(1)
            absolute_return = np.abs(np.log(close / close.shift(1)))
            derived[pair] = {
                "log_volume": log_volume,
                "x": x,
                "absolute_return": absolute_return,
            }

        for pair in common.ALL_PAIRS:
            reasons: Counter[str] = Counter()
            others = [other for other in common.ALL_PAIRS if other != pair]
            own = derived[pair]
            frame = pd.DataFrame(
                {
                    "date": merged["date"],
                    "l_prev": own["log_volume"].shift(1),
                    "x": own["x"],
                    "x_reverse": own["x"].shift(-HORIZON_CANDLES),
                    "current_risk": sum(
                        own["absolute_return"].shift(offset) for offset in range(HORIZON_CANDLES)
                    ),
                    "market_activity": sum(derived[other]["x"] for other in others) / len(others),
                    "market_risk": sum(derived[other]["absolute_return"] for other in others) / len(others),
                    "y_activity": sum(
                        own["log_volume"].shift(-offset) for offset in range(1, HORIZON_CANDLES + 1)
                    ) / HORIZON_CANDLES,
                    "y_risk": sum(
                        own["absolute_return"].shift(-offset) for offset in range(1, HORIZON_CANDLES + 1)
                    ),
                }
            )
            frame["hour_of_week"] = frame["date"].dt.weekday * 24 + frame["date"].dt.hour
            frame["day"] = frame["date"].dt.floor("D")
            required = [
                "l_prev", "x", "x_reverse", "current_risk", "market_activity", "market_risk",
                "y_activity", "y_risk",
            ]
            finite = np.isfinite(frame[required].to_numpy(dtype=float)).all(axis=1)
            candidate_rows: list[int] = []
            for index in range(HORIZON_CANDLES, len(frame) - HORIZON_CANDLES):
                if not finite[index]:
                    reasons["nonfinite_derived_value"] += 1
                    continue
                segment = frame["date"].iloc[index - HORIZON_CANDLES : index + HORIZON_CANDLES + 1]
                if (
                    len(segment) != 2 * HORIZON_CANDLES + 1
                    or segment.iloc[-1] - segment.iloc[0]
                    != pd.Timedelta(minutes=TIMEFRAME_MINUTES * 2 * HORIZON_CANDLES)
                    or not (segment.diff().dropna() == pd.Timedelta(minutes=TIMEFRAME_MINUTES)).all()
                ):
                    reasons["gap_in_predictor_or_label_window"] += 1
                    continue
                candidate_rows.append(index)

            unit = frame.iloc[candidate_rows].copy().reset_index(drop=True)
            split = int(math.floor(len(unit) * TRAIN_FRACTION))
            train_end = max(0, split - EMBARGO_CANDLES)
            train = unit.iloc[:train_end].copy().reset_index(drop=True)
            evaluation = unit.iloc[split:].copy().reset_index(drop=True)
            informative = len(evaluation) >= MIN_EVALUATION_EVENTS and len(train) > HOUR_CATEGORIES + len(FULL_FEATURES)
            if informative:
                train["x_circular"] = _circular_shift(train["x"])
                evaluation["x_circular"] = _circular_shift(evaluation["x"])
                train["x_day_permuted"] = _permute_complete_days(
                    train, "x", _stable_seed(pair, block_id, "train")
                )
                evaluation["x_day_permuted"] = _permute_complete_days(
                    evaluation, "x", _stable_seed(pair, block_id, "evaluation")
                )
                train["pair"] = pair
                train["block"] = block_id
                train["segment"] = "train"
                evaluation["pair"] = pair
                evaluation["block"] = block_id
                evaluation["segment"] = "evaluation"
                all_rows.extend([train, evaluation])
            discarded_total.update(reasons)
            last_train_label_end = (
                train["date"].iloc[-1] + pd.Timedelta(minutes=TIMEFRAME_MINUTES * HORIZON_CANDLES)
                if len(train)
                else None
            )
            first_evaluation = evaluation["date"].iloc[0] if len(evaluation) else None
            unit_audit.append(
                {
                    "pair": pair,
                    "block": block_id,
                    "eligible_events": int(len(unit)),
                    "train_events": int(len(train)),
                    "embargo_events": int(min(EMBARGO_CANDLES, max(0, split))),
                    "evaluation_events": int(len(evaluation)),
                    "last_train_label_end": last_train_label_end.isoformat() if last_train_label_end is not None else None,
                    "first_evaluation_timestamp": first_evaluation.isoformat() if first_evaluation is not None else None,
                    "embargo_valid": bool(
                        last_train_label_end is not None
                        and first_evaluation is not None
                        and last_train_label_end < first_evaluation
                    ),
                    "discarded": dict(reasons),
                    "informative": informative,
                }
            )

    samples = pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()
    informative_units = [unit for unit in unit_audit if unit["informative"]]
    informative_pairs = sorted({unit["pair"] for unit in informative_units})
    informative_blocks = sorted({unit["block"] for unit in informative_units})
    file_audit = audit["file_audit"]
    files_complete = len(file_audit) == len(common.ALL_PAIRS) and all(
        value.get("exists") and not value.get("missing_columns") for value in file_audit.values()
    )
    timezone_ok = files_complete and all(
        value.get("source_timezone") in {"UTC", "UTC+00:00", "Etc/UTC"} for value in file_audit.values()
    )
    duplicate_free = files_complete and all(value.get("duplicate_timestamps") == 0 for value in file_audit.values())
    synchronization_valid = len(audit["block_audit"]) == 5 and all(
        block.get("valid") and block.get("duplicate_timestamps") == 0 for block in audit["block_audit"]
    )
    embargo_valid = bool(informative_units) and all(unit["embargo_valid"] for unit in informative_units)
    sample_sufficient = (
        len(informative_pairs) >= MIN_INFORMATIVE_PAIRS
        and len(informative_blocks) >= MIN_INFORMATIVE_BLOCKS
        and len(informative_units) >= MIN_INFORMATIVE_PAIRS * MIN_INFORMATIVE_BLOCKS
    )
    integrity_sufficient = bool(
        PROTOCOL_FILE.exists()
        and common.WINDOWS_FILE.exists()
        and len(audit["windows"]) == 5
        and files_complete
        and timezone_ok
        and duplicate_free
        and synchronization_valid
        and embargo_valid
        and sample_sufficient
    )
    audit.update(
        {
            "unit_audit": unit_audit,
            "discarded_events_by_reason": dict(discarded_total),
            "informative_units": int(len(informative_units)),
            "informative_pairs": informative_pairs,
            "informative_blocks": informative_blocks,
            "checks": {
                "files_complete": files_complete,
                "five_frozen_windows": len(audit["windows"]) == 5,
                "source_timezone_utc": timezone_ok,
                "duplicate_free": duplicate_free,
                "synchronization_valid": synchronization_valid,
                "lookahead_absent_by_construction": True,
                "labels_do_not_cross_blocks": True,
                "embargo_valid": embargo_valid,
                "sample_sufficient": sample_sufficient,
                "integrity_sufficient": integrity_sufficient,
            },
            "development_consumed": True,
            "holdout_status": "no prospective holdout",
        }
    )
    return samples, audit


def _fit_unit_models(train: Any) -> dict[str, Any]:
    models: dict[str, Any] = {}
    for outcome, target in OUTCOMES.items():
        models[f"{outcome}_baseline"] = _fit_hour_fixed_effects(train, target, BASE_FEATURES)
        models[f"{outcome}_full"] = _fit_hour_fixed_effects(train, target, FULL_FEATURES)
        for control, column in CONTROL_COLUMNS.items():
            if control == "cross_asset":
                continue
            control_frame = train.copy()
            control_frame["x_control"] = control_frame[column]
            models[f"{outcome}_{control}"] = _fit_hour_fixed_effects(
                control_frame, target, [*BASE_FEATURES, "x_control"]
            )
    return models


def _prepare_states(samples: Any) -> tuple[dict[tuple[str, int], dict[str, Any]], list[dict[str, Any]]]:
    states: dict[tuple[str, int], dict[str, Any]] = {}
    failures: list[dict[str, Any]] = []
    if samples.empty:
        return states, failures
    for (pair, block), unit in samples.groupby(["pair", "block"], sort=True):
        train = unit[unit["segment"] == "train"].sort_values("date", kind="stable").reset_index(drop=True)
        evaluation = unit[unit["segment"] == "evaluation"].sort_values("date", kind="stable").reset_index(drop=True)
        try:
            models = _fit_unit_models(train)
        except ValueError as exc:
            failures.append({"pair": pair, "block": int(block), "reason": str(exc)})
            continue
        prediction_columns: dict[str, Any] = {}
        for outcome, target in OUTCOMES.items():
            prediction_columns[f"{outcome}_actual"] = evaluation[target].to_numpy(dtype=float)
            prediction_columns[f"{outcome}_baseline_pred"] = _predict_hour_fixed_effects(
                evaluation, models[f"{outcome}_baseline"]
            )
            prediction_columns[f"{outcome}_full_pred"] = _predict_hour_fixed_effects(
                evaluation, models[f"{outcome}_full"]
            )
            for control, column in CONTROL_COLUMNS.items():
                if control == "cross_asset":
                    prediction_columns[f"{outcome}_{control}_pred"] = prediction_columns[
                        f"{outcome}_baseline_pred"
                    ]
                    continue
                control_frame = evaluation.copy()
                control_frame["x_control"] = control_frame[column]
                prediction_columns[f"{outcome}_{control}_pred"] = _predict_hour_fixed_effects(
                    control_frame, models[f"{outcome}_{control}"]
                )
        prepared_evaluation = evaluation.copy()
        for column, values in prediction_columns.items():
            prepared_evaluation[column] = values
        states[(pair, int(block))] = {
            "pair": pair,
            "block": int(block),
            "train": train,
            "evaluation": prepared_evaluation,
            "models": models,
        }
    return states, failures


def _evaluate_unit(
    state: dict[str, Any],
    evaluation: Any | None = None,
    include_diagnostics: bool = True,
) -> dict[str, Any]:
    frame = state["evaluation"] if evaluation is None else evaluation
    result: dict[str, Any] = {
        "pair": state["pair"],
        "block": state["block"],
        "train_events": int(len(state["train"])),
        "evaluation_events": int(len(frame)),
    }
    for outcome in OUTCOMES:
        actual = frame[f"{outcome}_actual"].to_numpy(dtype=float)
        baseline_pred = frame[f"{outcome}_baseline_pred"].to_numpy(dtype=float)
        full_pred = frame[f"{outcome}_full_pred"].to_numpy(dtype=float)
        baseline_loss = _losses(actual, baseline_pred)
        full_loss = _losses(actual, full_pred)
        beta = _beta_summary(state["models"][f"{outcome}_full"])
        result.update(
            {
                f"{outcome}_beta": beta["beta"],
                f"{outcome}_beta_se": beta["se"],
                f"{outcome}_beta_p": beta["p_two_sided"],
                f"{outcome}_beta_ci_low": beta["ci95"][0],
                f"{outcome}_beta_ci_high": beta["ci95"][1],
                f"{outcome}_partial_correlation": (
                    _partial_correlation(frame, OUTCOMES[outcome]) if include_diagnostics else None
                ),
                f"{outcome}_mse_baseline": baseline_loss["mse"],
                f"{outcome}_mse_full": full_loss["mse"],
                f"{outcome}_mae_baseline": baseline_loss["mae"],
                f"{outcome}_mae_full": full_loss["mae"],
                f"{outcome}_mse_improvement": _improvement(baseline_loss["mse"], full_loss["mse"]),
                f"{outcome}_mae_improvement": _improvement(baseline_loss["mae"], full_loss["mae"]),
                f"{outcome}_r2_baseline": _r2(actual, baseline_pred) if include_diagnostics else None,
                f"{outcome}_r2_full": _r2(actual, full_pred) if include_diagnostics else None,
            }
        )
        result[f"{outcome}_r2_incremental"] = (
            None
            if result[f"{outcome}_r2_baseline"] is None or result[f"{outcome}_r2_full"] is None
            else result[f"{outcome}_r2_full"] - result[f"{outcome}_r2_baseline"]
        )
        for control in CONTROL_COLUMNS:
            control_pred = frame[f"{outcome}_{control}_pred"].to_numpy(dtype=float)
            control_loss = _losses(actual, control_pred)
            result[f"{outcome}_{control}_mse"] = control_loss["mse"]
            result[f"{outcome}_{control}_mae"] = control_loss["mae"]
            result[f"{outcome}_{control}_mse_superiority"] = _improvement(
                control_loss["mse"], full_loss["mse"]
            )
            result[f"{outcome}_{control}_mae_superiority"] = _improvement(
                control_loss["mae"], full_loss["mae"]
            )
    return result


METRIC_FIELDS = []
for _outcome in OUTCOMES:
    METRIC_FIELDS.extend(
        [
            f"{_outcome}_beta", f"{_outcome}_beta_se", f"{_outcome}_beta_p",
            f"{_outcome}_beta_ci_low", f"{_outcome}_beta_ci_high",
            f"{_outcome}_partial_correlation",
            f"{_outcome}_mse_baseline", f"{_outcome}_mse_full",
            f"{_outcome}_mae_baseline", f"{_outcome}_mae_full",
            f"{_outcome}_mse_improvement", f"{_outcome}_mae_improvement",
            f"{_outcome}_r2_baseline", f"{_outcome}_r2_full", f"{_outcome}_r2_incremental",
        ]
    )
    for _control in CONTROL_COLUMNS:
        METRIC_FIELDS.extend(
            [
                f"{_outcome}_{_control}_mse", f"{_outcome}_{_control}_mae",
                f"{_outcome}_{_control}_mse_superiority",
                f"{_outcome}_{_control}_mae_superiority",
            ]
        )


def _aggregate(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    result = {
        "units": int(len(metrics)),
        "train_events": int(sum(item.get("train_events", 0) for item in metrics)),
        "evaluation_events": int(sum(item.get("evaluation_events", 0) for item in metrics)),
    }
    result.update({field: _mean([item.get(field) for item in metrics]) for field in METRIC_FIELDS})
    for outcome in OUTCOMES:
        standard_errors = [item.get(f"{outcome}_beta_se") for item in metrics if _finite(item.get(f"{outcome}_beta_se"))]
        aggregate_se = (
            math.sqrt(sum(float(value) ** 2 for value in standard_errors)) / len(standard_errors)
            if standard_errors
            else None
        )
        beta = result.get(f"{outcome}_beta")
        result[f"{outcome}_beta_aggregate_se"] = aggregate_se
        result[f"{outcome}_beta_aggregate_ci95"] = (
            [beta - 1.959963984540054 * aggregate_se, beta + 1.959963984540054 * aggregate_se]
            if beta is not None and aggregate_se is not None
            else [None, None]
        )
    return result


def _estimate(states: dict[tuple[str, int], dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]], dict[tuple[str, int], dict[str, Any]]]:
    unit_metrics = {key: _evaluate_unit(state) for key, state in states.items()}
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
    matrix: list[dict[str, Any]] = [{"level": "overall", "pair": None, "block": None, **overall}]
    matrix.extend({"level": "pair", "pair": pair, "block": None, **value} for pair, value in by_pair.items())
    matrix.extend({"level": "block", "pair": None, "block": block, **value} for block, value in by_block.items())
    matrix.extend({"level": "unit", **value} for value in unit_metrics.values())
    return {"overall": overall, "by_pair": by_pair, "by_block": by_block}, matrix, unit_metrics


def _resample_days(frame: Any, rng: Any) -> Any:
    import pandas as pd

    days = list(frame["day"].drop_duplicates())
    selected = rng.choice(days, size=len(days), replace=True)
    return pd.concat([frame[frame["day"] == day] for day in selected], ignore_index=True)


BOOTSTRAP_FIELDS = [
    "activity_mse_improvement", "activity_mae_improvement",
    "risk_mse_improvement", "risk_mae_improvement",
]
for _outcome in OUTCOMES:
    for _control in CONTROL_COLUMNS:
        BOOTSTRAP_FIELDS.append(f"{_outcome}_{_control}_mse_superiority")


def _bootstrap(states: dict[tuple[str, int], dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    import numpy as np

    rng = np.random.default_rng(RANDOM_SEED)
    rows: list[dict[str, Any]] = []
    for replicate in range(BOOTSTRAP_REPS):
        metrics = []
        for state in states.values():
            sampled = _resample_days(state["evaluation"], rng)
            metrics.append(_evaluate_unit(state, sampled, include_diagnostics=False))
        aggregate = _aggregate(metrics)
        row = {"replicate": replicate}
        row.update({field: aggregate.get(field) for field in BOOTSTRAP_FIELDS})
        rows.append(row)

    pvalues = {
        field: _bootstrap_positive_p([row.get(field) for row in rows]) for field in BOOTSTRAP_FIELDS
    }
    holm = common.holm_adjust(pvalues)
    result = {
        "replicates_requested": BOOTSTRAP_REPS,
        "replicates_completed": int(len(rows)),
        "seed": RANDOM_SEED,
        "resampling_unit": "complete UTC days within each pair/block evaluation split",
        "aggregation": "equal weight across informative pair/block units",
        "ci95": {field: _ci([row.get(field) for row in rows]) for field in BOOTSTRAP_FIELDS},
        "p_bootstrap_one_sided": pvalues,
        "p_holm": holm,
        "holm_significant": {
            field: bool(holm.get(field) is not None and holm[field] < ALPHA) for field in BOOTSTRAP_FIELDS
        },
    }
    return result, rows


def _concentration(states: dict[tuple[str, int], dict[str, Any]]) -> dict[str, Any]:
    import numpy as np

    result: dict[str, Any] = {}
    for outcome in OUTCOMES:
        buckets: dict[str, defaultdict[str, float]] = {
            "pair": defaultdict(float), "block": defaultdict(float), "day": defaultdict(float)
        }
        total = 0.0
        for key, state in states.items():
            frame = state["evaluation"]
            actual = frame[f"{outcome}_actual"].to_numpy(dtype=float)
            baseline = frame[f"{outcome}_baseline_pred"].to_numpy(dtype=float)
            full = frame[f"{outcome}_full_pred"].to_numpy(dtype=float)
            positive = np.maximum((actual - baseline) ** 2 - (actual - full) ** 2, 0.0)
            for index, value in enumerate(positive):
                contribution = float(value) / max(1, len(frame))
                if contribution <= 0:
                    continue
                pair, block = key
                day = str(frame["day"].iloc[index].date())
                buckets["pair"][pair] += contribution
                buckets["block"][str(block)] += contribution
                buckets["day"][day] += contribution
                total += contribution
        outcome_result: dict[str, Any] = {"positive_reduction_total": total}
        for dimension, values in buckets.items():
            shares = {key: value / total if total > 0 else None for key, value in sorted(values.items())}
            finite = {key: value for key, value in shares.items() if _finite(value)}
            maximum_key = max(finite, key=finite.get) if finite else None
            outcome_result[dimension] = {
                "shares": shares,
                "maximum_key": maximum_key,
                "maximum_share": finite.get(maximum_key) if maximum_key else None,
            }
        result[outcome] = outcome_result
    result["method"] = "positive event-level squared-error reduction normalized by evaluation events per unit"
    return result


def _robustness_counts(estimates: dict[str, Any], outcome: str) -> tuple[int, int]:
    pair_count = sum(
        value.get(f"{outcome}_mse_improvement", 0) > 0
        and value.get(f"{outcome}_mae_improvement", 0) > 0
        for value in estimates["by_pair"].values()
    )
    block_count = sum(
        value.get(f"{outcome}_mse_improvement", 0) > 0
        and value.get(f"{outcome}_mae_improvement", 0) > 0
        for value in estimates["by_block"].values()
    )
    return int(pair_count), int(block_count)


def _outcome_gates(
    outcome: str,
    estimates: dict[str, Any],
    bootstrap: dict[str, Any],
    concentration: dict[str, Any],
) -> dict[str, Any]:
    overall = estimates["overall"]
    pairs, blocks = _robustness_counts(estimates, outcome)
    beta_ci = overall[f"{outcome}_beta_aggregate_ci95"]
    mse_field = f"{outcome}_mse_improvement"
    mae_field = f"{outcome}_mae_improvement"
    controls = [f"{outcome}_{control}_mse_superiority" for control in CONTROL_COLUMNS]
    concentration_pass = all(
        concentration[outcome][dimension]["maximum_share"] is not None
        and concentration[outcome][dimension]["maximum_share"] <= 0.30
        for dimension in ("pair", "block", "day")
    )
    gates = {
        "mse_improvement_at_least_5pct": overall.get(mse_field) is not None and overall[mse_field] >= MATERIAL_IMPROVEMENT,
        "mae_improvement_at_least_5pct": overall.get(mae_field) is not None and overall[mae_field] >= MATERIAL_IMPROVEMENT,
        "mse_ci95_positive": _ci_positive(bootstrap["ci95"][mse_field]),
        "mae_ci95_positive": _ci_positive(bootstrap["ci95"][mae_field]),
        "mse_survives_holm": bootstrap["holm_significant"][mse_field],
        "mae_survives_holm": bootstrap["holm_significant"][mae_field],
        "beta_positive_ci95": _ci_positive(beta_ci),
        "positive_at_least_7_of_10_pairs": pairs >= 7,
        "positive_at_least_4_of_5_blocks": blocks >= 4,
        "all_controls_survive_holm": all(
            _ci_positive(bootstrap["ci95"][field]) and bootstrap["holm_significant"][field]
            for field in controls
        ),
        "concentration_at_most_30pct": concentration_pass,
    }
    return {"gates": gates, "positive_pairs": pairs, "positive_blocks": blocks, "passes": all(gates.values())}


def _decide(
    estimates: dict[str, Any],
    bootstrap: dict[str, Any],
    concentration: dict[str, Any],
    audit: dict[str, Any],
) -> dict[str, Any]:
    activity = _outcome_gates("activity", estimates, bootstrap, concentration)
    risk = _outcome_gates("risk", estimates, bootstrap, concentration)
    integrity = bool(audit["checks"]["integrity_sufficient"])
    if not integrity:
        decision = DECISION_INCONCLUSIVE
        reason = "Data, sample, or integrity prevented a valid test after frozen technical checks."
    elif not activity["passes"]:
        decision = DECISION_REJECTED
        reason = "P1 activity failed at least one pre-registered economic, statistical, control, or robustness gate."
    elif risk["passes"]:
        decision = DECISION_OPERATIONAL
        reason = "P1 and P2 passed every pre-registered development gate; operational experimentation is justified, not a bot."
    else:
        decision = DECISION_ACTIVITY
        reason = "P1 activity passed, but P2 risk failed at least one required gate; no operational bot is justified."
    return {
        "decision": decision,
        "reason": reason,
        "integrity_sufficient": integrity,
        "activity": activity,
        "risk": risk,
        "operational_experiment_justified": decision == DECISION_OPERATIONAL,
        "scope": "activity/attention proxy and risk forecasting only; no flow, liquidity, causality, or trading claim",
    }


def _apply_bootstrap_to_matrix(matrix: list[dict[str, Any]], bootstrap: dict[str, Any]) -> None:
    for row in matrix:
        if row["level"] != "overall":
            continue
        for field in BOOTSTRAP_FIELDS:
            row[f"{field}_ci95"] = bootstrap["ci95"][field]
            row[f"{field}_p_bootstrap"] = bootstrap["p_bootstrap_one_sided"][field]
            row[f"{field}_p_holm"] = bootstrap["p_holm"][field]
            row[f"{field}_holm_significant"] = bootstrap["holm_significant"][field]


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
    lines = [
        "# PH4-A09 - OHLCV Volume Persistence",
        "",
        f"Generated: `{report['generated_at']}`",
        "",
        f"**Decision:** {decision['decision']}",
        "",
        decision["reason"],
        "",
        "## Frozen Design",
        "",
        "- Ten synchronized Binance spot pairs, 5m OHLCV, five frozen development-consumed blocks.",
        "- One 12-candle future horizon, one 12-candle risk lookback, 60/40 split, 12-candle embargo.",
        "- Hour-of-week fixed effects and frozen train coefficients; no threshold, strategy, or trading model.",
        "- Bootstrap: 1,000 complete-UTC-day replicates, equal-weight pair/block units, seed 2026071409.",
        "",
        "## P1 Activity",
        "",
        f"- Beta: `{_fmt(overall['activity_beta'])}`; aggregate CI95 `{overall['activity_beta_aggregate_ci95']}`",
        f"- Partial correlation: `{_fmt(overall['activity_partial_correlation'])}`",
        f"- MSE improvement: `{_fmt(overall['activity_mse_improvement'])}`; CI95 `{bootstrap['ci95']['activity_mse_improvement']}`; Holm `{bootstrap['p_holm']['activity_mse_improvement']}`",
        f"- MAE improvement: `{_fmt(overall['activity_mae_improvement'])}`; CI95 `{bootstrap['ci95']['activity_mae_improvement']}`; Holm `{bootstrap['p_holm']['activity_mae_improvement']}`",
        f"- Incremental R2: `{_fmt(overall['activity_r2_incremental'])}`",
        f"- Positive pairs/blocks: `{decision['activity']['positive_pairs']}/10`, `{decision['activity']['positive_blocks']}/5`",
        "",
        "## P2 Risk",
        "",
        f"- Beta: `{_fmt(overall['risk_beta'])}`; aggregate CI95 `{overall['risk_beta_aggregate_ci95']}`",
        f"- Partial correlation: `{_fmt(overall['risk_partial_correlation'])}`",
        f"- MSE improvement: `{_fmt(overall['risk_mse_improvement'])}`; CI95 `{bootstrap['ci95']['risk_mse_improvement']}`; Holm `{bootstrap['p_holm']['risk_mse_improvement']}`",
        f"- MAE improvement: `{_fmt(overall['risk_mae_improvement'])}`; CI95 `{bootstrap['ci95']['risk_mae_improvement']}`; Holm `{bootstrap['p_holm']['risk_mae_improvement']}`",
        f"- Incremental R2: `{_fmt(overall['risk_r2_incremental'])}`",
        f"- Positive pairs/blocks: `{decision['risk']['positive_pairs']}/10`, `{decision['risk']['positive_blocks']}/5`",
        "",
        "## Negative Controls",
        "",
    ]
    for outcome in OUTCOMES:
        for control in CONTROL_COLUMNS:
            field = f"{outcome}_{control}_mse_superiority"
            lines.append(
                f"- {outcome} vs {control}: `{_fmt(overall[field])}`; CI95 `{bootstrap['ci95'][field]}`; Holm `{bootstrap['p_holm'][field]}`"
            )
    lines.extend(["", "## Concentration", ""])
    for outcome in OUTCOMES:
        for dimension in ("pair", "block", "day"):
            item = report["concentration"][outcome][dimension]
            lines.append(
                f"- {outcome} {dimension}: max `{_fmt(item['maximum_share'])}` at `{item['maximum_key']}`"
            )
    lines.extend(["", "## Gates", "", "### P1 Activity", ""])
    lines.extend(f"- `{key}`: `{value}`" for key, value in decision["activity"]["gates"].items())
    lines.extend(["", "### P2 Risk", ""])
    lines.extend(f"- `{key}`: `{value}`" for key, value in decision["risk"]["gates"].items())
    lines.extend(
        [
            "",
            "## Integrity and Scope",
            "",
            f"- Integrity sufficient: `{decision['integrity_sufficient']}`",
            f"- Informative units: `{report['audit']['informative_units']}`",
            f"- Protocol SHA-256: `{report['audit']['protocol_sha256']}`",
            "- Volume is an OHLCV activity/attention proxy, not institutional flow or liquidity.",
            "- Current blocks are development-consumed and are not prospective confirmation.",
            f"- Operational experiment justified: `{decision['operational_experiment_justified']}`",
            "",
            "## Artifacts",
            "",
            f"- `{REPORT_MD}`",
            f"- `{REPORT_HTML}`",
            f"- `{REPORT_JSON}`",
            f"- `{MATRIX_CSV}`",
            f"- `{BOOTSTRAP_CSV}`",
            "",
        ]
    )
    return "\n".join(lines)


def _matrix_fields(matrix: list[dict[str, Any]]) -> list[str]:
    preferred = ["level", "pair", "block", "units", "train_events", "evaluation_events", *METRIC_FIELDS]
    for field in BOOTSTRAP_FIELDS:
        preferred.extend(
            [
                f"{field}_ci95", f"{field}_p_bootstrap", f"{field}_p_holm",
                f"{field}_holm_significant",
            ]
        )
    observed = {key for row in matrix for key in row}
    return [field for field in preferred if field in observed]


def run_analysis() -> int:
    samples, audit = _build_samples()
    states, preparation_failures = _prepare_states(samples)
    audit["preparation_failures"] = preparation_failures
    prepared_pairs = {pair for pair, _ in states}
    prepared_blocks = {block for _, block in states}
    if len(prepared_pairs) < MIN_INFORMATIVE_PAIRS or len(prepared_blocks) < MIN_INFORMATIVE_BLOCKS:
        audit["checks"]["integrity_sufficient"] = False
        audit["checks"]["prepared_sample_sufficient"] = False
    else:
        audit["checks"]["prepared_sample_sufficient"] = True

    if states:
        estimates, matrix, _ = _estimate(states)
        bootstrap, bootstrap_rows = _bootstrap(states)
        concentration = _concentration(states)
        _apply_bootstrap_to_matrix(matrix, bootstrap)
    else:
        estimates = {"overall": _aggregate([]), "by_pair": {}, "by_block": {}}
        matrix = [{"level": "overall", **estimates["overall"]}]
        bootstrap_rows = []
        bootstrap = {
            "replicates_requested": BOOTSTRAP_REPS,
            "replicates_completed": 0,
            "seed": RANDOM_SEED,
            "ci95": {field: [None, None] for field in BOOTSTRAP_FIELDS},
            "p_bootstrap_one_sided": {field: None for field in BOOTSTRAP_FIELDS},
            "p_holm": {field: None for field in BOOTSTRAP_FIELDS},
            "holm_significant": {field: False for field in BOOTSTRAP_FIELDS},
        }
        concentration = {
            outcome: {
                "positive_reduction_total": 0.0,
                **{dimension: {"shares": {}, "maximum_key": None, "maximum_share": None} for dimension in ("pair", "block", "day")},
            }
            for outcome in OUTCOMES
        }
        concentration["method"] = "unavailable"

    decision = _decide(estimates, bootstrap, concentration, audit)
    report = {
        "study": "PH4-A09",
        "title": "OHLCV Volume Persistence",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "protocol": {
            "file": str(PROTOCOL_FILE),
            "sha256": audit.get("protocol_sha256"),
            "question": "Does continuous own-volume innovation improve one-hour activity and risk forecasts?",
            "scope": "activity/attention and risk prediction, not trading or causal flow identification",
        },
        "mechanics": {
            "timeframe_minutes": TIMEFRAME_MINUTES,
            "future_horizon_candles": HORIZON_CANDLES,
            "risk_lookback_candles": HORIZON_CANDLES,
            "train_fraction": TRAIN_FRACTION,
            "evaluation_fraction": 1.0 - TRAIN_FRACTION,
            "embargo_candles": EMBARGO_CANDLES,
            "bootstrap_replicates": BOOTSTRAP_REPS,
            "bootstrap_seed": RANDOM_SEED,
            "hour_of_week_categories": HOUR_CATEGORIES,
            "multiple_testing": "one Holm family across P1/P2 loss gains and MSE control contrasts",
        },
        "audit": audit,
        "estimates": estimates,
        "bootstrap": bootstrap,
        "concentration": concentration,
        "decision": decision,
        "limitations": [
            "OHLCV volume is only an activity/attention proxy",
            "no aggressor side, institutional flow, spread, depth, or causal liquidity is observed",
            "all five blocks are development-consumed",
            "activity prediction alone is not a tradable advantage",
        ],
    }
    markdown = _render_markdown(report)
    html_text = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>PH4-A09 Volume Persistence</title>"
        "<style>body{font:15px/1.5 system-ui,sans-serif;max-width:1100px;margin:32px auto;padding:0 20px;color:#202124}"
        "pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f6f8fa;border:1px solid #d0d7de;padding:24px}</style>"
        "</head><body><pre>" + html.escape(markdown) + "</pre></body></html>"
    )
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    common.atomic_write_json(REPORT_JSON, report)
    common.atomic_write_text(REPORT_MD, markdown)
    common.atomic_write_text(REPORT_HTML, html_text)
    common.atomic_write_csv(MATRIX_CSV, matrix, _matrix_fields(matrix))
    common.atomic_write_csv(BOOTSTRAP_CSV, bootstrap_rows, ["replicate", *BOOTSTRAP_FIELDS])
    print(decision["decision"])
    for path in (REPORT_MD, REPORT_HTML, REPORT_JSON, MATRIX_CSV, BOOTSTRAP_CSV):
        print(path)
    return 0


def main() -> int:
    args = parse_args()
    if args.command == "analyze":
        return run_analysis()
    raise AssertionError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
