#!/usr/bin/env python3
"""Discovery V2 H01 preregistered economic research instrument. No trading API."""

from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
import math
import re
import sys
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RAW = HERE / "d1" / "raw"
RESULTS = HERE / "results"
PROTOCOL = HERE / "H01_D2_D4_PREREGISTRATION.json"
D1_RECLASS = HERE / "d1_reclassification" / "D1_RECLASSIFICATION.json"
SEAL = HERE / "H01_EXPERIMENT_SEAL.json"
HOLDOUT_OPEN = HERE / "H01_D3_HOLDOUT_OPENING.json"
ACTUAL_GAP_DATE = date(2026, 6, 29)
STEP = 300
DAY = 86400
WEEK = 7 * DAY
FAMILIES = [
    "spot_klines_5m", "usd_m_perp_klines_5m", "usd_m_markPriceKlines_5m",
    "usd_m_indexPriceKlines_5m", "usd_m_premiumIndexKlines_5m",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_new(path: Path, payload: str) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(path)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def ts(value: str) -> int:
    text = value.replace("Z", "+00:00")
    return int(datetime.fromisoformat(text).timestamp())


def iso(value: int) -> str:
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def normalized(row: list[str]) -> list[str]:
    return [re.sub(r"[^a-z0-9]+", "_", item.strip().lower()).strip("_") for item in row]


def epoch_seconds(raw: str) -> int:
    value = int(raw)
    magnitude = abs(value)
    if magnitude >= 100_000_000_000_000:
        return value // 1_000_000
    if magnitude >= 100_000_000_000:
        return value // 1000
    if magnitude >= 100_000_000:
        return value
    raise ValueError("unsupported timestamp")


def months_between(start: str, end: str) -> set[str]:
    current = datetime.strptime(start, "%Y-%m").date().replace(day=1)
    stop = datetime.strptime(end, "%Y-%m").date().replace(day=1)
    values = set()
    while current <= stop:
        values.add(current.strftime("%Y-%m"))
        current = (current.replace(day=28) + timedelta(days=4)).replace(day=1)
    return values


def read_kline_family(symbol: str, family: str, months: set[str]) -> dict[int, tuple[float, float]]:
    result: dict[int, tuple[float, float]] = {}
    base = RAW / family / symbol
    for archive_path in sorted(base.glob("*/*.zip")):
        if archive_path.parent.name not in months:
            continue
        with zipfile.ZipFile(archive_path) as archive:
            members = [item for item in archive.infolist() if item.filename.lower().endswith(".csv") and not item.is_dir()]
            require(len(members) == 1 and ".." not in PurePosixPath(members[0].filename).parts, f"unsafe archive {archive_path}")
            with archive.open(members[0]) as handle:
                text = (line.decode("utf-8-sig") for line in handle)
                reader = csv.reader(text)
                first = next(reader)
                try:
                    epoch_seconds(first[0]); has_header = False
                except ValueError:
                    has_header = True
                if has_header:
                    header = normalized(first)
                    rows = reader
                else:
                    header = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "trades", "taker_base", "taker_quote", "ignore"]
                    rows = iter([first] + list(reader))
                idx = {name: header.index(name) for name in ("open_time", "open", "close")}
                for row in rows:
                    stamp = epoch_seconds(row[idx["open_time"]])
                    result[stamp] = (float(row[idx["open"]]), float(row[idx["close"]]))
    return result


def read_funding(symbol: str, months: set[str]) -> list[tuple[int, float]]:
    values: list[tuple[int, float]] = []
    base = RAW / "usd_m_fundingRate" / symbol
    for archive_path in sorted(base.glob("*/*.zip")):
        if archive_path.parent.name not in months:
            continue
        with zipfile.ZipFile(archive_path) as archive:
            members = [item for item in archive.infolist() if item.filename.lower().endswith(".csv") and not item.is_dir()]
            require(len(members) == 1, f"unexpected funding archive {archive_path}")
            with archive.open(members[0]) as handle:
                text = (line.decode("utf-8-sig") for line in handle)
                reader = csv.DictReader(text)
                for row in reader:
                    values.append((epoch_seconds(row["calc_time"]), float(row["last_funding_rate"])))
    return sorted(values)


@dataclass
class AssetData:
    symbol: str
    events: list[dict[str, Any]]
    signal_by_time: dict[int, bool]
    common_ts: list[int]
    spot_close: np.ndarray
    perp_close: np.ndarray
    complete_days: set[date]

    def boundary_prices(self, cutoff: int) -> tuple[int, float, float]:
        index = bisect.bisect_right(self.common_ts, cutoff) - 1
        if index < 0:
            raise RuntimeError(f"no boundary price for {self.symbol} at {iso(cutoff)}")
        return self.common_ts[index], float(self.spot_close[index]), float(self.perp_close[index])


def load_asset(symbol: str, months: set[str]) -> AssetData:
    feeds = {family: read_kline_family(symbol, family, months) for family in FAMILIES}
    common = sorted(set.intersection(*(set(feed) for feed in feeds.values())))
    spot = feeds["spot_klines_5m"]
    perp = feeds["usd_m_perp_klines_5m"]
    mark = feeds["usd_m_markPriceKlines_5m"]
    counts: dict[date, int] = {}
    for stamp in common:
        current = datetime.fromtimestamp(stamp, timezone.utc).date()
        counts[current] = counts.get(current, 0) + 1
    complete_days = {current for current, count in counts.items() if count == 288}
    common_set = set(common)
    events: list[dict[str, Any]] = []
    for funding_time, rate in read_funding(symbol, months):
        prior, execution = funding_time - STEP, funding_time + STEP
        if prior not in common_set or execution not in common_set:
            continue
        spot_prior = spot[prior][1]
        perp_prior = perp[prior][1]
        eligible = rate > 0.0 and (perp_prior / spot_prior - 1.0) > 0.0
        events.append({
            "time": funding_time,
            "rate": rate,
            "eligible": eligible,
            "spot_open": spot[execution][0],
            "perp_open": perp[execution][0],
            "mark_close": mark[prior][1],
        })
    return AssetData(
        symbol=symbol,
        events=events,
        signal_by_time={event["time"]: event["eligible"] for event in events},
        common_ts=common,
        spot_close=np.array([spot[stamp][1] for stamp in common], dtype=float),
        perp_close=np.array([perp[stamp][1] for stamp in common], dtype=float),
        complete_days=complete_days,
    )


def segments(start: int, end: int, exclusions: set[date]) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    cursor = start
    for excluded in sorted(exclusions):
        block_start = int(datetime(excluded.year, excluded.month, excluded.day, tzinfo=timezone.utc).timestamp())
        block_end = block_start + DAY - 1
        if block_end < start or block_start > end:
            continue
        if cursor < block_start:
            ranges.append((cursor, min(end, block_start - 1)))
        cursor = max(cursor, block_end + 1)
    if cursor <= end:
        ranges.append((cursor, end))
    return ranges


def signal_for(kind: str, asset: AssetData, event_time: int, all_assets: dict[str, AssetData], next_symbol: str) -> bool:
    if kind == "PRIMARY":
        return asset.signal_by_time.get(event_time, False)
    if kind == "NC_CIRCULAR_30D":
        return asset.signal_by_time.get(event_time - 30 * DAY, False)
    if kind == "NC_CYCLIC_ASSET":
        return all_assets[next_symbol].signal_by_time.get(event_time, False)
    raise ValueError(kind)


def build_episodes(asset: AssetData, all_assets: dict[str, AssetData], start: int, end: int, exclusions: set[date], kind: str, next_symbol: str) -> list[dict[str, Any]]:
    episodes: list[dict[str, Any]] = []
    for segment_start, segment_end in segments(start, end, exclusions):
        position: dict[str, Any] | None = None
        for event in asset.events:
            current = event["time"]
            execution = current + STEP
            if current < segment_start or execution > segment_end:
                continue
            eligible = signal_for(kind, asset, current, all_assets, next_symbol)
            if position is not None:
                position["funding"] += event["rate"] * event["mark_close"] / position["perp_entry"]
                if not eligible:
                    episodes.append(close_episode(asset.symbol, position, current + STEP, event["spot_open"], event["perp_open"], False))
                    position = None
            elif eligible:
                position = {
                    "entry_time": execution,
                    "spot_entry": event["spot_open"],
                    "perp_entry": event["perp_open"],
                    "funding": 0.0,
                }
        if position is not None:
            cutoff, spot_exit, perp_exit = asset.boundary_prices(segment_end)
            if cutoff > position["entry_time"]:
                episodes.append(close_episode(asset.symbol, position, cutoff, spot_exit, perp_exit, True))
    return episodes


def close_episode(symbol: str, position: dict[str, Any], exit_time: int, spot_exit: float, perp_exit: float, forced: bool) -> dict[str, Any]:
    spot_return = spot_exit / position["spot_entry"] - 1.0
    perp_return = (position["perp_entry"] - perp_exit) / position["perp_entry"]
    gross = spot_return + perp_return + position["funding"]
    return {
        "asset": symbol,
        "entry_time": position["entry_time"],
        "exit_time": exit_time,
        "duration_days": max((exit_time - position["entry_time"]) / DAY, STEP / DAY),
        "spot_return": spot_return,
        "perp_return": perp_return,
        "funding_return": position["funding"],
        "gross_return": gross,
        "net_return": gross - 0.006,
        "forced_boundary_exit": forced,
    }


def bootstrap_stats(episodes: list[dict[str, Any]], seed: int = 4101, resamples: int = 10000) -> dict[str, Any]:
    if not episodes:
        return {"n": 0, "mean": None, "ci95": [None, None], "p_one_sided": None, "annualized_committed_capital_return": None}
    weeks = sorted({item["entry_time"] // WEEK for item in episodes})
    sums = np.array([sum(item["net_return"] for item in episodes if item["entry_time"] // WEEK == week) for week in weeks])
    counts = np.array([sum(1 for item in episodes if item["entry_time"] // WEEK == week) for week in weeks])
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(weeks), size=(resamples, len(weeks)))
    means = sums[draws].sum(axis=1) / counts[draws].sum(axis=1)
    values = np.array([item["net_return"] for item in episodes])
    annualized = 365.0 * values.sum() / (2.0 * sum(item["duration_days"] for item in episodes))
    return {
        "n": len(episodes),
        "clusters": len(weeks),
        "mean": float(values.mean()),
        "ci95": [float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))],
        "p_one_sided": float((1 + np.count_nonzero(means <= 0.0)) / (resamples + 1)),
        "annualized_committed_capital_return": float(annualized),
    }


def beta_stats(episodes: list[dict[str, Any]], seed: int = 4101, resamples: int = 10000) -> dict[str, Any]:
    if len(episodes) < 3:
        return {"beta": None, "ci95": [None, None]}
    weeks = sorted({item["entry_time"] // WEEK for item in episodes})
    grouped = []
    for week in weeks:
        subset = [item for item in episodes if item["entry_time"] // WEEK == week]
        x = np.array([item["spot_return"] for item in subset]); y = np.array([item["net_return"] for item in subset])
        grouped.append((len(x), x.sum(), y.sum(), np.square(x).sum(), np.multiply(x, y).sum()))
    arr = np.array(grouped, dtype=float)
    def beta(parts: np.ndarray) -> np.ndarray:
        n = parts[..., 0]; sx = parts[..., 1]; sy = parts[..., 2]; sxx = parts[..., 3]; sxy = parts[..., 4]
        denominator = sxx - sx * sx / n
        return np.where(np.abs(denominator) > 1e-18, (sxy - sx * sy / n) / denominator, np.nan)
    total = arr.sum(axis=0)
    point = float(beta(total))
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(arr), size=(resamples, len(arr)))
    sampled = arr[draws].sum(axis=1)
    values = beta(sampled)
    values = values[np.isfinite(values)]
    return {"beta": point, "ci95": [float(np.quantile(values, 0.025)), float(np.quantile(values, 0.975))]}


def holm(p_values: list[float | None]) -> list[float | None]:
    valid = [(index, value) for index, value in enumerate(p_values) if value is not None]
    ordered = sorted(valid, key=lambda item: item[1])
    adjusted: dict[int, float] = {}
    running = 0.0
    count = len(ordered)
    for rank, (index, value) in enumerate(ordered):
        running = max(running, min(1.0, (count - rank) * value))
        adjusted[index] = running
    return [adjusted.get(index) for index in range(len(p_values))]


def stage_analysis(all_assets: dict[str, AssetData], protocol: dict[str, Any], stage: str, extra_exclusion: date | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    universe = protocol["frozen_universe"]
    window = protocol["data_window"]["development" if stage == "d2" else "historical_holdout"]
    start, end = ts(window[0]), ts(window[1])
    exclusions = {ACTUAL_GAP_DATE}
    if extra_exclusion is not None:
        exclusions.add(extra_exclusion)
    primary: list[dict[str, Any]] = []
    by_asset_episodes: dict[str, list[dict[str, Any]]] = {}
    for index, symbol in enumerate(universe):
        episodes = build_episodes(all_assets[symbol], all_assets, start, end, exclusions, "PRIMARY", universe[(index + 1) % len(universe)])
        by_asset_episodes[symbol] = episodes; primary.extend(episodes)
    aggregate = bootstrap_stats(primary)
    asset_stats = {symbol: bootstrap_stats(by_asset_episodes[symbol]) for symbol in universe}
    asset_adjusted = holm([asset_stats[symbol]["p_one_sided"] for symbol in universe])
    for symbol, adjusted in zip(universe, asset_adjusted): asset_stats[symbol]["holm_p"] = adjusted
    temporal_stats = []
    for block_start, block_end in protocol[stage]["temporal_blocks"]:
        bstart = ts(block_start + "T00:00:00Z"); bend = ts(block_end + "T23:59:59Z")
        block_episodes = []
        for index, symbol in enumerate(universe):
            block_episodes.extend(build_episodes(all_assets[symbol], all_assets, bstart, bend, exclusions, "PRIMARY", universe[(index + 1) % len(universe)]))
        temporal_stats.append({"window": [block_start, block_end], **bootstrap_stats(block_episodes)})
    temporal_adjusted = holm([item["p_one_sided"] for item in temporal_stats])
    for item, adjusted in zip(temporal_stats, temporal_adjusted): item["holm_p"] = adjusted
    controls = []
    for kind in ("NC_CIRCULAR_30D", "NC_CYCLIC_ASSET"):
        control_episodes = []
        for index, symbol in enumerate(universe):
            control_episodes.extend(build_episodes(all_assets[symbol], all_assets, start, end, exclusions, kind, universe[(index + 1) % len(universe)]))
        controls.append({"id": kind, **bootstrap_stats(control_episodes)})
    control_adjusted = holm([item["p_one_sided"] for item in controls])
    for item, adjusted in zip(controls, control_adjusted): item["holm_p"] = adjusted
    beta = beta_stats(primary)
    minimum = protocol[stage]["minimum_completed_episodes_per_asset"]
    sufficient_assets = sum(asset_stats[symbol]["n"] >= minimum for symbol in universe)
    positive_assets = sum((asset_stats[symbol]["mean"] or -math.inf) > 0 for symbol in universe)
    significant_assets = sum((asset_stats[symbol]["holm_p"] or 1.0) < 0.05 and (asset_stats[symbol]["mean"] or -math.inf) > 0 for symbol in universe)
    positive_blocks = sum((item["mean"] or -math.inf) > 0 for item in temporal_stats)
    significant_blocks = sum((item["holm_p"] or 1.0) < 0.05 and (item["mean"] or -math.inf) > 0 for item in temporal_stats)
    control_clean = all(not ((item["holm_p"] or 1.0) < 0.05 and (item["mean"] or -math.inf) > 0) for item in controls)
    beta_ok = beta["beta"] is not None and abs(beta["beta"]) <= 0.10 and beta["ci95"][0] <= 0 <= beta["ci95"][1]
    gates = {
        "sample": sufficient_assets >= 8,
        "aggregate": aggregate["mean"] is not None and aggregate["mean"] > 0 and aggregate["ci95"][0] > 0 and aggregate["p_one_sided"] < 0.05,
        "economic": aggregate["annualized_committed_capital_return"] is not None and aggregate["annualized_committed_capital_return"] >= 0.10,
        "cross_asset": positive_assets >= 8 and significant_assets >= 5,
        "temporal": positive_blocks == 3 and significant_blocks >= 2,
        "negative_controls": control_clean,
        "market_neutrality": beta_ok,
    }
    report = {
        "stage": stage.upper(), "decision": "PASS" if all(gates.values()) else "FAIL", "extra_exclusion": extra_exclusion.isoformat() if extra_exclusion else None,
        "gates": gates, "sample_summary": {"sufficient_assets": sufficient_assets, "positive_assets": positive_assets, "holm_significant_assets": significant_assets},
        "aggregate": aggregate, "market_neutrality": beta, "by_asset": asset_stats, "temporal_blocks": temporal_stats, "negative_controls": controls,
    }
    return report, primary


def markdown_report(title: str, report: dict[str, Any]) -> str:
    lines = [f"# {title}", "", f"Decision: `{report['decision']}`", "", "## Gates", ""]
    lines.extend(f"- {name}: {'PASS' if value else 'FAIL'}" for name, value in report["gates"].items())
    aggregate = report["aggregate"]
    lines += ["", "## Aggregate", "", f"- episodes: {aggregate['n']}", f"- mean net return: {aggregate['mean']}", f"- CI95: {aggregate['ci95']}", f"- one-sided p: {aggregate['p_one_sided']}", f"- annualized committed-capital return: {aggregate['annualized_committed_capital_return']}"]
    return "\n".join(lines) + "\n"


def protocol_and_state() -> tuple[dict[str, Any], dict[str, Any]]:
    protocol = load_json(PROTOCOL); d1 = load_json(D1_RECLASS)
    require(protocol["registration_state"]["outcomes_inspected"] is False, "protocol is not outcome-blind")
    require(d1["d1_global_state"] == "CONDITIONAL_PASS_DOCUMENTED_DATASET_LIMITATION", "D1 is not conditionally admissible")
    require(d1["outcomes_inspected"] is False, "D1 outcomes flag changed")
    return protocol, d1


def seal() -> int:
    protocol, _ = protocol_and_state()
    require(not SEAL.exists(), "experiment is already sealed")
    payload = {
        "program": "Discovery V2", "hypothesis": "V2-H01", "state": "SEALED_BEFORE_OUTCOMES",
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "protocol_version": protocol["version"], "protocol_sha256": sha256(PROTOCOL), "instrument_sha256": sha256(Path(__file__)),
        "d1_reclassification_sha256": sha256(D1_RECLASS), "outcomes_inspected": False, "holdout": "SEALED",
    }
    write_new(SEAL, json.dumps(payload, indent=2) + "\n"); print("SEALED_BEFORE_OUTCOMES"); return 0


def verify_seal() -> dict[str, Any]:
    sealed = load_json(SEAL)
    require(sealed["protocol_sha256"] == sha256(PROTOCOL), "protocol changed after seal")
    require(sealed["instrument_sha256"] == sha256(Path(__file__)), "instrument changed after seal")
    require(sealed["d1_reclassification_sha256"] == sha256(D1_RECLASS), "D1 reclassification changed after seal")
    return sealed


def load_assets(protocol: dict[str, Any], month_start: str, month_end: str) -> dict[str, AssetData]:
    months = months_between(month_start, month_end)
    return {symbol: load_asset(symbol, months) for symbol in protocol["frozen_universe"]}


def run_d2() -> int:
    protocol, _ = protocol_and_state(); verify_seal()
    output = RESULTS / "d2" / "D2_REPORT.json"; require(not output.exists(), "D2 already executed")
    assets = load_assets(protocol, "2024-07", "2025-12")
    report, episodes = stage_analysis(assets, protocol, "d2")
    report.update({"program": "Discovery V2", "hypothesis": "V2-H01", "protocol_sha256": sha256(PROTOCOL), "instrument_sha256": sha256(Path(__file__)), "outcomes_inspected": True, "holdout_opened": False})
    write_new(output, json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    write_new(output.with_suffix(".md"), markdown_report("Discovery V2 H01 — D2", report))
    write_new(output.parent / "D2_EPISODES.csv", episodes_csv(episodes))
    print(report["decision"]); return 0


def episodes_csv(episodes: list[dict[str, Any]]) -> str:
    if not episodes: return ""
    import io
    buffer = io.StringIO(); writer = csv.DictWriter(buffer, fieldnames=list(episodes[0]))
    writer.writeheader()
    for item in episodes:
        row = dict(item); row["entry_time"] = iso(row["entry_time"]); row["exit_time"] = iso(row["exit_time"]); writer.writerow(row)
    return buffer.getvalue()


def run_d3_d4() -> int:
    protocol, _ = protocol_and_state(); sealed = verify_seal()
    d2_path = RESULTS / "d2" / "D2_REPORT.json"; require(d2_path.is_file(), "D2 must exist")
    d2 = load_json(d2_path)
    require(not HOLDOUT_OPEN.exists(), "holdout was already opened")
    opening = {
        "program": "Discovery V2", "hypothesis": "V2-H01", "state": "HISTORICAL_HOLDOUT_OPENED_ONCE",
        "opened_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "protocol_sha256": sealed["protocol_sha256"],
        "instrument_sha256": sealed["instrument_sha256"], "d2_report_sha256": sha256(d2_path), "protocol_changes_after_d2": False,
    }
    write_new(HOLDOUT_OPEN, json.dumps(opening, indent=2) + "\n")
    assets = load_assets(protocol, "2024-07", "2026-06")
    d3, episodes = stage_analysis(assets, protocol, "d3")
    d3.update({"program": "Discovery V2", "hypothesis": "V2-H01", "holdout_opened_once": True, "protocol_sha256": sha256(PROTOCOL), "instrument_sha256": sha256(Path(__file__))})
    d3_path = RESULTS / "d3" / "D3_REPORT.json"
    write_new(d3_path, json.dumps(d3, indent=2, ensure_ascii=False) + "\n"); write_new(d3_path.with_suffix(".md"), markdown_report("Discovery V2 H01 — D3", d3)); write_new(d3_path.parent / "D3_EPISODES.csv", episodes_csv(episodes))

    complete_days = set.intersection(*(asset.complete_days for asset in assets.values()))
    start_day, end_day = date(2024, 7, 1), date(2026, 6, 30)
    candidates = sorted(day for day in complete_days if start_day <= day <= end_day and day != ACTUAL_GAP_DATE)
    primary_final = "CONFIRMED_READY_FOR_PROSPECTIVE_CONFIRMATION" if d2["decision"] == "PASS" and d3["decision"] == "PASS" else "REJECTED"
    rows = []
    changed = False
    for candidate in candidates:
        trial_d2, _ = stage_analysis(assets, protocol, "d2", candidate)
        trial_d3, _ = stage_analysis(assets, protocol, "d3", candidate)
        trial_final = "CONFIRMED_READY_FOR_PROSPECTIVE_CONFIRMATION" if trial_d2["decision"] == "PASS" and trial_d3["decision"] == "PASS" else "REJECTED"
        flip = trial_d2["decision"] != d2["decision"] or trial_d3["decision"] != d3["decision"] or trial_final != primary_final
        changed = changed or flip
        rows.append({"excluded_utc_day": candidate.isoformat(), "d2": trial_d2["decision"], "d3": trial_d3["decision"], "final": trial_final, "decision_flip": flip})
    final = "INCONCLUSIVE" if changed else primary_final
    d4 = {
        "program": "Discovery V2", "hypothesis": "V2-H01", "stage": "D4", "decision": "FAIL_DEPENDENCE" if changed else "PASS_STABLE",
        "primary_d2": d2["decision"], "primary_d3": d3["decision"], "primary_final": primary_final,
        "eligible_matched_days": len(candidates), "tested_matched_days": len(rows), "any_decision_flip": changed,
        "final_scientific_decision": final, "bot_authorized": False,
        "prospective_confirmation_required": final == "CONFIRMED_READY_FOR_PROSPECTIVE_CONFIRMATION",
    }
    d4_path = RESULTS / "d4" / "D4_REPORT.json"
    write_new(d4_path, json.dumps(d4, indent=2) + "\n")
    write_new(d4_path.with_suffix(".md"), "# Discovery V2 H01 — D4\n\n" + f"Decision: `{d4['decision']}`\n\nMatched UTC days tested: {len(rows)}\n\nAny decision flip: {changed}\n\nFinal H01 decision: `{final}`\n")
    import io
    buffer = io.StringIO(); writer = csv.DictWriter(buffer, fieldnames=list(rows[0]) if rows else ["excluded_utc_day", "d2", "d3", "final", "decision_flip"]); writer.writeheader(); writer.writerows(rows)
    write_new(d4_path.parent / "D4_MATCHED_BLOCK_SENSITIVITY.csv", buffer.getvalue())
    print(final); return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="V2-H01 frozen cash-and-carry research instrument; never places orders.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seal", help="Freeze protocol and instrument hashes before outcomes")
    sub.add_parser("run-d2", help="Run development stage only; holdout remains sealed")
    sub.add_parser("run-d3-d4", help="Open holdout once, run holdout and mandatory matched-block sensitivity")
    args = parser.parse_args()
    return {"seal": seal, "run-d2": run_d2, "run-d3-d4": run_d3_d4}[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())
