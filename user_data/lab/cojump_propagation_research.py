"""PH4-A04 offline co-jump propagation event study.

The module is isolated from trading and operational infrastructure. Import and
--help do not read data. The analyze command executes the frozen PH4-A04 design.
"""

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
PROTOCOL_FILE = LAB_DIR.parent.parent / "PHASE4_A04_PROTOCOL.md"
REPORT_MD = LAB_DIR / "ph4_a04_cojump_propagation_report.md"
REPORT_JSON = LAB_DIR / "ph4_a04_cojump_propagation_report.json"
REPORT_HTML = LAB_DIR / "ph4_a04_cojump_propagation_report.html"
MATRIX_CSV = LAB_DIR / "ph4_a04_cojump_propagation_matrix.csv"
BOOTSTRAP_CSV = LAB_DIR / "ph4_a04_cojump_propagation_bootstrap.csv"

VOLATILITY_WINDOW = 2016
JUMP_MULTIPLIER = 4.0
MIN_SAME_SIGN_JUMPS = 3
DECLUSTER_CANDLES = 12
BOOTSTRAP_REPS = 1000
RANDOM_SEED = 2026071404
MIN_EVENTS_PER_BLOCK = 30
ALPHA = 0.05
FEE_PER_SIDE = 0.001
SLIPPAGE_PER_SIDE = 0.0005
CONSERVATIVE_COST = 2 * (FEE_PER_SIDE + SLIPPAGE_PER_SIDE)
FEE_ONLY_COST = 2 * FEE_PER_SIDE


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "PH4-A04 offline co-jump propagation audit. No strategy, "
            "backtest, parameter search, or order execution is performed."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("analyze", help="Run the frozen PH4-A04 event study.")
    return parser.parse_args()


def safe_mean(values: Any) -> float | None:
    import numpy as np

    array = np.asarray(list(values), dtype=float)
    array = array[np.isfinite(array)]
    return None if len(array) == 0 else float(np.mean(array))


def safe_median(values: Any) -> float | None:
    import numpy as np

    array = np.asarray(list(values), dtype=float)
    array = array[np.isfinite(array)]
    return None if len(array) == 0 else float(np.median(array))


def controlled_event_beta(frame: Any, outcome: str, placebo: str, contemporaneous: str, placebo_contemporaneous: str) -> float | None:
    import numpy as np

    actual = np.column_stack(
        [np.ones(len(frame), dtype=float), frame[contemporaneous].to_numpy(dtype=float)]
    )
    shifted = np.column_stack(
        [np.zeros(len(frame), dtype=float), frame[placebo_contemporaneous].to_numpy(dtype=float)]
    )
    x = np.vstack([actual, shifted])
    y = np.concatenate(
        [frame[outcome].to_numpy(dtype=float), frame[placebo].to_numpy(dtype=float)]
    )
    fitted = common.ols_fit(y, x, ["event", "contemporaneous_response"])
    return fitted.get("coefficients", {}).get("event", {}).get("beta")


def block_metrics(frame: Any) -> dict[str, Any]:
    import numpy as np

    gross = frame["gross_response"].to_numpy(dtype=float)
    net = gross - CONSERVATIVE_COST
    placebo = frame["placebo_gross_response"].to_numpy(dtype=float)
    event_minus_placebo = gross - placebo
    controlled = controlled_event_beta(
        frame,
        "gross_response",
        "placebo_gross_response",
        "contemporaneous_response",
        "placebo_contemporaneous_response",
    )
    reverse_controlled = controlled_event_beta(
        frame,
        "pre_event_response",
        "placebo_pre_event_response",
        "contemporaneous_response",
        "placebo_contemporaneous_response",
    )
    return {
        "events": int(len(frame)),
        "mean_gross": float(np.mean(gross)),
        "median_gross": float(np.median(gross)),
        "mean_net_fee_only": float(np.mean(gross - FEE_ONLY_COST)),
        "mean_net_conservative": float(np.mean(net)),
        "median_net_conservative": float(np.median(net)),
        "hit_rate_net_conservative": float(np.mean(net > 0)),
        "event_minus_placebo": float(np.mean(event_minus_placebo)),
        "controlled_event_beta": controlled,
        "reverse_controlled_event_beta": reverse_controlled,
    }


def aggregate_blocks(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    fields = [
        "mean_gross",
        "median_gross",
        "mean_net_fee_only",
        "mean_net_conservative",
        "median_net_conservative",
        "hit_rate_net_conservative",
        "event_minus_placebo",
        "controlled_event_beta",
        "reverse_controlled_event_beta",
    ]
    result = {
        "blocks": len(metrics),
        "events_descriptive": int(sum(item["events"] for item in metrics)),
    }
    for field in fields:
        result[field] = safe_mean(
            item[field] for item in metrics if item.get(field) is not None
        )
    return result


def load_events() -> tuple[Any, dict[str, Any]]:
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
        returns = np.log(close / close.shift(1))
        rms = returns.pow(2).rolling(VOLATILITY_WINDOW, min_periods=VOLATILITY_WINDOW).mean().shift(1).pow(0.5)
        jumps = returns.abs() > (JUMP_MULTIPLIER * rms)
        positive = jumps & (returns > 0)
        negative = jumps & (returns < 0)
        candidates: list[tuple[int, int, list[str]]] = []
        ties = 0
        for idx in range(VOLATILITY_WINDOW + 1, len(merged) - 1):
            pos_count = int(positive.iloc[idx].sum())
            neg_count = int(negative.iloc[idx].sum())
            if pos_count < MIN_SAME_SIGN_JUMPS and neg_count < MIN_SAME_SIGN_JUMPS:
                continue
            if pos_count == neg_count:
                ties += 1
                continue
            direction = 1 if pos_count > neg_count else -1
            response_pairs = [pair for pair in common.ALL_PAIRS if not bool(jumps.iloc[idx][pair])]
            if not response_pairs:
                continue
            candidates.append((idx, direction, response_pairs))

        kept: list[tuple[int, int, list[str]]] = []
        last_idx = -DECLUSTER_CANDLES
        for item in candidates:
            if item[0] - last_idx >= DECLUSTER_CANDLES:
                kept.append(item)
                last_idx = item[0]

        eligible_start = VOLATILITY_WINDOW + 1
        eligible_length = (len(merged) - 1) - eligible_start
        shift = max(1, eligible_length // 2)
        rows: list[dict[str, Any]] = []
        for idx, direction, response_pairs in kept:
            shifted_idx = eligible_start + ((idx - eligible_start + shift) % eligible_length)
            if shifted_idx >= len(merged) - 1:
                shifted_idx = len(merged) - 2
            current_response = float(direction * returns.iloc[idx][response_pairs].mean())
            future_response = float(direction * returns.iloc[idx + 1][response_pairs].mean())
            pre_response = float(direction * returns.iloc[idx - 1][response_pairs].mean())
            placebo_current = float(direction * returns.iloc[shifted_idx][response_pairs].mean())
            placebo_future = float(direction * returns.iloc[shifted_idx + 1][response_pairs].mean())
            placebo_pre = float(direction * returns.iloc[shifted_idx - 1][response_pairs].mean())
            record: dict[str, Any] = {
                "block": block_id,
                "date": merged.loc[idx, "date"],
                "day": merged.loc[idx, "date"].floor("D"),
                "direction": direction,
                "jump_count": int(jumps.iloc[idx].sum()),
                "response_count": len(response_pairs),
                "response_pairs": "|".join(response_pairs),
                "gross_response": future_response,
                "contemporaneous_response": current_response,
                "pre_event_response": pre_response,
                "placebo_gross_response": placebo_future,
                "placebo_contemporaneous_response": placebo_current,
                "placebo_pre_event_response": placebo_pre,
            }
            for pair in common.ALL_PAIRS:
                record[f"asset_{pair}"] = (
                    float(direction * returns.iloc[idx + 1][pair]) if pair in response_pairs else np.nan
                )
            rows.append(record)
        block_frame = pd.DataFrame(rows)
        if not block_frame.empty:
            event_frames.append(block_frame)
        block_audit.append(
            {
                "block": block_id,
                "rows_before_sync_by_pair": before_counts,
                "rows_after_sync": int(len(merged)),
                "warmup_rows": VOLATILITY_WINDOW,
                "candidate_events": len(candidates),
                "discarded_ties": ties,
                "declustered_events": len(kept),
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
        item["block"] for item in block_audit if item["declustered_events"] < MIN_EVENTS_PER_BLOCK
    ]
    audit = {
        "windows_file": str(common.WINDOWS_FILE),
        "files": file_audit,
        "blocks": block_audit,
        "hard_failures": hard_failures,
        "insufficient_event_blocks": insufficient_blocks,
        "integrity_sufficient": not hard_failures,
        "sample_sufficient": len(insufficient_blocks) == 0,
        "lookahead_proof": (
            "Jump scale uses returns through t-1 only. Event classification uses return t. "
            "The response uses only return t+1, and no event crosses a frozen block."
        ),
    }
    return events, audit


def estimate(events: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    block_rows: list[dict[str, Any]] = []
    for block, frame in events.groupby("block", sort=True):
        metrics = block_metrics(frame)
        block_rows.append({"level": "block", "block": int(block), "pair": None, **metrics})
    aggregate = aggregate_blocks(block_rows)

    by_asset: dict[str, Any] = {}
    for pair in common.ALL_PAIRS:
        values = events[f"asset_{pair}"].dropna().to_numpy(dtype=float)
        net = values - CONSERVATIVE_COST
        metrics = {
            "observations": int(len(values)),
            "mean_gross": safe_mean(values),
            "mean_net_conservative": safe_mean(net),
            "hit_rate_net_conservative": safe_mean(net > 0),
        }
        by_asset[pair] = metrics
        block_rows.append({"level": "asset", "block": None, "pair": pair, **metrics})
    return {"aggregate": aggregate, "by_block": {str(row["block"]): row for row in block_rows if row["level"] == "block"}, "by_asset": by_asset}, block_rows


def bootstrap(events: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(RANDOM_SEED)
    block_frames = {int(block): frame.copy() for block, frame in events.groupby("block")}
    rows: list[dict[str, Any]] = []
    asset_values: dict[str, list[float]] = defaultdict(list)
    for replicate in range(BOOTSTRAP_REPS):
        metrics: list[dict[str, Any]] = []
        sampled_all: list[Any] = []
        for block, frame in block_frames.items():
            days = list(frame["day"].drop_duplicates())
            sampled_days = rng.choice(days, size=len(days), replace=True)
            sampled = pd.concat([frame[frame["day"] == day] for day in sampled_days], ignore_index=True)
            metrics.append(block_metrics(sampled))
            sampled_all.append(sampled)
        aggregate = aggregate_blocks(metrics)
        combined = pd.concat(sampled_all, ignore_index=True)
        row = {
            "replicate": replicate,
            "mean_net_conservative": aggregate["mean_net_conservative"],
            "event_minus_placebo": aggregate["event_minus_placebo"],
            "controlled_event_beta": aggregate["controlled_event_beta"],
        }
        rows.append(row)
        for pair in common.ALL_PAIRS:
            values = combined[f"asset_{pair}"].dropna().to_numpy(dtype=float) - CONSERVATIVE_COST
            asset_values[pair].append(float(np.mean(values)) if len(values) else float("nan"))

    mean_net = [row["mean_net_conservative"] for row in rows]
    placebo = [row["event_minus_placebo"] for row in rows]
    controlled = [row["controlled_event_beta"] for row in rows]
    raw_primary = {
        "mean_net_positive": common.one_sided_positive_pvalue_from_bootstrap(mean_net),
        "event_minus_placebo_positive": common.one_sided_positive_pvalue_from_bootstrap(placebo),
        "controlled_event_beta_positive": common.one_sided_positive_pvalue_from_bootstrap(controlled),
    }
    raw_asset = {
        pair: common.one_sided_positive_pvalue_from_bootstrap(values)
        for pair, values in asset_values.items()
    }
    return {
        "replicates": BOOTSTRAP_REPS,
        "seed": RANDOM_SEED,
        "unit": "complete UTC event days within block; blocks equally weighted",
        "mean_net_conservative_ci95": common.ci95(mean_net),
        "event_minus_placebo_ci95": common.ci95(placebo),
        "controlled_event_beta_ci95": common.ci95(controlled),
        "raw_primary_pvalues": raw_primary,
        "holm_primary_pvalues": common.holm_adjust(raw_primary),
        "asset_diagnostics": {
            pair: {
                "mean_net_ci95": common.ci95(asset_values[pair]),
                "raw_pvalue": raw_asset[pair],
                "holm_pvalue": common.holm_adjust(raw_asset)[pair],
            }
            for pair in common.ALL_PAIRS
        },
    }, rows


def concentration(events: Any) -> dict[str, Any]:
    import numpy as np
    import pandas as pd

    asset_rows: list[dict[str, Any]] = []
    for _, event in events.iterrows():
        for pair in common.ALL_PAIRS:
            value = event[f"asset_{pair}"]
            if pd.notna(value):
                asset_rows.append(
                    {
                        "pair": pair,
                        "block": int(event["block"]),
                        "day": event["day"],
                        "direction": int(event["direction"]),
                        "net": float(value - CONSERVATIVE_COST),
                    }
                )
    frame = pd.DataFrame(asset_rows)
    positive = frame[frame["net"] > 0]
    total = float(positive["net"].sum()) if not positive.empty else 0.0
    if total <= 0:
        return {"positive_total": total, "max_pair_share": None, "max_block_share": None, "max_day_share": None, "max_direction_share": None}

    def share(column: str) -> float:
        return float(positive.groupby(column)["net"].sum().max() / total)

    return {
        "positive_total": total,
        "max_pair_share": share("pair"),
        "max_block_share": share("block"),
        "max_day_share": share("day"),
        "max_direction_share": share("direction"),
    }


def decide(estimates: dict[str, Any], bootstrap_result: dict[str, Any], audit: dict[str, Any], concentration_result: dict[str, Any]) -> dict[str, Any]:
    aggregate = estimates["aggregate"]
    holm = bootstrap_result["holm_primary_pvalues"]
    positive_blocks = sum(
        row["mean_net_conservative"] > 0 for row in estimates["by_block"].values()
    )
    eligible_assets = [
        row for row in estimates["by_asset"].values() if row["observations"] >= 30
    ]
    positive_assets = sum(row["mean_net_conservative"] > 0 for row in eligible_assets)
    concentration_ok = all(
        concentration_result.get(field) is not None and concentration_result[field] <= 0.30
        for field in ("max_pair_share", "max_block_share", "max_day_share", "max_direction_share")
    )
    gates = {
        "mean_and_median_net_positive": aggregate["mean_net_conservative"] > 0 and aggregate["median_net_conservative"] > 0,
        "mean_net_ci95_above_zero": bootstrap_result["mean_net_conservative_ci95"][0] is not None and bootstrap_result["mean_net_conservative_ci95"][0] > 0,
        "event_beats_placebo_after_holm": bootstrap_result["event_minus_placebo_ci95"][0] is not None and bootstrap_result["event_minus_placebo_ci95"][0] > 0 and holm["event_minus_placebo_positive"] < ALPHA,
        "hit_rate_net_gt_52pct": aggregate["hit_rate_net_conservative"] > 0.52,
        "positive_at_least_4_of_5_blocks": positive_blocks >= 4,
        "positive_at_least_7_of_10_assets": len(eligible_assets) == 10 and positive_assets >= 7,
        "concentration_le_30pct": concentration_ok,
        "controlled_effect_positive_after_holm": bootstrap_result["controlled_event_beta_ci95"][0] is not None and bootstrap_result["controlled_event_beta_ci95"][0] > 0 and holm["controlled_event_beta_positive"] < ALPHA,
        "reverse_time_weaker_than_forward": aggregate["reverse_controlled_event_beta"] is not None and aggregate["controlled_event_beta"] > aggregate["reverse_controlled_event_beta"],
        "sample_and_integrity_sufficient": audit["sample_sufficient"] and audit["integrity_sufficient"],
    }
    if not audit["integrity_sufficient"] or not audit["sample_sufficient"]:
        decision = "INCONCLUSIVE CO-JUMP PROPAGATION AUDIT"
    elif all(gates.values()):
        decision = "DEVELOPMENT CO-JUMP PROPAGATION DETECTED - PROSPECTIVE HOLDOUT REQUIRED"
    else:
        decision = "CO-JUMP PROPAGATION HYPOTHESIS REJECTED IN PRIMARY SCOPE"
    return {
        "decision": decision,
        "gates": gates,
        "positive_blocks": positive_blocks,
        "positive_assets": positive_assets,
        "eligible_assets": len(eligible_assets),
    }


def render_markdown(report: dict[str, Any]) -> str:
    result = report["estimates"]["aggregate"]
    boot = report["bootstrap"]
    decision = report["decision"]
    lines = [
        "# PH4-A04 - Co-Jumps and Cross-Asset Propagation",
        "",
        f"Generated: `{report['generated_at']}`",
        "",
        f"**Decision:** {decision['decision']}",
        "",
        "## Frozen Design",
        "",
        "- Jump: absolute 5m log return above 4x causal seven-day RMS.",
        "- Co-jump: at least three same-sign assets.",
        "- Response: non-jump assets in the next 5m candle.",
        "- Fixed one-hour event de-clustering; no alternate definition tested.",
        "",
        "## Primary Results",
        "",
        f"- Events (descriptive): `{result['events_descriptive']}`",
        f"- Conservative mean net: `{result['mean_net_conservative']}`; CI95 `{boot['mean_net_conservative_ci95']}`",
        f"- Conservative median net: `{result['median_net_conservative']}`",
        f"- Conservative hit rate: `{result['hit_rate_net_conservative']}`",
        f"- Event minus circular placebo: `{result['event_minus_placebo']}`; CI95 `{boot['event_minus_placebo_ci95']}`",
        f"- Controlled event beta: `{result['controlled_event_beta']}`; CI95 `{boot['controlled_event_beta_ci95']}`",
        f"- Positive blocks: `{decision['positive_blocks']}/5`",
        f"- Positive eligible assets: `{decision['positive_assets']}/{decision['eligible_assets']}`",
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
            "This candle-based event study cannot identify order flow or prove causal contagion. All data are development-consumed and no strategy is authorized.",
            "",
        ]
    )
    return "\n".join(lines)


def run_analysis() -> int:
    events, audit = load_events()
    if events.empty:
        estimates = {"aggregate": {}, "by_block": {}, "by_asset": {}}
        bootstrap_result = {}
        bootstrap_rows: list[dict[str, Any]] = []
        concentration_result = {}
        decision = {
            "decision": "INCONCLUSIVE CO-JUMP PROPAGATION AUDIT",
            "gates": {"sample_and_integrity_sufficient": False},
            "positive_blocks": 0,
            "positive_assets": 0,
            "eligible_assets": 0,
        }
        matrix_rows: list[dict[str, Any]] = []
    else:
        estimates, matrix_rows = estimate(events)
        if audit["sample_sufficient"] and audit["integrity_sufficient"]:
            bootstrap_result, bootstrap_rows = bootstrap(events)
            concentration_result = concentration(events)
            decision = decide(estimates, bootstrap_result, audit, concentration_result)
        else:
            bootstrap_result = {}
            bootstrap_rows = []
            concentration_result = concentration(events)
            decision = {
                "decision": "INCONCLUSIVE CO-JUMP PROPAGATION AUDIT",
                "gates": {"sample_and_integrity_sufficient": False},
                "positive_blocks": sum(row["mean_net_conservative"] > 0 for row in estimates["by_block"].values()),
                "positive_assets": 0,
                "eligible_assets": 0,
            }

    report = {
        "study": "PH4-A04",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "protocol_file": str(PROTOCOL_FILE),
        "mechanics": {
            "volatility_window": VOLATILITY_WINDOW,
            "jump_multiplier": JUMP_MULTIPLIER,
            "minimum_same_sign_jumps": MIN_SAME_SIGN_JUMPS,
            "decluster_candles": DECLUSTER_CANDLES,
            "bootstrap_reps": BOOTSTRAP_REPS,
            "seed": RANDOM_SEED,
            "conservative_roundtrip_cost": CONSERVATIVE_COST,
        },
        "audit": audit,
        "estimates": estimates,
        "bootstrap": bootstrap_result,
        "concentration": concentration_result,
        "decision": decision,
    }
    if bootstrap_result:
        markdown = render_markdown(report)
    else:
        markdown = (
            "# PH4-A04 - Co-Jumps and Cross-Asset Propagation\n\n"
            f"**Decision:** {decision['decision']}\n\n"
            f"Insufficient blocks: `{audit.get('insufficient_event_blocks')}`.\n"
        )
    html_text = "<!doctype html><html><head><meta charset='utf-8'><title>PH4-A04</title></head><body><pre>" + html.escape(markdown) + "</pre></body></html>"
    common.atomic_write_json(REPORT_JSON, report)
    common.atomic_write_text(REPORT_MD, markdown)
    common.atomic_write_text(REPORT_HTML, html_text)
    common.atomic_write_csv(
        MATRIX_CSV,
        matrix_rows,
        [
            "level", "block", "pair", "events", "observations", "mean_gross",
            "median_gross", "mean_net_fee_only", "mean_net_conservative",
            "median_net_conservative", "hit_rate_net_conservative",
            "event_minus_placebo", "controlled_event_beta", "reverse_controlled_event_beta",
        ],
    )
    common.atomic_write_csv(
        BOOTSTRAP_CSV,
        bootstrap_rows,
        ["replicate", "mean_net_conservative", "event_minus_placebo", "controlled_event_beta"],
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

