"""PH4-A05 offline cross-sectional dispersion risk audit."""

from __future__ import annotations

import argparse
import html
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import btc_leadership_research as common
import volatility_persistence_research as risk_common


LAB_DIR = Path(__file__).resolve().parent
PROTOCOL_FILE = LAB_DIR.parent.parent / "PHASE4_A05_PROTOCOL.md"
REPORT_MD = LAB_DIR / "ph4_a05_dispersion_risk_report.md"
REPORT_JSON = LAB_DIR / "ph4_a05_dispersion_risk_report.json"
REPORT_HTML = LAB_DIR / "ph4_a05_dispersion_risk_report.html"
MATRIX_CSV = LAB_DIR / "ph4_a05_dispersion_risk_matrix.csv"
BOOTSTRAP_CSV = LAB_DIR / "ph4_a05_dispersion_risk_bootstrap.csv"

HORIZON_CANDLES = 24
BOOTSTRAP_REPS = 1000
RANDOM_SEED = 2026071405
MIN_EVALUATION_EVENTS = 30
EPSILON = 1e-12
ALPHA = 0.05


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "PH4-A05 offline cross-sectional dispersion risk audit. "
            "No strategy, backtest, or parameter search is performed."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("analyze", help="Run the frozen PH4-A05 protocol.")
    return parser.parse_args()


def load_raw_events() -> tuple[Any, dict[str, Any]]:
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
        frames[pair] = frame[["date", "close"]].rename(columns={"close": pair})

    event_frames: list[Any] = []
    block_audit: list[dict[str, Any]] = []
    for window in windows:
        block_id = int(window["window_index"])
        start = pd.Timestamp(window["start"], tz="UTC")
        end = pd.Timestamp(window["end"], tz="UTC")
        merged = None
        before_counts: dict[str, int] = {}
        for pair in common.ALL_PAIRS:
            part = frames[pair][
                (frames[pair]["date"] >= start) & (frames[pair]["date"] < end)
            ].copy()
            before_counts[pair] = int(len(part))
            merged = part if merged is None else merged.merge(part, on="date", how="inner")
        merged = merged.sort_values("date").reset_index(drop=True)
        close = merged[common.ALL_PAIRS].astype(float)
        log_close = np.log(close)
        returns = log_close.diff()
        rows: list[dict[str, Any]] = []
        for t in range(HORIZON_CANDLES, len(merged) - HORIZON_CANDLES, HORIZON_CANDLES):
            trailing = (log_close.iloc[t] - log_close.iloc[t - HORIZON_CANDLES]).to_numpy(dtype=float)
            future_returns = returns.iloc[t + 1 : t + HORIZON_CANDLES + 1]
            if len(future_returns) != HORIZON_CANDLES:
                continue
            future_ssq = (future_returns**2).sum(axis=0).to_numpy(dtype=float)
            if not np.isfinite(trailing).all() or not np.isfinite(future_ssq).all():
                continue
            record: dict[str, Any] = {
                "block": block_id,
                "date": merged.loc[t, "date"],
                "day": merged.loc[t, "date"].floor("D"),
            }
            for index, pair in enumerate(common.ALL_PAIRS):
                record[f"past_{pair}"] = float(trailing[index])
                record[f"future_ssq_{pair}"] = float(future_ssq[index])
            rows.append(record)
        block_frame = pd.DataFrame(rows)
        event_frames.append(block_frame)
        block_audit.append(
            {
                "block": block_id,
                "rows_before_sync_by_pair": before_counts,
                "rows_after_sync": int(len(merged)),
                "eligible_events": int(len(block_frame)),
                "event_start": None if block_frame.empty else block_frame["date"].min().isoformat(),
                "event_end": None if block_frame.empty else block_frame["date"].max().isoformat(),
            }
        )

    events = pd.concat(event_frames, ignore_index=True) if event_frames else pd.DataFrame()
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
    insufficient_blocks = [
        item["block"]
        for item in block_audit
        if item["eligible_events"] < 2 * MIN_EVALUATION_EVENTS
    ]
    audit = {
        "windows_file": str(common.WINDOWS_FILE),
        "files": file_audit,
        "blocks": block_audit,
        "hard_failures": hard_failures,
        "insufficient_blocks": insufficient_blocks,
        "integrity_sufficient": not hard_failures,
        "sample_sufficient": not insufficient_blocks and not events.empty,
        "lookahead_proof": (
            "D_t uses close[t] and close[t-24]. Future risk uses only 5m returns "
            "t+1 through t+24. Events remain inside one frozen block, and "
            "calibration chronologically precedes evaluation."
        ),
    }
    return events, audit


def build_model_frames(events: Any, universe: list[str]) -> dict[int, Any]:
    import numpy as np

    result: dict[int, Any] = {}
    past_columns = [f"past_{pair}" for pair in universe]
    future_columns = [f"future_ssq_{pair}" for pair in universe]
    for block, raw in events.groupby("block", sort=True):
        frame = raw[["block", "date", "day"]].copy()
        dispersion = raw[past_columns].to_numpy(dtype=float).std(axis=1, ddof=0)
        future_risk = np.sqrt(raw[future_columns].to_numpy(dtype=float).mean(axis=1))
        frame["x"] = np.log(np.maximum(dispersion, EPSILON))
        frame["y"] = np.log(np.maximum(future_risk, EPSILON))
        split = len(frame) // 2
        calibration = frame.iloc[:split].copy()
        evaluation = frame.iloc[split:].copy()
        intercept, beta = risk_common.linear_fit(calibration["x"], calibration["y"])
        baseline = float(calibration["y"].mean())
        evaluation["prediction"] = intercept + beta * evaluation["x"]
        evaluation["baseline"] = baseline
        evaluation["calibration_intercept"] = intercept
        evaluation["calibration_beta"] = beta
        result[int(block)] = evaluation.reset_index(drop=True)
    return result


def summarize_frames(frames: dict[int, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    by_block: dict[str, Any] = {}
    metrics: list[dict[str, Any]] = []
    for block, frame in sorted(frames.items()):
        item = risk_common.unit_metrics(frame)
        by_block[str(block)] = item
        metrics.append(item)
    return risk_common.aggregate_unit_metrics(metrics), by_block


def bootstrap(frames: dict[int, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(RANDOM_SEED)
    rows: list[dict[str, Any]] = []
    for replicate in range(BOOTSTRAP_REPS):
        metrics: list[dict[str, Any]] = []
        for block, frame in frames.items():
            days = list(frame["day"].drop_duplicates())
            sampled_days = rng.choice(days, size=len(days), replace=True)
            sampled = pd.concat([frame[frame["day"] == day] for day in sampled_days], ignore_index=True)
            metrics.append(risk_common.unit_metrics(sampled))
        aggregate = risk_common.aggregate_unit_metrics(metrics)
        rows.append(
            {
                "replicate": replicate,
                "beta": aggregate["beta"],
                "mse_improvement": aggregate["mse_improvement"],
                "model_minus_placebo_loss_reduction": aggregate["model_minus_placebo_loss_reduction"],
            }
        )
    beta = [row["beta"] for row in rows]
    mse = [row["mse_improvement"] for row in rows]
    placebo = [row["model_minus_placebo_loss_reduction"] for row in rows]
    raw = {
        "beta_positive": common.one_sided_positive_pvalue_from_bootstrap(beta),
        "mse_improvement_positive": common.one_sided_positive_pvalue_from_bootstrap(mse),
        "model_beats_circular_placebo": common.one_sided_positive_pvalue_from_bootstrap(placebo),
    }
    return {
        "replicates": BOOTSTRAP_REPS,
        "seed": RANDOM_SEED,
        "unit": "complete UTC days within block; five blocks equally weighted",
        "beta_ci95": common.ci95(beta),
        "mse_improvement_ci95": common.ci95(mse),
        "model_minus_placebo_loss_reduction_ci95": common.ci95(placebo),
        "raw_primary_pvalues": raw,
        "holm_primary_pvalues": common.holm_adjust(raw),
    }, rows


def concentration(frames: dict[int, Any]) -> dict[str, Any]:
    import pandas as pd

    pieces: list[Any] = []
    for block, frame in frames.items():
        part = frame[["day", "y", "prediction", "baseline"]].copy()
        part["block"] = block
        part["loss_reduction"] = (part["y"] - part["baseline"]) ** 2 - (
            part["y"] - part["prediction"]
        ) ** 2
        pieces.append(part)
    merged = pd.concat(pieces, ignore_index=True)
    positive = merged[merged["loss_reduction"] > 0]
    total = float(positive["loss_reduction"].sum()) if not positive.empty else 0.0
    if total <= 0:
        return {"positive_total": total, "max_block_share": None, "max_day_share": None}
    return {
        "positive_total": total,
        "max_block_share": float(positive.groupby("block")["loss_reduction"].sum().max() / total),
        "max_day_share": float(positive.groupby("day")["loss_reduction"].sum().max() / total),
    }


def decide(primary: dict[str, Any], by_block: dict[str, Any], leave_one_out: dict[str, Any], boot: dict[str, Any], audit: dict[str, Any], conc: dict[str, Any]) -> dict[str, Any]:
    beta_ci = boot["beta_ci95"]
    mse_ci = boot["mse_improvement_ci95"]
    placebo_ci = boot["model_minus_placebo_loss_reduction_ci95"]
    holm = boot["holm_primary_pvalues"]
    positive_blocks = sum(item["mse_improvement"] > 0 for item in by_block.values())
    positive_loo = sum(item["aggregate"]["mse_improvement"] > 0 for item in leave_one_out.values())
    concentration_ok = (
        conc.get("max_block_share") is not None
        and conc["max_block_share"] <= 0.30
        and conc.get("max_day_share") is not None
        and conc["max_day_share"] <= 0.30
    )
    gates = {
        "beta_positive_ci95_above_zero": primary["beta"] > 0 and beta_ci[0] is not None and beta_ci[0] > 0,
        "mse_improvement_positive_ci95_above_zero": primary["mse_improvement"] > 0 and mse_ci[0] is not None and mse_ci[0] > 0,
        "model_beats_circular_placebo_after_holm": placebo_ci[0] is not None and placebo_ci[0] > 0 and holm["model_beats_circular_placebo"] < ALPHA,
        "positive_at_least_4_of_5_blocks": positive_blocks >= 4,
        "positive_at_least_7_of_10_leave_one_out_universes": positive_loo >= 7,
        "concentration_le_30pct": concentration_ok,
        "primary_effects_survive_holm": all(value < ALPHA for value in holm.values()),
        "sample_and_integrity_sufficient": audit["sample_sufficient"] and audit["integrity_sufficient"],
    }
    if not audit["sample_sufficient"] or not audit["integrity_sufficient"]:
        decision = "INCONCLUSIVE CROSS-SECTIONAL DISPERSION AUDIT"
    elif all(gates.values()):
        decision = "DEVELOPMENT DISPERSION RISK SIGNAL DETECTED - PROSPECTIVE HOLDOUT REQUIRED"
    else:
        decision = "CROSS-SECTIONAL DISPERSION HYPOTHESIS REJECTED IN PRIMARY SCOPE"
    return {
        "decision": decision,
        "gates": gates,
        "positive_blocks": positive_blocks,
        "positive_leave_one_out_universes": positive_loo,
    }


def render_markdown(report: dict[str, Any]) -> str:
    primary = report["estimates"]["primary"]
    boot = report["bootstrap"]
    decision = report["decision"]
    lines = [
        "# PH4-A05 - Cross-Sectional Dispersion as a Market-Risk State",
        "",
        f"Generated: `{report['generated_at']}`",
        "",
        f"**Decision:** {decision['decision']}",
        "",
        "## Frozen Design",
        "",
        "- Predictor: standard deviation of ten trailing 2h log returns.",
        "- Outcome: equal-universe realized volatility over the next 2h.",
        "- Chronological calibration/evaluation split inside each block.",
        "- One horizon, no threshold, rank, top-k, or direction.",
        "",
        "## Primary Results",
        "",
        f"- Evaluation events: `{primary['events']}`",
        f"- Equal-block beta: `{primary['beta']}`; CI95 `{boot['beta_ci95']}`",
        f"- MSE improvement: `{primary['mse_improvement']}`; CI95 `{boot['mse_improvement_ci95']}`",
        f"- Model minus circular-placebo loss reduction: `{primary['model_minus_placebo_loss_reduction']}`; CI95 `{boot['model_minus_placebo_loss_reduction_ci95']}`",
        f"- Positive blocks: `{decision['positive_blocks']}/5`",
        f"- Positive leave-one-out universes: `{decision['positive_leave_one_out_universes']}/10`",
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
            "The result concerns risk magnitude only. It does not establish return direction, profit, causal mechanism, or permission to build a bot.",
            "",
        ]
    )
    return "\n".join(lines)


def run_analysis() -> int:
    events, audit = load_raw_events()
    primary_frames = build_model_frames(events, common.ALL_PAIRS) if not events.empty else {}
    if primary_frames:
        primary, by_block = summarize_frames(primary_frames)
        leave_one_out: dict[str, Any] = {}
        for excluded in common.ALL_PAIRS:
            universe = [pair for pair in common.ALL_PAIRS if pair != excluded]
            aggregate, blocks = summarize_frames(build_model_frames(events, universe))
            leave_one_out[excluded] = {"aggregate": aggregate, "by_block": blocks}
        boot, bootstrap_rows = bootstrap(primary_frames)
        conc = concentration(primary_frames)
        decision = decide(primary, by_block, leave_one_out, boot, audit, conc)
    else:
        primary, by_block, leave_one_out, boot, bootstrap_rows, conc = {}, {}, {}, {}, [], {}
        decision = {
            "decision": "INCONCLUSIVE CROSS-SECTIONAL DISPERSION AUDIT",
            "gates": {"sample_and_integrity_sufficient": False},
            "positive_blocks": 0,
            "positive_leave_one_out_universes": 0,
        }

    matrix_rows: list[dict[str, Any]] = []
    for block, metrics in by_block.items():
        matrix_rows.append({"level": "block", "excluded_pair": None, "block": int(block), **metrics})
    for excluded, item in leave_one_out.items():
        matrix_rows.append({"level": "leave_one_out", "excluded_pair": excluded, "block": None, **item["aggregate"]})
    report = {
        "study": "PH4-A05",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "protocol_file": str(PROTOCOL_FILE),
        "mechanics": {
            "horizon_candles": HORIZON_CANDLES,
            "bootstrap_reps": BOOTSTRAP_REPS,
            "seed": RANDOM_SEED,
            "epsilon": EPSILON,
        },
        "audit": audit,
        "estimates": {"primary": primary, "by_block": by_block, "leave_one_out": leave_one_out},
        "bootstrap": boot,
        "concentration": conc,
        "decision": decision,
    }
    markdown = render_markdown(report) if primary else "# PH4-A05\n\n**Decision:** INCONCLUSIVE CROSS-SECTIONAL DISPERSION AUDIT\n"
    html_text = "<!doctype html><html><head><meta charset='utf-8'><title>PH4-A05</title></head><body><pre>" + html.escape(markdown) + "</pre></body></html>"
    common.atomic_write_json(REPORT_JSON, report)
    common.atomic_write_text(REPORT_MD, markdown)
    common.atomic_write_text(REPORT_HTML, html_text)
    common.atomic_write_csv(
        MATRIX_CSV,
        matrix_rows,
        [
            "level", "excluded_pair", "block", "units", "events", "n", "beta",
            "correlation", "mse_model", "mse_baseline", "mse_placebo",
            "mse_improvement", "mae_improvement", "model_minus_placebo_loss_reduction",
            "calibration_beta",
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

