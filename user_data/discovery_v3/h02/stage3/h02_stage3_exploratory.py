#!/usr/bin/env python3
"""Discovery V3 H02 Stage 3 frozen exploratory convergence test.

Reads only the pre-classified Discovery V2 development archive. The H02 July
2026 holdout is explicitly forbidden and is never referenced by this module.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


VERSION = "1.0.0"
SEED = 20260724
BOOTSTRAPS = 1000
COST = 0.003
HOLD_MINUTES = 30
SYMBOLS = [
    "ADAUSDT", "AVAXUSDT", "BNBUSDT", "BTCUSDT", "DOGEUSDT",
    "ETHUSDT", "LINKUSDT", "LTCUSDT", "SOLUSDT", "XRPUSDT",
]
SCRIPT = Path(__file__).resolve()
STAGE_DIR = SCRIPT.parent
ROOT = SCRIPT.parents[4]
V2_RAW = ROOT / "user_data" / "discovery_v2" / "h01" / "d1" / "raw"
H02_HOLDOUT = ROOT / "user_data" / "discovery_v3" / "h02" / "stage2" / "raw"
PLAN = STAGE_DIR / "H02_STAGE3_EXPLORATORY_PLAN.json"
RESULT_JSON = STAGE_DIR / "H02_STAGE3_RESULTS.json"
RESULT_MD = STAGE_DIR / "H02_STAGE3_RESULTS.md"
ASSET_CSV = STAGE_DIR / "H02_STAGE3_ASSET_MATRIX.csv"
BLOCK_CSV = STAGE_DIR / "H02_STAGE3_BLOCK_MATRIX.csv"
QUINTILE_CSV = STAGE_DIR / "H02_STAGE3_QUINTILE_MATRIX.csv"
CONTROL_CSV = STAGE_DIR / "H02_STAGE3_CONTROL_MATRIX.csv"
DECISION_JSON = STAGE_DIR / "H02_STAGE3_FINAL_DECISION.json"
DECISION_MD = STAGE_DIR / "H02_STAGE3_FINAL_DECISION.md"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(clean(payload), ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(rows[0]) if rows else ["empty"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        if rows:
            writer.writerows([clean(row) for row in rows])


def normalize_ms(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="raise").astype("int64")
    return numeric.where(numeric < 10**14, numeric // 1000)


def read_monthly_family(family: str, symbol: str, prefix: str) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    paths = sorted((V2_RAW / family / symbol).rglob("*.zip"))
    if len(paths) != 24:
        raise RuntimeError(f"{family}/{symbol}: expected 24 files, found {len(paths)}")
    for path in paths:
        with zipfile.ZipFile(path) as archive:
            member = archive.namelist()[0]
            frame = pd.read_csv(
                archive.open(member),
                header=None,
                usecols=[0, 1, 4],
                names=["timestamp", f"{prefix}_open", f"{prefix}_close"],
                skiprows=lambda i: i == 0 and family != "spot_klines_5m",
                dtype=str,
            )
        frame["timestamp"] = normalize_ms(frame["timestamp"])
        frame[f"{prefix}_open"] = pd.to_numeric(frame[f"{prefix}_open"], errors="raise")
        frame[f"{prefix}_close"] = pd.to_numeric(frame[f"{prefix}_close"], errors="raise")
        frames.append(frame)
    result = pd.concat(frames, ignore_index=True)
    result = result.drop_duplicates("timestamp").sort_values("timestamp")
    return result


def read_funding(symbol: str) -> tuple[np.ndarray, np.ndarray]:
    times: list[int] = []
    rates: list[float] = []
    paths = sorted((V2_RAW / "usd_m_fundingRate" / symbol).rglob("*.zip"))
    if len(paths) != 24:
        raise RuntimeError(f"funding/{symbol}: expected 24 files, found {len(paths)}")
    for path in paths:
        with zipfile.ZipFile(path) as archive:
            frame = pd.read_csv(archive.open(archive.namelist()[0]), usecols=["calc_time", "last_funding_rate"])
        times.extend(normalize_ms(frame["calc_time"]).tolist())
        rates.extend(pd.to_numeric(frame["last_funding_rate"], errors="raise").tolist())
    order = np.argsort(times)
    return np.asarray(times, dtype=np.int64)[order], np.asarray(rates, dtype=float)[order]


def funding_between(entry: np.ndarray, exit_: np.ndarray, times: np.ndarray, rates: np.ndarray) -> np.ndarray:
    cumulative = np.concatenate([[0.0], np.cumsum(rates)])
    left = np.searchsorted(times, entry, side="left")
    right = np.searchsorted(times, exit_, side="right")
    return cumulative[right] - cumulative[left]


def build_symbol(symbol: str) -> pd.DataFrame:
    spot = read_monthly_family("spot_klines_5m", symbol, "spot")
    perp = read_monthly_family("usd_m_perp_klines_5m", symbol, "perp")
    mark = read_monthly_family("usd_m_markPriceKlines_5m", symbol, "mark")[["timestamp", "mark_close"]]
    index = read_monthly_family("usd_m_indexPriceKlines_5m", symbol, "index")[["timestamp", "index_close"]]
    frame = (
        spot.merge(perp, on="timestamp", how="inner")
        .merge(mark, on="timestamp", how="left")
        .merge(index, on="timestamp", how="left")
    )
    timestamps = frame["timestamp"].to_numpy(dtype=np.int64)
    if np.any(np.diff(timestamps) != 300_000):
        raise RuntimeError(f"{symbol}: development grid is not continuous")
    frame["basis"] = np.log(frame["perp_close"] / frame["spot_close"])
    frame["pseudo_mark_index"] = np.log(frame["mark_close"] / frame["index_close"])
    frame["basis_spot_misaligned_5m"] = np.log(frame["perp_close"] / frame["spot_close"].shift(1))
    frame["spot_signal_return"] = np.log(frame["spot_close"] / frame["spot_open"])
    frame["perp_signal_return"] = np.log(frame["perp_close"] / frame["perp_open"])
    frame["spot_entry"] = frame["spot_open"].shift(-1)
    frame["perp_entry"] = frame["perp_open"].shift(-1)
    frame["spot_exit"] = frame["spot_open"].shift(-7)
    frame["perp_exit"] = frame["perp_open"].shift(-7)
    frame["entry_timestamp"] = frame["timestamp"].shift(-1)
    frame["exit_timestamp"] = frame["timestamp"].shift(-7)
    frame["gross"] = np.log(frame["spot_exit"] / frame["spot_entry"]) - np.log(frame["perp_exit"] / frame["perp_entry"])
    funding_times, funding_rates = read_funding(symbol)
    valid = frame["entry_timestamp"].notna() & frame["exit_timestamp"].notna()
    credits = np.zeros(len(frame), dtype=float)
    credits[valid.to_numpy()] = funding_between(
        frame.loc[valid, "entry_timestamp"].to_numpy(dtype=np.int64),
        frame.loc[valid, "exit_timestamp"].to_numpy(dtype=np.int64),
        funding_times,
        funding_rates,
    )
    frame["funding_credit_short"] = credits
    frame["net"] = frame["gross"] + frame["funding_credit_short"] - COST
    frame["symbol"] = symbol
    frame["datetime"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
    frame["day"] = frame["datetime"].dt.strftime("%Y-%m-%d")
    frame["block"] = np.select(
        [
            frame["datetime"] < pd.Timestamp("2025-01-01", tz="UTC"),
            frame["datetime"] < pd.Timestamp("2025-07-01", tz="UTC"),
            frame["datetime"] < pd.Timestamp("2026-01-01", tz="UTC"),
        ],
        ["2024H2", "2025H1", "2025H2"],
        default="2026H1",
    )
    frame = frame[(frame["datetime"].dt.minute.isin([0, 30])) & frame["gross"].notna()].copy()
    frame["basis_shift_7d"] = np.roll(frame["basis"].to_numpy(), 7 * 48)
    frame["basis_reverse"] = frame["basis"].to_numpy()[::-1]
    return frame


def ols_stats(frame: pd.DataFrame, predictor: str) -> dict[str, Any]:
    needed = [predictor, "spot_signal_return", "perp_signal_return", "gross"]
    data = frame.dropna(subset=needed)
    y = data["gross"].to_numpy(float)
    x = np.column_stack([
        np.ones(len(data)),
        data[predictor].to_numpy(float),
        data["spot_signal_return"].to_numpy(float),
        data["perp_signal_return"].to_numpy(float),
    ])
    beta, _, _, _ = np.linalg.lstsq(x, y, rcond=None)
    residual = y - x @ beta
    dof = max(1, len(y) - x.shape[1])
    sigma2 = float(residual @ residual / dof)
    covariance = sigma2 * np.linalg.pinv(x.T @ x)
    standard_error = float(np.sqrt(max(covariance[1, 1], 0)))
    reduced = x[:, [0, 2, 3]]
    reduced_beta, _, _, _ = np.linalg.lstsq(reduced, y, rcond=None)
    sst = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - float((residual ** 2).sum()) / sst if sst else 0.0
    reduced_residual = y - reduced @ reduced_beta
    reduced_r2 = 1 - float((reduced_residual ** 2).sum()) / sst if sst else 0.0
    z = float(beta[1] / standard_error) if standard_error else 0.0
    pvalue = math.erfc(abs(z) / math.sqrt(2))
    return {
        "n": len(data),
        "coefficient": float(beta[1]),
        "standard_error": standard_error,
        "normal_p_value": pvalue,
        "r2": r2,
        "incremental_r2": r2 - reduced_r2,
        "_x": x,
        "_y": y,
        "_days": data["day"].to_numpy(),
    }


def bootstrap_ols(stats: dict[str, Any], rng: np.random.Generator) -> tuple[float, float]:
    x = stats["_x"]
    y = stats["_y"]
    days = stats["_days"]
    unique, inverse = np.unique(days, return_inverse=True)
    xtx = np.zeros((len(unique), x.shape[1], x.shape[1]))
    xty = np.zeros((len(unique), x.shape[1]))
    for i in range(len(unique)):
        xi = x[inverse == i]
        yi = y[inverse == i]
        xtx[i] = xi.T @ xi
        xty[i] = xi.T @ yi
    draws = np.empty(BOOTSTRAPS)
    for b in range(BOOTSTRAPS):
        indices = rng.integers(0, len(unique), len(unique))
        beta = np.linalg.pinv(xtx[indices].sum(axis=0)) @ xty[indices].sum(axis=0)
        draws[b] = beta[1]
    return tuple(np.quantile(draws, [0.025, 0.975]))


def bootstrap_mean(frame: pd.DataFrame, column: str, rng: np.random.Generator) -> tuple[float, float]:
    grouped = frame.groupby("day")[column].agg(["sum", "count"])
    sums = grouped["sum"].to_numpy(float)
    counts = grouped["count"].to_numpy(float)
    draws = np.empty(BOOTSTRAPS)
    for b in range(BOOTSTRAPS):
        indices = rng.integers(0, len(grouped), len(grouped))
        draws[b] = sums[indices].sum() / counts[indices].sum()
    return tuple(np.quantile(draws, [0.025, 0.975]))


def top_decile(frame: pd.DataFrame, predictor: str) -> pd.DataFrame:
    eligible = frame[frame[predictor] > 0].copy()
    eligible["rank"] = eligible.groupby("symbol")[predictor].rank(pct=True, method="average")
    return eligible[eligible["rank"] > 0.9].copy()


def summarize_slice(frame: pd.DataFrame) -> dict[str, Any]:
    return {
        "observations": len(frame),
        "gross_mean": frame["gross"].mean(),
        "gross_median": frame["gross"].median(),
        "funding_mean": frame["funding_credit_short"].mean(),
        "net_mean": frame["net"].mean(),
        "net_median": frame["net"].median(),
        "win_rate_net": (frame["net"] > 0).mean(),
    }


def analyze() -> dict[str, Any]:
    if not PLAN.exists():
        raise RuntimeError("Frozen exploratory plan is missing")
    if not V2_RAW.exists() or not H02_HOLDOUT.exists():
        raise RuntimeError("Expected development or sealed holdout path is missing")
    frames = [build_symbol(symbol) for symbol in SYMBOLS]
    panel = pd.concat(frames, ignore_index=True)
    if panel["datetime"].max() >= pd.Timestamp("2026-07-01", tz="UTC"):
        raise RuntimeError("Development data crossed into the sealed H02 holdout")
    rng = np.random.default_rng(SEED)
    primary = top_decile(panel, "basis")
    primary_summary = summarize_slice(primary)
    primary_net_ci = bootstrap_mean(primary, "net", rng)
    primary_gross_ci = bootstrap_mean(primary, "gross", rng)
    regression = ols_stats(panel[panel["basis"] > 0], "basis")
    coefficient_ci = bootstrap_ols(regression, rng)
    regression_public = {k: v for k, v in regression.items() if not k.startswith("_")}
    regression_public["bootstrap_ci95"] = coefficient_ci

    asset_rows = []
    for symbol in SYMBOLS:
        part = primary[primary["symbol"] == symbol]
        row = {"symbol": symbol, **summarize_slice(part)}
        asset_rows.append(row)
    block_rows = []
    for block in ["2024H2", "2025H1", "2025H2", "2026H1"]:
        part = primary[primary["block"] == block]
        block_rows.append({"block": block, **summarize_slice(part)})

    positive = panel[panel["basis"] > 0].copy()
    positive["quintile"] = positive.groupby("symbol")["basis"].transform(
        lambda values: pd.qcut(values.rank(method="first"), 5, labels=False) + 1
    )
    quintile_rows = []
    for quintile in range(1, 6):
        part = positive[positive["quintile"] == quintile]
        quintile_rows.append({"quintile": quintile, **summarize_slice(part)})

    control_predictors = {
        "circular_shift_plus_7d": "basis_shift_7d",
        "reverse_time": "basis_reverse",
        "spot_misaligned_plus_5m": "basis_spot_misaligned_5m",
        "mark_index_pseudo_divergence": "pseudo_mark_index",
    }
    control_rows = []
    controls_reproducing = []
    for name, predictor in control_predictors.items():
        sample = top_decile(panel, predictor)
        summary = summarize_slice(sample)
        stats = ols_stats(panel[panel[predictor] > 0], predictor)
        ci = bootstrap_ols(stats, rng)
        reproduces = (
            summary["net_mean"] > 0
            and summary["gross_mean"] >= primary_summary["gross_mean"]
            and stats["coefficient"] > 0
            and ci[0] > 0
            and stats["incremental_r2"] >= 0.0001
        )
        if reproduces:
            controls_reproducing.append(name)
        control_rows.append({
            "control": name,
            **summary,
            "coefficient": stats["coefficient"],
            "coefficient_ci95_lower": ci[0],
            "coefficient_ci95_upper": ci[1],
            "incremental_r2": stats["incremental_r2"],
            "reproduces_primary": reproduces,
        })

    negative = panel[panel["basis"] < 0].copy()
    negative["abs_basis"] = -negative["basis"]
    negative_top = top_decile(negative, "abs_basis")
    negative_top["gross"] = -negative_top["gross"]
    negative_top["funding_credit_short"] = -negative_top["funding_credit_short"]
    negative_top["net"] = negative_top["gross"] + negative_top["funding_credit_short"] - COST
    negative_diagnostic = summarize_slice(negative_top)

    positive_assets = sum(row["net_mean"] > 0 for row in asset_rows)
    positive_blocks = sum(row["net_mean"] > 0 for row in block_rows)
    quintile_means = [row["gross_mean"] for row in quintile_rows]
    monotonic = all(b >= a for a, b in zip(quintile_means, quintile_means[1:]))
    positive_pnl_by_asset = primary.assign(pos=primary["gross"].clip(lower=0)).groupby("symbol")["pos"].sum()
    total_positive = positive_pnl_by_asset.sum()
    concentration = float(positive_pnl_by_asset.max() / total_positive) if total_positive > 0 else 1.0
    gates = {
        "top_decile_net_mean_gt_zero": primary_summary["net_mean"] > 0,
        "top_decile_net_ci95_lower_gt_zero": primary_net_ci[0] > 0,
        "top_decile_gross_mean_ge_0_003": primary_summary["gross_mean"] >= 0.003,
        "coefficient_positive_ci95_lower_gt_zero": regression_public["coefficient"] > 0 and coefficient_ci[0] > 0,
        "incremental_r2_ge_0_0001": regression_public["incremental_r2"] >= 0.0001,
        "positive_assets_ge_7": positive_assets >= 7,
        "positive_blocks_eq_4": positive_blocks == 4,
        "quintile_means_non_decreasing": monotonic,
        "negative_controls_do_not_reproduce": not controls_reproducing,
        "single_asset_positive_pnl_share_le_0_35": concentration <= 0.35,
    }
    decision = "ADVANCE_TO_STAGE4" if all(gates.values()) else "REJECTED"
    result = {
        "project": "Discovery V3",
        "hypothesis_id": "H02",
        "stage": 3,
        "script_version": VERSION,
        "plan_sha256": sha256_file(PLAN),
        "development_period": "2024-07-01/2026-06-30",
        "holdout_state": "SEALED_UNOPENED",
        "holdout_read": False,
        "panel_observations": len(panel),
        "primary": {
            **primary_summary,
            "gross_bootstrap_ci95": primary_gross_ci,
            "net_bootstrap_ci95": primary_net_ci,
            "roundtrip_cost_envelope": COST,
        },
        "regression": regression_public,
        "replication": {
            "positive_assets": positive_assets,
            "asset_count": len(SYMBOLS),
            "positive_blocks": positive_blocks,
            "block_count": 4,
            "max_single_asset_share_positive_gross_pnl": concentration,
        },
        "quintile_gross_means": quintile_means,
        "controls_reproducing_primary": controls_reproducing,
        "negative_basis_non_promotional_diagnostic": negative_diagnostic,
        "gates": gates,
        "decision": decision,
        "no_search_declaration": "One 30-minute horizon, one top-decile slice, one 0.30% envelope; no alternatives computed.",
    }
    write_csv(ASSET_CSV, asset_rows)
    write_csv(BLOCK_CSV, block_rows)
    write_csv(QUINTILE_CSV, quintile_rows)
    write_csv(CONTROL_CSV, control_rows)
    write_json(RESULT_JSON, result)
    failed = [name for name, passed in gates.items() if not passed]
    markdown = (
        "# H02 Stage 3 — Resultados exploratórios\n\n"
        f"**Decisão:** `{decision}`  \n"
        f"**Observações na grade:** {len(panel):,}  \n"
        f"**Eventos no decil superior:** {len(primary):,}  \n"
        f"**Retorno bruto médio:** {primary_summary['gross_mean']:.6%}  \n"
        f"**Retorno líquido médio:** {primary_summary['net_mean']:.6%}  \n"
        f"**IC95% bootstrap líquido:** [{primary_net_ci[0]:.6%}, {primary_net_ci[1]:.6%}]  \n"
        f"**Coeficiente de convergência:** {regression_public['coefficient']:.8f}  \n"
        f"**IC95% bootstrap do coeficiente:** [{coefficient_ci[0]:.8f}, {coefficient_ci[1]:.8f}]  \n"
        f"**R² incremental:** {regression_public['incremental_r2']:.8f}  \n"
        f"**Ativos líquidos positivos:** {positive_assets}/10  \n"
        f"**Blocos líquidos positivos:** {positive_blocks}/4  \n\n"
        "## Gates reprovados\n\n"
        + "\n".join(f"- `{name}`" for name in failed)
        + "\n\nO holdout 2026-07 permanece selado e não foi lido.\n"
    )
    RESULT_MD.write_text(markdown, encoding="utf-8")
    final_decision = {
        "project": "Discovery V3",
        "hypothesis_id": "H02",
        "stage": 3,
        "decision_date": "2026-07-24",
        "decision": decision,
        "failed_gates": failed,
        "holdout_state": "SEALED_UNOPENED",
        "holdout_opened": False,
        "reopening_rule": "Do not change horizon, decile, costs, direction, universe or controls to rescue H02.",
        "next_hypothesis_if_rejected": "H03",
        "results_sha256": sha256_file(RESULT_JSON),
    }
    write_json(DECISION_JSON, final_decision)
    DECISION_MD.write_text(
        "# H02 Stage 3 — Decisão científica\n\n"
        f"**Decisão:** `{decision}`  \n"
        f"**Gates reprovados:** {', '.join(failed) if failed else 'nenhum'}  \n"
        "**Holdout:** `SEALED_UNOPENED`\n",
        encoding="utf-8",
    )
    return result


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--version", action="version", version=VERSION)
    result.add_argument("command", choices=["analyze"])
    return result


def main() -> int:
    args = parser().parse_args()
    if args.command == "analyze":
        result = analyze()
        print(json.dumps({"decision": result["decision"], "result": str(RESULT_JSON)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
