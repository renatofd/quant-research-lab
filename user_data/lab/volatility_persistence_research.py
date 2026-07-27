"""PH4-A02 offline volatility-persistence audit.

This module forecasts risk magnitude only.  It does not create trading signals,
strategies, orders, or parameter searches.  Import and --help are data-free.
"""

from __future__ import annotations

import argparse
import html
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import btc_leadership_research as common


LAB_DIR = Path(__file__).resolve().parent
PROTOCOL_FILE = LAB_DIR.parent.parent / "PHASE4_A02_PROTOCOL.md"
REPORT_MD = LAB_DIR / "ph4_a02_volatility_persistence_report.md"
REPORT_JSON = LAB_DIR / "ph4_a02_volatility_persistence_report.json"
REPORT_HTML = LAB_DIR / "ph4_a02_volatility_persistence_report.html"
MATRIX_CSV = LAB_DIR / "ph4_a02_volatility_persistence_matrix.csv"
BOOTSTRAP_CSV = LAB_DIR / "ph4_a02_volatility_persistence_bootstrap.csv"

HORIZON_CANDLES = 24
BOOTSTRAP_REPS = 1000
RANDOM_SEED = 2026071402
ALPHA = 0.05
MIN_EVALUATION_EVENTS = 30
EPSILON = 1e-12


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "PH4-A02 offline volatility-persistence research. No backtest, "
            "strategy, order execution, or parameter search is performed."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "analyze",
        help="Run the immutable PH4-A02 risk-forecasting protocol.",
    )
    return parser.parse_args()


def linear_fit(x_values: Any, y_values: Any) -> tuple[float, float]:
    import numpy as np

    x = np.asarray(x_values, dtype=float)
    y = np.asarray(y_values, dtype=float)
    design = np.column_stack([np.ones(len(x)), x])
    coefficients, *_ = np.linalg.lstsq(design, y, rcond=None)
    return float(coefficients[0]), float(coefficients[1])


def safe_mean(values: Any) -> float | None:
    import numpy as np

    array = np.asarray(list(values), dtype=float)
    array = array[np.isfinite(array)]
    return None if len(array) == 0 else float(np.mean(array))


def safe_corr(x_values: Any, y_values: Any) -> float | None:
    import numpy as np

    x = np.asarray(x_values, dtype=float)
    y = np.asarray(y_values, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    x = x[mask]
    y = y[mask]
    if len(x) < 3 or float(np.std(x)) == 0.0 or float(np.std(y)) == 0.0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def unit_metrics(frame: Any) -> dict[str, Any]:
    import numpy as np

    if frame.empty:
        return {}
    x = frame["x"].to_numpy(dtype=float)
    y = frame["y"].to_numpy(dtype=float)
    prediction = frame["prediction"].to_numpy(dtype=float)
    baseline = frame["baseline"].to_numpy(dtype=float)
    shift = max(1, len(x) // 2)
    shifted_prediction = frame["calibration_intercept"].iloc[0] + (
        frame["calibration_beta"].iloc[0] * np.roll(x, shift)
    )

    model_error = y - prediction
    baseline_error = y - baseline
    placebo_error = y - shifted_prediction
    mse_model = float(np.mean(model_error**2))
    mse_baseline = float(np.mean(baseline_error**2))
    mse_placebo = float(np.mean(placebo_error**2))
    mae_model = float(np.mean(np.abs(model_error)))
    mae_baseline = float(np.mean(np.abs(baseline_error)))
    _, evaluation_beta = linear_fit(x, y)

    return {
        "n": int(len(frame)),
        "beta": evaluation_beta,
        "correlation": safe_corr(x, y),
        "mse_model": mse_model,
        "mse_baseline": mse_baseline,
        "mse_placebo": mse_placebo,
        "mse_improvement": None if mse_baseline <= 0 else 1.0 - (mse_model / mse_baseline),
        "mae_improvement": None if mae_baseline <= 0 else 1.0 - (mae_model / mae_baseline),
        "model_minus_placebo_loss_reduction": mse_placebo - mse_model,
        "calibration_beta": float(frame["calibration_beta"].iloc[0]),
    }


def aggregate_unit_metrics(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    fields = [
        "beta",
        "correlation",
        "mse_improvement",
        "mae_improvement",
        "model_minus_placebo_loss_reduction",
    ]
    result: dict[str, Any] = {
        "units": len(metrics),
        "events": int(sum(int(item.get("n", 0)) for item in metrics)),
    }
    for field in fields:
        result[field] = safe_mean(
            item[field] for item in metrics if item.get(field) is not None
        )
    return result


def load_samples() -> tuple[Any, dict[str, Any]]:
    import numpy as np
    import pandas as pd

    windows = common.load_json(common.WINDOWS_FILE)["windows"]
    file_audit: dict[str, Any] = {}
    frames: dict[str, Any] = {}

    for pair in common.ALL_PAIRS:
        path = common.DATA_DIR / common.pair_to_filename(pair)
        frame = pd.read_feather(path).sort_values("date").reset_index(drop=True)
        diffs = frame["date"].diff().dropna()
        invalid = (
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
            "sha256": common.sha256_file(path),
            "rows": int(len(frame)),
            "start": frame["date"].min().isoformat(),
            "end": frame["date"].max().isoformat(),
            "timezone": str(frame["date"].dt.tz),
            "duplicate_timestamps": int(frame["date"].duplicated().sum()),
            "non_5m_gaps": int((diffs != pd.Timedelta(minutes=5)).sum()),
            "invalid_ohlcv_rows": int(invalid.sum()),
        }
        frames[pair] = frame[["date", "close"]].copy()

    rows: list[Any] = []
    unit_audit: list[dict[str, Any]] = []
    for window in windows:
        block_id = int(window["window_index"])
        start = pd.Timestamp(window["start"], tz="UTC")
        end = pd.Timestamp(window["end"], tz="UTC")
        for pair in common.ALL_PAIRS:
            source = frames[pair]
            block = source[(source["date"] >= start) & (source["date"] < end)].copy()
            block = block.sort_values("date").reset_index(drop=True)
            close = block["close"].to_numpy(dtype=float)
            dates = block["date"].reset_index(drop=True)
            log_returns = np.diff(np.log(close))
            events: list[dict[str, Any]] = []
            for t in range(HORIZON_CANDLES, len(close) - HORIZON_CANDLES, HORIZON_CANDLES):
                past = log_returns[t - HORIZON_CANDLES : t]
                future = log_returns[t : t + HORIZON_CANDLES]
                if len(past) != HORIZON_CANDLES or len(future) != HORIZON_CANDLES:
                    continue
                past_rv = float(np.sqrt(np.sum(past**2)))
                future_rv = float(np.sqrt(np.sum(future**2)))
                if not np.isfinite(past_rv) or not np.isfinite(future_rv):
                    continue
                events.append(
                    {
                        "pair": pair,
                        "block": block_id,
                        "date": dates.iloc[t],
                        "day": dates.iloc[t].floor("D"),
                        "x": math.log(max(past_rv, EPSILON)),
                        "y": math.log(max(future_rv, EPSILON)),
                    }
                )

            event_frame = pd.DataFrame(events)
            if len(event_frame) < 2 * MIN_EVALUATION_EVENTS:
                unit_audit.append(
                    {
                        "pair": pair,
                        "block": block_id,
                        "raw_rows": int(len(block)),
                        "eligible_events": int(len(event_frame)),
                        "status": "insufficient",
                    }
                )
                continue
            split = len(event_frame) // 2
            calibration = event_frame.iloc[:split].copy()
            evaluation = event_frame.iloc[split:].copy()
            intercept, beta = linear_fit(calibration["x"], calibration["y"])
            baseline = float(calibration["y"].mean())
            evaluation["prediction"] = intercept + beta * evaluation["x"]
            evaluation["baseline"] = baseline
            evaluation["calibration_intercept"] = intercept
            evaluation["calibration_beta"] = beta
            rows.append(evaluation)
            unit_audit.append(
                {
                    "pair": pair,
                    "block": block_id,
                    "raw_rows": int(len(block)),
                    "eligible_events": int(len(event_frame)),
                    "calibration_events": int(len(calibration)),
                    "evaluation_events": int(len(evaluation)),
                    "status": "valid",
                }
            )

    samples = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    expected_units = len(common.ALL_PAIRS) * len(windows)
    valid_units = sum(item["status"] == "valid" for item in unit_audit)
    hard_failures: list[str] = []
    if len(file_audit) != len(common.ALL_PAIRS):
        hard_failures.append("missing expected files")
    if valid_units != expected_units:
        hard_failures.append("not all pair/block units have sufficient samples")
    for pair, item in file_audit.items():
        if item["duplicate_timestamps"]:
            hard_failures.append(f"{pair}: duplicate timestamps")
        if item["non_5m_gaps"]:
            hard_failures.append(f"{pair}: non-5m gaps")
        if item["invalid_ohlcv_rows"]:
            hard_failures.append(f"{pair}: invalid OHLCV")
        if item["timezone"] != "UTC":
            hard_failures.append(f"{pair}: timezone is not UTC")
    audit = {
        "windows_file": str(common.WINDOWS_FILE),
        "data_dir": str(common.DATA_DIR),
        "files": file_audit,
        "units": unit_audit,
        "expected_units": expected_units,
        "valid_units": valid_units,
        "evaluation_events": int(len(samples)),
        "hard_failures": hard_failures,
        "integrity_sufficient": not hard_failures and not samples.empty,
        "lookahead_proof": (
            "At event t, x uses only the preceding 24 close-to-close log returns. "
            "The label y uses the following 24 returns. Events are built within "
            "one frozen block, and calibration precedes evaluation."
        ),
    }
    return samples, audit


def estimate(samples: Any) -> tuple[dict[str, Any], list[dict[str, Any]], dict[tuple[str, int], Any]]:
    unit_rows: list[dict[str, Any]] = []
    unit_frames: dict[tuple[str, int], Any] = {}
    for (pair, block), frame in samples.groupby(["pair", "block"], sort=True):
        frame = frame.sort_values("date").reset_index(drop=True)
        unit_frames[(str(pair), int(block))] = frame
        metrics = unit_metrics(frame)
        unit_rows.append({"level": "unit", "pair": pair, "block": int(block), **metrics})

    unit_metrics_only = [
        {key: value for key, value in row.items() if key not in {"level", "pair", "block"}}
        for row in unit_rows
    ]
    overall = aggregate_unit_metrics(unit_metrics_only)

    by_pair: dict[str, Any] = {}
    for pair in common.ALL_PAIRS:
        subset = [row for row in unit_rows if row["pair"] == pair]
        metrics = aggregate_unit_metrics(subset)
        by_pair[pair] = metrics
        unit_rows.append({"level": "pair", "pair": pair, "block": None, **metrics})

    by_block: dict[str, Any] = {}
    for block in sorted(samples["block"].unique()):
        subset = [row for row in unit_rows if row["level"] == "unit" and row["block"] == int(block)]
        metrics = aggregate_unit_metrics(subset)
        by_block[str(int(block))] = metrics
        unit_rows.append({"level": "block", "pair": None, "block": int(block), **metrics})

    return {"overall": overall, "by_pair": by_pair, "by_block": by_block}, unit_rows, unit_frames


def bootstrap(unit_frames: dict[tuple[str, int], Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(RANDOM_SEED)
    rows: list[dict[str, Any]] = []
    pair_beta: dict[str, list[float]] = defaultdict(list)
    pair_mse: dict[str, list[float]] = defaultdict(list)

    for replicate in range(BOOTSTRAP_REPS):
        sampled_metrics: list[dict[str, Any]] = []
        sampled_by_pair: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for (pair, block), frame in unit_frames.items():
            days = list(frame["day"].drop_duplicates())
            sampled_days = rng.choice(days, size=len(days), replace=True)
            pieces = [frame[frame["day"] == day] for day in sampled_days]
            sampled = pd.concat(pieces, ignore_index=True)
            metrics = unit_metrics(sampled)
            sampled_metrics.append(metrics)
            sampled_by_pair[pair].append(metrics)
        aggregate = aggregate_unit_metrics(sampled_metrics)
        rows.append(
            {
                "replicate": replicate,
                "beta": aggregate["beta"],
                "mse_improvement": aggregate["mse_improvement"],
                "model_minus_placebo_loss_reduction": aggregate["model_minus_placebo_loss_reduction"],
            }
        )
        for pair, metrics in sampled_by_pair.items():
            summary = aggregate_unit_metrics(metrics)
            pair_beta[pair].append(summary["beta"])
            pair_mse[pair].append(summary["mse_improvement"])

    beta_values = [row["beta"] for row in rows]
    mse_values = [row["mse_improvement"] for row in rows]
    placebo_values = [row["model_minus_placebo_loss_reduction"] for row in rows]
    raw_p = {
        "beta_positive": common.one_sided_positive_pvalue_from_bootstrap(beta_values),
        "mse_improvement_positive": common.one_sided_positive_pvalue_from_bootstrap(mse_values),
        "model_beats_circular_placebo": common.one_sided_positive_pvalue_from_bootstrap(placebo_values),
    }
    pair_p = {
        pair: common.one_sided_positive_pvalue_from_bootstrap(values)
        for pair, values in pair_mse.items()
    }
    summary = {
        "replicates": BOOTSTRAP_REPS,
        "seed": RANDOM_SEED,
        "unit": "complete UTC days resampled within each pair/block; units equally weighted",
        "beta_ci95": common.ci95(beta_values),
        "mse_improvement_ci95": common.ci95(mse_values),
        "model_minus_placebo_loss_reduction_ci95": common.ci95(placebo_values),
        "raw_primary_pvalues": raw_p,
        "holm_primary_pvalues": common.holm_adjust(raw_p),
        "pair_diagnostics": {
            pair: {
                "beta_ci95": common.ci95(pair_beta[pair]),
                "mse_improvement_ci95": common.ci95(pair_mse[pair]),
                "raw_pvalue": pair_p[pair],
                "holm_pvalue": common.holm_adjust(pair_p)[pair],
            }
            for pair in common.ALL_PAIRS
        },
    }
    return summary, rows


def concentration(samples: Any) -> dict[str, Any]:
    frame = samples.copy()
    frame["loss_reduction"] = (frame["y"] - frame["baseline"]) ** 2 - (
        frame["y"] - frame["prediction"]
    ) ** 2
    positive = frame[frame["loss_reduction"] > 0].copy()
    total = float(positive["loss_reduction"].sum())
    if total <= 0:
        return {"positive_total": total, "max_pair_share": None, "max_block_share": None, "max_day_share": None}

    def maximum_share(column: str) -> float:
        return float(positive.groupby(column)["loss_reduction"].sum().max() / total)

    return {
        "positive_total": total,
        "max_pair_share": maximum_share("pair"),
        "max_block_share": maximum_share("block"),
        "max_day_share": maximum_share("day"),
    }


def decide(estimates: dict[str, Any], bootstrap_result: dict[str, Any], audit: dict[str, Any], concentration_result: dict[str, Any]) -> dict[str, Any]:
    overall = estimates["overall"]
    beta_ci = bootstrap_result["beta_ci95"]
    mse_ci = bootstrap_result["mse_improvement_ci95"]
    placebo_ci = bootstrap_result["model_minus_placebo_loss_reduction_ci95"]
    holm = bootstrap_result["holm_primary_pvalues"]
    positive_blocks = sum(
        item.get("mse_improvement") is not None and item["mse_improvement"] > 0
        for item in estimates["by_block"].values()
    )
    positive_pairs = sum(
        item.get("mse_improvement") is not None and item["mse_improvement"] > 0
        for item in estimates["by_pair"].values()
    )
    concentration_ok = all(
        concentration_result.get(field) is not None and concentration_result[field] <= 0.30
        for field in ("max_pair_share", "max_block_share", "max_day_share")
    )
    gates = {
        "beta_positive_ci95_above_zero": overall.get("beta") is not None and beta_ci[0] is not None and beta_ci[0] > 0,
        "mse_improvement_positive_ci95_above_zero": overall.get("mse_improvement") is not None and mse_ci[0] is not None and mse_ci[0] > 0,
        "model_beats_circular_placebo_after_holm": placebo_ci[0] is not None and placebo_ci[0] > 0 and holm["model_beats_circular_placebo"] < ALPHA,
        "positive_at_least_4_of_5_blocks": positive_blocks >= 4,
        "positive_at_least_7_of_10_pairs": positive_pairs >= 7,
        "concentration_le_30pct": concentration_ok,
        "integrity_sufficient": bool(audit["integrity_sufficient"]),
        "primary_effects_survive_holm": all(value < ALPHA for value in holm.values()),
    }
    if not audit["integrity_sufficient"]:
        decision = "INCONCLUSIVE VOLATILITY PERSISTENCE AUDIT"
    elif all(gates.values()):
        decision = "DEVELOPMENT VOLATILITY PERSISTENCE DETECTED - PROSPECTIVE HOLDOUT REQUIRED"
    else:
        decision = "VOLATILITY PERSISTENCE HYPOTHESIS REJECTED IN PRIMARY SCOPE"
    return {
        "decision": decision,
        "gates": gates,
        "positive_blocks": positive_blocks,
        "positive_pairs": positive_pairs,
    }


def render_markdown(report: dict[str, Any]) -> str:
    overall = report["estimates"]["overall"]
    boot = report["bootstrap"]
    decision = report["decision"]
    lines = [
        "# PH4-A02 - Volatility Persistence as Risk Forecasting",
        "",
        f"Generated: `{report['generated_at']}`",
        "",
        f"**Decision:** {decision['decision']}",
        "",
        "## Frozen Protocol",
        "",
        "- One fixed horizon: 24 candles (2h) past and 24 candles future.",
        "- Chronological calibration/evaluation split inside every pair/block.",
        "- Outcome is future realized-volatility magnitude, not return direction.",
        "- Five blocks are development-consumed; no prospective holdout exists.",
        "",
        "## Primary Results",
        "",
        f"- Pair/block units: `{overall['units']}`",
        f"- Evaluation events: `{overall['events']}`",
        f"- Equal-weight beta: `{overall['beta']}`; CI95 `{boot['beta_ci95']}`",
        f"- Equal-weight MSE improvement: `{overall['mse_improvement']}`; CI95 `{boot['mse_improvement_ci95']}`",
        f"- Model minus circular-placebo loss reduction: `{overall['model_minus_placebo_loss_reduction']}`; CI95 `{boot['model_minus_placebo_loss_reduction_ci95']}`",
        f"- Positive blocks: `{decision['positive_blocks']}/5`",
        f"- Positive pairs: `{decision['positive_pairs']}/10`",
        "",
        "## Decision Gates",
        "",
    ]
    lines.extend(f"- `{key}`: `{value}`" for key, value in decision["gates"].items())
    lines.extend(
        [
            "",
            "## Scope",
            "",
            "This is an offline development audit of risk predictability. It does not establish causal identification, directional edge, profitability, or permission to build or operate a bot.",
            "",
        ]
    )
    return "\n".join(lines)


def run_analysis() -> int:
    samples, audit = load_samples()
    estimates, matrix_rows, unit_frames = estimate(samples)
    bootstrap_result, bootstrap_rows = bootstrap(unit_frames)
    concentration_result = concentration(samples)
    decision = decide(estimates, bootstrap_result, audit, concentration_result)
    report = {
        "study": "PH4-A02",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "protocol_file": str(PROTOCOL_FILE),
        "mechanics": {
            "horizon_candles": HORIZON_CANDLES,
            "bootstrap_reps": BOOTSTRAP_REPS,
            "seed": RANDOM_SEED,
            "minimum_evaluation_events": MIN_EVALUATION_EVENTS,
            "epsilon": EPSILON,
        },
        "audit": audit,
        "estimates": estimates,
        "bootstrap": bootstrap_result,
        "concentration": concentration_result,
        "decision": decision,
    }
    markdown = render_markdown(report)
    html_text = "<!doctype html><html><head><meta charset='utf-8'><title>PH4-A02</title></head><body><pre>" + html.escape(markdown) + "</pre></body></html>"
    common.atomic_write_json(REPORT_JSON, report)
    common.atomic_write_text(REPORT_MD, markdown)
    common.atomic_write_text(REPORT_HTML, html_text)
    common.atomic_write_csv(
        MATRIX_CSV,
        matrix_rows,
        [
            "level", "pair", "block", "units", "events", "n", "beta", "correlation",
            "mse_model", "mse_baseline", "mse_placebo", "mse_improvement",
            "mae_improvement", "model_minus_placebo_loss_reduction", "calibration_beta",
        ],
    )
    common.atomic_write_csv(
        BOOTSTRAP_CSV,
        bootstrap_rows,
        ["replicate", "beta", "mse_improvement", "model_minus_placebo_loss_reduction"],
    )
    print(decision["decision"])
    for path in (REPORT_MD, REPORT_JSON, REPORT_HTML, MATRIX_CSV, BOOTSTRAP_CSV):
        print(f"Wrote {path}")
    return 0


def main() -> int:
    args = parse_args()
    if args.command == "analyze":
        return run_analysis()
    raise RuntimeError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())

