#!/usr/bin/env python3
"""Execute the single frozen H04 5-minute cross-exchange leadership screen."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


VERSION = "1.0.0"
DEV_END = 1782863999999
COST = 0.0015
BOOTSTRAPS = 1000
SEED = 20260724
SYMBOLS = ["ADAUSDT", "AVAXUSDT", "BNBUSDT", "BTCUSDT", "DOGEUSDT", "ETHUSDT", "LINKUSDT", "LTCUSDT", "SOLUSDT", "XRPUSDT"]
SCRIPT = Path(__file__).resolve()
STAGE = SCRIPT.parent
ROOT = SCRIPT.parents[4]
BINANCE = ROOT / "user_data" / "discovery_v2" / "h01" / "d1" / "raw" / "usd_m_perp_klines_5m"
BYBIT_STAGE2 = ROOT / "user_data" / "discovery_v3" / "h04" / "stage2"
MANIFEST = BYBIT_STAGE2 / "H04_STAGE2_MANIFEST.csv"
BOUNDARY = BYBIT_STAGE2 / "H04_STAGE2_DEV_BOUNDARY_MANIFEST.csv"
PLAN = STAGE / "H04_STAGE3_EXPLORATORY_PLAN.json"
RESULT = STAGE / "H04_STAGE3_RESULTS.json"
RESULT_MD = STAGE / "H04_STAGE3_RESULTS.md"
ASSET = STAGE / "H04_STAGE3_ASSET_MATRIX.csv"
BLOCK = STAGE / "H04_STAGE3_BLOCK_MATRIX.csv"
CONTROL = STAGE / "H04_STAGE3_CONTROL_MATRIX.csv"
DECISION = STAGE / "H04_STAGE3_FINAL_DECISION.json"
DECISION_MD = STAGE / "H04_STAGE3_FINAL_DECISION.md"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(safe(payload), ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows([safe(row) for row in rows])


def read_binance(symbol: str) -> pd.DataFrame:
    frames = []
    paths = sorted((BINANCE / symbol).rglob("*.zip"))
    if len(paths) != 24:
        raise RuntimeError(f"{symbol}: expected 24 Binance files")
    for path in paths:
        with zipfile.ZipFile(path) as archive:
            frame = pd.read_csv(
                archive.open(archive.namelist()[0]), usecols=["open_time", "open", "close"],
                dtype={"open_time": "int64", "open": "float64", "close": "float64"},
            )
        frame.columns = ["timestamp", "binance_open", "binance_close"]
        frames.append(frame)
    return pd.concat(frames, ignore_index=True).drop_duplicates("timestamp").sort_values("timestamp")


def manifest_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_bybit(symbol: str) -> pd.DataFrame:
    rows = [
        row for row in manifest_rows(MANIFEST)
        if row["symbol"] == symbol and int(row["end_ms"]) <= DEV_END and row["status"] == "VALID"
    ]
    rows += [row for row in manifest_rows(BOUNDARY) if row["symbol"] == symbol and row["status"] == "VALID"]
    records: list[tuple[int, float, float]] = []
    for row in rows:
        path = BYBIT_STAGE2 / row["local_path"]
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            data = json.load(handle)
        for item in data["result"]["list"]:
            records.append((int(item[0]), float(item[1]), float(item[4])))
    frame = pd.DataFrame(records, columns=["timestamp", "bybit_open", "bybit_close"])
    frame = frame.drop_duplicates("timestamp").sort_values("timestamp")
    if len(frame) != 210240 or frame["timestamp"].max() > DEV_END:
        raise RuntimeError(f"{symbol}: development isolation failed, rows={len(frame)}")
    return frame


def build_symbol(symbol: str) -> pd.DataFrame:
    frame = read_binance(symbol).merge(read_bybit(symbol), on="timestamp", how="inner")
    if len(frame) != 210240 or np.any(np.diff(frame["timestamp"].to_numpy()) != 300_000):
        raise RuntimeError(f"{symbol}: synchronized development grid failed")
    frame["binance_return"] = np.log(frame["binance_close"] / frame["binance_open"])
    frame["bybit_return"] = np.log(frame["bybit_close"] / frame["bybit_open"])
    frame["bybit_next"] = np.log(frame["bybit_open"].shift(-2) / frame["bybit_open"].shift(-1))
    frame["binance_next"] = np.log(frame["binance_open"].shift(-2) / frame["binance_open"].shift(-1))
    frame["binance_shift_7d"] = np.roll(frame["binance_return"].to_numpy(), 7 * 288)
    frame["binance_reverse"] = frame["binance_return"].to_numpy()[::-1]
    frame["binance_lag_minus_5m"] = frame["binance_return"].shift(1)
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
    return frame.dropna(subset=["bybit_next", "binance_next"]).copy()


def regression(frame: pd.DataFrame, predictor: str, outcome: str, contemporaneous: str) -> dict[str, Any]:
    data = frame.dropna(subset=[predictor, outcome, contemporaneous])
    y = data[outcome].to_numpy(float)
    x = np.column_stack([np.ones(len(data)), data[predictor].to_numpy(float), data[contemporaneous].to_numpy(float)])
    beta = np.linalg.lstsq(x, y, rcond=None)[0]
    residual = y - x @ beta
    dof = max(1, len(y) - 3)
    covariance = (residual @ residual / dof) * np.linalg.pinv(x.T @ x)
    se = float(np.sqrt(max(covariance[1, 1], 0)))
    reduced = x[:, [0, 2]]
    rb = np.linalg.lstsq(reduced, y, rcond=None)[0]
    sst = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - float((residual ** 2).sum()) / sst
    rr = y - reduced @ rb
    rr2 = 1 - float((rr ** 2).sum()) / sst
    z = float(beta[1] / se) if se else 0.0
    return {
        "n": len(data), "coefficient": float(beta[1]), "standard_error": se,
        "normal_p_value": math.erfc(abs(z) / math.sqrt(2)), "r2": r2,
        "incremental_r2": r2 - rr2, "_x": x, "_y": y, "_days": data["day"].to_numpy(),
    }


def bootstrap_coefficient(stats: dict[str, Any], rng: np.random.Generator) -> tuple[float, float]:
    x, y, days = stats["_x"], stats["_y"], stats["_days"]
    unique, inverse = np.unique(days, return_inverse=True)
    xtx = np.zeros((len(unique), x.shape[1], x.shape[1]))
    xty = np.zeros((len(unique), x.shape[1]))
    for i in range(len(unique)):
        xi, yi = x[inverse == i], y[inverse == i]
        xtx[i], xty[i] = xi.T @ xi, xi.T @ yi
    draws = np.empty(BOOTSTRAPS)
    for i in range(BOOTSTRAPS):
        chosen = rng.integers(0, len(unique), len(unique))
        draws[i] = (np.linalg.pinv(xtx[chosen].sum(axis=0)) @ xty[chosen].sum(axis=0))[1]
    return tuple(np.quantile(draws, [0.025, 0.975]))


def economic_slice(frame: pd.DataFrame, predictor: str, outcome: str) -> pd.DataFrame:
    data = frame.dropna(subset=[predictor, outcome]).copy()
    data["rank"] = data.groupby("symbol")[predictor].transform(lambda values: values.abs().rank(pct=True))
    data = data[data["rank"] > 0.9].copy()
    data["gross"] = np.sign(data[predictor]) * data[outcome]
    data["net"] = data["gross"] - COST
    return data


def summary(frame: pd.DataFrame) -> dict[str, Any]:
    return {
        "observations": len(frame), "gross_mean": frame["gross"].mean(),
        "gross_median": frame["gross"].median(), "net_mean": frame["net"].mean(),
        "net_median": frame["net"].median(), "net_win_rate": (frame["net"] > 0).mean(),
    }


def bootstrap_mean(frame: pd.DataFrame, rng: np.random.Generator) -> tuple[float, float]:
    grouped = frame.groupby("day")["net"].agg(["sum", "count"])
    sums, counts = grouped["sum"].to_numpy(float), grouped["count"].to_numpy(float)
    draws = np.empty(BOOTSTRAPS)
    for i in range(BOOTSTRAPS):
        chosen = rng.integers(0, len(grouped), len(grouped))
        draws[i] = sums[chosen].sum() / counts[chosen].sum()
    return tuple(np.quantile(draws, [0.025, 0.975]))


def analyze() -> dict[str, Any]:
    if not PLAN.exists() or not BOUNDARY.exists():
        raise RuntimeError("Frozen plan or isolated development boundary missing")
    panel = pd.concat([build_symbol(symbol) for symbol in SYMBOLS], ignore_index=True)
    if panel["timestamp"].max() > DEV_END:
        raise RuntimeError("H04 holdout access guard triggered")
    rng = np.random.default_rng(SEED)
    primary_sample = economic_slice(panel, "binance_return", "bybit_next")
    primary = summary(primary_sample)
    net_ci = bootstrap_mean(primary_sample, rng)
    stats = regression(panel, "binance_return", "bybit_next", "bybit_return")
    coef_ci = bootstrap_coefficient(stats, rng)
    public_stats = {k: v for k, v in stats.items() if not k.startswith("_")}
    public_stats["bootstrap_ci95"] = coef_ci

    asset_rows = [{"symbol": symbol, **summary(primary_sample[primary_sample["symbol"] == symbol])} for symbol in SYMBOLS]
    block_rows = [{"block": block, **summary(primary_sample[primary_sample["block"] == block])} for block in ["2024H2", "2025H1", "2025H2", "2026H1"]]
    positive_assets = sum(row["net_mean"] > 0 for row in asset_rows)
    positive_blocks = sum(row["net_mean"] > 0 for row in block_rows)
    positive_pnl = primary_sample.assign(pos=primary_sample["gross"].clip(lower=0)).groupby("symbol")["pos"].sum()
    concentration = float(positive_pnl.max() / positive_pnl.sum())

    specs = [
        ("reverse_leader", "bybit_return", "binance_next", "binance_return"),
        ("circular_shift_plus_7d", "binance_shift_7d", "bybit_next", "bybit_return"),
        ("reverse_time", "binance_reverse", "bybit_next", "bybit_return"),
        ("lag_minus_5m", "binance_lag_minus_5m", "bybit_next", "bybit_return"),
    ]
    control_rows = []
    reproduced = []
    reverse_coefficient = None
    for name, predictor, outcome, current in specs:
        sample = economic_slice(panel, predictor, outcome)
        econ = summary(sample)
        control_stats = regression(panel, predictor, outcome, current)
        ci = bootstrap_coefficient(control_stats, rng)
        if name == "reverse_leader":
            reverse_coefficient = control_stats["coefficient"]
        is_reproduced = (
            econ["gross_mean"] >= primary["gross_mean"]
            and control_stats["coefficient"] > 0 and ci[0] > 0
            and control_stats["incremental_r2"] >= 0.0001
        )
        if is_reproduced:
            reproduced.append(name)
        control_rows.append({
            "control": name, **econ, "coefficient": control_stats["coefficient"],
            "coefficient_ci95_lower": ci[0], "coefficient_ci95_upper": ci[1],
            "incremental_r2": control_stats["incremental_r2"], "reproduces": is_reproduced,
        })
    gates = {
        "net_mean_gt_zero": primary["net_mean"] > 0,
        "net_bootstrap_ci95_lower_gt_zero": net_ci[0] > 0,
        "gross_mean_ge_0_0015": primary["gross_mean"] >= COST,
        "coefficient_positive_ci95_lower_gt_zero": public_stats["coefficient"] > 0 and coef_ci[0] > 0,
        "incremental_r2_ge_0_0001": public_stats["incremental_r2"] >= 0.0001,
        "positive_assets_ge_7": positive_assets >= 7,
        "positive_blocks_eq_4": positive_blocks == 4,
        "binance_coefficient_gt_reverse_leader": public_stats["coefficient"] > float(reverse_coefficient),
        "placebos_do_not_reproduce": not reproduced,
        "asset_concentration_le_0_35": concentration <= 0.35,
    }
    decision = "ADVANCE_TO_STAGE4_TICK_DATA_REQUIRED" if all(gates.values()) else "REJECTED"
    result = {
        "project": "Discovery V3", "hypothesis_id": "H04", "stage": 3,
        "decision": decision, "development": "2024-07-01/2026-06-30",
        "holdout_state": "SEALED_UNOPENED", "holdout_read": False,
        "panel_observations": len(panel), "primary": {**primary, "net_bootstrap_ci95": net_ci, "cost": COST},
        "regression": public_stats,
        "replication": {"positive_assets": positive_assets, "positive_blocks": positive_blocks, "asset_concentration": concentration},
        "controls_reproducing": reproduced, "gates": gates,
        "plan_sha256": sha256(PLAN),
        "no_search": "One leader, one follower, one 5m horizon, one top decile and one 0.15% cost envelope.",
    }
    write_csv(ASSET, asset_rows)
    write_csv(BLOCK, block_rows)
    write_csv(CONTROL, control_rows)
    write_json(RESULT, result)
    failed = [key for key, passed in gates.items() if not passed]
    RESULT_MD.write_text(
        "# H04 Stage 3 — Resultados\n\n"
        f"**Decisão:** `{decision}`  \n"
        f"**Retorno bruto médio:** {primary['gross_mean']:.6%}  \n"
        f"**Retorno líquido médio:** {primary['net_mean']:.6%}  \n"
        f"**IC95% líquido:** [{net_ci[0]:.6%}, {net_ci[1]:.6%}]  \n"
        f"**Coeficiente Binance:** {public_stats['coefficient']:.8f}  \n"
        f"**IC95% coeficiente:** [{coef_ci[0]:.8f}, {coef_ci[1]:.8f}]  \n"
        f"**R² incremental:** {public_stats['incremental_r2']:.8f}  \n"
        f"**Ativos/blocos líquidos positivos:** {positive_assets}/10; {positive_blocks}/4  \n\n"
        "Gates reprovados:\n\n" + "\n".join(f"- `{key}`" for key in failed)
        + "\n\nO holdout permanece selado.\n",
        encoding="utf-8",
    )
    final = {
        "project": "Discovery V3", "hypothesis_id": "H04", "stage": 3,
        "decision_date": "2026-07-24", "decision": decision, "failed_gates": failed,
        "holdout_state": "SEALED_UNOPENED", "next_hypothesis_if_rejected": "H05",
        "reopening_rule": "Do not alter leader, follower, lag, horizon, cost, decile or universe. Tick data is justified only if every gate passes.",
        "results_sha256": sha256(RESULT),
    }
    write_json(DECISION, final)
    DECISION_MD.write_text(f"# H04 Stage 3 — Decisão\n\n**Decisão:** `{decision}`  \n**Holdout:** `SEALED_UNOPENED`  \n**Gates reprovados:** {', '.join(failed)}\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("command", choices=["analyze"])
    args = parser.parse_args()
    if args.command == "analyze":
        result = analyze()
        print(json.dumps({"decision": result["decision"], "result": str(RESULT)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
