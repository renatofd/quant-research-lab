#!/usr/bin/env python3
"""H04 Stage 2: acquire official Bybit 5m klines and perform timestamp QA only."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VERSION = "1.0.0"
START_MS = 1719792000000  # 2024-07-01T00:00:00Z
DEV_END_MS = 1782863999999  # 2026-06-30T23:59:59.999Z
END_MS = 1784851199999  # 2026-07-23T23:59:59.999Z
STEP_MS = 300_000
LIMIT = 1000
WORKERS = 8
SYMBOLS = [
    "ADAUSDT", "AVAXUSDT", "BNBUSDT", "BTCUSDT", "DOGEUSDT",
    "ETHUSDT", "LINKUSDT", "LTCUSDT", "SOLUSDT", "XRPUSDT",
]
API = "https://api.bybit.com/v5/market/kline"
SCRIPT = Path(__file__).resolve()
STAGE_DIR = SCRIPT.parent
ROOT = SCRIPT.parents[4]
RAW = STAGE_DIR / "raw" / "bybit_linear_klines_5m"
SEAL = STAGE_DIR / "H04_STAGE2_HOLDOUT_SEAL.json"
MANIFEST = STAGE_DIR / "H04_STAGE2_MANIFEST.csv"
REPORT = STAGE_DIR / "H04_STAGE2_QA_REPORT.json"
REPORT_MD = STAGE_DIR / "H04_STAGE2_QA_REPORT.md"
DECISION = STAGE_DIR / "H04_STAGE2_FINAL_DECISION.json"
DECISION_MD = STAGE_DIR / "H04_STAGE2_FINAL_DECISION.md"
BOUNDARY_MANIFEST = STAGE_DIR / "H04_STAGE2_DEV_BOUNDARY_MANIFEST.csv"
BINANCE_DEV = ROOT / "user_data" / "discovery_v2" / "h01" / "d1" / "raw" / "usd_m_perp_klines_5m"
BINANCE_HOLD = ROOT / "user_data" / "discovery_v3" / "h02" / "stage2" / "raw" / "usd_m_perp_klines_5m"
FIELDS = ["symbol", "chunk", "start_ms", "end_ms", "url", "local_path", "sha256", "bytes", "rows", "min_timestamp", "max_timestamp", "ret_code", "status"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temp, path)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temp, path)


def ensure_seal() -> dict[str, Any]:
    payload = {
        "project": "Discovery V3",
        "hypothesis_id": "H04",
        "state": "SEALED",
        "created_before_bybit_outcome_access": True,
        "development": "2024-07-01T00:00:00Z/2026-06-30T23:59:59.999Z",
        "holdout": "2026-07-01T00:00:00Z/2026-07-23T23:59:59.999Z",
        "leader": "Binance USD-M",
        "follower": "Bybit linear",
        "frequency": "5m",
        "outcome_calculation_permitted": False,
        "qa_only": True,
    }
    if SEAL.exists():
        current = json.loads(SEAL.read_text(encoding="utf-8"))
        if current["holdout"] != payload["holdout"] or current["state"] != "SEALED":
            raise RuntimeError("Existing H04 seal differs")
        return current
    payload["created_utc"] = datetime.now(timezone.utc).isoformat()
    write_json(SEAL, payload)
    return payload


def chunks() -> list[dict[str, Any]]:
    rows = []
    for symbol in SYMBOLS:
        cursor = START_MS
        index = 0
        while cursor <= END_MS:
            end = min(END_MS, cursor + (LIMIT - 1) * STEP_MS)
            query = urllib.parse.urlencode({
                "category": "linear", "symbol": symbol, "interval": "5",
                "start": cursor, "end": end, "limit": LIMIT,
            })
            path = RAW / symbol / f"{index:04d}_{cursor}_{end}.json.gz"
            rows.append({
                "symbol": symbol, "chunk": index, "start_ms": cursor, "end_ms": end,
                "url": API + "?" + query, "local_path": path.relative_to(STAGE_DIR).as_posix(),
                "sha256": "", "bytes": "", "rows": "", "min_timestamp": "",
                "max_timestamp": "", "ret_code": "", "status": "PENDING",
            })
            cursor = end + STEP_MS
            index += 1
    return rows


def fetch(row: dict[str, Any]) -> dict[str, Any]:
    path = STAGE_DIR / row["local_path"]
    result = dict(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: bytes | None = None
    if path.exists():
        with gzip.open(path, "rb") as handle:
            payload = handle.read()
    else:
        for attempt in range(3):
            try:
                request = urllib.request.Request(row["url"], headers={"User-Agent": "DiscoveryV3-H04/1.0"})
                with urllib.request.urlopen(request, timeout=60) as response:
                    payload = response.read()
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(1 + attempt)
        temp = path.with_suffix(".gz.tmp")
        with gzip.open(temp, "wb", compresslevel=6) as handle:
            handle.write(payload or b"")
        os.replace(temp, path)
    data = json.loads(payload or b"{}")
    if data.get("retCode") != 0:
        raise RuntimeError(f"Bybit retCode={data.get('retCode')} {data.get('retMsg')}")
    records = data.get("result", {}).get("list", [])
    times = sorted(int(record[0]) for record in records)
    expected = ((int(row["end_ms"]) - int(row["start_ms"])) // STEP_MS) + 1
    status = "VALID" if len(times) == expected and len(times) == len(set(times)) and all(t % STEP_MS == 0 for t in times) else "FAILED"
    result.update({
        "sha256": sha256(path), "bytes": path.stat().st_size, "rows": len(times),
        "min_timestamp": min(times) if times else "", "max_timestamp": max(times) if times else "",
        "ret_code": data.get("retCode"), "status": status,
    })
    return result


def read_binance_timestamps(symbol: str) -> set[int]:
    values: set[int] = set()
    for base in (BINANCE_DEV, BINANCE_HOLD):
        for path in sorted((base / symbol).rglob("*.zip")):
            with zipfile.ZipFile(path) as archive:
                with archive.open(archive.namelist()[0]) as handle:
                    reader = csv.reader(line.decode("utf-8-sig").strip() for line in handle)
                    for index, fields in enumerate(reader):
                        if index == 0 and not fields[0].isdigit():
                            continue
                        value = int(fields[0])
                        values.add(value // 1000 if value >= 10**14 else value)
    return {v for v in values if START_MS <= v <= END_MS}


def acquire_and_qa() -> dict[str, Any]:
    ensure_seal()
    planned = chunks()
    completed = []
    errors = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(fetch, row): row for row in planned}
        for future in as_completed(futures):
            row = futures[future]
            try:
                completed.append(future.result())
            except Exception as exc:
                failed = dict(row)
                failed["status"] = "FAILED"
                completed.append(failed)
                errors.append(f"{row['symbol']} chunk {row['chunk']}: {exc}")
    completed.sort(key=lambda row: (row["symbol"], int(row["chunk"])))
    write_csv(MANIFEST, completed)
    by_symbol = {}
    expected_grid = set(range(START_MS, END_MS + 1, STEP_MS))
    for symbol in SYMBOLS:
        bybit: set[int] = set()
        for row in completed:
            if row["symbol"] != symbol or row["status"] != "VALID":
                continue
            path = STAGE_DIR / row["local_path"]
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                data = json.load(handle)
            bybit.update(int(record[0]) for record in data["result"]["list"])
        binance = read_binance_timestamps(symbol)
        common = expected_grid & bybit & binance
        by_symbol[symbol] = {
            "expected_rows": len(expected_grid),
            "bybit_rows": len(bybit & expected_grid),
            "binance_rows": len(binance & expected_grid),
            "common_rows": len(common),
            "bybit_coverage": len(bybit & expected_grid) / len(expected_grid),
            "binance_coverage": len(binance & expected_grid) / len(expected_grid),
            "synchronization": len(common) / len(expected_grid),
            "bybit_duplicates": sum(int(row["rows"] or 0) for row in completed if row["symbol"] == symbol and row["status"] == "VALID") - len(bybit),
        }
    all_valid = not errors and all(row["status"] == "VALID" for row in completed)
    sync_pass = all(item["synchronization"] >= 0.999 and item["bybit_duplicates"] == 0 for item in by_symbol.values())
    status = "PASS" if all_valid and sync_pass else "FAIL"
    report = {
        "project": "Discovery V3", "hypothesis_id": "H04", "stage": 2,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": status, "api_responses": len(completed),
        "valid_local_hashes": sum(row["status"] == "VALID" and bool(row["sha256"]) for row in completed),
        "errors": errors, "by_symbol": by_symbol,
        "holdout_state": "SEALED_UNOPENED", "outcomes_inspected": False,
        "economic_statistics_computed": False, "imputation": False,
        "sources": ["https://api.bybit.com/v5/market/kline", "https://data.binance.vision/"],
    }
    write_json(REPORT, report)
    REPORT_MD.write_text(
        "# H04 Stage 2 — QA\n\n"
        f"**Status:** `{status}`  \n"
        f"**Respostas API:** {len(completed)}  \n"
        f"**Respostas válidas/hash local:** {report['valid_local_hashes']}  \n"
        f"**Menor sincronização:** {min(v['synchronization'] for v in by_symbol.values()):.6%}  \n"
        "**Holdout:** `SEALED_UNOPENED`  \n\nNenhum retorno, correlação ou outcome foi calculado.\n",
        encoding="utf-8",
    )
    decision = {
        "project": "Discovery V3", "hypothesis_id": "H04", "stage": 2,
        "decision_date": "2026-07-24", "decision": "STAGE2_PASS" if status == "PASS" else "STAGE2_FAIL",
        "authorized_next_stage": 3 if status == "PASS" else None,
        "holdout_state": "SEALED_UNOPENED", "manifest_sha256": sha256(MANIFEST),
        "report_sha256": sha256(REPORT),
    }
    write_json(DECISION, decision)
    DECISION_MD.write_text(f"# H04 Stage 2 — Decisão\n\n**Decisão:** `{decision['decision']}`  \n**Holdout:** `SEALED_UNOPENED`\n", encoding="utf-8")
    return report


def isolate_development_boundary() -> list[dict[str, Any]]:
    """Re-request only the development side of chunks crossing the sealed boundary."""
    ensure_seal()
    start = 1782792000000
    end = 1782863700000
    rows = []
    for symbol in SYMBOLS:
        query = urllib.parse.urlencode({
            "category": "linear", "symbol": symbol, "interval": "5",
            "start": start, "end": end, "limit": LIMIT,
        })
        path = STAGE_DIR / "boundary" / "development_only" / symbol / f"{start}_{end}.json.gz"
        row = {
            "symbol": symbol, "chunk": "DEV_BOUNDARY", "start_ms": start, "end_ms": end,
            "url": API + "?" + query, "local_path": path.relative_to(STAGE_DIR).as_posix(),
            "sha256": "", "bytes": "", "rows": "", "min_timestamp": "",
            "max_timestamp": "", "ret_code": "", "status": "PENDING",
        }
        rows.append(fetch(row))
    write_csv(BOUNDARY_MANIFEST, rows)
    if any(row["status"] != "VALID" or int(row["rows"]) != 240 for row in rows):
        raise RuntimeError("Development-boundary isolation failed QA")
    return rows


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--version", action="version", version=VERSION)
    result.add_argument("command", choices=["seal", "boundary", "run"])
    return result


def main() -> int:
    args = parser().parse_args()
    if args.command == "seal":
        print(json.dumps(ensure_seal(), indent=2))
    elif args.command == "boundary":
        rows = isolate_development_boundary()
        print(json.dumps({"status": "PASS", "objects": len(rows), "manifest": str(BOUNDARY_MANIFEST)}, indent=2))
    else:
        report = acquire_and_qa()
        print(json.dumps({"status": report["status"], "report": str(REPORT)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
