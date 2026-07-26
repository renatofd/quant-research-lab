"""PH4-A01 BTC lead-lag offline research.

This module is intentionally isolated from strategy, backtest, Hyperopt and
operational code. Importing it or asking for --help does not read OHLCV data.
The `analyze` subcommand performs the offline scientific audit described in
PHASE4_FIRST_EXPERIMENT.md when explicitly executed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from statistics import NormalDist
from typing import Any


LAB_DIR = Path(__file__).resolve().parent
USER_DATA_DIR = LAB_DIR.parent
PROJECT_ROOT = USER_DATA_DIR.parent
DATA_DIR = USER_DATA_DIR / "data" / "binance"
WINDOWS_FILE = LAB_DIR / "ph3_c03r_windows.json"

REPORT_JSON = LAB_DIR / "btc_leadership_report.json"
REPORT_MD = LAB_DIR / "btc_leadership_report.md"
REPORT_HTML = LAB_DIR / "btc_leadership_report.html"
MATRIX_CSV = LAB_DIR / "btc_leadership_matrix.csv"
BOOTSTRAP_CSV = LAB_DIR / "btc_leadership_bootstrap.csv"

BTC_PAIR = "BTC/USDT"
ALT_PAIRS = [
    "ETH/USDT",
    "SOL/USDT",
    "BNB/USDT",
    "XRP/USDT",
    "ADA/USDT",
    "DOGE/USDT",
    "LINK/USDT",
    "AVAX/USDT",
    "LTC/USDT",
]
ALL_PAIRS = [BTC_PAIR, *ALT_PAIRS]
PSEUDO_LEADERS = [
    "ETH/USDT",
    "XRP/USDT",
    "SOL/USDT",
    "DOGE/USDT",
    "LINK/USDT",
    "LTC/USDT",
    "ADA/USDT",
    "AVAX/USDT",
]

FEE_PER_SIDE = 0.001
SLIPPAGE_PER_SIDE = 0.0005
COST_SCENARIOS = {
    "fee_only": 2 * FEE_PER_SIDE,
    "fee_plus_5bps_per_side": 2 * (FEE_PER_SIDE + SLIPPAGE_PER_SIDE),
}
DECISION_COST_SCENARIO = "fee_plus_5bps_per_side"

BOOTSTRAP_REPS = 1000
RANDOM_SEED = 2026071301
CIRCULAR_SHIFT_RULE = "floor(n / 2), minimum 1, within each block"
ALPHA = 0.05


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "PH4-A01 offline BTC lead-lag research. The analyze subcommand "
            "reads existing 5m Feather OHLCV and writes report artifacts. "
            "No strategy, backtest or trading execution is created."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "analyze",
        help="Run the pre-registered offline BTC lead-lag audit.",
        description=(
            "Run PH4-A01 exactly as specified: one 5m lag, BTC as leader, "
            "nine altcoins as response, no threshold/grid/hyperopt."
        ),
    )
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def pair_to_filename(pair: str) -> str:
    return f"{pair.replace('/', '_')}-5m.feather"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def finite_or_none(value: Any) -> Any:
    try:
        import numpy as np
    except Exception:  # pragma: no cover - help/import path does not need numpy.
        np = None

    if np is not None:
        if isinstance(value, np.integer):
            return int(value)
        if isinstance(value, np.floating):
            value = float(value)
        if isinstance(value, np.bool_):
            return bool(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def sanitize_json(value: Any) -> Any:
    value = finite_or_none(value)
    if isinstance(value, dict):
        return {str(k): sanitize_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_json(v) for v in value]
    return value


def atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(sanitize_json(payload), ensure_ascii=False, indent=2))


def atomic_write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: finite_or_none(row.get(key)) for key in fieldnames})
    os.replace(tmp, path)


def normal_cdf(x: float) -> float:
    return NormalDist().cdf(x)


def betacf(a: float, b: float, x: float) -> float:
    max_iter = 200
    eps = 3.0e-12
    fpmin = 1.0e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def regularized_beta(a: float, b: float, x: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_bt = (
        math.lgamma(a + b)
        - math.lgamma(a)
        - math.lgamma(b)
        + a * math.log(x)
        + b * math.log(1.0 - x)
    )
    bt = math.exp(log_bt)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * betacf(a, b, x) / a
    return 1.0 - bt * betacf(b, a, 1.0 - x) / b


def student_t_cdf(t_value: float, df: int) -> float:
    if df <= 0:
        return normal_cdf(t_value)
    x = df / (df + t_value * t_value)
    ib = regularized_beta(df / 2.0, 0.5, x)
    if t_value >= 0:
        return 1.0 - 0.5 * ib
    return 0.5 * ib


def two_sided_t_pvalue(t_value: float, df: int) -> float | None:
    if not math.isfinite(t_value):
        return None
    tail = 1.0 - student_t_cdf(abs(t_value), df)
    return max(0.0, min(1.0, 2.0 * tail))


def one_sided_positive_pvalue_from_bootstrap(values: list[float]) -> float | None:
    finite = [v for v in values if v is not None and math.isfinite(v)]
    if not finite:
        return None
    return (sum(1 for v in finite if v <= 0.0) + 1.0) / (len(finite) + 1.0)


def quantile(values: list[float], q: float) -> float | None:
    import numpy as np

    finite = [v for v in values if v is not None and math.isfinite(v)]
    if not finite:
        return None
    return float(np.quantile(np.asarray(finite, dtype=float), q))


def ci95(values: list[float]) -> list[float | None]:
    return [quantile(values, 0.025), quantile(values, 0.975)]


def mean(values: list[float]) -> float | None:
    finite = [v for v in values if v is not None and math.isfinite(v)]
    if not finite:
        return None
    return sum(finite) / len(finite)


def median(values: list[float]) -> float | None:
    import numpy as np

    finite = [v for v in values if v is not None and math.isfinite(v)]
    if not finite:
        return None
    return float(np.median(np.asarray(finite, dtype=float)))


def holm_adjust(pvalues: dict[str, float | None]) -> dict[str, float | None]:
    valid = sorted(
        [(key, value) for key, value in pvalues.items() if value is not None],
        key=lambda item: item[1],
    )
    adjusted = {key: None for key in pvalues}
    prev = 0.0
    total = len(valid)
    for rank, (key, pvalue) in enumerate(valid, start=1):
        value = min(1.0, pvalue * (total - rank + 1))
        value = max(prev, value)
        adjusted[key] = value
        prev = value
    return adjusted


def evidence_label(effect: float | None, ci: list[float | None], all_gates: bool) -> str:
    if effect is None or effect <= 0:
        return "Rejected"
    if ci[0] is None or ci[0] <= 0:
        return "Weak"
    if all_gates:
        return "Strong evidence"
    return "Moderate"


def ols_fit(y_values: Any, x_values: Any, predictor_names: list[str]) -> dict[str, Any]:
    import numpy as np

    y = np.asarray(y_values, dtype=float)
    x = np.asarray(x_values, dtype=float)
    if x.ndim == 1:
        x = x.reshape(-1, 1)
    mask = np.isfinite(y) & np.isfinite(x).all(axis=1)
    y = y[mask]
    x = x[mask]
    n = int(len(y))
    if n == 0:
        return {"n": 0, "error": "no finite observations"}
    design = np.column_stack([np.ones(n), x])
    names = ["intercept", *predictor_names]
    k = design.shape[1]
    if n <= k:
        return {"n": n, "error": "insufficient observations for OLS"}
    beta, *_ = np.linalg.lstsq(design, y, rcond=None)
    fitted = design @ beta
    residuals = y - fitted
    sse = float(np.sum(residuals * residuals))
    centered = y - float(np.mean(y))
    sst = float(np.sum(centered * centered))
    df = n - k
    sigma2 = sse / df if df > 0 else float("nan")
    xtx_inv = np.linalg.pinv(design.T @ design)
    covariance = sigma2 * xtx_inv
    standard_errors = np.sqrt(np.maximum(np.diag(covariance), 0.0))
    coefficients: dict[str, dict[str, float | None]] = {}
    for idx, name in enumerate(names):
        se = float(standard_errors[idx])
        coef = float(beta[idx])
        t_stat = coef / se if se > 0 else float("nan")
        pvalue = two_sided_t_pvalue(t_stat, df)
        ci_low = coef - 1.96 * se
        ci_high = coef + 1.96 * se
        coefficients[name] = {
            "beta": coef,
            "se": se,
            "t_stat": t_stat,
            "p_value": pvalue,
            "ci95": [ci_low, ci_high],
        }
    r2 = None if sst <= 0 else 1.0 - sse / sst
    return {
        "n": n,
        "df": df,
        "r2": r2,
        "sse": sse,
        "coefficients": coefficients,
    }


def simple_corr(a_values: Any, b_values: Any) -> float | None:
    import numpy as np

    a = np.asarray(a_values, dtype=float)
    b = np.asarray(b_values, dtype=float)
    mask = np.isfinite(a) & np.isfinite(b)
    a = a[mask]
    b = b[mask]
    if len(a) < 3 or float(np.std(a)) == 0.0 or float(np.std(b)) == 0.0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def residualize(values: Any, controls: Any) -> Any:
    import numpy as np

    y = np.asarray(values, dtype=float)
    x = np.asarray(controls, dtype=float)
    if x.ndim == 1:
        x = x.reshape(-1, 1)
    design = np.column_stack([np.ones(len(y)), x])
    beta, *_ = np.linalg.lstsq(design, y, rcond=None)
    return y - design @ beta


def partial_corr(y_values: Any, x_values: Any, controls: Any) -> float | None:
    import numpy as np

    y = np.asarray(y_values, dtype=float)
    x = np.asarray(x_values, dtype=float)
    c = np.asarray(controls, dtype=float)
    if c.ndim == 1:
        c = c.reshape(-1, 1)
    mask = np.isfinite(y) & np.isfinite(x) & np.isfinite(c).all(axis=1)
    if int(mask.sum()) < c.shape[1] + 4:
        return None
    y_resid = residualize(y[mask], c[mask])
    x_resid = residualize(x[mask], c[mask])
    return simple_corr(y_resid, x_resid)


def add_regression_metrics(frame: Any, y_col: str, x_col: str, control_cols: list[str]) -> dict[str, Any]:
    import numpy as np

    cols = [x_col, *control_cols]
    full = ols_fit(frame[y_col].to_numpy(), frame[cols].to_numpy(), cols)
    baseline = ols_fit(frame[y_col].to_numpy(), frame[control_cols].to_numpy(), control_cols)
    x_coef = full.get("coefficients", {}).get(x_col, {})
    full_r2 = full.get("r2")
    baseline_r2 = baseline.get("r2")
    incremental_r2 = (
        None
        if full_r2 is None or baseline_r2 is None
        else float(max(-1.0, full_r2 - baseline_r2))
    )
    return {
        "n": full.get("n"),
        "simple_correlation": simple_corr(frame[x_col].to_numpy(), frame[y_col].to_numpy()),
        "partial_correlation": partial_corr(
            frame[y_col].to_numpy(),
            frame[x_col].to_numpy(),
            frame[control_cols].to_numpy(),
        ),
        "regression": full,
        "baseline_regression": baseline,
        "beta": x_coef.get("beta"),
        "se": x_coef.get("se"),
        "p_value": x_coef.get("p_value"),
        "ci95": x_coef.get("ci95"),
        "r2_full": full_r2,
        "r2_baseline": baseline_r2,
        "r2_incremental": incremental_r2,
    }


def economic_contrast(frame: Any, response_col: str, signal_col: str) -> dict[str, Any]:
    import numpy as np

    response = frame[response_col].to_numpy(dtype=float)
    signal = frame[signal_col].to_numpy(dtype=float) > 0
    result: dict[str, Any] = {
        "n_total": int(len(response)),
        "n_signal_positive": int(signal.sum()),
        "gross": {
            "conditional_mean": float(np.mean(response[signal])) if signal.any() else None,
            "conditional_median": float(np.median(response[signal])) if signal.any() else None,
            "unconditional_mean": float(np.mean(response)) if len(response) else None,
            "unconditional_median": float(np.median(response)) if len(response) else None,
        },
    }
    for scenario, cost in COST_SCENARIOS.items():
        net = response - cost
        conditional = net[signal]
        result[scenario] = {
            "round_trip_cost": cost,
            "conditional_mean_net": float(np.mean(conditional)) if signal.any() else None,
            "conditional_median_net": float(np.median(conditional)) if signal.any() else None,
            "unconditional_mean_net": float(np.mean(net)) if len(net) else None,
            "unconditional_median_net": float(np.median(net)) if len(net) else None,
            "effect_conditional_minus_unconditional": (
                float(np.mean(conditional) - np.mean(net)) if signal.any() and len(net) else None
            ),
            "hit_rate_net": float(np.mean(conditional > 0)) if signal.any() else None,
        }
    return result


def return_column(pair: str, suffix: str) -> str:
    if pair == BTC_PAIR:
        return f"btc_ret_{suffix}"
    return f"{pair}_ret_{suffix}"


def metric_from_regression(metrics: dict[str, Any], name: str) -> float | None:
    value = metrics.get(name)
    return None if value is None else float(value)


def metric_from_economic(economic: dict[str, Any], name: str) -> float | None:
    scenario = economic.get(DECISION_COST_SCENARIO, {})
    value = scenario.get(name)
    return None if value is None else float(value)


def equal_weighted_block_summary(block_metrics: list[dict[str, Any]]) -> dict[str, Any]:
    betas = [metric_from_regression(block, "beta") for block in block_metrics]
    econ_effects = [
        metric_from_economic(block.get("economic_contrast", {}), "effect_conditional_minus_unconditional")
        for block in block_metrics
    ]
    means = [
        metric_from_economic(block.get("economic_contrast", {}), "conditional_mean_net")
        for block in block_metrics
    ]
    medians = [
        metric_from_economic(block.get("economic_contrast", {}), "conditional_median_net")
        for block in block_metrics
    ]
    hit_rates = [
        metric_from_economic(block.get("economic_contrast", {}), "hit_rate_net")
        for block in block_metrics
    ]
    return {
        "n_blocks": len(block_metrics),
        "beta": mean(betas),
        "economic_effect_net": mean(econ_effects),
        "conditional_mean_net": mean(means),
        "conditional_median_net": mean(medians),
        "hit_rate_net": mean(hit_rates),
        "aggregation": "equal-weighted mean of per-block estimates; pooled values are descriptive only.",
    }


def integrity_checks(samples: Any, audit: dict[str, Any], expected_blocks: int) -> dict[str, Any]:
    import pandas as pd

    file_checks = []
    for pair, entry in audit["file_audit"].items():
        timezone_ok = entry.get("timezone") == "UTC"
        file_checks.append(
            {
                "pair": pair,
                "file_present": bool(entry.get("path")),
                "timezone_utc": timezone_ok,
                "duplicate_timestamps_ok": entry.get("duplicate_timestamps") == 0,
                "invalid_ohlcv_ok": entry.get("invalid_ohlcv_rows") == 0,
                "strict_5m_spacing": entry.get("non_5m_gaps") == 0,
                "rows_positive": entry.get("rows", 0) > 0,
            }
        )
    block_checks = []
    for entry in audit["block_audit"]:
        dates = pd.to_datetime(samples.loc[samples["block"] == entry["block"], "date"], utc=True)
        block_checks.append(
            {
                "block": entry["block"],
                "timerange": entry.get("timerange"),
                "synchronized_rows_positive": entry.get("rows_after_sync", 0) > 0,
                "samples_sufficient": entry.get("samples", 0) >= 30,
                "timezone_utc": bool(len(dates) == 0 or str(dates.dt.tz) == "UTC"),
            }
        )
    observed_blocks = int(samples["block"].nunique()) if "block" in samples else 0
    sample_sufficient = len(samples) >= expected_blocks * 30 and observed_blocks == expected_blocks
    hard_failures = []
    for entry in file_checks:
        for key in ("file_present", "timezone_utc", "duplicate_timestamps_ok", "invalid_ohlcv_ok", "rows_positive"):
            if not entry[key]:
                hard_failures.append(f"{entry['pair']}:{key}")
    for entry in block_checks:
        for key in ("synchronized_rows_positive", "samples_sufficient", "timezone_utc"):
            if not entry[key]:
                hard_failures.append(f"block_{entry['block']}:{key}")
    if not sample_sufficient:
        hard_failures.append("sample_sufficient")
    return {
        "expected_blocks": expected_blocks,
        "observed_blocks": observed_blocks,
        "total_samples": int(len(samples)),
        "minimum_samples_per_block": 30,
        "file_checks": file_checks,
        "block_checks": block_checks,
        "hard_failures": hard_failures,
        "integrity_sufficient": len(hard_failures) == 0,
        "non_impeding_warnings": [
            f"{entry['pair']}:non_5m_gaps"
            for entry in file_checks
            if not entry["strict_5m_spacing"]
        ],
    }


def build_primary_samples() -> tuple[Any, dict[str, Any]]:
    import numpy as np
    import pandas as pd

    windows = load_json(WINDOWS_FILE)["windows"]
    frames: dict[str, Any] = {}
    file_audit: dict[str, Any] = {}
    for pair in ALL_PAIRS:
        path = DATA_DIR / pair_to_filename(pair)
        frame = pd.read_feather(path).sort_values("date").reset_index(drop=True)
        diffs = frame["date"].diff().dropna()
        invalid_ohlcv = (
            (frame["open"] <= 0)
            | (frame["high"] <= 0)
            | (frame["low"] <= 0)
            | (frame["close"] <= 0)
            | (frame["volume"] < 0)
            | (frame["high"] < frame[["open", "close", "low"]].max(axis=1))
            | (frame["low"] > frame[["open", "close", "high"]].min(axis=1))
        )
        file_audit[pair] = {
            "path": str(path),
            "sha256": sha256_file(path),
            "rows": int(len(frame)),
            "start": frame["date"].min().isoformat(),
            "end": frame["date"].max().isoformat(),
            "duplicate_timestamps": int(frame["date"].duplicated().sum()),
            "non_5m_gaps": int((diffs != pd.Timedelta(minutes=5)).sum()) if len(diffs) else 0,
            "invalid_ohlcv_rows": int(invalid_ohlcv.sum()),
            "timezone": str(frame["date"].dt.tz),
        }
        frames[pair] = frame[["date", "close"]].rename(columns={"close": pair})

    sample_frames = []
    block_audit: list[dict[str, Any]] = []
    discarded: list[dict[str, Any]] = []
    for window in windows:
        start = pd.Timestamp(window["start"], tz="UTC")
        end = pd.Timestamp(window["end"], tz="UTC")
        merged = None
        pre_counts: dict[str, int] = {}
        for pair in ALL_PAIRS:
            block = frames[pair][(frames[pair]["date"] >= start) & (frames[pair]["date"] < end)].copy()
            pre_counts[pair] = int(len(block))
            merged = block if merged is None else merged.merge(block, on="date", how="inner")
        merged = merged.sort_values("date").reset_index(drop=True)
        if len(merged) < 3:
            discarded.append(
                {
                    "block": int(window["window_index"]),
                    "reason": "fewer than 3 synchronized rows",
                    "rows_after_sync": int(len(merged)),
                }
            )
            continue
        close = merged[[BTC_PAIR, *ALT_PAIRS]].astype(float)
        returns = close / close.shift(1) - 1.0
        rows = []
        for idx in range(1, len(merged) - 1):
            current = returns.iloc[idx]
            nxt = returns.iloc[idx + 1]
            if not np.isfinite(current[[BTC_PAIR, *ALT_PAIRS]].to_numpy(dtype=float)).all():
                continue
            if not np.isfinite(nxt[ALT_PAIRS].to_numpy(dtype=float)).all():
                continue
            alt_now = current[ALT_PAIRS].to_numpy(dtype=float)
            alt_next = nxt[ALT_PAIRS].to_numpy(dtype=float)
            a_t = float(np.median(alt_now))
            y_t = float(np.mean(alt_now))
            y_next = float(np.mean(alt_next))
            record: dict[str, Any] = {
                "date": merged.loc[idx, "date"],
                "day": pd.Timestamp(merged.loc[idx, "date"]).floor("D"),
                "block": int(window["window_index"]),
                "timerange": window.get("timerange"),
                "btc_ret_t": float(current[BTC_PAIR]),
                "btc_ret_next": float(nxt[BTC_PAIR]),
                "A_t": a_t,
                "X_t": float(current[BTC_PAIR] - a_t),
                "Y_t": y_t,
                "Y_next": y_next,
            }
            for alt in ALT_PAIRS:
                record[f"{alt}_ret_t"] = float(current[alt])
                record[f"{alt}_ret_next"] = float(nxt[alt])
            rows.append(record)
        block_frame = pd.DataFrame(rows)
        sample_frames.append(block_frame)
        block_audit.append(
            {
                "block": int(window["window_index"]),
                "timerange": window.get("timerange"),
                "rows_before_sync_by_pair": pre_counts,
                "rows_after_sync": int(len(merged)),
                "samples": int(len(block_frame)),
                "sample_start": None if block_frame.empty else block_frame["date"].min().isoformat(),
                "sample_end": None if block_frame.empty else block_frame["date"].max().isoformat(),
                "rows_dropped_by_sync_by_pair": {
                    pair: pre_counts[pair] - int(len(merged)) for pair in ALL_PAIRS
                },
            }
        )
    if not sample_frames:
        raise RuntimeError("No synchronized PH4-A01 samples could be built.")
    samples = pd.concat(sample_frames, ignore_index=True)
    audit = {
        "windows_file": str(WINDOWS_FILE),
        "data_dir": str(DATA_DIR),
        "pairs": ALL_PAIRS,
        "file_audit": file_audit,
        "block_audit": block_audit,
        "discarded": discarded,
        "lookahead_proof": (
            "Predictors r_BTC,t, A_t, X_t and Y_t are built from candle t "
            "close-to-close returns. The label Y_t+1 uses only the next candle "
            "return and is never used in predictor construction. Samples are "
            "built inside each frozen block and cannot cross block boundaries."
        ),
    }
    audit["integrity_checks"] = integrity_checks(samples, audit, expected_blocks=len(windows))
    return samples, audit


def estimate_primary(frame: Any) -> dict[str, Any]:
    aggregate = add_regression_metrics(frame, "Y_next", "X_t", ["A_t", "Y_t"])
    econ = economic_contrast(frame, "Y_next", "X_t")
    by_block = []
    for block, block_frame in frame.groupby("block", sort=True):
        metrics = add_regression_metrics(block_frame, "Y_next", "X_t", ["A_t", "Y_t"])
        metrics["block"] = int(block)
        metrics["economic_contrast"] = economic_contrast(block_frame, "Y_next", "X_t")
        by_block.append(metrics)
    return {
        "aggregate_regression_full_sample": aggregate,
        "economic_contrast_full_sample": econ,
        "block_equal_weighted": equal_weighted_block_summary(by_block),
        "by_block": by_block,
    }


def estimate_altcoin_diagnostics(frame: Any) -> dict[str, Any]:
    diagnostics = {}
    for alt in ALT_PAIRS:
        y_col = f"{alt}_ret_next"
        own_col = f"{alt}_ret_t"
        metrics = add_regression_metrics(frame, y_col, "X_t", ["A_t", own_col])
        econ = economic_contrast(frame, y_col, "X_t")
        by_block = []
        for block, block_frame in frame.groupby("block", sort=True):
            block_metrics = add_regression_metrics(block_frame, y_col, "X_t", ["A_t", own_col])
            block_metrics["block"] = int(block)
            block_metrics["economic_contrast"] = economic_contrast(block_frame, y_col, "X_t")
            by_block.append(block_metrics)
        diagnostics[alt] = {
            "regression": metrics,
            "economic_contrast_full_sample": econ,
            "block_equal_weighted": equal_weighted_block_summary(by_block),
            "by_block": by_block,
            "note": "Diagnostic only; altcoins are not independent primary observations.",
        }
    return diagnostics


def make_leader_frame(frame: Any, leader: str, response_pairs: list[str], x_col: str) -> Any:
    import numpy as np

    result = frame[["date", "day", "block", "timerange"]].copy()
    response_now = frame[[return_column(pair, "t") for pair in response_pairs]].to_numpy(dtype=float)
    response_next = frame[[return_column(pair, "next") for pair in response_pairs]].to_numpy(dtype=float)
    leader_now = frame[return_column(leader, "t")].to_numpy(dtype=float)
    market_now = np.median(response_now, axis=1)
    result[x_col] = leader_now - market_now
    result["market_t"] = market_now
    result["response_t"] = np.mean(response_now, axis=1)
    result["response_next"] = np.mean(response_next, axis=1)
    return result


def estimate_leader(frame: Any, leader: str) -> dict[str, Any]:
    response_pairs = [pair for pair in ALL_PAIRS if pair != leader]
    leader_frame = make_leader_frame(frame, leader, response_pairs, "leader_x")
    metrics = add_regression_metrics(leader_frame, "response_next", "leader_x", ["market_t", "response_t"])
    by_block = []
    for block, block_frame in leader_frame.groupby("block", sort=True):
        block_metrics = add_regression_metrics(block_frame, "response_next", "leader_x", ["market_t", "response_t"])
        block_metrics["block"] = int(block)
        block_metrics["economic_contrast"] = economic_contrast(block_frame, "response_next", "leader_x")
        by_block.append(block_metrics)
    return {
        "leader": leader,
        "response_pairs": response_pairs,
        "metrics": metrics,
        "economic_contrast": economic_contrast(leader_frame, "response_next", "leader_x"),
        "block_equal_weighted": equal_weighted_block_summary(by_block),
        "by_block": by_block,
    }


def estimate_controls(frame: Any) -> dict[str, Any]:
    controls: dict[str, Any] = {}
    shifted_frames = []
    for block, block_frame in frame.groupby("block", sort=True):
        block_copy = block_frame.copy()
        shift = max(1, len(block_copy) // 2)
        block_copy["X_shifted"] = block_copy["X_t"].shift(shift)
        block_copy["X_shifted"] = block_copy["X_shifted"].fillna(block_copy["X_t"].shift(shift - len(block_copy)))
        shifted_frames.append(block_copy)

    import pandas as pd

    shifted = pd.concat(shifted_frames, ignore_index=True)
    controls["circular_shift"] = add_regression_metrics(
        shifted.dropna(subset=["X_shifted"]), "Y_next", "X_shifted", ["A_t", "Y_t"]
    )
    controls["circular_shift"]["shift_rule"] = CIRCULAR_SHIFT_RULE
    shifted_by_block = []
    for block, block_frame in shifted.dropna(subset=["X_shifted"]).groupby("block", sort=True):
        block_metrics = add_regression_metrics(block_frame, "Y_next", "X_shifted", ["A_t", "Y_t"])
        block_metrics["block"] = int(block)
        block_metrics["economic_contrast"] = economic_contrast(block_frame, "Y_next", "X_shifted")
        shifted_by_block.append(block_metrics)
    controls["circular_shift"]["block_equal_weighted"] = equal_weighted_block_summary(shifted_by_block)
    controls["circular_shift"]["by_block"] = shifted_by_block
    controls["reverse_time_falsification"] = add_regression_metrics(
        frame, "X_t", "Y_next", ["A_t", "Y_t"]
    )
    pseudo = {}
    for leader in PSEUDO_LEADERS:
        pseudo[leader] = estimate_leader(frame, leader)
    controls["pseudo_leaders"] = pseudo
    return controls


def estimate_concentration(frame: Any) -> dict[str, Any]:
    import numpy as np

    positive = frame[frame["X_t"] > 0].copy()
    by_day = positive.groupby("day").size().to_dict()
    by_block = positive.groupby("block").size().to_dict()
    day_share = max(by_day.values()) / len(positive) if len(positive) else None
    block_share = max(by_block.values()) / len(positive) if len(positive) else None
    alt_positive_contribution = {}
    total_positive_sum = 0.0
    for alt in ALT_PAIRS:
        values = positive[f"{alt}_ret_next"].to_numpy(dtype=float)
        positive_sum = float(np.sum(values[values > 0])) if len(values) else 0.0
        alt_positive_contribution[alt] = positive_sum
        total_positive_sum += max(0.0, positive_sum)
    max_asset_share = (
        max((value / total_positive_sum for value in alt_positive_contribution.values()), default=None)
        if total_positive_sum > 0
        else None
    )
    return {
        "positive_x_events": int(len(positive)),
        "max_day_share": day_share,
        "max_block_share": block_share,
        "positive_contribution_by_alt": alt_positive_contribution,
        "max_asset_positive_contribution_share": max_asset_share,
        "threshold": 0.30,
    }


def bootstrap_estimates(frame: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(RANDOM_SEED)
    block_days = {
        int(block): sorted(block_frame["day"].drop_duplicates().tolist())
        for block, block_frame in frame.groupby("block", sort=True)
    }
    grouped = {
        (int(block), day): day_frame
        for (block, day), day_frame in frame.groupby(["block", "day"], sort=True)
    }

    rows = []
    for rep in range(BOOTSTRAP_REPS):
        sampled_blocks = []
        sampled_block_betas = []
        sampled_block_econ_effects = []
        sampled_block_means = []
        sampled_block_medians = []
        sampled_block_hits = []
        sampled_shifted_betas = []
        sampled_alt_betas = {alt: [] for alt in ALT_PAIRS}
        sampled_alt_econ_effects = {alt: [] for alt in ALT_PAIRS}
        sampled_pseudo_betas = {leader: [] for leader in PSEUDO_LEADERS}
        for block, days in block_days.items():
            sampled_days = rng.choice(days, size=len(days), replace=True)
            pieces = [grouped[(block, day)].copy() for day in sampled_days]
            block_sample = pd.concat(pieces, ignore_index=True)
            sampled_blocks.append(block_sample)
            block_primary = add_regression_metrics(block_sample, "Y_next", "X_t", ["A_t", "Y_t"])
            block_econ = economic_contrast(block_sample, "Y_next", "X_t")[DECISION_COST_SCENARIO]
            if block_primary.get("beta") is not None:
                sampled_block_betas.append(block_primary["beta"])
            if block_econ.get("effect_conditional_minus_unconditional") is not None:
                sampled_block_econ_effects.append(block_econ["effect_conditional_minus_unconditional"])
            if block_econ.get("conditional_mean_net") is not None:
                sampled_block_means.append(block_econ["conditional_mean_net"])
            if block_econ.get("conditional_median_net") is not None:
                sampled_block_medians.append(block_econ["conditional_median_net"])
            if block_econ.get("hit_rate_net") is not None:
                sampled_block_hits.append(block_econ["hit_rate_net"])
            shifted_block = block_sample.copy()
            shift = max(1, len(shifted_block) // 2)
            shifted_block["X_shifted"] = np.roll(shifted_block["X_t"].to_numpy(dtype=float), shift)
            shifted_block_metrics = add_regression_metrics(shifted_block, "Y_next", "X_shifted", ["A_t", "Y_t"])
            if shifted_block_metrics.get("beta") is not None:
                sampled_shifted_betas.append(shifted_block_metrics["beta"])
            for alt in ALT_PAIRS:
                y_col = f"{alt}_ret_next"
                own_col = f"{alt}_ret_t"
                alt_metrics = add_regression_metrics(block_sample, y_col, "X_t", ["A_t", own_col])
                alt_econ = economic_contrast(block_sample, y_col, "X_t")[DECISION_COST_SCENARIO]
                if alt_metrics.get("beta") is not None:
                    sampled_alt_betas[alt].append(alt_metrics["beta"])
                if alt_econ.get("effect_conditional_minus_unconditional") is not None:
                    sampled_alt_econ_effects[alt].append(alt_econ["effect_conditional_minus_unconditional"])
            for leader in PSEUDO_LEADERS:
                pseudo_metrics = estimate_leader(block_sample, leader)["metrics"]
                if pseudo_metrics.get("beta") is not None:
                    sampled_pseudo_betas[leader].append(pseudo_metrics["beta"])
        sample = pd.concat(sampled_blocks, ignore_index=True)
        primary = add_regression_metrics(sample, "Y_next", "X_t", ["A_t", "Y_t"])
        econ = economic_contrast(sample, "Y_next", "X_t")[DECISION_COST_SCENARIO]

        shifted_pieces = []
        for block, block_frame in sample.groupby("block", sort=True):
            block_copy = block_frame.copy()
            shift = max(1, len(block_copy) // 2)
            block_copy["X_shifted"] = np.roll(block_copy["X_t"].to_numpy(dtype=float), shift)
            shifted_pieces.append(block_copy)
        shifted = pd.concat(shifted_pieces, ignore_index=True)
        shifted_metrics = add_regression_metrics(shifted, "Y_next", "X_shifted", ["A_t", "Y_t"])
        beta_eqw = mean(sampled_block_betas)
        shifted_beta_eqw = mean(sampled_shifted_betas)

        record = {
            "replicate": rep,
            "beta": primary.get("beta"),
            "beta_block_equal_weighted": beta_eqw,
            "economic_effect_net": econ.get("effect_conditional_minus_unconditional"),
            "economic_effect_net_block_equal_weighted": mean(sampled_block_econ_effects),
            "conditional_mean_net": econ.get("conditional_mean_net"),
            "conditional_mean_net_block_equal_weighted": mean(sampled_block_means),
            "conditional_median_net": econ.get("conditional_median_net"),
            "conditional_median_net_block_equal_weighted": mean(sampled_block_medians),
            "hit_rate_net": econ.get("hit_rate_net"),
            "hit_rate_net_block_equal_weighted": mean(sampled_block_hits),
            "shifted_beta": shifted_metrics.get("beta"),
            "shifted_beta_block_equal_weighted": shifted_beta_eqw,
            "beta_minus_shifted_beta": (
                None if beta_eqw is None or shifted_beta_eqw is None else beta_eqw - shifted_beta_eqw
            ),
        }
        for alt in ALT_PAIRS:
            alt_beta_eqw = mean(sampled_alt_betas[alt])
            record[f"alt_beta_block_equal_weighted_{alt}"] = alt_beta_eqw
            record[f"alt_economic_effect_net_block_equal_weighted_{alt}"] = mean(sampled_alt_econ_effects[alt])
        for leader in PSEUDO_LEADERS:
            pseudo = estimate_leader(sample, leader)
            pseudo_beta = pseudo["metrics"].get("beta")
            pseudo_beta_eqw = mean(sampled_pseudo_betas[leader])
            record[f"pseudo_beta_{leader}"] = pseudo_beta
            record[f"pseudo_beta_block_equal_weighted_{leader}"] = pseudo_beta_eqw
            record[f"beta_minus_pseudo_{leader}"] = (
                None if beta_eqw is None or pseudo_beta_eqw is None else beta_eqw - pseudo_beta_eqw
            )
        rows.append(record)

    beta_values = [row["beta_block_equal_weighted"] for row in rows if row.get("beta_block_equal_weighted") is not None]
    econ_values = [
        row["economic_effect_net_block_equal_weighted"]
        for row in rows
        if row.get("economic_effect_net_block_equal_weighted") is not None
    ]
    shifted_diff = [row["beta_minus_shifted_beta"] for row in rows if row.get("beta_minus_shifted_beta") is not None]
    observed_primary = estimate_primary(frame)
    observed_altcoins = estimate_altcoin_diagnostics(frame)
    alt_raw_pvalues = {
        alt: one_sided_positive_pvalue_from_bootstrap(
            [row.get(f"alt_beta_block_equal_weighted_{alt}") for row in rows]
        )
        for alt in ALT_PAIRS
    }
    alt_holm = holm_adjust(alt_raw_pvalues)
    altcoin_bootstrap = {}
    for alt in ALT_PAIRS:
        values = [row.get(f"alt_beta_block_equal_weighted_{alt}") for row in rows]
        observed = observed_altcoins[alt]
        altcoin_bootstrap[alt] = {
            "observed_beta_block_equal_weighted": observed["block_equal_weighted"].get("beta"),
            "observed_economic_effect_net_block_equal_weighted": observed["block_equal_weighted"].get("economic_effect_net"),
            "beta_ci95": ci95(values),
            "beta_p_bootstrap": alt_raw_pvalues[alt],
            "beta_p_holm_adjusted_diagnostic_family": alt_holm[alt],
            "evidence_taxonomy": evidence_label(
                observed["block_equal_weighted"].get("beta"),
                ci95(values),
                alt_holm[alt] is not None and alt_holm[alt] < ALPHA,
            ),
            "note": "Diagnostic family only; altcoins are not independent primary observations.",
        }
    pseudo_pvalues = {
        f"btc_gt_{leader}": one_sided_positive_pvalue_from_bootstrap(
            [row.get(f"beta_minus_pseudo_{leader}") for row in rows]
        )
        for leader in PSEUDO_LEADERS
    }
    raw_pvalues = {
        "btc_beta_positive": one_sided_positive_pvalue_from_bootstrap(beta_values),
        "economic_effect_positive": one_sided_positive_pvalue_from_bootstrap(econ_values),
        "btc_gt_circular_shift": one_sided_positive_pvalue_from_bootstrap(shifted_diff),
        **pseudo_pvalues,
    }
    summary = {
        "bootstrap_reps": BOOTSTRAP_REPS,
        "seed": RANDOM_SEED,
        "unit": "UTC days sampled within each frozen block; block-level estimates are aggregated with equal block weight for decision CIs.",
        "observed_block_equal_weighted": observed_primary["block_equal_weighted"],
        "beta_ci95": ci95(beta_values),
        "economic_effect_net_ci95": ci95(econ_values),
        "conditional_mean_net_ci95": ci95([row["conditional_mean_net_block_equal_weighted"] for row in rows]),
        "conditional_median_net_ci95": ci95([row["conditional_median_net_block_equal_weighted"] for row in rows]),
        "hit_rate_net_ci95": ci95([row["hit_rate_net_block_equal_weighted"] for row in rows]),
        "beta_minus_shifted_beta_ci95": ci95(shifted_diff),
        "altcoin_diagnostic_bootstrap": altcoin_bootstrap,
        "raw_decision_pvalues": raw_pvalues,
        "holm_adjusted_decision_pvalues": holm_adjust(raw_pvalues),
        "raw_altcoin_diagnostic_pvalues": alt_raw_pvalues,
        "holm_adjusted_altcoin_diagnostic_pvalues": alt_holm,
    }
    return summary, rows


def evaluate_decision(
    primary: dict[str, Any],
    altcoin_diagnostics: dict[str, Any],
    controls: dict[str, Any],
    concentration: dict[str, Any],
    bootstrap: dict[str, Any],
    integrity: dict[str, Any],
) -> dict[str, Any]:
    regression = primary["aggregate_regression_full_sample"]
    observed_equal_weighted = primary["block_equal_weighted"]
    beta = observed_equal_weighted.get("beta")
    beta_ci = bootstrap["beta_ci95"]
    econ_effect_ci = bootstrap["economic_effect_net_ci95"]
    holm = bootstrap["holm_adjusted_decision_pvalues"]
    block_positive = 0
    for block in primary["by_block"]:
        block_beta = block.get("beta")
        if block_beta is not None and block_beta > 0:
            block_positive += 1
    alt_positive = 0
    for alt, result in altcoin_diagnostics.items():
        alt_beta = result["regression"].get("beta")
        if alt_beta is not None and alt_beta > 0:
            alt_positive += 1
    concentration_ok = (
        (concentration.get("max_asset_positive_contribution_share") is None or concentration["max_asset_positive_contribution_share"] <= 0.30)
        and (concentration.get("max_day_share") is None or concentration["max_day_share"] <= 0.30)
        and (concentration.get("max_block_share") is None or concentration["max_block_share"] <= 0.30)
    )
    btc_superiority_keys = ["btc_gt_circular_shift", *[f"btc_gt_{leader}" for leader in PSEUDO_LEADERS]]
    btc_superiority = all(holm.get(key) is not None and holm[key] < ALPHA for key in btc_superiority_keys)
    gates = {
        "beta_positive_ci95_above_zero": beta is not None and beta_ci[0] is not None and beta > 0 and beta_ci[0] > 0,
        "economic_effect_x_positive_vs_unconditional_ci95_above_zero": econ_effect_ci[0] is not None and econ_effect_ci[0] > 0,
        "conservative_mean_net_positive": (
            observed_equal_weighted.get("conditional_mean_net") is not None
            and observed_equal_weighted["conditional_mean_net"] > 0
        ),
        "conservative_median_net_positive": (
            observed_equal_weighted.get("conditional_median_net") is not None
            and observed_equal_weighted["conditional_median_net"] > 0
        ),
        "hit_rate_net_gt_52pct": (
            observed_equal_weighted.get("hit_rate_net") is not None
            and observed_equal_weighted["hit_rate_net"] > 0.52
        ),
        "positive_at_least_4_of_5_blocks": block_positive >= 4,
        "positive_at_least_7_of_9_altcoins": alt_positive >= 7,
        "btc_superior_to_pseudo_leaders_and_shift_after_holm": btc_superiority,
        "concentration_le_30pct": concentration_ok,
        "effect_survives_controls": regression.get("r2_incremental") is not None and regression.get("r2_incremental") >= 0,
        "integrity_sufficient": bool(integrity.get("integrity_checks", {}).get("integrity_sufficient")),
    }
    if all(gates.values()):
        decision = "DEVELOPMENT BTC LEAD-LAG SIGNAL DETECTED — PROSPECTIVE HOLDOUT REQUIRED"
    elif not gates["integrity_sufficient"]:
        decision = "INCONCLUSIVE BTC LEAD-LAG AUDIT"
    else:
        decision = "BTC LEAD-LAG HYPOTHESIS REJECTED IN PRIMARY SCOPE"
    evidence = evidence_label(beta, beta_ci, all(gates.values()))
    return {
        "decision": decision,
        "evidence_taxonomy": evidence,
        "gates": gates,
        "block_positive_count": block_positive,
        "altcoin_positive_count": alt_positive,
        "note": "Evidence taxonomy is descriptive only; scientific decision follows pre-registered gates.",
    }


def render_markdown(report: dict[str, Any]) -> str:
    def pct(value: float | None) -> str:
        return "NA" if value is None else f"{value * 100:.4f}%"

    primary = report["primary"]
    regression = primary["aggregate_regression_full_sample"]
    observed_equal_weighted = primary["block_equal_weighted"]
    econ = primary["economic_contrast_full_sample"][DECISION_COST_SCENARIO]
    bootstrap = report["bootstrap_summary"]
    lines = [
        "# PH4-A01 — BTC Lead-Lag and Delayed Altcoin Price Discovery",
        "",
        f"Generated at: `{report['generated_at']}`",
        "",
        f"**Decision:** {report['decision']['decision']}",
        "",
        f"**Evidence taxonomy:** {report['decision']['evidence_taxonomy']}",
        "",
        "## Protocol",
        "",
        "- Single fixed lag: one 5m candle.",
        "- Leader: BTC/USDT.",
        "- Response: equal-weight portfolio of nine altcoins.",
        "- Primary model: `Y_t+1 ~ intercept + X_t + A_t + Y_t`.",
        "- No thresholds, grids, top-k, Hyperopt or strategy signals.",
        "",
        "## Primary Estimate",
        "",
        f"- N: `{regression.get('n')}`",
        f"- Beta observed, equal-weighted by block: `{observed_equal_weighted.get('beta')}`",
        f"- Beta pooled descriptive: `{regression.get('beta')}`",
        f"- SE: `{regression.get('se')}`",
        f"- p-value: `{regression.get('p_value')}`",
        f"- OLS CI95: `{regression.get('ci95')}`",
        f"- Bootstrap CI95 beta: `{bootstrap.get('beta_ci95')}`",
        f"- R2 full: `{regression.get('r2_full')}`",
        f"- R2 baseline: `{regression.get('r2_baseline')}`",
        f"- R2 incremental: `{regression.get('r2_incremental')}`",
        "",
        "## Economic Contrast",
        "",
        f"- Conservative conditional mean net, equal-weighted by block: {pct(observed_equal_weighted.get('conditional_mean_net'))}",
        f"- Conservative conditional median net, equal-weighted by block: {pct(observed_equal_weighted.get('conditional_median_net'))}",
        f"- Conservative unconditional mean net: {pct(econ.get('unconditional_mean_net'))}",
        f"- Effect conditional minus unconditional, equal-weighted by block: {pct(observed_equal_weighted.get('economic_effect_net'))}",
        f"- Bootstrap CI95 economic effect: `{bootstrap.get('economic_effect_net_ci95')}`",
        f"- Hit rate net, equal-weighted by block: {pct(observed_equal_weighted.get('hit_rate_net'))}",
        "",
        "## Decision Gates",
        "",
    ]
    for name, value in report["decision"]["gates"].items():
        lines.append(f"- `{name}`: `{value}`")
    lines.extend(
        [
            "",
            "## Controls",
            "",
            f"- Pseudo-leaders: {', '.join(PSEUDO_LEADERS)}.",
            f"- Circular shift rule: {CIRCULAR_SHIFT_RULE}.",
            "- Reverse-time falsification included.",
            "- Holm correction applied to BTC vs pseudo-leaders/placebos.",
            "",
            "## Integrity",
            "",
            report["integrity"]["lookahead_proof"],
            "",
            "## Scope Guardrails",
            "",
            "- No strategy, plugin, Hyperopt, order execution or backtest is created.",
            "- Reports are scientific artifacts only.",
            "- Current data are development-consumed; positive development result would still require prospective holdout.",
        ]
    )
    return "\n".join(lines) + "\n"


def run_analysis() -> int:
    samples, integrity = build_primary_samples()
    primary = estimate_primary(samples)
    altcoin_diagnostics = estimate_altcoin_diagnostics(samples)
    controls = estimate_controls(samples)
    concentration = estimate_concentration(samples)
    bootstrap_summary, bootstrap_rows = bootstrap_estimates(samples)
    decision = evaluate_decision(primary, altcoin_diagnostics, controls, concentration, bootstrap_summary, integrity)

    report = {
        "phase": "PH4-A01",
        "title": "BTC Lead-Lag and Delayed Altcoin Price Discovery",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "constants": {
            "lag_candles": 1,
            "timeframe": "5m",
            "bootstrap_reps": BOOTSTRAP_REPS,
            "random_seed": RANDOM_SEED,
            "circular_shift_rule": CIRCULAR_SHIFT_RULE,
            "fee_per_side": FEE_PER_SIDE,
            "slippage_per_side": SLIPPAGE_PER_SIDE,
            "decision_cost_scenario": DECISION_COST_SCENARIO,
            "pseudo_leaders": PSEUDO_LEADERS,
        },
        "integrity": integrity,
        "primary": primary,
        "altcoin_diagnostics": altcoin_diagnostics,
        "controls": controls,
        "concentration": concentration,
        "bootstrap_summary": bootstrap_summary,
        "decision": decision,
        "scope_guardrails": {
            "strategy_created": False,
            "backtest_executed": False,
            "trading_signal_created": False,
            "hyperopt_used": False,
            "ohlcv_modified": False,
            "sqlite_modified": False,
        },
        "generated_files": [
            str(REPORT_HTML),
            str(REPORT_MD),
            str(REPORT_JSON),
            str(MATRIX_CSV),
            str(BOOTSTRAP_CSV),
        ],
    }

    atomic_write_json(REPORT_JSON, report)
    markdown = render_markdown(report)
    atomic_write_text(REPORT_MD, markdown)
    atomic_write_text(
        REPORT_HTML,
        (
            '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
            "<title>PH4-A01 BTC Leadership Report</title>"
            "<style>body{font-family:Arial,sans-serif;max-width:1200px;margin:32px auto;"
            "line-height:1.45;color:#17202a}pre{white-space:pre-wrap;background:#f6f8fa;"
            "padding:18px;border:1px solid #ddd;border-radius:6px}</style></head><body><pre>"
            + html.escape(markdown)
            + "</pre></body></html>"
        ),
    )

    matrix_rows = []

    def add_matrix_row(
        estimand: str,
        asset: str,
        metrics: dict[str, Any],
        *,
        role: str,
        beta_block_equal_weighted: float | None = None,
        economic_effect_net_block_equal_weighted: float | None = None,
        bootstrap_ci: list[float | None] | None = None,
        bootstrap_p: float | None = None,
        holm_p: float | None = None,
        evidence: str | None = None,
        notes: str | None = None,
    ) -> None:
        matrix_rows.append(
            {
                "estimand": estimand,
                "asset": asset,
                "role": role,
                "beta": metrics.get("beta"),
                "beta_block_equal_weighted": beta_block_equal_weighted,
                "se": metrics.get("se"),
                "p_value": metrics.get("p_value"),
                "p_value_holm": holm_p,
                "ci95_low": (metrics.get("ci95") or [None, None])[0],
                "ci95_high": (metrics.get("ci95") or [None, None])[1],
                "bootstrap_ci95_low": (bootstrap_ci or [None, None])[0],
                "bootstrap_ci95_high": (bootstrap_ci or [None, None])[1],
                "bootstrap_p": bootstrap_p,
                "simple_correlation": metrics.get("simple_correlation"),
                "partial_correlation": metrics.get("partial_correlation"),
                "r2_full": metrics.get("r2_full"),
                "r2_baseline": metrics.get("r2_baseline"),
                "r2_incremental": metrics.get("r2_incremental"),
                "economic_effect_net_block_equal_weighted": economic_effect_net_block_equal_weighted,
                "evidence": evidence,
                "notes": notes,
            }
        )

    add_matrix_row(
        "aggregate_primary",
        "ALT_EW",
        primary["aggregate_regression_full_sample"],
        role="primary",
        beta_block_equal_weighted=primary["block_equal_weighted"].get("beta"),
        economic_effect_net_block_equal_weighted=primary["block_equal_weighted"].get("economic_effect_net"),
        bootstrap_ci=bootstrap_summary.get("beta_ci95"),
        bootstrap_p=bootstrap_summary.get("raw_decision_pvalues", {}).get("btc_beta_positive"),
        holm_p=bootstrap_summary.get("holm_adjusted_decision_pvalues", {}).get("btc_beta_positive"),
        evidence=decision["evidence_taxonomy"],
        notes="Primary estimand uses equal-weighted block point estimate; pooled beta is descriptive.",
    )
    for alt, result in altcoin_diagnostics.items():
        reg = result["regression"]
        alt_bootstrap = bootstrap_summary.get("altcoin_diagnostic_bootstrap", {}).get(alt, {})
        add_matrix_row(
            "altcoin_diagnostic",
            alt,
            reg,
            role="diagnostic_altcoin_not_primary_n",
            beta_block_equal_weighted=result["block_equal_weighted"].get("beta"),
            economic_effect_net_block_equal_weighted=result["block_equal_weighted"].get("economic_effect_net"),
            bootstrap_ci=alt_bootstrap.get("beta_ci95"),
            bootstrap_p=alt_bootstrap.get("beta_p_bootstrap"),
            holm_p=alt_bootstrap.get("beta_p_holm_adjusted_diagnostic_family"),
            evidence=alt_bootstrap.get("evidence_taxonomy"),
            notes="Diagnostic family only; assets are not independent primary observations.",
        )
    add_matrix_row(
        "control_circular_shift",
        "ALT_EW",
        controls["circular_shift"],
        role="placebo_control",
        beta_block_equal_weighted=controls["circular_shift"]["block_equal_weighted"].get("beta"),
        economic_effect_net_block_equal_weighted=controls["circular_shift"]["block_equal_weighted"].get("economic_effect_net"),
        bootstrap_ci=None,
        bootstrap_p=None,
        holm_p=bootstrap_summary.get("holm_adjusted_decision_pvalues", {}).get("btc_gt_circular_shift"),
        evidence=None,
        notes="Circular shift control; Holm p-value column stores BTC superiority versus this control.",
    )
    for leader, result in controls["pseudo_leaders"].items():
        add_matrix_row(
            "control_pseudo_leader",
            leader,
            result["metrics"],
            role="pseudo_leader_control",
            beta_block_equal_weighted=result["block_equal_weighted"].get("beta"),
            economic_effect_net_block_equal_weighted=result["block_equal_weighted"].get("economic_effect_net"),
            bootstrap_ci=None,
            bootstrap_p=None,
            holm_p=bootstrap_summary.get("holm_adjusted_decision_pvalues", {}).get(f"btc_gt_{leader}"),
            evidence=None,
            notes="Pseudo-leader control; Holm p-value column stores BTC superiority versus this pseudo-leader.",
        )
    atomic_write_csv(
        MATRIX_CSV,
        matrix_rows,
        [
            "estimand",
            "asset",
            "role",
            "beta",
            "beta_block_equal_weighted",
            "se",
            "p_value",
            "p_value_holm",
            "ci95_low",
            "ci95_high",
            "bootstrap_ci95_low",
            "bootstrap_ci95_high",
            "bootstrap_p",
            "simple_correlation",
            "partial_correlation",
            "r2_full",
            "r2_baseline",
            "r2_incremental",
            "economic_effect_net_block_equal_weighted",
            "evidence",
            "notes",
        ],
    )
    bootstrap_fieldnames = sorted({key for row in bootstrap_rows for key in row})
    atomic_write_csv(BOOTSTRAP_CSV, bootstrap_rows, bootstrap_fieldnames)
    print(f"Wrote {REPORT_JSON}")
    print(f"Wrote {REPORT_MD}")
    print(f"Wrote {REPORT_HTML}")
    print(f"Wrote {MATRIX_CSV}")
    print(f"Wrote {BOOTSTRAP_CSV}")
    print(f"Decision: {decision['decision']}")
    return 0


def main() -> int:
    args = parse_args()
    if args.command == "analyze":
        return run_analysis()
    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
