"""PH4-A03 offline signed-semivariance risk audit."""

from __future__ import annotations

import argparse
import html
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import btc_leadership_research as common


LAB_DIR = Path(__file__).resolve().parent
PROTOCOL_FILE = LAB_DIR.parent.parent / "PHASE4_A03_PROTOCOL.md"
REPORT_MD = LAB_DIR / "ph4_a03_signed_volatility_report.md"
REPORT_JSON = LAB_DIR / "ph4_a03_signed_volatility_report.json"
REPORT_HTML = LAB_DIR / "ph4_a03_signed_volatility_report.html"
MATRIX_CSV = LAB_DIR / "ph4_a03_signed_volatility_matrix.csv"
BOOTSTRAP_CSV = LAB_DIR / "ph4_a03_signed_volatility_bootstrap.csv"

HORIZON_CANDLES = 24
BOOTSTRAP_REPS = 1000
RANDOM_SEED = 2026071403
MIN_EVALUATION_EVENTS = 30
EPSILON = 1e-12
ALPHA = 0.05


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "PH4-A03 offline signed-semivariance risk audit. No strategy, "
            "backtest, threshold search, or order execution is performed."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("analyze", help="Run the frozen PH4-A03 protocol.")
    return parser.parse_args()


def fit_linear(y: Any, x: Any) -> Any:
    import numpy as np

    y_array = np.asarray(y, dtype=float)
    x_array = np.asarray(x, dtype=float)
    if x_array.ndim == 1:
        x_array = x_array.reshape(-1, 1)
    design = np.column_stack([np.ones(len(y_array)), x_array])
    beta, *_ = np.linalg.lstsq(design, y_array, rcond=None)
    return beta


def safe_mean(values: Any) -> float | None:
    import numpy as np

    array = np.asarray(list(values), dtype=float)
    array = array[np.isfinite(array)]
    return None if len(array) == 0 else float(np.mean(array))


def metrics_from_arrays(arrays: dict[str, Any], indices: Any | None = None) -> dict[str, Any]:
    import numpy as np

    select = slice(None) if indices is None else indices
    y = arrays["y"][select]
    total = arrays["total"][select]
    imbalance = arrays["imbalance"][select]
    full_prediction = arrays["full_prediction"][select]
    baseline_prediction = arrays["baseline_prediction"][select]
    placebo_prediction = arrays["placebo_prediction"][select]
    evaluation_beta = fit_linear(y, np.column_stack([total, imbalance]))[2]
    mse_full = float(np.mean((y - full_prediction) ** 2))
    mse_baseline = float(np.mean((y - baseline_prediction) ** 2))
    mse_placebo = float(np.mean((y - placebo_prediction) ** 2))
    return {
        "n": int(len(y)),
        "imbalance_beta": float(evaluation_beta),
        "mse_full": mse_full,
        "mse_baseline": mse_baseline,
        "mse_placebo": mse_placebo,
        "mse_improvement": None if mse_baseline <= 0 else 1.0 - (mse_full / mse_baseline),
        "full_minus_placebo_loss_reduction": mse_placebo - mse_full,
    }


def aggregate(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "units": len(metrics),
        "events": int(sum(item["n"] for item in metrics)),
        "imbalance_beta": safe_mean(item["imbalance_beta"] for item in metrics),
        "mse_improvement": safe_mean(item["mse_improvement"] for item in metrics),
        "full_minus_placebo_loss_reduction": safe_mean(
            item["full_minus_placebo_loss_reduction"] for item in metrics
        ),
    }


def load_units() -> tuple[dict[tuple[str, int], dict[str, Any]], dict[str, Any]]:
    import numpy as np
    import pandas as pd

    windows = common.load_json(common.WINDOWS_FILE)["windows"]
    frames: dict[str, Any] = {}
    file_audit: dict[str, Any] = {}
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

    units: dict[tuple[str, int], dict[str, Any]] = {}
    unit_audit: list[dict[str, Any]] = []
    for window in windows:
        block_id = int(window["window_index"])
        start = pd.Timestamp(window["start"], tz="UTC")
        end = pd.Timestamp(window["end"], tz="UTC")
        for pair in common.ALL_PAIRS:
            block = frames[pair][
                (frames[pair]["date"] >= start) & (frames[pair]["date"] < end)
            ].sort_values("date").reset_index(drop=True)
            close = block["close"].to_numpy(dtype=float)
            log_returns = np.diff(np.log(close))
            events: list[dict[str, Any]] = []
            for t in range(HORIZON_CANDLES, len(close) - HORIZON_CANDLES, HORIZON_CANDLES):
                past = log_returns[t - HORIZON_CANDLES : t]
                future = log_returns[t : t + HORIZON_CANDLES]
                positive = float(np.sum(np.square(past[past > 0])))
                negative = float(np.sum(np.square(past[past < 0])))
                total = positive + negative
                future_total = float(np.sum(np.square(future)))
                if total <= 0 or future_total <= 0:
                    continue
                events.append(
                    {
                        "date": block.loc[t, "date"],
                        "day": block.loc[t, "date"].floor("D"),
                        "total": math.log(max(math.sqrt(total), EPSILON)),
                        "imbalance": (negative - positive) / (total + EPSILON),
                        "y": math.log(max(math.sqrt(future_total), EPSILON)),
                    }
                )
            event_frame = pd.DataFrame(events)
            if len(event_frame) < 2 * MIN_EVALUATION_EVENTS:
                unit_audit.append(
                    {"pair": pair, "block": block_id, "events": int(len(event_frame)), "status": "insufficient"}
                )
                continue
            split = len(event_frame) // 2
            calibration = event_frame.iloc[:split]
            evaluation = event_frame.iloc[split:].copy()
            baseline_beta = fit_linear(calibration["y"], calibration[["total"]])
            full_beta = fit_linear(calibration["y"], calibration[["total", "imbalance"]])
            evaluation["baseline_prediction"] = baseline_beta[0] + baseline_beta[1] * evaluation["total"]
            evaluation["full_prediction"] = (
                full_beta[0]
                + full_beta[1] * evaluation["total"]
                + full_beta[2] * evaluation["imbalance"]
            )
            shifted_imbalance = np.roll(
                evaluation["imbalance"].to_numpy(dtype=float), max(1, len(evaluation) // 2)
            )
            evaluation["placebo_prediction"] = (
                full_beta[0]
                + full_beta[1] * evaluation["total"]
                + full_beta[2] * shifted_imbalance
            )
            arrays = {
                column: evaluation[column].to_numpy(dtype=float)
                for column in (
                    "y", "total", "imbalance", "baseline_prediction",
                    "full_prediction", "placebo_prediction",
                )
            }
            day_values = evaluation["day"].to_numpy()
            arrays["days"] = day_values
            arrays["day_indices"] = {
                str(day): np.flatnonzero(day_values == day) for day in np.unique(day_values)
            }
            arrays["pair"] = pair
            arrays["block"] = block_id
            units[(pair, block_id)] = arrays
            unit_audit.append(
                {
                    "pair": pair,
                    "block": block_id,
                    "events": int(len(event_frame)),
                    "calibration_events": int(len(calibration)),
                    "evaluation_events": int(len(evaluation)),
                    "status": "valid",
                }
            )

    expected_units = len(common.ALL_PAIRS) * len(windows)
    hard_failures: list[str] = []
    for pair, item in file_audit.items():
        if item["duplicate_timestamps"]:
            hard_failures.append(f"{pair}: duplicate timestamps")
        if item["non_5m_gaps"]:
            hard_failures.append(f"{pair}: non-5m gaps")
        if item["invalid_ohlcv_rows"]:
            hard_failures.append(f"{pair}: invalid OHLCV")
        if item["timezone"] != "UTC":
            hard_failures.append(f"{pair}: timezone is not UTC")
    if len(units) != expected_units:
        hard_failures.append("not all pair/block units have sufficient events")
    audit = {
        "files": file_audit,
        "units": unit_audit,
        "expected_units": expected_units,
        "valid_units": len(units),
        "hard_failures": hard_failures,
        "integrity_sufficient": not hard_failures,
        "lookahead_proof": (
            "Total volatility and signed imbalance use only the preceding 24 "
            "returns. Future RV uses only the following 24 returns. Calibration "
            "precedes evaluation and no event crosses a frozen block."
        ),
    }
    return units, audit


def estimate(units: dict[tuple[str, int], dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    unit_results: dict[tuple[str, int], dict[str, Any]] = {}
    for (pair, block), arrays in units.items():
        metrics = metrics_from_arrays(arrays)
        unit_results[(pair, block)] = metrics
        rows.append({"level": "unit", "pair": pair, "block": block, **metrics})
    overall = aggregate(list(unit_results.values()))
    by_pair: dict[str, Any] = {}
    for pair in common.ALL_PAIRS:
        metrics = aggregate([value for (unit_pair, _), value in unit_results.items() if unit_pair == pair])
        by_pair[pair] = metrics
        rows.append({"level": "pair", "pair": pair, "block": None, **metrics})
    by_block: dict[str, Any] = {}
    for block in sorted({key[1] for key in unit_results}):
        metrics = aggregate([value for (_, unit_block), value in unit_results.items() if unit_block == block])
        by_block[str(block)] = metrics
        rows.append({"level": "block", "pair": None, "block": block, **metrics})
    return {"overall": overall, "by_pair": by_pair, "by_block": by_block}, rows


def bootstrap(units: dict[tuple[str, int], dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    import numpy as np

    rng = np.random.default_rng(RANDOM_SEED)
    rows: list[dict[str, Any]] = []
    pair_mse: dict[str, list[float]] = defaultdict(list)
    for replicate in range(BOOTSTRAP_REPS):
        sampled_metrics: list[dict[str, Any]] = []
        sampled_by_pair: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for (pair, _block), arrays in units.items():
            day_keys = list(arrays["day_indices"])
            sampled_days = rng.choice(day_keys, size=len(day_keys), replace=True)
            indices = np.concatenate([arrays["day_indices"][str(day)] for day in sampled_days])
            metrics = metrics_from_arrays(arrays, indices)
            sampled_metrics.append(metrics)
            sampled_by_pair[pair].append(metrics)
        result = aggregate(sampled_metrics)
        rows.append(
            {
                "replicate": replicate,
                "imbalance_beta": result["imbalance_beta"],
                "mse_improvement": result["mse_improvement"],
                "full_minus_placebo_loss_reduction": result["full_minus_placebo_loss_reduction"],
            }
        )
        for pair, metrics in sampled_by_pair.items():
            pair_mse[pair].append(aggregate(metrics)["mse_improvement"])

    beta = [row["imbalance_beta"] for row in rows]
    mse = [row["mse_improvement"] for row in rows]
    placebo = [row["full_minus_placebo_loss_reduction"] for row in rows]
    raw = {
        "imbalance_beta_positive": common.one_sided_positive_pvalue_from_bootstrap(beta),
        "incremental_mse_improvement_positive": common.one_sided_positive_pvalue_from_bootstrap(mse),
        "full_model_beats_circular_placebo": common.one_sided_positive_pvalue_from_bootstrap(placebo),
    }
    pair_raw = {
        pair: common.one_sided_positive_pvalue_from_bootstrap(values)
        for pair, values in pair_mse.items()
    }
    pair_holm = common.holm_adjust(pair_raw)
    return {
        "replicates": BOOTSTRAP_REPS,
        "seed": RANDOM_SEED,
        "unit": "complete UTC days within pair/block; all units equally weighted",
        "imbalance_beta_ci95": common.ci95(beta),
        "mse_improvement_ci95": common.ci95(mse),
        "full_minus_placebo_loss_reduction_ci95": common.ci95(placebo),
        "raw_primary_pvalues": raw,
        "holm_primary_pvalues": common.holm_adjust(raw),
        "pair_diagnostics": {
            pair: {
                "mse_improvement_ci95": common.ci95(pair_mse[pair]),
                "raw_pvalue": pair_raw[pair],
                "holm_pvalue": pair_holm[pair],
            }
            for pair in common.ALL_PAIRS
        },
    }, rows


def concentration(units: dict[tuple[str, int], dict[str, Any]]) -> dict[str, Any]:
    contributions: list[dict[str, Any]] = []
    for (pair, block), arrays in units.items():
        reduction = (arrays["y"] - arrays["baseline_prediction"]) ** 2 - (
            arrays["y"] - arrays["full_prediction"]
        ) ** 2
        for index, value in enumerate(reduction):
            if value > 0:
                contributions.append(
                    {
                        "pair": pair,
                        "block": block,
                        "day": str(arrays["days"][index]),
                        "value": float(value),
                    }
                )
    total = sum(item["value"] for item in contributions)
    if total <= 0:
        return {"positive_total": total, "max_pair_share": None, "max_block_share": None, "max_day_share": None}

    def maximum_share(field: str) -> float:
        grouped: dict[str, float] = defaultdict(float)
        for item in contributions:
            grouped[str(item[field])] += item["value"]
        return max(grouped.values()) / total

    return {
        "positive_total": total,
        "max_pair_share": maximum_share("pair"),
        "max_block_share": maximum_share("block"),
        "max_day_share": maximum_share("day"),
    }


def decide(estimates: dict[str, Any], boot: dict[str, Any], audit: dict[str, Any], conc: dict[str, Any]) -> dict[str, Any]:
    overall = estimates["overall"]
    holm = boot["holm_primary_pvalues"]
    positive_blocks = sum(item["mse_improvement"] > 0 for item in estimates["by_block"].values())
    positive_pairs = sum(item["mse_improvement"] > 0 for item in estimates["by_pair"].values())
    concentration_ok = all(
        conc.get(field) is not None and conc[field] <= 0.30
        for field in ("max_pair_share", "max_block_share", "max_day_share")
    )
    gates = {
        "imbalance_beta_positive_ci95_above_zero": overall["imbalance_beta"] > 0 and boot["imbalance_beta_ci95"][0] is not None and boot["imbalance_beta_ci95"][0] > 0,
        "incremental_mse_improvement_positive_ci95_above_zero": overall["mse_improvement"] > 0 and boot["mse_improvement_ci95"][0] is not None and boot["mse_improvement_ci95"][0] > 0,
        "full_model_beats_circular_placebo_after_holm": boot["full_minus_placebo_loss_reduction_ci95"][0] is not None and boot["full_minus_placebo_loss_reduction_ci95"][0] > 0 and holm["full_model_beats_circular_placebo"] < ALPHA,
        "positive_at_least_4_of_5_blocks": positive_blocks >= 4,
        "positive_at_least_7_of_10_pairs": positive_pairs >= 7,
        "concentration_le_30pct": concentration_ok,
        "primary_effects_survive_holm": all(value < ALPHA for value in holm.values()),
        "integrity_sufficient": audit["integrity_sufficient"],
    }
    if not audit["integrity_sufficient"]:
        decision = "INCONCLUSIVE SIGNED VOLATILITY AUDIT"
    elif all(gates.values()):
        decision = "DEVELOPMENT NEGATIVE SEMIVARIANCE RISK SIGNAL DETECTED - PROSPECTIVE HOLDOUT REQUIRED"
    else:
        decision = "SIGNED VOLATILITY ASYMMETRY HYPOTHESIS REJECTED IN PRIMARY SCOPE"
    return {
        "decision": decision,
        "gates": gates,
        "positive_blocks": positive_blocks,
        "positive_pairs": positive_pairs,
    }


def render_markdown(report: dict[str, Any]) -> str:
    result = report["estimates"]["overall"]
    boot = report["bootstrap"]
    decision = report["decision"]
    lines = [
        "# PH4-A03 - Incremental Risk Information in Negative Semivariance",
        "",
        f"Generated: `{report['generated_at']}`",
        "",
        f"**Decision:** {decision['decision']}",
        "",
        "## Primary Results",
        "",
        f"- Evaluation events: `{result['events']}`",
        f"- Signed-imbalance beta: `{result['imbalance_beta']}`; CI95 `{boot['imbalance_beta_ci95']}`",
        f"- Incremental MSE improvement: `{result['mse_improvement']}`; CI95 `{boot['mse_improvement_ci95']}`",
        f"- Full minus circular-placebo loss reduction: `{result['full_minus_placebo_loss_reduction']}`; CI95 `{boot['full_minus_placebo_loss_reduction_ci95']}`",
        f"- Positive blocks: `{decision['positive_blocks']}/5`",
        f"- Positive pairs: `{decision['positive_pairs']}/10`",
        "",
        "## Gates",
        "",
    ]
    lines.extend(f"- `{key}`: `{value}`" for key, value in decision["gates"].items())
    lines.extend(
        [
            "",
            "## Scope",
            "",
            "This is a risk-magnitude association using candle semivariance. It cannot identify liquidations/order flow and does not authorize directional trading or a bot.",
            "",
        ]
    )
    return "\n".join(lines)


def run_analysis() -> int:
    units, audit = load_units()
    if units:
        estimates, matrix_rows = estimate(units)
        boot, bootstrap_rows = bootstrap(units)
        conc = concentration(units)
        decision = decide(estimates, boot, audit, conc)
    else:
        estimates, matrix_rows, boot, bootstrap_rows, conc = {}, [], {}, [], {}
        decision = {"decision": "INCONCLUSIVE SIGNED VOLATILITY AUDIT", "gates": {"integrity_sufficient": False}, "positive_blocks": 0, "positive_pairs": 0}
    report = {
        "study": "PH4-A03",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "protocol_file": str(PROTOCOL_FILE),
        "mechanics": {
            "horizon_candles": HORIZON_CANDLES,
            "bootstrap_reps": BOOTSTRAP_REPS,
            "seed": RANDOM_SEED,
            "epsilon": EPSILON,
        },
        "audit": audit,
        "estimates": estimates,
        "bootstrap": boot,
        "concentration": conc,
        "decision": decision,
    }
    markdown = render_markdown(report) if estimates else "# PH4-A03\n\n**Decision:** INCONCLUSIVE SIGNED VOLATILITY AUDIT\n"
    html_text = "<!doctype html><html><head><meta charset='utf-8'><title>PH4-A03</title></head><body><pre>" + html.escape(markdown) + "</pre></body></html>"
    common.atomic_write_json(REPORT_JSON, report)
    common.atomic_write_text(REPORT_MD, markdown)
    common.atomic_write_text(REPORT_HTML, html_text)
    common.atomic_write_csv(
        MATRIX_CSV,
        matrix_rows,
        [
            "level", "pair", "block", "units", "events", "n", "imbalance_beta",
            "mse_full", "mse_baseline", "mse_placebo", "mse_improvement",
            "full_minus_placebo_loss_reduction",
        ],
    )
    common.atomic_write_csv(
        BOOTSTRAP_CSV,
        bootstrap_rows,
        ["replicate", "imbalance_beta", "mse_improvement", "full_minus_placebo_loss_reduction"],
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

