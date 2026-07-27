#!/usr/bin/env python3
"""Discovery V3 H01 development-only exploratory analysis.

The module enforces the Stage-2 development boundary, never computes a holdout
outcome, never searches horizons or thresholds, and implements exactly the
frozen Stage-3 exploratory plan.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import os
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


VERSION = "1.0.0"
HORIZONS = [1, 5, 15, 60]
BOOTSTRAPS = 500
SEED = 20260724
PLACEBO_SHIFT_MINUTES = 7 * 24 * 60
SYMBOLS = [
    "BTCUSD_PERP",
    "ETHUSD_PERP",
    "BNBUSD_PERP",
    "ADAUSD_PERP",
    "LINKUSD_PERP",
    "LTCUSD_PERP",
]

SCRIPT = Path(__file__).resolve()
BASE = SCRIPT.parent
STAGE2 = BASE.parent / "stage2"
MANIFEST = STAGE2 / "H01_STAGE2_MANIFEST.csv"
REPAIR_MANIFEST = STAGE2 / "H01_STAGE2_REPAIR_MANIFEST.csv"
SEAL = STAGE2 / "H01_STAGE2_HOLDOUT_SEAL.json"
NORMALIZED_EVENTS = STAGE2 / "normalized" / "liquidation_events.csv.gz"
PLAN = BASE / "H01_STAGE3_EXPLORATORY_PLAN.json"
RESULT_JSON = BASE / "H01_STAGE3_RESULTS.json"
RESULT_MD = BASE / "H01_STAGE3_RESULTS.md"
HORIZON_MATRIX = BASE / "H01_STAGE3_HORIZON_MATRIX.csv"
ASSET_MATRIX = BASE / "H01_STAGE3_ASSET_MATRIX.csv"
LOG = BASE / "H01_STAGE3_RUN.log"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def log(message: str) -> None:
    line = f"{utc_now()} {message}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, payload: Any) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
    os.replace(temp, path)


def atomic_text(path: Path, payload: str) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(payload, encoding="utf-8", newline="\n")
    os.replace(temp, path)


def atomic_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = sorted({field for row in rows for field in row})
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temp, path)


def timestamp_ms(value: str) -> int:
    number = int(float(value))
    if number > 10**15:
        return number // 1000
    if number < 10**11:
        return number * 1000
    return number


def load_contract() -> tuple[int, int, int]:
    seal = json.loads(SEAL.read_text(encoding="utf-8"))
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    if seal["state"] != "SEALED" or plan["holdout"] != "SEALED":
        raise RuntimeError("Holdout contract is not sealed.")
    if plan["horizons_minutes"] != HORIZONS:
        raise RuntimeError("Code horizons differ from the frozen plan.")
    development_start = int(
        datetime.fromisoformat(
            seal["development"]["start"] + "T00:00:00+00:00"
        ).timestamp()
        * 1000
    )
    development_end = int(
        datetime.fromisoformat(
            seal["development"]["end"] + "T23:59:00+00:00"
        ).timestamp()
        * 1000
    )
    holdout_start = int(
        datetime.fromisoformat(
            seal["historical_holdout"]["start"] + "T00:00:00+00:00"
        ).timestamp()
        * 1000
    )
    if development_end >= holdout_start:
        raise RuntimeError("Development and holdout overlap.")
    return development_start, development_end, holdout_start


def manifest_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in [MANIFEST, REPAIR_MANIFEST]:
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows.extend(csv.DictReader(handle))
    return rows


def zip_rows(
    source: dict[str, str], lower_ms: int, upper_ms: int
) -> Iterable[tuple[int, float, float]]:
    """Yield timestamp/open/close without converting holdout price fields."""
    path = STAGE2 / source["local_path"]
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(members) != 1:
            raise RuntimeError(f"Invalid kline archive: {path}")
        with archive.open(members[0]) as raw:
            reader = csv.reader(
                line.decode("utf-8-sig").strip() for line in raw
            )
            for values in reader:
                if len(values) < 5:
                    continue
                try:
                    stamp = timestamp_ms(values[0])
                except ValueError:  # header row
                    continue
                if stamp < lower_ms or stamp > upper_ms:
                    continue
                yield stamp, float(values[1]), float(values[4])


def load_prices(
    symbol: str,
    family: str,
    rows: list[dict[str, str]],
    lower_ms: int,
    upper_ms: int,
) -> pd.DataFrame:
    observed: dict[int, tuple[float, float]] = {}
    for source in rows:
        if source["symbol"] != symbol or source["family"] != family:
            continue
        for stamp, open_price, close_price in zip_rows(
            source, lower_ms, upper_ms
        ):
            prior = observed.get(stamp)
            if prior is not None and not (
                math.isclose(prior[0], open_price, rel_tol=0, abs_tol=1e-12)
                and math.isclose(prior[1], close_price, rel_tol=0, abs_tol=1e-12)
            ):
                raise RuntimeError(
                    f"Conflicting {family} values for {symbol} at {stamp}"
                )
            observed[stamp] = (open_price, close_price)
    frame = pd.DataFrame.from_dict(
        observed, orient="index", columns=["open", "close"]
    ).sort_index()
    frame.index.name = "minute_ms"
    return frame


def load_events(lower_ms: int, upper_ms: int) -> dict[str, pd.DataFrame]:
    aggregates: dict[str, dict[int, list[float]]] = {
        symbol: defaultdict(lambda: [0.0, 0.0, 0.0]) for symbol in SYMBOLS
    }
    with gzip.open(NORMALIZED_EVENTS, "rt", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            symbol = row["symbol"]
            if symbol not in aggregates:
                continue
            stamp = timestamp_ms(row["time"])
            if stamp < lower_ms or stamp > upper_ms:
                continue
            minute = stamp // 60_000 * 60_000
            quantity = float(row["accumulated_fill_quantity"])
            direction = 1.0 if row["side"].upper() == "BUY" else -1.0
            values = aggregates[symbol][minute]
            values[0] += direction * quantity
            values[1] += abs(quantity)
            values[2] += 1.0
    frames: dict[str, pd.DataFrame] = {}
    for symbol, mapping in aggregates.items():
        frame = pd.DataFrame.from_dict(
            mapping,
            orient="index",
            columns=["net_contracts", "total_contracts", "event_count"],
        ).sort_index()
        frame.index.name = "minute_ms"
        frame = frame[frame["net_contracts"] != 0].copy()
        signed_log = np.sign(frame["net_contracts"]) * np.log1p(
            np.abs(frame["net_contracts"])
        )
        scale = float(signed_log.std(ddof=0))
        if not np.isfinite(scale) or scale <= 0:
            raise RuntimeError(f"Degenerate event-flow scale for {symbol}")
        frame["x_flow"] = (signed_log - float(signed_log.mean())) / scale
        frame["flow_sign"] = np.sign(frame["net_contracts"])
        intensity_rank = frame["total_contracts"].rank(method="first", pct=True)
        frame["intensity_quartile"] = np.minimum(
            4, np.floor(intensity_rank * 4).astype(int) + 1
        )
        frames[symbol] = frame
        log(f"EVENTS {symbol} net_event_minutes={len(frame)}")
    return frames


def ols(y: np.ndarray, x: np.ndarray) -> tuple[np.ndarray, float]:
    beta = np.linalg.lstsq(x, y, rcond=None)[0]
    residual = y - x @ beta
    sse = float(residual @ residual)
    centered = y - y.mean()
    sst = float(centered @ centered)
    r2 = 1.0 - sse / sst if sst > 0 else 0.0
    return beta, r2


def regression_stats(frame: pd.DataFrame) -> dict[str, float]:
    y = frame["forward_return"].to_numpy(float)
    control = frame["event_return"].to_numpy(float)
    flow = frame["x_flow"].to_numpy(float)
    x0 = np.column_stack([np.ones(len(frame)), control])
    x1 = np.column_stack([np.ones(len(frame)), control, flow])
    _, r2_control = ols(y, x0)
    beta, r2_full = ols(y, x1)
    return {
        "coefficient": float(beta[-1]),
        "r2_control": r2_control,
        "r2_full": r2_full,
        "incremental_r2": r2_full - r2_control,
    }


def bootstrap_by_day(frame: pd.DataFrame, rng: np.random.Generator) -> dict[str, Any]:
    matrices: list[tuple[np.ndarray, np.ndarray]] = []
    top_stats: list[tuple[float, int]] = []
    for _, group in frame.groupby("utc_day", sort=True):
        y = group["forward_return"].to_numpy(float)
        x = np.column_stack(
            [
                np.ones(len(group)),
                group["event_return"].to_numpy(float),
                group["x_flow"].to_numpy(float),
            ]
        )
        matrices.append((x.T @ x, x.T @ y))
        top = group[group["intensity_quartile"] == 4]["aligned_return"]
        top_stats.append((float(top.sum()), int(top.count())))
    if len(matrices) < 20:
        raise RuntimeError("Too few UTC days for bootstrap.")
    coefficients: list[float] = []
    top_means: list[float] = []
    count = len(matrices)
    for _ in range(BOOTSTRAPS):
        sample = rng.integers(0, count, size=count)
        xtx = sum((matrices[index][0] for index in sample), np.zeros((3, 3)))
        xty = sum((matrices[index][1] for index in sample), np.zeros(3))
        beta = np.linalg.pinv(xtx) @ xty
        coefficients.append(float(beta[-1]))
        total = sum(top_stats[index][0] for index in sample)
        observations = sum(top_stats[index][1] for index in sample)
        top_means.append(total / observations if observations else float("nan"))
    return {
        "coefficient_ci95": [
            float(np.nanquantile(coefficients, 0.025)),
            float(np.nanquantile(coefficients, 0.975)),
        ],
        "top_quartile_mean_ci95": [
            float(np.nanquantile(top_means, 0.025)),
            float(np.nanquantile(top_means, 0.975)),
        ],
    }


def response_frame(
    events: pd.DataFrame,
    perp: pd.DataFrame,
    horizon: int,
    shift_minutes: int = 0,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for minute, event in events.iterrows():
        analysis_minute = int(minute) + shift_minutes * 60_000
        entry_minute = analysis_minute + 60_000
        exit_minute = analysis_minute + horizon * 60_000
        if (
            analysis_minute not in perp.index
            or entry_minute not in perp.index
            or exit_minute not in perp.index
        ):
            continue
        event_open = float(perp.at[analysis_minute, "open"])
        event_close = float(perp.at[analysis_minute, "close"])
        entry_open = float(perp.at[entry_minute, "open"])
        exit_close = float(perp.at[exit_minute, "close"])
        if min(event_open, event_close, entry_open, exit_close) <= 0:
            continue
        forward = exit_close / entry_open - 1.0
        rows.append(
            {
                "minute_ms": analysis_minute,
                "utc_day": datetime.fromtimestamp(
                    analysis_minute / 1000, tz=timezone.utc
                ).date().isoformat(),
                "x_flow": float(event["x_flow"]),
                "flow_sign": float(event["flow_sign"]),
                "total_contracts": float(event["total_contracts"]),
                "intensity_quartile": int(event["intensity_quartile"]),
                "event_return": event_close / event_open - 1.0,
                "forward_return": forward,
                "aligned_return": float(event["flow_sign"]) * forward,
            }
        )
    return pd.DataFrame(rows)


def pooled_design(frames: list[pd.DataFrame]) -> pd.DataFrame:
    pooled = pd.concat(frames, ignore_index=True)
    return pooled.replace([np.inf, -np.inf], np.nan).dropna()


def run() -> dict[str, Any]:
    lower_ms, upper_ms, holdout_start = load_contract()
    rows = manifest_rows()
    events = load_events(lower_ms, upper_ms)
    perps: dict[str, pd.DataFrame] = {}
    for symbol in SYMBOLS:
        perps[symbol] = load_prices(
            symbol, "perp_1m", rows, lower_ms, upper_ms
        )
        if perps[symbol].index.max() >= holdout_start:
            raise RuntimeError("Holdout price entered development frame.")
        log(f"PRICES {symbol} development_minutes={len(perps[symbol])}")

    rng = np.random.default_rng(SEED)
    horizon_rows: list[dict[str, Any]] = []
    asset_rows: list[dict[str, Any]] = []
    horizon_payload: dict[str, Any] = {}
    development_span = upper_ms - lower_ms + 60_000

    for horizon in HORIZONS:
        real_frames: list[pd.DataFrame] = []
        placebo_frames: list[pd.DataFrame] = []
        per_asset: dict[str, Any] = {}
        for symbol in SYMBOLS:
            real = response_frame(events[symbol], perps[symbol], horizon)
            placebo = response_frame(
                events[symbol],
                perps[symbol],
                horizon,
                shift_minutes=PLACEBO_SHIFT_MINUTES,
            )
            if len(real) < 200 or len(placebo) < 200:
                raise RuntimeError(f"Insufficient event minutes for {symbol}, h={horizon}")
            real["symbol"] = symbol
            placebo["symbol"] = symbol
            elapsed = real["minute_ms"] - lower_ms
            real["time_block"] = np.minimum(
                4, (elapsed * 4 // development_span).astype(int) + 1
            )
            stats = regression_stats(real)
            top = real[real["intensity_quartile"] == 4]["aligned_return"]
            asset = {
                "n": len(real),
                **stats,
                "top_quartile_n": int(top.count()),
                "top_quartile_aligned_mean": float(top.mean()),
            }
            per_asset[symbol] = asset
            asset_rows.append({"horizon": horizon, "symbol": symbol, **asset})
            real_frames.append(real)
            placebo_frames.append(placebo)

        pooled = pooled_design(real_frames)
        placebo_pooled = pooled_design(placebo_frames)
        real_stats = regression_stats(pooled)
        placebo_stats = regression_stats(placebo_pooled)
        bootstrap = bootstrap_by_day(pooled, rng)
        placebo_bootstrap = bootstrap_by_day(placebo_pooled, rng)
        top = pooled[pooled["intensity_quartile"] == 4]["aligned_return"]
        top_mean = float(top.mean())
        block_effects = {
            str(block): float(
                pooled[
                    (pooled["intensity_quartile"] == 4)
                    & (pooled["time_block"] == block)
                ]["aligned_return"].mean()
            )
            for block in range(1, 5)
        }
        positive_assets = sum(
            value["top_quartile_aligned_mean"] > 0 for value in per_asset.values()
        )
        positive_blocks = sum(value > 0 for value in block_effects.values())
        placebo_top = placebo_pooled[
            placebo_pooled["intensity_quartile"] == 4
        ]["aligned_return"]
        placebo_smaller = (
            placebo_stats["coefficient"] < real_stats["coefficient"]
            and float(placebo_top.mean()) < top_mean
        )
        passes = {
            "coefficient_ci_above_zero": bootstrap["coefficient_ci95"][0] > 0,
            "material_top_quartile": top_mean >= 0.001,
            "incremental_r2": real_stats["incremental_r2"] >= 0.0001,
            "cross_asset": positive_assets >= 4,
            "temporal": positive_blocks >= 3,
            "placebo": placebo_smaller,
        }
        screen_pass = all(passes.values())
        payload = {
            "horizon_minutes": horizon,
            "n": len(pooled),
            **real_stats,
            **bootstrap,
            "top_quartile_n": int(top.count()),
            "top_quartile_aligned_mean": top_mean,
            "positive_assets": positive_assets,
            "positive_temporal_blocks": positive_blocks,
            "temporal_block_effects": block_effects,
            "placebo": {
                "n": len(placebo_pooled),
                **placebo_stats,
                **placebo_bootstrap,
                "top_quartile_aligned_mean": float(placebo_top.mean()),
            },
            "screen_components": passes,
            "screen_pass": screen_pass,
            "per_asset": per_asset,
        }
        horizon_payload[str(horizon)] = payload
        horizon_rows.append(
            {
                "horizon": horizon,
                "n": len(pooled),
                "coefficient": real_stats["coefficient"],
                "coefficient_ci_low": bootstrap["coefficient_ci95"][0],
                "coefficient_ci_high": bootstrap["coefficient_ci95"][1],
                "incremental_r2": real_stats["incremental_r2"],
                "top_quartile_aligned_mean": top_mean,
                "positive_assets": positive_assets,
                "positive_temporal_blocks": positive_blocks,
                "placebo_coefficient": placebo_stats["coefficient"],
                "placebo_top_quartile_aligned_mean": float(placebo_top.mean()),
                "screen_pass": screen_pass,
            }
        )
        log(
            f"HORIZON {horizon} n={len(pooled)} coefficient="
            f"{real_stats['coefficient']:.8g} top_q={top_mean:.8g} "
            f"screen_pass={screen_pass}"
        )

    adjacent_pairs = [(1, 5), (5, 15), (15, 60)]
    passing_pairs = [
        list(pair)
        for pair in adjacent_pairs
        if horizon_payload[str(pair[0])]["screen_pass"]
        and horizon_payload[str(pair[1])]["screen_pass"]
    ]
    decision = (
        "PASS_TO_STAGE_4" if passing_pairs else "REJECT_AT_STAGE_3"
    )
    result = {
        "project": "Discovery V3",
        "hypothesis_id": "H01",
        "stage": 3,
        "created_utc": utc_now(),
        "decision": decision,
        "primary_direction": "continuation",
        "development": {
            "start_ms": lower_ms,
            "end_ms": upper_ms,
            "max_analyzed_minute_ms": max(
                int(frame.index.max()) for frame in perps.values()
            ),
        },
        "holdout": {
            "state": "SEALED",
            "start_ms": holdout_start,
            "outcomes_computed": False,
        },
        "fixed_horizons_minutes": HORIZONS,
        "bootstrap": {"unit": "UTC day", "replicates": BOOTSTRAPS, "seed": SEED},
        "placebo_shift_days": 7,
        "horizons": horizon_payload,
        "passing_adjacent_pairs": passing_pairs,
        "plan_sha256": sha256_file(PLAN),
        "normalized_events_sha256": sha256_file(NORMALIZED_EVENTS),
    }
    atomic_csv(HORIZON_MATRIX, horizon_rows)
    atomic_csv(ASSET_MATRIX, asset_rows)
    result["horizon_matrix_sha256"] = sha256_file(HORIZON_MATRIX)
    result["asset_matrix_sha256"] = sha256_file(ASSET_MATRIX)
    atomic_json(RESULT_JSON, result)

    lines = [
        "# H01 — Stage 3 Exploratory Results",
        "",
        f"Decision: **{decision}**",
        "",
        "Primary direction: continuation. Holdout outcomes remained sealed.",
        "",
        "| Horizon | N | Flow coefficient (95% day bootstrap) | Incremental R² | "
        "Top-Q aligned mean | Positive assets | Positive blocks | Placebo top-Q | Pass |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in horizon_rows:
        lines.append(
            f"| {row['horizon']}m | {row['n']} | {row['coefficient']:.8f} "
            f"[{row['coefficient_ci_low']:.8f}, {row['coefficient_ci_high']:.8f}] | "
            f"{row['incremental_r2']:.8f} | "
            f"{row['top_quartile_aligned_mean']:.6%} | "
            f"{row['positive_assets']}/6 | "
            f"{row['positive_temporal_blocks']}/4 | "
            f"{row['placebo_top_quartile_aligned_mean']:.6%} | "
            f"{'yes' if row['screen_pass'] else 'no'} |"
        )
    lines.extend(
        [
            "",
            f"Passing adjacent horizon pairs: {passing_pairs or 'none'}",
            "",
            "No formal p-value, Holm correction, protocol promotion or holdout result "
            "was produced in Stage 3.",
        ]
    )
    atomic_text(RESULT_MD, "\n".join(lines) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Discovery V3 H01 Stage 3 development-only exploration"
    )
    parser.add_argument("command", choices=["analyze"])
    args = parser.parse_args()
    if args.command == "analyze":
        run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
