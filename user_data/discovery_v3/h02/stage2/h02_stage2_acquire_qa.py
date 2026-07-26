#!/usr/bin/env python3
"""Discovery V3 H02 Stage 2: official acquisition and mechanical QA only.

This instrument must not calculate basis, returns, convergence, PnL, correlations,
regressions, or inspect any economic outcome. It reads only timestamps and structure.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import threading
import urllib.parse
import urllib.request
import zipfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any


VERSION = "1.0.0"
SOURCE_BASE = "https://data.binance.vision/"
FUNDING_API = "https://fapi.binance.com/fapi/v1/fundingRate"
START_DATE = date(2026, 7, 1)
END_DATE = date(2026, 7, 23)
SYMBOLS = [
    "ADAUSDT", "AVAXUSDT", "BNBUSDT", "BTCUSDT", "DOGEUSDT",
    "ETHUSDT", "LINKUSDT", "LTCUSDT", "SOLUSDT", "XRPUSDT",
]
FAMILIES = {
    "spot_klines_5m": "data/spot/daily/klines/{symbol}/5m/{symbol}-5m-{day}.zip",
    "usd_m_perp_klines_5m": "data/futures/um/daily/klines/{symbol}/5m/{symbol}-5m-{day}.zip",
    "usd_m_markPriceKlines_5m": "data/futures/um/daily/markPriceKlines/{symbol}/5m/{symbol}-5m-{day}.zip",
    "usd_m_indexPriceKlines_5m": "data/futures/um/daily/indexPriceKlines/{symbol}/5m/{symbol}-5m-{day}.zip",
    "usd_m_premiumIndexKlines_5m": "data/futures/um/daily/premiumIndexKlines/{symbol}/5m/{symbol}-5m-{day}.zip",
}
SCRIPT = Path(__file__).resolve()
STAGE_DIR = SCRIPT.parent
ROOT = SCRIPT.parents[4]
RAW_DIR = STAGE_DIR / "raw"
EVIDENCE_DIR = STAGE_DIR / "evidence"
MANIFEST_PATH = STAGE_DIR / "H02_STAGE2_MANIFEST.csv"
QA_PATH = STAGE_DIR / "H02_STAGE2_QA_MATRIX.csv"
SEAL_PATH = STAGE_DIR / "H02_STAGE2_HOLDOUT_SEAL.json"
PROVENANCE_PATH = STAGE_DIR / "H02_STAGE2_PROVENANCE.json"
REPORT_JSON = STAGE_DIR / "H02_STAGE2_QA_REPORT.json"
REPORT_MD = STAGE_DIR / "H02_STAGE2_QA_REPORT.md"
DECISION_JSON = STAGE_DIR / "H02_STAGE2_FINAL_DECISION.json"
DECISION_MD = STAGE_DIR / "H02_STAGE2_FINAL_DECISION.md"
V2_INVENTORY = ROOT / "DISCOVERY_V2_H01_D1_INVENTORY.csv"
V2_QA = ROOT / "DISCOVERY_V2_H01_D1_QA_MATRIX.csv"
USER_AGENT = "DiscoveryV3-H02-Stage2/1.0 structural-qa-only"
TIMEOUT = 60
WORKERS = 8
CHUNK = 1024 * 1024

MANIFEST_FIELDS = [
    "symbol", "day", "family", "source_url", "checksum_url", "local_path",
    "expected_sha256", "actual_sha256", "size_bytes", "status", "downloaded_utc",
]
QA_FIELDS = [
    "symbol", "day", "family", "zip_valid", "member_count", "schema",
    "row_count", "timestamp_unit", "min_timestamp_utc", "max_timestamp_utc",
    "sorted", "duplicates", "out_of_day_rows", "expected_rows",
    "missing_rows", "irregular_intervals", "qa_status", "notes",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
    os.replace(temp, path)


def atomic_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(payload, encoding="utf-8", newline="\n")
    os.replace(temp, path)


def atomic_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows([{k: row.get(k, "") for k in fields} for row in rows])
    os.replace(temp, path)


def get_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}: {url}")
        return response.read()


def date_range() -> list[date]:
    count = (END_DATE - START_DATE).days + 1
    return [START_DATE + timedelta(days=i) for i in range(count)]


def ensure_seal() -> dict[str, Any]:
    payload = {
        "project": "Discovery V3",
        "hypothesis_id": "H02",
        "state": "SEALED",
        "sealed_before_new_archive_open": True,
        "development_reference": {
            "period": "2024-07-01/2026-06-30",
            "classification": "development_only",
            "location": "user_data/discovery_v2/h01/d1/raw",
            "inventory_sha256": sha256_file(V2_INVENTORY),
            "qa_matrix_sha256": sha256_file(V2_QA),
        },
        "sealed_holdout": {
            "start_utc": "2026-07-01T00:00:00Z",
            "end_utc": "2026-07-23T23:59:59.999Z",
        },
        "qa_scope": [
            "checksums", "zip_structure", "schema", "timestamps", "gaps",
            "duplicates", "continuity", "synchronization",
        ],
        "outcome_calculation_permitted": False,
        "prohibited_during_stage2": [
            "basis", "returns", "convergence", "pnl", "correlation", "regression",
            "funding aggregation", "price statistics",
        ],
        "prospective_replication_still_required_if_positive": True,
    }
    if SEAL_PATH.exists():
        current = json.loads(SEAL_PATH.read_text(encoding="utf-8"))
        for key in ("project", "hypothesis_id", "state", "sealed_holdout"):
            if current.get(key) != payload.get(key):
                raise RuntimeError(f"Existing seal differs at {key}")
        return current
    payload["created_utc"] = utc_now()
    atomic_json(SEAL_PATH, payload)
    return payload


def build_manifest() -> list[dict[str, Any]]:
    ensure_seal()
    rows: list[dict[str, Any]] = []
    for day in date_range():
        day_text = day.isoformat()
        for symbol in SYMBOLS:
            for family, template in FAMILIES.items():
                key = template.format(symbol=symbol, day=day_text)
                url = SOURCE_BASE + key
                local = RAW_DIR / family / symbol / Path(key).name
                rows.append({
                    "symbol": symbol,
                    "day": day_text,
                    "family": family,
                    "source_url": url,
                    "checksum_url": url + ".CHECKSUM",
                    "local_path": local.relative_to(STAGE_DIR).as_posix(),
                    "expected_sha256": "",
                    "actual_sha256": "",
                    "size_bytes": "",
                    "status": "PENDING",
                    "downloaded_utc": "",
                })
    atomic_csv(MANIFEST_PATH, MANIFEST_FIELDS, rows)
    return rows


def load_manifest() -> list[dict[str, Any]]:
    if not MANIFEST_PATH.exists():
        return build_manifest()
    with MANIFEST_PATH.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def download_archive(row: dict[str, Any]) -> dict[str, Any]:
    result = dict(row)
    local = STAGE_DIR / row["local_path"]
    evidence = EVIDENCE_DIR / row["family"] / row["symbol"] / (local.name + ".CHECKSUM")
    checksum_raw = get_bytes(row["checksum_url"])
    expected = checksum_raw.decode("utf-8").strip().split()[0].lower()
    if len(expected) != 64:
        raise RuntimeError(f"Invalid checksum for {row['source_url']}")
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_bytes(checksum_raw)
    local.parent.mkdir(parents=True, exist_ok=True)
    if not local.exists() or sha256_file(local) != expected:
        payload = get_bytes(row["source_url"])
        temp = local.with_suffix(local.suffix + ".tmp")
        temp.write_bytes(payload)
        actual = sha256_file(temp)
        if actual != expected:
            temp.unlink(missing_ok=True)
            raise RuntimeError(f"Checksum mismatch for {row['source_url']}")
        os.replace(temp, local)
    actual = sha256_file(local)
    if actual != expected:
        raise RuntimeError(f"Persisted checksum mismatch for {row['source_url']}")
    result.update({
        "expected_sha256": expected,
        "actual_sha256": actual,
        "size_bytes": local.stat().st_size,
        "status": "VALID",
        "downloaded_utc": utc_now(),
    })
    return result


def acquire_archives() -> list[dict[str, Any]]:
    ensure_seal()
    rows = load_manifest()
    completed: list[dict[str, Any]] = []
    lock = threading.Lock()
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(download_archive, row): row for row in rows}
        for future in as_completed(futures):
            row = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                result = dict(row)
                result["status"] = "FAILED"
                errors.append(f"{row['symbol']} {row['day']} {row['family']}: {exc}")
            with lock:
                completed.append(result)
    completed.sort(key=lambda r: (r["day"], r["symbol"], r["family"]))
    atomic_csv(MANIFEST_PATH, MANIFEST_FIELDS, completed)
    if errors:
        raise RuntimeError(f"{len(errors)} archive downloads failed; first: {errors[0]}")
    return completed


def acquire_funding() -> list[dict[str, Any]]:
    ensure_seal()
    start_ms = int(datetime(2026, 7, 1, tzinfo=timezone.utc).timestamp() * 1000)
    end_ms = int(datetime(2026, 7, 24, tzinfo=timezone.utc).timestamp() * 1000) - 1
    rows: list[dict[str, Any]] = []
    for symbol in SYMBOLS:
        query = urllib.parse.urlencode({
            "symbol": symbol, "startTime": start_ms, "endTime": end_ms, "limit": 1000,
        })
        url = FUNDING_API + "?" + query
        payload = get_bytes(url)
        parsed = json.loads(payload)
        if not isinstance(parsed, list):
            raise RuntimeError(f"Unexpected funding response for {symbol}")
        path = RAW_DIR / "usd_m_fundingRate" / symbol / f"{symbol}-fundingRate-2026-07-01_2026-07-23.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".json.tmp")
        temp.write_bytes(payload)
        os.replace(temp, path)
        rows.append({
            "symbol": symbol,
            "source_url": url,
            "local_path": path.relative_to(STAGE_DIR).as_posix(),
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
            "records": len(parsed),
            "downloaded_utc": utc_now(),
        })
    atomic_json(STAGE_DIR / "H02_STAGE2_FUNDING_MANIFEST.json", rows)
    return rows


def timestamp_to_ms(raw: str) -> tuple[int, str]:
    value = int(float(raw))
    if value >= 10**14:
        return value // 1000, "us"
    return value, "ms"


def iso_ms(value: int) -> str:
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def qa_archive(row: dict[str, Any]) -> dict[str, Any]:
    path = STAGE_DIR / row["local_path"]
    output = {
        "symbol": row["symbol"], "day": row["day"], "family": row["family"],
        "zip_valid": False, "member_count": 0, "schema": "", "row_count": 0,
        "timestamp_unit": "", "min_timestamp_utc": "", "max_timestamp_utc": "",
        "sorted": False, "duplicates": 0, "out_of_day_rows": 0,
        "expected_rows": 288, "missing_rows": "", "irregular_intervals": "",
        "qa_status": "FAIL", "notes": "",
    }
    try:
        with zipfile.ZipFile(path) as archive:
            members = [m for m in archive.infolist() if not m.is_dir()]
            if any(PurePosixPath(m.filename).is_absolute() or ".." in PurePosixPath(m.filename).parts for m in members):
                raise ValueError("unsafe zip member")
            output["zip_valid"] = archive.testzip() is None
            output["member_count"] = len(members)
            if len(members) != 1:
                raise ValueError(f"expected one CSV member, found {len(members)}")
            with archive.open(members[0]) as raw:
                text = (line.decode("utf-8-sig").strip() for line in raw)
                reader = csv.reader(text)
                values: list[int] = []
                unit = ""
                schema = ""
                for index, fields in enumerate(reader):
                    if not fields:
                        continue
                    if index == 0 and not fields[0].lstrip("-").isdigit():
                        schema = "header_plus_" + str(len(fields)) + "_columns"
                        continue
                    if not schema:
                        schema = str(len(fields)) + "_columns_no_header"
                    timestamp, detected = timestamp_to_ms(fields[0])
                    unit = unit or detected
                    values.append(timestamp)
        start = int(datetime.fromisoformat(row["day"]).replace(tzinfo=timezone.utc).timestamp() * 1000)
        end = start + 86_400_000
        unique = set(values)
        output.update({
            "schema": schema,
            "row_count": len(values),
            "timestamp_unit": unit,
            "min_timestamp_utc": iso_ms(min(values)) if values else "",
            "max_timestamp_utc": iso_ms(max(values)) if values else "",
            "sorted": values == sorted(values),
            "duplicates": len(values) - len(unique),
            "out_of_day_rows": sum(not (start <= ts < end) for ts in values),
            "missing_rows": max(0, 288 - len(unique)),
            "irregular_intervals": sum((b - a) != 300_000 for a, b in zip(sorted(unique), sorted(unique)[1:])),
        })
        passed = (
            output["zip_valid"] and output["row_count"] == 288 and output["sorted"]
            and output["duplicates"] == 0 and output["out_of_day_rows"] == 0
            and output["irregular_intervals"] == 0
        )
        output["qa_status"] = "PASS" if passed else "FAIL"
    except Exception as exc:
        output["notes"] = str(exc)
    return output


def qa_funding() -> dict[str, Any]:
    manifest_path = STAGE_DIR / "H02_STAGE2_FUNDING_MANIFEST.json"
    rows = json.loads(manifest_path.read_text(encoding="utf-8"))
    results = []
    for row in rows:
        path = STAGE_DIR / row["local_path"]
        data = json.loads(path.read_text(encoding="utf-8"))
        times = [int(item["fundingTime"]) for item in data]
        results.append({
            "symbol": row["symbol"],
            "records": len(data),
            "sorted": times == sorted(times),
            "duplicates": len(times) - len(set(times)),
            "in_sealed_period": all(
                int(datetime(2026, 7, 1, tzinfo=timezone.utc).timestamp() * 1000)
                <= value
                < int(datetime(2026, 7, 24, tzinfo=timezone.utc).timestamp() * 1000)
                for value in times
            ),
            "sha256": sha256_file(path),
        })
    passed = all(r["records"] > 0 and r["sorted"] and r["duplicates"] == 0 and r["in_sealed_period"] for r in results)
    payload = {"status": "PASS" if passed else "FAIL", "assets": results}
    atomic_json(STAGE_DIR / "H02_STAGE2_FUNDING_QA.json", payload)
    return payload


def run_qa() -> dict[str, Any]:
    ensure_seal()
    rows = load_manifest()
    if not rows or any(r["status"] != "VALID" for r in rows):
        raise RuntimeError("Archive acquisition is incomplete")
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        qa_rows = list(pool.map(qa_archive, rows))
    qa_rows.sort(key=lambda r: (r["day"], r["symbol"], r["family"]))
    atomic_csv(QA_PATH, QA_FIELDS, qa_rows)
    funding = qa_funding()
    expected = len(date_range()) * len(SYMBOLS)
    by_family: dict[str, dict[str, Any]] = {}
    for family in FAMILIES:
        selected = [r for r in qa_rows if r["family"] == family]
        observed = sum(int(r["row_count"]) for r in selected)
        expected_rows = expected * 288
        by_family[family] = {
            "files": len(selected),
            "qa_pass": sum(r["qa_status"] == "PASS" for r in selected),
            "observed_rows": observed,
            "expected_rows": expected_rows,
            "coverage": observed / expected_rows,
        }
    all_archive_pass = all(r["qa_status"] == "PASS" for r in qa_rows)
    spot_perp_sync = min(
        by_family["spot_klines_5m"]["coverage"],
        by_family["usd_m_perp_klines_5m"]["coverage"],
    )
    status = "PASS" if all_archive_pass and funding["status"] == "PASS" and spot_perp_sync >= 0.999 else "FAIL"
    report = {
        "project": "Discovery V3",
        "hypothesis_id": "H02",
        "stage": 2,
        "generated_utc": utc_now(),
        "status": status,
        "outcomes_inspected": False,
        "economic_values_reported": False,
        "archive_objects": len(rows),
        "archive_checksums_valid": sum(r["expected_sha256"] == r["actual_sha256"] and r["status"] == "VALID" for r in rows),
        "archive_qa_pass": sum(r["qa_status"] == "PASS" for r in qa_rows),
        "by_family": by_family,
        "spot_perpetual_sync_lower_bound": spot_perp_sync,
        "funding_qa": funding,
        "holdout": json.loads(SEAL_PATH.read_text(encoding="utf-8")),
        "prohibitions_observed": {
            "basis_calculated": False,
            "returns_calculated": False,
            "convergence_calculated": False,
            "pnl_calculated": False,
            "correlations_calculated": False,
            "regressions_calculated": False,
            "funding_values_aggregated": False,
            "prices_read": False,
            "gaps_filled": False,
        },
    }
    atomic_json(REPORT_JSON, report)
    md = (
        "# H02 Stage 2 — QA mecânico\n\n"
        f"**Status:** `{status}`  \n"
        f"**Arquivos oficiais:** {len(rows)}  \n"
        f"**Checksums válidos:** {report['archive_checksums_valid']}  \n"
        f"**QA estrutural aprovado:** {report['archive_qa_pass']}  \n"
        f"**Sincronização spot/perp:** {spot_perp_sync:.6%}  \n"
        f"**Funding QA:** `{funding['status']}`  \n\n"
        "Nenhum preço, basis, retorno, convergência, PnL ou outcome foi calculado. "
        "O período 2026-07-01 a 2026-07-23 permanece selado.\n"
    )
    atomic_text(REPORT_MD, md)
    decision = {
        "project": "Discovery V3",
        "hypothesis_id": "H02",
        "stage": 2,
        "decision_date": "2026-07-24",
        "decision": "STAGE2_PASS" if status == "PASS" else "STAGE2_FAIL",
        "authorized_next_stage": 3 if status == "PASS" else None,
        "holdout_state": "SEALED_UNOPENED",
        "outcomes_inspected": False,
        "report_sha256": sha256_file(REPORT_JSON),
        "manifest_sha256": sha256_file(MANIFEST_PATH),
        "qa_matrix_sha256": sha256_file(QA_PATH),
        "funding_manifest_sha256": sha256_file(STAGE_DIR / "H02_STAGE2_FUNDING_MANIFEST.json"),
    }
    atomic_json(DECISION_JSON, decision)
    atomic_text(
        DECISION_MD,
        "# H02 Stage 2 — Decisão\n\n"
        f"**Decisão:** `{decision['decision']}`  \n"
        "**Holdout:** `SEALED_UNOPENED`  \n"
        f"**Próxima etapa:** {decision['authorized_next_stage'] or 'bloqueada'}\n",
    )
    provenance = {
        "project": "Discovery V3",
        "hypothesis_id": "H02",
        "stage": 2,
        "generated_utc": utc_now(),
        "official_sources": [SOURCE_BASE, FUNDING_API],
        "script_version": VERSION,
        "script_sha256": sha256_file(SCRIPT),
        "raw_archive_count": len(rows),
        "raw_archive_bytes": sum(int(r["size_bytes"]) for r in rows),
        "holdout_opened": False,
        "outcome_analysis_performed": False,
    }
    atomic_json(PROVENANCE_PATH, provenance)
    return report


def run_all() -> None:
    ensure_seal()
    build_manifest()
    acquire_archives()
    acquire_funding()
    report = run_qa()
    print(json.dumps({"status": report["status"], "report": str(REPORT_JSON)}, indent=2))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--version", action="version", version=VERSION)
    sub = result.add_subparsers(dest="command", required=True)
    sub.add_parser("seal", help="Create or validate the sealed H02 holdout contract.")
    sub.add_parser("inventory", help="Create the official archive manifest without opening data.")
    sub.add_parser("acquire", help="Download and checksum official archives and funding responses.")
    sub.add_parser("qa", help="Run structural/timestamp QA only; no economic values.")
    sub.add_parser("run", help="Seal, inventory, acquire and run structural QA.")
    return result


def main() -> int:
    args = parser().parse_args()
    if args.command == "seal":
        print(json.dumps(ensure_seal(), indent=2))
    elif args.command == "inventory":
        print(json.dumps({"rows": len(build_manifest()), "path": str(MANIFEST_PATH)}, indent=2))
    elif args.command == "acquire":
        archives = acquire_archives()
        funding = acquire_funding()
        print(json.dumps({"archives": len(archives), "funding_assets": len(funding)}, indent=2))
    elif args.command == "qa":
        print(json.dumps(run_qa(), indent=2))
    elif args.command == "run":
        run_all()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
