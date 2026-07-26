"""PH4-A11 offline OHLCV calendar-seasonality research.

Import and --help are data-free. The frozen analysis runs only through the
explicit ``analyze`` subcommand and never creates trading signals or orders.
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
PROTOCOL_FILE = PROJECT_ROOT / "PH4_A11_PROTOCOL.md"

if str(LAB_DIR) not in sys.path:
    sys.path.insert(0, str(LAB_DIR))

import btc_leadership_research as common  # noqa: E402


STEM = "ph4_a11_calendar_seasonality"
REPORT_MD = REPORTS_DIR / f"{STEM}_report.md"
REPORT_HTML = REPORTS_DIR / f"{STEM}_report.html"
REPORT_JSON = REPORTS_DIR / f"{STEM}_report.json"
MATRIX_CSV = REPORTS_DIR / f"{STEM}_matrix.csv"
BOOTSTRAP_CSV = REPORTS_DIR / f"{STEM}_bootstrap.csv"

HORIZON = 12
TRAIN_FRACTION = 0.60
BOOTSTRAP_REPS = 1000
SEED = 2026071411
FEE_ONLY_COST = 0.002
CONSERVATIVE_COST = 0.003
MIN_EVAL = 30
MIN_PAIRS = 8
MIN_BLOCKS = 4
MATERIAL_GAIN = 0.05
ALPHA = 0.05

CONTRASTS = [
    "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY",
    "WEEKEND", "UTC_00_08", "UTC_08_16", "UTC_16_24",
]
RETURN_BASE = ["past_return", "past_risk", "market_past_return", "market_past_risk"]
RISK_BASE = ["past_risk", "abs_past_return", "market_past_risk", "abs_market_past_return"]
CONTROLS = ["circular", "week_permutation", "reverse_time"]

DECISION_CONFIRMED = "OHLCV CALENDAR-SEASONALITY CONFIRMED \u2014 OPERATIONAL EXPERIMENT JUSTIFIED"
DECISION_REJECTED = "OHLCV CALENDAR-SEASONALITY HYPOTHESIS REJECTED IN PRIMARY SCOPE"
DECISION_INCONCLUSIVE = "INCONCLUSIVE OHLCV CALENDAR-SEASONALITY AUDIT"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "PH4-A11 offline calendar-seasonality audit. analyze uses only "
            "existing synchronized 5m OHLCV and the frozen 11 contrasts."
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("analyze", help="Run the frozen PH4-A11 analysis.")
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
    return bool(interval and interval[0] is not None and interval[0] > 0)


def _normal_positive_p(values: list[Any]) -> float | None:
    import numpy as np

    valid = np.asarray([float(value) for value in values if _finite(value)], dtype=float)
    if len(valid) < 2:
        return None
    standard_error = float(np.std(valid, ddof=1))
    estimate = float(np.mean(valid))
    if standard_error <= 0:
        return 0.0 if estimate > 0 else 1.0
    return 1.0 - NormalDist().cdf(estimate / standard_error)


def _stable_seed(*parts: Any) -> int:
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode()).digest()
    return SEED + int.from_bytes(digest[:4], "big")


def _fit_ols(frame: Any, target: str, features: list[str]) -> dict[str, Any]:
    import numpy as np

    matrix = frame[[target, *features]].to_numpy(dtype=float)
    matrix = matrix[np.isfinite(matrix).all(axis=1)]
    if len(matrix) <= len(features) + 1:
        raise ValueError("insufficient rows for OLS")
    y = matrix[:, 0]
    x = np.column_stack([np.ones(len(matrix)), matrix[:, 1:]])
    coefficients, _, rank, _ = np.linalg.lstsq(x, y, rcond=None)
    if rank < x.shape[1]:
        raise ValueError("rank-deficient OLS")
    residual = y - x @ coefficients
    degrees = len(y) - x.shape[1]
    sigma2 = float(np.sum(residual**2)) / degrees
    covariance = sigma2 * np.linalg.pinv(x.T @ x)
    standard_errors = np.sqrt(np.maximum(np.diag(covariance), 0))
    return {"features": features, "coefficients": coefficients, "standard_errors": standard_errors}


def _predict(frame: Any, model: dict[str, Any]) -> Any:
    import numpy as np

    x = np.column_stack(
        [np.ones(len(frame)), *[frame[name].to_numpy(dtype=float) for name in model["features"]]]
    )
    return x @ model["coefficients"]


def _beta(model: dict[str, Any], feature: str = "label") -> dict[str, Any]:
    index = model["features"].index(feature) + 1
    beta = float(model["coefficients"][index])
    se = float(model["standard_errors"][index])
    z = beta / se if se > 0 else None
    p_two = 2 * (1 - NormalDist().cdf(abs(z))) if z is not None else None
    p_one = 1 - NormalDist().cdf(z) if z is not None else (0.0 if beta > 0 else 1.0)
    return {
        "beta": beta,
        "se": se,
        "p_two_sided": p_two,
        "p_one_sided_positive": p_one,
        "ci95": [beta - 1.959963984540054 * se, beta + 1.959963984540054 * se],
    }


def _losses(actual: Any, prediction: Any) -> dict[str, float]:
    import numpy as np

    residual = np.asarray(actual, dtype=float) - np.asarray(prediction, dtype=float)
    return {"mse": float(np.mean(residual**2)), "mae": float(np.mean(np.abs(residual)))}


def _r2(actual: Any, prediction: Any) -> float | None:
    import numpy as np

    y = np.asarray(actual, dtype=float)
    sst = float(np.sum((y - np.mean(y)) ** 2))
    return None if sst <= 0 else 1 - float(np.sum((y - prediction) ** 2)) / sst


def _partial_corr(frame: Any, target: str, base: list[str], label: str) -> float | None:
    import numpy as np

    try:
        y_model = _fit_ols(frame, target, base)
        xframe = frame.copy()
        xframe["label_target"] = xframe[label]
        x_model = _fit_ols(xframe, "label_target", base)
    except ValueError:
        return None
    y_res = frame[target].to_numpy(dtype=float) - _predict(frame, y_model)
    x_res = frame[label].to_numpy(dtype=float) - _predict(xframe, x_model)
    if np.std(y_res) <= 0 or np.std(x_res) <= 0:
        return None
    return float(np.corrcoef(y_res, x_res)[0, 1])


def _invalid_ohlcv(frame: Any) -> Any:
    import numpy as np

    value = frame[["open", "high", "low", "close", "volume"]].astype(float)
    finite = np.isfinite(value.to_numpy()).all(axis=1)
    return (
        ~finite | (value["open"] <= 0) | (value["high"] <= 0) | (value["low"] <= 0)
        | (value["close"] <= 0) | (value["volume"] < 0)
        | (value["high"] < value[["open", "close", "low"]].max(axis=1))
        | (value["low"] > value[["open", "close", "high"]].min(axis=1))
    )


def _load_blocks() -> tuple[dict[int, Any], dict[str, Any]]:
    import pandas as pd

    windows = common.load_json(common.WINDOWS_FILE)["windows"]
    frames: dict[str, Any] = {}
    files: dict[str, Any] = {}
    for pair in common.ALL_PAIRS:
        path = common.DATA_DIR / common.pair_to_filename(pair)
        if not path.exists():
            files[pair] = {"path": str(path), "exists": False}
            continue
        frame = pd.read_feather(path)
        required = {"date", "open", "high", "low", "close", "volume"}
        missing = sorted(required - set(frame.columns))
        if missing:
            files[pair] = {"path": str(path), "exists": True, "missing_columns": missing}
            continue
        source_tz = str(frame["date"].dt.tz)
        frame = frame.copy()
        frame["date"] = pd.to_datetime(frame["date"], utc=True)
        frame = frame.sort_values("date", kind="stable").reset_index(drop=True)
        diffs = frame["date"].diff().dropna()
        files[pair] = {
            "path": str(path), "exists": True, "sha256": common.sha256_file(path),
            "rows": int(len(frame)), "start": frame["date"].min().isoformat(),
            "end": frame["date"].max().isoformat(), "source_timezone": source_tz,
            "duplicates": int(frame["date"].duplicated().sum()),
            "gaps": int((diffs != pd.Timedelta(minutes=5)).sum()),
            "invalid_ohlcv": int(_invalid_ohlcv(frame).sum()),
        }
        frames[pair] = frame

    blocks: dict[int, Any] = {}
    block_audit = []
    for window in windows:
        block_id = int(window["window_index"])
        start, end = pd.Timestamp(window["start"], tz="UTC"), pd.Timestamp(window["end"], tz="UTC")
        merged = None
        before = {}
        for pair in common.ALL_PAIRS:
            if pair not in frames:
                continue
            subset = frames[pair][(frames[pair]["date"] >= start) & (frames[pair]["date"] < end)]
            before[pair] = len(subset)
            column = pair.replace("/", "_") + "__close"
            piece = subset[["date", "close"]].rename(columns={"close": column})
            merged = piece if merged is None else merged.merge(piece, on="date", how="inner")
        if merged is None:
            block_audit.append({"block": block_id, "valid": False, "rows": 0})
            continue
        merged = merged.sort_values("date", kind="stable").reset_index(drop=True)
        diffs = merged["date"].diff().dropna()
        blocks[block_id] = merged
        block_audit.append(
            {
                "block": block_id, "timerange": window.get("timerange"), "rows": len(merged),
                "pre_sync_rows": before, "duplicates": int(merged["date"].duplicated().sum()),
                "gaps": int((diffs != pd.Timedelta(minutes=5)).sum()),
                "start": merged["date"].min().isoformat(), "end": merged["date"].max().isoformat(),
                "valid": len(merged) > 2 * HORIZON,
            }
        )
    audit = {
        "protocol_file": str(PROTOCOL_FILE),
        "protocol_sha256": common.sha256_file(PROTOCOL_FILE) if PROTOCOL_FILE.exists() else None,
        "windows_file": str(common.WINDOWS_FILE), "windows_sha256": common.sha256_file(common.WINDOWS_FILE),
        "windows": windows, "file_audit": files, "block_audit": block_audit,
    }
    return blocks, audit


def _contrast_values(date: Any) -> dict[str, int]:
    weekday, hour = int(date.weekday()), int(date.hour)
    names = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
    values = {name: int(weekday == index) for index, name in enumerate(names)}
    values.update(
        {
            "WEEKEND": int(weekday >= 5), "UTC_00_08": int(hour < 8),
            "UTC_08_16": int(8 <= hour < 16), "UTC_16_24": int(hour >= 16),
        }
    )
    return values


def _week_start(series: Any) -> Any:
    import pandas as pd

    return (series - pd.to_timedelta(series.dt.weekday, unit="D")).dt.floor("D")


def _complete_week_mask(frame: Any) -> Any:
    import numpy as np
    import pandas as pd

    mask = np.zeros(len(frame), dtype=bool)
    for _, group in frame.groupby("week", sort=True):
        if (
            len(group) == 168
            and group["date"].iloc[0].weekday() == 0 and group["date"].iloc[0].hour == 0
            and group["date"].iloc[-1] - group["date"].iloc[0] == pd.Timedelta(hours=167)
            and (group["date"].diff().dropna() == pd.Timedelta(hours=1)).all()
        ):
            mask[group.index.to_numpy(dtype=int)] = True
    return mask


def _permute_week_labels(frame: Any, contrast: str, segment: str, pair: str, block: int) -> Any:
    import numpy as np

    result = frame[contrast].to_numpy(dtype=float).copy()
    rng = np.random.default_rng(_stable_seed(contrast, segment, pair, block))
    for _, group in frame.groupby("week", sort=True):
        indices = group.index.to_numpy(dtype=int)
        if len(indices) == 168:
            result[indices] = result[indices][rng.permutation(168)]
    return result


def _build_samples() -> tuple[Any, dict[str, Any]]:
    import numpy as np
    import pandas as pd

    blocks, audit = _load_blocks()
    pieces = []
    unit_audit = []
    discarded = Counter()
    for block_id, merged in blocks.items():
        closes = {pair: merged[pair.replace("/", "_") + "__close"].to_numpy(dtype=float) for pair in common.ALL_PAIRS}
        hourly_indices = [index for index, date in enumerate(merged["date"]) if date.minute == 0]
        for pair in common.ALL_PAIRS:
            rows = []
            for index in hourly_indices:
                if index < HORIZON or index + HORIZON >= len(merged):
                    discarded["boundary"] += 1
                    continue
                segment = merged["date"].iloc[index - HORIZON : index + HORIZON + 1]
                if not (
                    len(segment) == 25
                    and segment.iloc[-1] - segment.iloc[0] == pd.Timedelta(hours=2)
                    and (segment.diff().dropna() == pd.Timedelta(minutes=5)).all()
                ):
                    discarded["gap_in_lookback_or_label"] += 1
                    continue
                own = closes[pair]
                past_return = own[index] / own[index - HORIZON] - 1
                future_return = own[index + HORIZON] / own[index] - 1
                own_log = np.diff(np.log(own[index - HORIZON : index + HORIZON + 1]))
                past_risk = float(np.sum(np.abs(own_log[:HORIZON])))
                future_risk = float(np.sum(np.abs(own_log[HORIZON:])))
                other_past_returns, other_past_risks = [], []
                for other in common.ALL_PAIRS:
                    if other == pair:
                        continue
                    values = closes[other]
                    other_past_returns.append(values[index] / values[index - HORIZON] - 1)
                    other_log = np.diff(np.log(values[index - HORIZON : index + 1]))
                    other_past_risks.append(float(np.sum(np.abs(other_log))))
                date = merged["date"].iloc[index]
                row = {
                    "pair": pair, "block": block_id, "date": date,
                    "y_return": future_return, "y_risk": future_risk,
                    "past_return": past_return, "past_risk": past_risk,
                    "market_past_return": float(np.mean(other_past_returns)),
                    "market_past_risk": float(np.mean(other_past_risks)),
                    "abs_past_return": abs(past_return),
                    "abs_market_past_return": abs(float(np.mean(other_past_returns))),
                }
                row.update(_contrast_values(date))
                rows.append(row)
            unit = pd.DataFrame(rows).sort_values("date", kind="stable").reset_index(drop=True)
            if unit.empty:
                unit_audit.append({"pair": pair, "block": block_id, "informative": False})
                continue
            unit["week"] = _week_start(unit["date"])
            split = int(math.floor(len(unit) * TRAIN_FRACTION))
            train = unit.iloc[: max(0, split - 1)].copy().reset_index(drop=True)
            evaluation = unit.iloc[split:].copy().reset_index(drop=True)
            train["week"] = _week_start(train["date"])
            evaluation["week"] = _week_start(evaluation["date"])
            evaluation["bootstrap_eligible"] = _complete_week_mask(evaluation)
            full_weeks = int(evaluation.loc[evaluation["bootstrap_eligible"], "week"].nunique())
            informative = len(evaluation) >= MIN_EVAL and full_weeks >= 1
            if informative:
                for contrast in CONTRASTS:
                    train[f"{contrast}__circular"] = np.roll(train[contrast].to_numpy(), 84)
                    evaluation[f"{contrast}__circular"] = np.roll(evaluation[contrast].to_numpy(), 84)
                    train[f"{contrast}__week_permutation"] = _permute_week_labels(
                        train, contrast, "train", pair, block_id
                    )
                    evaluation[f"{contrast}__week_permutation"] = _permute_week_labels(
                        evaluation, contrast, "evaluation", pair, block_id
                    )
                    train[f"{contrast}__reverse_time"] = train[contrast].to_numpy()[::-1]
                    evaluation[f"{contrast}__reverse_time"] = evaluation[contrast].to_numpy()[::-1]
                train["segment"], evaluation["segment"] = "train", "evaluation"
                pieces.extend([train, evaluation])
            unit_audit.append(
                {
                    "pair": pair, "block": block_id, "hourly_observations": len(unit),
                    "train": len(train), "embargo_hourly_observations": 1,
                    "evaluation": len(evaluation), "complete_evaluation_weeks": full_weeks,
                    "anchors_hh00": bool((unit["date"].dt.minute == 0).all()),
                    "non_overlapping": bool((unit["date"].diff().dropna() >= pd.Timedelta(hours=1)).all()),
                    "embargo_valid": bool(
                        len(train) and len(evaluation)
                        and train["date"].iloc[-1] + pd.Timedelta(hours=1) < evaluation["date"].iloc[0]
                    ),
                    "informative": informative,
                }
            )
    samples = pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame()
    informative = [unit for unit in unit_audit if unit["informative"]]
    pairs, block_ids = sorted({u["pair"] for u in informative}), sorted({u["block"] for u in informative})
    files = audit["file_audit"]
    files_complete = len(files) == 10 and all(v.get("exists") and not v.get("missing_columns") for v in files.values())
    timezone_ok = files_complete and all(v.get("source_timezone") in {"UTC", "UTC+00:00", "Etc/UTC"} for v in files.values())
    duplicates_ok = files_complete and all(v.get("duplicates") == 0 for v in files.values())
    blocks_ok = len(audit["block_audit"]) == 5 and all(v.get("valid") and v.get("duplicates") == 0 for v in audit["block_audit"])
    anchors_ok = bool(informative) and all(v["anchors_hh00"] and v["non_overlapping"] for v in informative)
    embargo_ok = bool(informative) and all(v["embargo_valid"] for v in informative)
    sample_ok = len(pairs) >= MIN_PAIRS and len(block_ids) >= MIN_BLOCKS and len(informative) >= 40
    integrity = bool(
        PROTOCOL_FILE.exists() and len(audit["windows"]) == 5 and files_complete and timezone_ok
        and duplicates_ok and blocks_ok and anchors_ok and embargo_ok and sample_ok
    )
    audit.update(
        {
            "unit_audit": unit_audit, "discarded": dict(discarded),
            "informative_units": len(informative), "informative_pairs": pairs,
            "informative_blocks": block_ids, "checks": {
                "files_complete": files_complete, "timezone_utc": timezone_ok,
                "duplicate_free": duplicates_ok, "five_blocks_synchronized": blocks_ok,
                "hh00_non_overlapping": anchors_ok, "lookahead_absent": True,
                "labels_within_blocks": True, "embargo_valid": embargo_ok,
                "complete_week_sample_sufficient": sample_ok, "integrity_sufficient": integrity,
            }, "development_consumed": True, "holdout": "internal OOS only",
        }
    )
    return samples, audit


def _prepare_states(samples: Any) -> tuple[dict[tuple[str, int], dict[str, Any]], list[dict[str, Any]]]:
    states, failures = {}, []
    if samples.empty:
        return states, failures
    for (pair, block), unit in samples.groupby(["pair", "block"], sort=True):
        train = unit[unit["segment"] == "train"].sort_values("date").reset_index(drop=True)
        evaluation = unit[unit["segment"] == "evaluation"].sort_values("date").reset_index(drop=True)
        bootstrap_eval = evaluation[evaluation["bootstrap_eligible"]].copy().reset_index(drop=True)
        try:
            return_baseline = _fit_ols(train, "y_return", RETURN_BASE)
            risk_baseline = _fit_ols(train, "y_risk", RISK_BASE)
            models, predictions = {}, {
                "return_actual": evaluation["y_return"].to_numpy(),
                "risk_actual": evaluation["y_risk"].to_numpy(),
                "return_baseline": _predict(evaluation, return_baseline),
                "risk_baseline": _predict(evaluation, risk_baseline),
            }
            for contrast in CONTRASTS:
                for outcome, target, base in (
                    ("return", "y_return", RETURN_BASE), ("risk", "y_risk", RISK_BASE)
                ):
                    real_train = train.copy(); real_train["label"] = real_train[contrast]
                    real_eval = evaluation.copy(); real_eval["label"] = real_eval[contrast]
                    model = _fit_ols(real_train, target, [*base, "label"])
                    models[f"{contrast}__{outcome}__real"] = model
                    predictions[f"{contrast}__{outcome}__real"] = _predict(real_eval, model)
                    for control in CONTROLS:
                        column = f"{contrast}__{control}"
                        control_train = train.copy(); control_train["label"] = control_train[column]
                        control_eval = evaluation.copy(); control_eval["label"] = control_eval[column]
                        control_model = _fit_ols(control_train, target, [*base, "label"])
                        models[f"{contrast}__{outcome}__{control}"] = control_model
                        predictions[f"{contrast}__{outcome}__{control}"] = _predict(control_eval, control_model)
            prepared = evaluation.copy()
            for column, values in predictions.items():
                prepared[column] = values
            bootstrap_prepared = prepared[prepared["bootstrap_eligible"]].copy().reset_index(drop=True)
            states[(pair, int(block))] = {
                "pair": pair, "block": int(block), "train": train,
                "evaluation": prepared, "bootstrap_evaluation": bootstrap_prepared,
                "models": models, "return_baseline_model": return_baseline,
                "risk_baseline_model": risk_baseline,
            }
        except ValueError as exc:
            failures.append({"pair": pair, "block": int(block), "reason": str(exc)})
    return states, failures


def _evaluate_contrast(state: dict[str, Any], contrast: str, frame: Any | None = None, diagnostics: bool = True) -> dict[str, Any]:
    import numpy as np

    data = state["evaluation"] if frame is None else frame
    return_actual = data["return_actual"].to_numpy(dtype=float)
    result = {
        "pair": state["pair"], "block": state["block"], "contrast": contrast,
        "train_events": len(state["train"]), "evaluation_events": len(data),
    }
    label = data[contrast].to_numpy(dtype=bool)
    for outcome, target, base in (
        ("return", "y_return", RETURN_BASE), ("risk", "y_risk", RISK_BASE)
    ):
        actual = data[f"{outcome}_actual"].to_numpy(dtype=float)
        baseline = data[f"{outcome}_baseline"].to_numpy(dtype=float)
        real = data[f"{contrast}__{outcome}__real"].to_numpy(dtype=float)
        base_loss, real_loss = _losses(actual, baseline), _losses(actual, real)
        beta = _beta(state["models"][f"{contrast}__{outcome}__real"])
        result.update(
            {
                f"{outcome}_beta": beta["beta"], f"{outcome}_beta_se": beta["se"],
                f"{outcome}_beta_p_one": beta["p_one_sided_positive"],
                f"{outcome}_beta_ci_low": beta["ci95"][0], f"{outcome}_beta_ci_high": beta["ci95"][1],
                f"{outcome}_partial_corr": (
                    _partial_corr(data.assign(label=data[contrast]), target, base, "label") if diagnostics else None
                ),
                f"{outcome}_mse_baseline": base_loss["mse"], f"{outcome}_mse_full": real_loss["mse"],
                f"{outcome}_mae_baseline": base_loss["mae"], f"{outcome}_mae_full": real_loss["mae"],
                f"{outcome}_mse_improvement": _improvement(base_loss["mse"], real_loss["mse"]),
                f"{outcome}_mae_improvement": _improvement(base_loss["mae"], real_loss["mae"]),
                f"{outcome}_r2_incremental": (
                    None if not diagnostics else (_r2(actual, real) or 0) - (_r2(actual, baseline) or 0)
                ),
            }
        )
        for control in CONTROLS:
            prediction = data[f"{contrast}__{outcome}__{control}"].to_numpy(dtype=float)
            control_loss = _losses(actual, prediction)
            result[f"{outcome}_{control}_mse_superiority"] = _improvement(control_loss["mse"], real_loss["mse"])
    conditional, complement = return_actual[label], return_actual[~label]
    result.update(
        {
            "return_conditional_count": int(label.sum()), "return_complement_count": int((~label).sum()),
            "return_gross_mean": float(np.mean(conditional)) if len(conditional) else None,
            "return_gross_median": float(np.median(conditional)) if len(conditional) else None,
            "return_complement_mean": float(np.mean(complement)) if len(complement) else None,
            "return_complement_median": float(np.median(complement)) if len(complement) else None,
            "return_effect": (
                float(np.mean(conditional) - np.mean(complement)) if len(conditional) and len(complement) else None
            ),
            "return_net_mean_fee_only": float(np.mean(conditional) - FEE_ONLY_COST) if len(conditional) else None,
            "return_net_median_fee_only": float(np.median(conditional) - FEE_ONLY_COST) if len(conditional) else None,
            "return_net_mean_conservative": float(np.mean(conditional) - CONSERVATIVE_COST) if len(conditional) else None,
            "return_net_median_conservative": float(np.median(conditional) - CONSERVATIVE_COST) if len(conditional) else None,
        }
    )
    return result


FIELDS = [
    "return_beta", "return_beta_se", "return_beta_p_one", "return_beta_ci_low", "return_beta_ci_high",
    "return_partial_corr", "return_mse_baseline", "return_mse_full", "return_mae_baseline", "return_mae_full",
    "return_mse_improvement", "return_mae_improvement", "return_r2_incremental",
    "return_gross_mean", "return_gross_median", "return_complement_mean", "return_complement_median",
    "return_effect", "return_net_mean_fee_only", "return_net_median_fee_only",
    "return_net_mean_conservative", "return_net_median_conservative",
    "return_conditional_count", "return_complement_count",
    "risk_beta", "risk_beta_se", "risk_beta_p_one", "risk_beta_ci_low", "risk_beta_ci_high",
    "risk_partial_corr", "risk_mse_baseline", "risk_mse_full", "risk_mae_baseline", "risk_mae_full",
    "risk_mse_improvement", "risk_mae_improvement", "risk_r2_incremental",
]
for _outcome in ("return", "risk"):
    for _control in CONTROLS:
        FIELDS.append(f"{_outcome}_{_control}_mse_superiority")


def _aggregate(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    result = {
        "units": len(metrics), "train_events": sum(m.get("train_events", 0) for m in metrics),
        "evaluation_events": sum(m.get("evaluation_events", 0) for m in metrics),
    }
    result.update({field: _mean([m.get(field) for m in metrics]) for field in FIELDS})
    for outcome in ("return", "risk"):
        se_values = [m[f"{outcome}_beta_se"] for m in metrics if _finite(m.get(f"{outcome}_beta_se"))]
        se = math.sqrt(sum(value * value for value in se_values)) / len(se_values) if se_values else None
        beta = result.get(f"{outcome}_beta")
        result[f"{outcome}_beta_aggregate_se"] = se
        result[f"{outcome}_beta_aggregate_ci95"] = (
            [beta - 1.959963984540054 * se, beta + 1.959963984540054 * se]
            if beta is not None and se is not None else [None, None]
        )
        z = beta / se if beta is not None and se and se > 0 else None
        result[f"{outcome}_beta_aggregate_p_one"] = 1 - NormalDist().cdf(z) if z is not None else None
    return result


def _estimate(states: dict[tuple[str, int], dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    estimates, matrix = {}, []
    for contrast in CONTRASTS:
        units = [_evaluate_contrast(state, contrast) for state in states.values()]
        overall = _aggregate(units)
        by_pair, by_block = {}, {}
        for pair in common.ALL_PAIRS:
            values = [m for m in units if m["pair"] == pair]
            if values: by_pair[pair] = _aggregate(values)
        for block in sorted({m["block"] for m in units}):
            values = [m for m in units if m["block"] == block]
            if values: by_block[str(block)] = _aggregate(values)
        estimates[contrast] = {"overall": overall, "by_pair": by_pair, "by_block": by_block}
        matrix.append({"level": "overall", "contrast": contrast, "pair": None, "block": None, **overall})
        matrix.extend({"level": "pair", "contrast": contrast, "pair": pair, "block": None, **value} for pair, value in by_pair.items())
        matrix.extend({"level": "block", "contrast": contrast, "pair": None, "block": block, **value} for block, value in by_block.items())
        matrix.extend({"level": "unit", **value} for value in units)
    return estimates, matrix


BOOT_FIELDS_P1 = [
    "return_net_mean_conservative", "return_effect", "return_mse_improvement", "return_mae_improvement",
    *[f"return_{control}_mse_superiority" for control in CONTROLS],
]
BOOT_FIELDS_P2 = [
    "risk_mse_improvement", "risk_mae_improvement",
    *[f"risk_{control}_mse_superiority" for control in CONTROLS],
]
BOOT_FIELDS = [*BOOT_FIELDS_P1, *BOOT_FIELDS_P2]


def _resample_weeks(frame: Any, rng: Any) -> Any:
    import pandas as pd

    weeks = list(frame["week"].drop_duplicates())
    selected = rng.choice(weeks, size=len(weeks), replace=True)
    return pd.concat([frame[frame["week"] == week] for week in selected], ignore_index=True)


def _bootstrap(states: dict[tuple[str, int], dict[str, Any]], estimates: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    import numpy as np

    rng = np.random.default_rng(SEED)
    rows = []
    for replicate in range(BOOTSTRAP_REPS):
        per_contrast = {contrast: [] for contrast in CONTRASTS}
        for state in states.values():
            sampled = _resample_weeks(state["bootstrap_evaluation"], rng)
            for contrast in CONTRASTS:
                per_contrast[contrast].append(_evaluate_contrast(state, contrast, sampled, diagnostics=False))
        for contrast in CONTRASTS:
            aggregate = _aggregate(per_contrast[contrast])
            rows.append({"replicate": replicate, "contrast": contrast, **{f: aggregate.get(f) for f in BOOT_FIELDS}})

    by_contrast = {}
    p1_family, p2_family = {}, {}
    for contrast in CONTRASTS:
        contrast_rows = [row for row in rows if row["contrast"] == contrast]
        summary = {
            "ci95": {field: _ci([row.get(field) for row in contrast_rows]) for field in BOOT_FIELDS},
            "p_raw": {field: _normal_positive_p([row.get(field) for row in contrast_rows]) for field in BOOT_FIELDS},
        }
        by_contrast[contrast] = summary
        for field in BOOT_FIELDS_P1:
            p1_family[f"{contrast}::{field}"] = summary["p_raw"][field]
        p1_family[f"{contrast}::return_beta"] = estimates[contrast]["overall"]["return_beta_aggregate_p_one"]
        for field in BOOT_FIELDS_P2:
            p2_family[f"{contrast}::{field}"] = summary["p_raw"][field]
        p2_family[f"{contrast}::risk_beta"] = estimates[contrast]["overall"]["risk_beta_aggregate_p_one"]
    p1_holm, p2_holm = common.holm_adjust(p1_family), common.holm_adjust(p2_family)
    for contrast in CONTRASTS:
        by_contrast[contrast]["p_holm_p1"] = {
            key.split("::", 1)[1]: value for key, value in p1_holm.items() if key.startswith(contrast + "::")
        }
        by_contrast[contrast]["p_holm_p2"] = {
            key.split("::", 1)[1]: value for key, value in p2_holm.items() if key.startswith(contrast + "::")
        }
    return {
        "replicates": BOOTSTRAP_REPS, "seed": SEED,
        "resampling": "complete UTC weeks within pair/block evaluation",
        "by_contrast": by_contrast, "p1_family_size": len(p1_family), "p2_family_size": len(p2_family),
    }, rows


def _shares(buckets: dict[str, defaultdict[str, float]], total: float) -> dict[str, Any]:
    result = {}
    for dimension, values in buckets.items():
        shares = {key: value / total if total > 0 else None for key, value in sorted(values.items())}
        finite = {key: value for key, value in shares.items() if _finite(value)}
        key = max(finite, key=finite.get) if finite else None
        result[dimension] = {"shares": shares, "maximum_key": key, "maximum_share": finite.get(key) if key else None}
    return result


def _concentration(states: dict[tuple[str, int], dict[str, Any]]) -> dict[str, Any]:
    import numpy as np

    output = {}
    for contrast in CONTRASTS:
        metrics = {}
        for kind in ("return_mse", "return_net", "risk_mse"):
            buckets = {"pair": defaultdict(float), "block": defaultdict(float), "week": defaultdict(float)}
            total = 0.0
            for (pair, block), state in states.items():
                frame = state["evaluation"]
                if kind.endswith("mse"):
                    outcome = "return" if kind == "return_mse" else "risk"
                    actual = frame[f"{outcome}_actual"].to_numpy()
                    baseline = frame[f"{outcome}_baseline"].to_numpy()
                    full = frame[f"{contrast}__{outcome}__real"].to_numpy()
                    values = np.maximum((actual - baseline) ** 2 - (actual - full) ** 2, 0) / len(frame)
                else:
                    label = frame[contrast].to_numpy(dtype=bool)
                    values = np.where(label, np.maximum(frame["y_return"].to_numpy() - CONSERVATIVE_COST, 0), 0)
                    values = values / max(1, int(label.sum()))
                for index, value in enumerate(values):
                    if value <= 0: continue
                    week = str(frame["week"].iloc[index].date())
                    buckets["pair"][pair] += float(value); buckets["block"][str(block)] += float(value)
                    buckets["week"][week] += float(value); total += float(value)
            metrics[kind] = {"total": total, **_shares(buckets, total)}
        output[contrast] = metrics
    return output


def _positive_counts(item: dict[str, Any]) -> tuple[int, int]:
    def passes(value: dict[str, Any]) -> bool:
        return (
            value.get("return_net_mean_conservative", -1) > 0
            and value.get("return_mse_improvement", -1) > 0
            and value.get("return_mae_improvement", -1) > 0
        )
    return sum(passes(v) for v in item["by_pair"].values()), sum(passes(v) for v in item["by_block"].values())


def _contrast_decision(contrast: str, estimates: dict[str, Any], boot: dict[str, Any], concentration: dict[str, Any]) -> dict[str, Any]:
    overall, stats = estimates[contrast]["overall"], boot["by_contrast"][contrast]
    pairs, blocks = _positive_counts(estimates[contrast])
    p1 = stats["p_holm_p1"]
    controls = [f"return_{control}_mse_superiority" for control in CONTROLS]
    concentration_pass = all(
        concentration[contrast][kind][dimension]["maximum_share"] is not None
        and concentration[contrast][kind][dimension]["maximum_share"] <= 0.30
        for kind in ("return_mse", "return_net") for dimension in ("pair", "block", "week")
    )
    gates = {
        "net_mean_and_median_positive": overall["return_net_mean_conservative"] > 0 and overall["return_net_median_conservative"] > 0,
        "net_mean_ci95_and_holm": _ci_positive(stats["ci95"]["return_net_mean_conservative"]) and p1["return_net_mean_conservative"] < ALPHA,
        "effect_positive_ci95_holm": overall["return_effect"] > 0 and _ci_positive(stats["ci95"]["return_effect"]) and p1["return_effect"] < ALPHA,
        "beta_positive_ci95_holm": overall["return_beta"] > 0 and _ci_positive(overall["return_beta_aggregate_ci95"]) and p1["return_beta"] < ALPHA,
        "mse_at_least_5pct_ci95_holm": overall["return_mse_improvement"] >= MATERIAL_GAIN and _ci_positive(stats["ci95"]["return_mse_improvement"]) and p1["return_mse_improvement"] < ALPHA,
        "mae_at_least_5pct_ci95_holm": overall["return_mae_improvement"] >= MATERIAL_GAIN and _ci_positive(stats["ci95"]["return_mae_improvement"]) and p1["return_mae_improvement"] < ALPHA,
        "seven_pairs_four_blocks": pairs >= 7 and blocks >= 4,
        "all_placebos_survived_holm": all(_ci_positive(stats["ci95"][field]) and p1[field] < ALPHA for field in controls),
        "concentration_at_most_30pct": concentration_pass,
    }
    return {"passes": all(gates.values()), "positive_pairs": pairs, "positive_blocks": blocks, "gates": gates}


def _decide(estimates: dict[str, Any], boot: dict[str, Any], concentration: dict[str, Any], audit: dict[str, Any]) -> dict[str, Any]:
    contrast_results = {
        contrast: _contrast_decision(contrast, estimates, boot, concentration) for contrast in CONTRASTS
    }
    passing = [contrast for contrast, result in contrast_results.items() if result["passes"]]
    if not audit["checks"]["integrity_sufficient"]:
        decision, reason = DECISION_INCONCLUSIVE, "Data, complete-week sample, or integrity prevented the frozen test."
    elif passing:
        decision, reason = DECISION_CONFIRMED, "At least one fixed contrast passed every P1 gate without post-hoc selection."
    else:
        decision, reason = DECISION_REJECTED, "No fixed contrast passed every pre-registered P1 gate on valid data."
    return {
        "decision": decision, "reason": reason, "passing_contrasts": passing,
        "contrast_results": contrast_results, "integrity_sufficient": audit["checks"]["integrity_sufficient"],
        "operational_experiment_justified": decision == DECISION_CONFIRMED,
    }


def _render(report: dict[str, Any]) -> str:
    lines = [
        "# PH4-A11 - Calendar Seasonality", "", f"Generated: `{report['generated_at']}`", "",
        f"**Decision:** {report['decision']['decision']}", "", report["decision"]["reason"], "",
        "## Frozen protocol", "", "- Eleven fixed contrasts; hourly HH:00 UTC observations; one 60-minute horizon.",
        "- Conservative round-trip cost 0.30%; 60/40 chronological split and 12-candle embargo.",
        "- 1,000 complete-UTC-week bootstrap replicates; no label selection or ranking.", "",
        "## Contrasts", "",
    ]
    for contrast in CONTRASTS:
        overall = report["estimates"][contrast]["overall"]
        stats = report["bootstrap"]["by_contrast"][contrast]
        result = report["decision"]["contrast_results"][contrast]
        lines.extend(
            [
                f"### {contrast}", "",
                f"- Net mean/median 0.30%: `{overall['return_net_mean_conservative']}` / `{overall['return_net_median_conservative']}`; mean CI95 `{stats['ci95']['return_net_mean_conservative']}`",
                f"- Return beta/effect: `{overall['return_beta']}` / `{overall['return_effect']}`",
                f"- Return MSE/MAE improvement: `{overall['return_mse_improvement']}` / `{overall['return_mae_improvement']}`",
                f"- Positive pairs/blocks: `{result['positive_pairs']}/10`, `{result['positive_blocks']}/5`",
                f"- P1 Holm: `{stats['p_holm_p1']}`",
                f"- Risk beta, MSE, MAE: `{overall['risk_beta']}`, `{overall['risk_mse_improvement']}`, `{overall['risk_mae_improvement']}`",
                f"- P2 Holm: `{stats['p_holm_p2']}`", f"- Passes all P1 gates: `{result['passes']}`", "",
            ]
        )
    lines.extend(
        [
            "## Integrity", "", f"- Integrity sufficient: `{report['decision']['integrity_sufficient']}`",
            f"- Informative units: `{report['audit']['informative_units']}`",
            f"- Protocol SHA-256: `{report['audit']['protocol_sha256']}`",
            f"- Operational experiment justified: `{report['decision']['operational_experiment_justified']}`", "",
        ]
    )
    return "\n".join(lines)


def run_analysis() -> int:
    samples, audit = _build_samples()
    states, failures = _prepare_states(samples)
    audit["preparation_failures"] = failures
    if len(states) < 40:
        audit["checks"]["integrity_sufficient"] = False
    if states:
        estimates, matrix = _estimate(states)
        bootstrap, bootstrap_rows = _bootstrap(states, estimates)
        concentration = _concentration(states)
    else:
        estimates, matrix, bootstrap_rows, concentration = {}, [], [], {}
        bootstrap = {"replicates": 0, "seed": SEED, "by_contrast": {}, "p1_family_size": 0, "p2_family_size": 0}
    decision = _decide(estimates, bootstrap, concentration, audit) if states else {
        "decision": DECISION_INCONCLUSIVE, "reason": "No estimable pair/block units.",
        "passing_contrasts": [], "contrast_results": {}, "integrity_sufficient": False,
        "operational_experiment_justified": False,
    }
    report = {
        "study": "PH4-A11", "generated_at": datetime.now(timezone.utc).isoformat(),
        "protocol": {"file": str(PROTOCOL_FILE), "sha256": audit.get("protocol_sha256")},
        "mechanics": {
            "contrasts": CONTRASTS, "horizon_candles": HORIZON, "train_fraction": TRAIN_FRACTION,
            "embargo_candles": HORIZON, "fee_only_cost": FEE_ONLY_COST,
            "conservative_cost": CONSERVATIVE_COST, "bootstrap_replicates": BOOTSTRAP_REPS,
            "seed": SEED, "p1_holm_family_size": 88, "p2_holm_family_size": 66,
        },
        "audit": audit, "estimates": estimates, "bootstrap": bootstrap,
        "concentration": concentration, "decision": decision,
        "scope": "offline long-only return and risk audit; no strategy or causal claim",
    }
    markdown = _render(report)
    html_text = (
        "<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
        "<title>PH4-A11</title><style>body{font:15px/1.5 system-ui;max-width:1100px;margin:32px auto;padding:0 20px}"
        "pre{white-space:pre-wrap;background:#f6f8fa;border:1px solid #d0d7de;padding:24px}</style></head><body><pre>"
        + html.escape(markdown) + "</pre></body></html>"
    )
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    common.atomic_write_json(REPORT_JSON, report); common.atomic_write_text(REPORT_MD, markdown)
    common.atomic_write_text(REPORT_HTML, html_text)
    matrix_fields = ["level", "contrast", "pair", "block", "units", "train_events", "evaluation_events", *FIELDS]
    common.atomic_write_csv(MATRIX_CSV, matrix, matrix_fields)
    common.atomic_write_csv(BOOTSTRAP_CSV, bootstrap_rows, ["replicate", "contrast", *BOOT_FIELDS])
    print(decision["decision"])
    for path in (REPORT_MD, REPORT_HTML, REPORT_JSON, MATRIX_CSV, BOOTSTRAP_CSV): print(path)
    return 0


def main() -> int:
    args = parse_args()
    return run_analysis() if args.command == "analyze" else 2


if __name__ == "__main__":
    raise SystemExit(main())
