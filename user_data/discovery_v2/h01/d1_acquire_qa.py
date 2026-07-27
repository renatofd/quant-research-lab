#!/usr/bin/env python3
"""Discovery V2 H01 D1 public-data acquisition and structural QA.

This module never computes returns, carry, PnL, correlations, regressions, or
any economic outcome. It downloads only D0-manifested Binance public archives,
validates SHA-256, and inspects ZIP/CSV structure and timestamps.
"""

from __future__ import annotations

import argparse
import calendar
import csv
import hashlib
import json
import os
import re
import stat
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from itertools import chain
from pathlib import Path, PurePosixPath
from typing import Any


VERSION = "1.0.0"
AUTHORIZATION_TEXT = "autorizo, e não precisa mais pedir autorização pra esse tipo de coisa"
PERMANENT_SCOPE = (
    "Free official public data, manifests/checksums, reversible ingestion, "
    "structural QA, and automatic resumption of already approved protocols."
)
SOURCE_BASE = "https://data.binance.vision/"
SOURCE_HOST = "data.binance.vision"
USER_AGENT = "DiscoveryV2-H01-D1/1.0 (official-public-data-structural-qa-only)"
DOWNLOAD_WORKERS = 8
QA_WORKERS = 4
MAX_ATTEMPTS = 3
TIMEOUT_SECONDS = 90
CHUNK_BYTES = 1024 * 1024
FAMILY_ORDER = [
    "spot_klines_5m",
    "usd_m_perp_klines_5m",
    "usd_m_markPriceKlines_5m",
    "usd_m_indexPriceKlines_5m",
    "usd_m_premiumIndexKlines_5m",
    "usd_m_fundingRate",
]
KLINE_FAMILIES = set(FAMILY_ORDER[:-1])
SYMBOLS = [
    "ADAUSDT", "AVAXUSDT", "BNBUSDT", "BTCUSDT", "DOGEUSDT",
    "ETHUSDT", "LINKUSDT", "LTCUSDT", "SOLUSDT", "XRPUSDT",
]

SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parents[3]
D0_MANIFEST = ROOT / "DISCOVERY_V2_H01_D0_MANIFEST.csv"
D0_DECISION = ROOT / "DISCOVERY_V2_H01_D0_SCIENTIFIC_DECISION.json"
BASE_DIR = SCRIPT.parent / "d1"
RAW_DIR = BASE_DIR / "raw"
EVIDENCE_DIR = BASE_DIR / "evidence"
LOG_DIR = BASE_DIR / "logs"
INVENTORY_PATH = ROOT / "DISCOVERY_V2_H01_D1_INVENTORY.csv"
QA_PATH = ROOT / "DISCOVERY_V2_H01_D1_QA_MATRIX.csv"
PROVENANCE_PATH = ROOT / "DISCOVERY_V2_H01_D1_PROVENANCE.json"
HOLDOUT_PATH = ROOT / "DISCOVERY_V2_H01_D1_HOLDOUT.json"
REPORT_JSON_PATH = ROOT / "DISCOVERY_V2_H01_D1_REPORT.json"
REPORT_MD_PATH = ROOT / "DISCOVERY_V2_H01_D1_REPORT.md"
RUN_LOG = LOG_DIR / "run.log"

INVENTORY_FIELDS = [
    "symbol", "month", "family", "source_url", "local_path",
    "expected_size", "actual_size", "expected_sha256", "actual_sha256",
    "download_status", "checksum_match", "attempts", "first_download_utc",
    "completed_utc",
]
QA_FIELDS = [
    "symbol", "month", "family", "zip_valid", "csv_member_count",
    "schema_id", "header_mode", "row_count", "timestamp_unit",
    "min_timestamp_utc", "max_timestamp_utc", "sorted",
    "duplicate_timestamps", "out_of_month_rows", "expected_grid_rows",
    "missing_grid_rows", "irregular_intervals", "numeric_parse_failures",
    "qa_status", "notes",
]


class RunState:
    def __init__(self) -> None:
        self.started = utc_now()
        self.lock = threading.Lock()
        self.request_count = 0
        self.http_status = Counter()
        self.retries: list[dict[str, Any]] = []
        self.errors: list[dict[str, Any]] = []
        self.network_bytes = 0
        self.initial_free = free_space(ROOT)

    def request(self) -> None:
        with self.lock:
            self.request_count += 1

    def status(self, code: int) -> None:
        with self.lock:
            self.http_status[str(code)] += 1

    def add_bytes(self, count: int) -> None:
        with self.lock:
            self.network_bytes += count

    def retry(self, data: dict[str, Any]) -> None:
        with self.lock:
            self.retries.append(data)

    def error(self, data: dict[str, Any]) -> None:
        with self.lock:
            self.errors.append(data)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def free_space(path: Path) -> int | None:
    try:
        return os.statvfs(path).f_bavail * os.statvfs(path).f_frsize
    except (AttributeError, OSError):
        try:
            import shutil
            return shutil.disk_usage(path).free
        except OSError:
            return None


def log(message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = f"{utc_now()} {message}"
    print(line, flush=True)
    with RUN_LOG.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(CHUNK_BYTES)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
    os.replace(temp, path)


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    os.replace(temp, path)


def atomic_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: "" if row.get(key) is None else row.get(key) for key in fields})
    os.replace(temp, path)


def holdout_contract() -> dict[str, Any]:
    return {
        "program": "Discovery V2",
        "hypothesis": "V2-H01",
        "state": "SEALED",
        "sealed_before_any_zip_open": True,
        "development": {
            "start_utc": "2024-07-01T00:00:00Z",
            "end_utc": "2025-12-31T23:59:59.999Z",
        },
        "sealed_historical_holdout": {
            "start_utc": "2026-01-01T00:00:00Z",
            "end_utc": "2026-06-30T23:59:59.999Z",
            "economic_analysis_permitted": False,
        },
        "qa_scope": ["schema", "timestamps", "gaps", "duplicates", "continuity", "synchronization"],
        "outcome_calculation_permitted": False,
        "prospective_operational_replication_still_required": True,
    }


def ensure_holdout() -> None:
    expected = holdout_contract()
    if HOLDOUT_PATH.exists():
        with HOLDOUT_PATH.open("r", encoding="utf-8") as handle:
            existing = json.load(handle)
        for key in ["program", "hypothesis", "state", "development", "sealed_historical_holdout"]:
            if existing.get(key) != expected.get(key):
                raise RuntimeError(f"Existing holdout contract differs at {key}.")
        return
    expected["created_utc"] = utc_now()
    atomic_json(HOLDOUT_PATH, expected)
    log(f"HOLDOUT_SEALED path={HOLDOUT_PATH}")


def load_d0() -> list[dict[str, Any]]:
    if not D0_MANIFEST.exists() or not D0_DECISION.exists():
        raise RuntimeError("Required D0 artifacts are missing.")
    with D0_DECISION.open("r", encoding="utf-8") as handle:
        decision = json.load(handle)
    if decision.get("d0_scientific_decision") != "CONDITIONAL_PASS_FOR_D1_ACQUISITION_ONLY":
        raise RuntimeError("D0 scientific decision does not authorize requesting D1.")
    rows: list[dict[str, Any]] = []
    with D0_MANIFEST.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            rows.append(row)
    if len(rows) != 1440:
        raise RuntimeError(f"D0 manifest must contain 1440 rows, found {len(rows)}.")
    keys = {(r["symbol"], r["month"], r["family"]) for r in rows}
    if len(keys) != 1440:
        raise RuntimeError("D0 manifest keys are not unique.")
    for row in rows:
        if row["symbol"] not in SYMBOLS or row["family"] not in FAMILY_ORDER:
            raise RuntimeError("D0 manifest contains an out-of-scope key.")
        if row.get("object_present", "").lower() != "true":
            raise RuntimeError("D0 manifest contains a non-present object.")
        if not re.fullmatch(r"[0-9a-fA-F]{64}\s+.+\.zip", row.get("checksum_text", "")):
            raise RuntimeError("D0 checksum text is invalid.")
    return rows


def source_url(object_key: str) -> str:
    pure = PurePosixPath(object_key)
    if pure.is_absolute() or ".." in pure.parts or not object_key.endswith(".zip"):
        raise RuntimeError(f"Unsafe object key: {object_key}")
    url = SOURCE_BASE + urllib.parse.quote(object_key, safe="/")
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != SOURCE_HOST:
        raise RuntimeError(f"Forbidden source URL: {url}")
    return url


def local_path(row: dict[str, Any]) -> Path:
    name = PurePosixPath(row["object_key"]).name
    if not name.endswith(".zip") or name != Path(name).name:
        raise RuntimeError("Unsafe archive name.")
    return RAW_DIR / row["family"] / row["symbol"] / row["month"] / name


def expected_sha(row: dict[str, Any]) -> str:
    value = row["checksum_text"].split()[0].lower()
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise RuntimeError("Invalid expected SHA-256.")
    return value


def make_read_only(path: Path) -> None:
    try:
        path.chmod(stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
    except OSError:
        path.chmod(stat.S_IREAD)


def move_evidence(path: Path, label: str) -> Path:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass
    target = EVIDENCE_DIR / f"{path.name}.{label}.{int(time.time() * 1000)}"
    os.replace(path, target)
    return target


def download_one(row: dict[str, Any], state: RunState) -> dict[str, Any]:
    url = source_url(row["object_key"])
    final = local_path(row)
    final.parent.mkdir(parents=True, exist_ok=True)
    expected_size = int(row["object_size_bytes"])
    expected_digest = expected_sha(row)
    result = {
        "symbol": row["symbol"], "month": row["month"], "family": row["family"],
        "source_url": url, "local_path": str(final.relative_to(ROOT)),
        "expected_size": expected_size, "actual_size": None,
        "expected_sha256": expected_digest, "actual_sha256": None,
        "download_status": "failed", "checksum_match": False, "attempts": 0,
        "first_download_utc": None, "completed_utc": None,
    }
    if final.exists():
        actual_size = final.stat().st_size
        actual_digest = sha256_file(final) if actual_size == expected_size else None
        if actual_size == expected_size and actual_digest == expected_digest:
            make_read_only(final)
            result.update({
                "actual_size": actual_size, "actual_sha256": actual_digest,
                "download_status": "reused_valid", "checksum_match": True,
                "attempts": 0, "completed_utc": utc_now(),
            })
            return result
        moved = move_evidence(final, "invalid-existing")
        state.error({"object_key": row["object_key"], "stage": "existing_raw_validation", "evidence": str(moved)})
    part = final.with_suffix(final.suffix + ".part")
    for attempt in range(1, MAX_ATTEMPTS + 1):
        result["attempts"] = attempt
        if result["first_download_utc"] is None:
            result["first_download_utc"] = utc_now()
        start = part.stat().st_size if part.exists() else 0
        if start > expected_size:
            move_evidence(part, "oversized-part")
            start = 0
        headers = {"User-Agent": USER_AGENT, "Accept": "application/zip"}
        if start:
            headers["Range"] = f"bytes={start}-"
        request = urllib.request.Request(url, headers=headers)
        state.request()
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                status_code = int(getattr(response, "status", 200))
                state.status(status_code)
                mode = "ab" if start and status_code == 206 else "wb"
                if start and status_code != 206:
                    start = 0
                with part.open(mode) as handle:
                    while True:
                        chunk = response.read(CHUNK_BYTES)
                        if not chunk:
                            break
                        handle.write(chunk)
                        state.add_bytes(len(chunk))
            actual_size = part.stat().st_size
            actual_digest = sha256_file(part)
            result["actual_size"] = actual_size
            result["actual_sha256"] = actual_digest
            if actual_size == expected_size and actual_digest == expected_digest:
                os.replace(part, final)
                make_read_only(final)
                result.update({
                    "download_status": "downloaded_valid", "checksum_match": True,
                    "completed_utc": utc_now(),
                })
                return result
            moved = move_evidence(part, f"checksum-mismatch-attempt-{attempt}")
            state.error({
                "object_key": row["object_key"], "stage": "checksum",
                "attempt": attempt, "actual_size": actual_size,
                "actual_sha256": actual_digest, "evidence": str(moved),
            })
            error = "size_or_checksum_mismatch"
        except urllib.error.HTTPError as exc:
            state.status(exc.code)
            error = f"HTTP {exc.code}: {exc.reason}"
        except Exception as exc:  # noqa: BLE001 - evidence is recorded for all transport failures.
            error = f"{type(exc).__name__}: {exc}"
        if attempt < MAX_ATTEMPTS:
            state.retry({"object_key": row["object_key"], "attempt": attempt, "reason": error})
            time.sleep(attempt)
        else:
            state.error({"object_key": row["object_key"], "stage": "download", "error": error})
    return result


def acquire(rows: list[dict[str, Any]], state: RunState) -> list[dict[str, Any]]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
        futures = {pool.submit(download_one, row, state): row for row in rows}
        completed = 0
        for future in as_completed(futures):
            results.append(future.result())
            completed += 1
            if completed % 100 == 0 or completed == len(rows):
                valid = sum(r["checksum_match"] is True for r in results)
                log(f"ACQUIRE_PROGRESS completed={completed}/{len(rows)} checksum_valid={valid}")
    results.sort(key=lambda r: (SYMBOLS.index(r["symbol"]), r["month"], FAMILY_ORDER.index(r["family"])))
    atomic_csv(INVENTORY_PATH, INVENTORY_FIELDS, results)
    return results


def inventory_from_raw(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for row in rows:
        final = local_path(row)
        expected_size = int(row["object_size_bytes"])
        digest = sha256_file(final) if final.exists() and final.stat().st_size == expected_size else None
        match = digest == expected_sha(row)
        results.append({
            "symbol": row["symbol"], "month": row["month"], "family": row["family"],
            "source_url": source_url(row["object_key"]),
            "local_path": str(final.relative_to(ROOT)), "expected_size": expected_size,
            "actual_size": final.stat().st_size if final.exists() else None,
            "expected_sha256": expected_sha(row), "actual_sha256": digest,
            "download_status": "reused_valid" if match else "missing_or_invalid",
            "checksum_match": match, "attempts": 0, "first_download_utc": None,
            "completed_utc": utc_now() if match else None,
        })
    atomic_csv(INVENTORY_PATH, INVENTORY_FIELDS, results)
    return results


def month_bounds_us(month: str) -> tuple[int, int, int]:
    year, mon = map(int, month.split("-"))
    start = datetime(year, mon, 1, tzinfo=timezone.utc)
    if mon == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(year, mon + 1, 1, tzinfo=timezone.utc)
    start_us = int(start.timestamp() * 1_000_000)
    end_us = int(end.timestamp() * 1_000_000)
    expected = calendar.monthrange(year, mon)[1] * 24 * 12
    return start_us, end_us, expected


def parse_timestamp(value: str) -> tuple[int, str]:
    raw = int(value.strip())
    magnitude = abs(raw)
    if magnitude >= 100_000_000_000_000:
        return raw, "us"
    if magnitude >= 100_000_000_000:
        return raw * 1000, "ms"
    if magnitude >= 100_000_000:
        return raw * 1_000_000, "s"
    raise ValueError("unsupported timestamp magnitude")


def iso_from_us(value: int | None) -> str | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value / 1_000_000, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def normalized_header(row: list[str]) -> list[str]:
    return [re.sub(r"[^a-z0-9]+", "_", item.strip().lower()).strip("_") for item in row]


def inspect_archive(item: dict[str, Any]) -> tuple[dict[str, Any], set[int] | None, dict[str, Any]]:
    path = ROOT / item["local_path"]
    family = item["family"]
    row: dict[str, Any] = {
        "symbol": item["symbol"], "month": item["month"], "family": family,
        "zip_valid": False, "csv_member_count": 0, "schema_id": None,
        "header_mode": None, "row_count": 0, "timestamp_unit": None,
        "min_timestamp_utc": None, "max_timestamp_utc": None,
        "sorted": False, "duplicate_timestamps": None,
        "out_of_month_rows": None, "expected_grid_rows": None,
        "missing_grid_rows": None, "irregular_intervals": None,
        "numeric_parse_failures": None, "qa_status": "FAIL", "notes": None,
    }
    aux = {"funding_material_gaps": None, "schema_identified": False}
    if not item.get("checksum_match") or not path.exists():
        row["notes"] = "Raw archive missing or checksum invalid."
        return row, None, aux
    try:
        with zipfile.ZipFile(path, "r") as archive:
            members = archive.infolist()
            unsafe = []
            for member in members:
                pure = PurePosixPath(member.filename)
                if pure.is_absolute() or ".." in pure.parts or "\\" in member.filename:
                    unsafe.append(member.filename)
            csv_members = [m for m in members if m.filename.lower().endswith(".csv") and not m.is_dir()]
            row["csv_member_count"] = len(csv_members)
            if unsafe:
                row["notes"] = "Path traversal or unsafe ZIP member detected."
                return row, None, aux
            if len(csv_members) != 1:
                row["notes"] = f"Expected exactly one CSV member, found {len(csv_members)}."
                return row, None, aux
            member = csv_members[0]
            expected_member = path.stem + ".csv"
            if PurePosixPath(member.filename).name != expected_member:
                row["notes"] = f"Unexpected CSV member name: {member.filename}."
                return row, None, aux
            with archive.open(member, "r") as binary:
                import io
                text = io.TextIOWrapper(binary, encoding="utf-8-sig", newline="")
                reader = csv.reader(text)
                first = next(reader, None)
                if first is None:
                    row["notes"] = "CSV is empty."
                    return row, None, aux
                try:
                    parse_timestamp(first[0])
                    has_header = False
                except (ValueError, IndexError):
                    has_header = True
                header = normalized_header(first) if has_header else [f"col_{i}" for i in range(len(first))]
                row["header_mode"] = "present" if has_header else "absent"
                expected_columns = 12 if family in KLINE_FAMILIES else 3
                if len(header) != expected_columns:
                    row["schema_id"] = f"unknown_{family}_{len(header)}cols_{row['header_mode']}"
                    row["notes"] = f"Undocumented column count {len(header)}; expected {expected_columns}."
                    return row, None, aux
                if has_header:
                    candidates = ["open_time"] if family in KLINE_FAMILIES else ["calc_time", "funding_time"]
                    timestamp_indexes = [header.index(name) for name in candidates if name in header]
                    if len(timestamp_indexes) != 1:
                        row["schema_id"] = f"unknown_{family}_{len(header)}cols_header"
                        row["notes"] = "Timestamp column is ambiguous in documented header."
                        return row, None, aux
                    timestamp_index = timestamp_indexes[0]
                else:
                    timestamp_index = 0
                kind = "kline" if family in KLINE_FAMILIES else "funding"
                row["schema_id"] = f"{kind}_{len(header)}cols_{row['header_mode']}_ts{timestamp_index}"
                aux["schema_identified"] = True
                numeric_failed = {name: False for name in header}
                timestamps: list[int] = []
                units: set[str] = set()
                column_mismatch = 0
                data_rows = reader if has_header else chain([first], reader)
                for values in data_rows:
                    row["row_count"] += 1
                    if len(values) != len(header):
                        column_mismatch += 1
                        continue
                    for index, value in enumerate(values):
                        if not numeric_failed[header[index]]:
                            try:
                                float(value)
                            except ValueError:
                                numeric_failed[header[index]] = True
                    try:
                        timestamp_us, unit = parse_timestamp(values[timestamp_index])
                        timestamps.append(timestamp_us)
                        units.add(unit)
                    except (ValueError, IndexError):
                        numeric_failed[header[timestamp_index]] = True
                row["zip_valid"] = True
                row["numeric_parse_failures"] = json.dumps(numeric_failed, sort_keys=True, separators=(",", ":"))
                row["timestamp_unit"] = next(iter(units)) if len(units) == 1 else ("mixed" if units else None)
                start_us, end_us, expected_grid = month_bounds_us(item["month"])
                row["min_timestamp_utc"] = iso_from_us(min(timestamps) if timestamps else None)
                row["max_timestamp_utc"] = iso_from_us(max(timestamps) if timestamps else None)
                row["sorted"] = all(timestamps[i] >= timestamps[i - 1] for i in range(1, len(timestamps)))
                unique = set(timestamps)
                row["duplicate_timestamps"] = len(timestamps) - len(unique)
                row["out_of_month_rows"] = sum(not (start_us <= value < end_us) for value in timestamps)
                sorted_unique = sorted(unique)
                deltas = [sorted_unique[i] - sorted_unique[i - 1] for i in range(1, len(sorted_unique))]
                if family in KLINE_FAMILIES:
                    step_us = 300_000_000
                    row["expected_grid_rows"] = expected_grid
                    in_month = {value for value in unique if start_us <= value < end_us and (value - start_us) % step_us == 0}
                    row["missing_grid_rows"] = expected_grid - len(in_month)
                    row["irregular_intervals"] = sum(delta != step_us for delta in deltas)
                    timestamp_set: set[int] | None = in_month
                else:
                    row["expected_grid_rows"] = None
                    row["missing_grid_rows"] = None
                    positive_deltas = [delta for delta in deltas if delta > 0]
                    if positive_deltas:
                        mode_delta = Counter(positive_deltas).most_common(1)[0][0]
                        row["irregular_intervals"] = sum(delta != mode_delta for delta in positive_deltas)
                        aux["funding_material_gaps"] = sum(delta > 2 * mode_delta for delta in positive_deltas)
                    else:
                        row["irregular_intervals"] = 0
                        aux["funding_material_gaps"] = 0 if timestamps else None
                    timestamp_set = None
                structural_ok = all([
                    row["zip_valid"], aux["schema_identified"], bool(timestamps),
                    row["timestamp_unit"] in {"ms", "us"}, row["sorted"],
                    row["duplicate_timestamps"] == 0, row["out_of_month_rows"] == 0,
                    not any(numeric_failed.values()), column_mismatch == 0,
                ])
                row["qa_status"] = "PASS" if structural_ok else "FAIL"
                notes = []
                if column_mismatch:
                    notes.append(f"column_mismatch_rows={column_mismatch}")
                if family == "spot_klines_5m" and item["month"] >= "2025-01":
                    notes.append(f"spot_timestamp_transition_detected={row['timestamp_unit']}")
                if family == "usd_m_fundingRate":
                    notes.append(f"funding_material_gaps={aux['funding_material_gaps']}")
                row["notes"] = ";".join(notes) or None
                return row, timestamp_set, aux
    except (zipfile.BadZipFile, RuntimeError, OSError, UnicodeError, csv.Error) as exc:
        row["notes"] = f"{type(exc).__name__}: {exc}"
        return row, None, aux


def process_group(group: tuple[str, str], items: dict[tuple[str, str, str], dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any], dict[tuple[str, str, str], dict[str, Any]]]:
    symbol, month = group
    qa_rows = []
    timestamp_sets: dict[str, set[int]] = {}
    aux_map: dict[tuple[str, str, str], dict[str, Any]] = {}
    for family in FAMILY_ORDER:
        item = items[(symbol, month, family)]
        qa_row, timestamps, aux = inspect_archive(item)
        qa_rows.append(qa_row)
        aux_map[(symbol, month, family)] = aux
        if timestamps is not None:
            timestamp_sets[family] = timestamps
    _, _, expected = month_bounds_us(month)
    if len(timestamp_sets) == len(KLINE_FAMILIES):
        common = set.intersection(*(timestamp_sets[family] for family in FAMILY_ORDER[:-1]))
        common_count = len(common)
    else:
        common_count = 0
    sync = {
        "symbol": symbol, "month": month, "common_timestamps": common_count,
        "expected_grid_rows": expected,
        "common_proportion_of_expected": common_count / expected if expected else 0.0,
    }
    return qa_rows, sync, aux_map


def qa(inventory: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[tuple[str, str, str], dict[str, Any]]]:
    items = {(r["symbol"], r["month"], r["family"]): r for r in inventory}
    months = sorted({r["month"] for r in inventory})
    groups = [(symbol, month) for symbol in SYMBOLS for month in months]
    qa_rows: list[dict[str, Any]] = []
    sync_rows: list[dict[str, Any]] = []
    aux_all: dict[tuple[str, str, str], dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=QA_WORKERS) as pool:
        futures = [pool.submit(process_group, group, items) for group in groups]
        completed = 0
        for future in as_completed(futures):
            rows, sync, aux = future.result()
            qa_rows.extend(rows)
            sync_rows.append(sync)
            aux_all.update(aux)
            completed += 1
            if completed % 20 == 0 or completed == len(groups):
                log(f"QA_PROGRESS groups={completed}/{len(groups)} files={len(qa_rows)}")
    qa_rows.sort(key=lambda r: (SYMBOLS.index(r["symbol"]), r["month"], FAMILY_ORDER.index(r["family"])))
    sync_rows.sort(key=lambda r: (SYMBOLS.index(r["symbol"]), r["month"]))
    atomic_csv(QA_PATH, QA_FIELDS, qa_rows)
    return qa_rows, sync_rows, aux_all


def summarize(inventory: list[dict[str, Any]], qa_rows: list[dict[str, Any]], sync_rows: list[dict[str, Any]], aux: dict[tuple[str, str, str], dict[str, Any]]) -> dict[str, Any]:
    by_family: dict[str, Any] = {}
    by_asset: dict[str, Any] = {}
    for family in FAMILY_ORDER:
        inv = [r for r in inventory if r["family"] == family]
        qq = [r for r in qa_rows if r["family"] == family]
        by_family[family] = {
            "objects": len(inv),
            "checksum_match": sum(bool(r["checksum_match"]) for r in inv),
            "zip_valid": sum(bool(r["zip_valid"]) for r in qq),
            "qa_pass": sum(r["qa_status"] == "PASS" for r in qq),
            "rows": sum(int(r["row_count"] or 0) for r in qq),
            "duplicate_timestamps": sum(int(r["duplicate_timestamps"] or 0) for r in qq),
            "out_of_month_rows": sum(int(r["out_of_month_rows"] or 0) for r in qq),
            "missing_grid_rows": None if family == "usd_m_fundingRate" else sum(int(r["missing_grid_rows"] or 0) for r in qq),
            "irregular_intervals": sum(int(r["irregular_intervals"] or 0) for r in qq),
        }
    for symbol in SYMBOLS:
        inv = [r for r in inventory if r["symbol"] == symbol]
        qq = [r for r in qa_rows if r["symbol"] == symbol]
        by_asset[symbol] = {
            "objects": len(inv),
            "checksum_match": sum(bool(r["checksum_match"]) for r in inv),
            "zip_valid": sum(bool(r["zip_valid"]) for r in qq),
            "qa_pass": sum(r["qa_status"] == "PASS" for r in qq),
            "duplicate_timestamps": sum(int(r["duplicate_timestamps"] or 0) for r in qq),
            "out_of_month_rows": sum(int(r["out_of_month_rows"] or 0) for r in qq),
        }
    coverage: dict[str, dict[str, Any]] = {}
    coverage_all = True
    for symbol in SYMBOLS:
        coverage[symbol] = {}
        for family in FAMILY_ORDER[:-1]:
            qq = [r for r in qa_rows if r["symbol"] == symbol and r["family"] == family]
            expected = sum(int(r["expected_grid_rows"] or 0) for r in qq)
            missing = sum(int(r["missing_grid_rows"] or 0) for r in qq)
            proportion = (expected - missing) / expected if expected else 0.0
            passed = proportion >= 0.999
            coverage_all = coverage_all and passed
            coverage[symbol][family] = {
                "expected_grid_rows": expected, "missing_grid_rows": missing,
                "coverage_proportion": proportion, "passes_99_9pct": passed,
            }
    synchronization: dict[str, Any] = {}
    sync_pass_assets = []
    for symbol in SYMBOLS:
        ss = [r for r in sync_rows if r["symbol"] == symbol]
        common = sum(r["common_timestamps"] for r in ss)
        expected = sum(r["expected_grid_rows"] for r in ss)
        proportion = common / expected if expected else 0.0
        passed = proportion >= 0.995
        if passed:
            sync_pass_assets.append(symbol)
        synchronization[symbol] = {
            "common_timestamps": common, "expected_grid_rows": expected,
            "common_proportion": proportion, "passes_99_5pct": passed,
        }
    funding_status: dict[str, Any] = {}
    funding_pass_assets = []
    for symbol in SYMBOLS:
        qq = [r for r in qa_rows if r["symbol"] == symbol and r["family"] == "usd_m_fundingRate"]
        material = sum(int(aux[(r["symbol"], r["month"], r["family"])].get("funding_material_gaps") or 0) for r in qq)
        passed = len(qq) == 24 and all(r["qa_status"] == "PASS" for r in qq) and material == 0
        if passed:
            funding_pass_assets.append(symbol)
        funding_status[symbol] = {"files": len(qq), "material_gap_intervals": material, "passes": passed}
    schema_distribution = {}
    timestamp_distribution = {}
    for family in FAMILY_ORDER:
        qq = [r for r in qa_rows if r["family"] == family]
        schema_distribution[family] = dict(Counter(str(r["schema_id"]) for r in qq))
        timestamp_distribution[family] = dict(Counter(str(r["timestamp_unit"]) for r in qq))
    schema_identified = all(r["schema_id"] and not str(r["schema_id"]).startswith("unknown") for r in qa_rows)
    timestamps_valid = all(r["timestamp_unit"] in {"ms", "us"} and bool(r["sorted"]) for r in qa_rows)
    duplicates_material = sum(int(r["duplicate_timestamps"] or 0) for r in qa_rows)
    criteria = {
        "downloads_1440_and_100pct_checksum": len(inventory) == 1440 and all(bool(r["checksum_match"]) for r in inventory),
        "all_zips_valid_no_path_traversal": len(qa_rows) == 1440 and all(bool(r["zip_valid"]) and int(r["csv_member_count"]) == 1 for r in qa_rows),
        "schemas_identified_or_documented": schema_identified,
        "timestamps_parseable_ordered_normalized": timestamps_valid,
        "no_material_duplicates": duplicates_material == 0,
        "all_kline_symbol_family_coverage_ge_99_9pct": coverage_all,
        "sync_ge_99_5pct_for_at_least_8_assets": len(sync_pass_assets) >= 8,
        "funding_ordered_no_material_gaps_for_at_least_8_assets": len(funding_pass_assets) >= 8,
        "holdout_sealed_zero_outcome_inspection": HOLDOUT_PATH.exists(),
        "no_gap_fill_or_raw_mutation": True,
    }
    fail_keys = [
        "downloads_1440_and_100pct_checksum", "all_zips_valid_no_path_traversal",
        "timestamps_parseable_ordered_normalized", "no_material_duplicates",
        "all_kline_symbol_family_coverage_ge_99_9pct",
        "sync_ge_99_5pct_for_at_least_8_assets",
        "funding_ordered_no_material_gaps_for_at_least_8_assets",
        "holdout_sealed_zero_outcome_inspection", "no_gap_fill_or_raw_mutation",
    ]
    if not all(criteria[key] for key in fail_keys):
        result = "D1_QA_MECHANICAL_FAIL"
    elif not criteria["schemas_identified_or_documented"]:
        result = "D1_QA_MECHANICAL_INCONCLUSIVE"
    else:
        result = "D1_QA_MECHANICAL_PASS"
    return {
        "mechanical_result": result,
        "criteria": criteria,
        "by_family": by_family,
        "by_asset": by_asset,
        "coverage": coverage,
        "synchronization": synchronization,
        "sync_pass_assets": sync_pass_assets,
        "funding": funding_status,
        "funding_pass_assets": funding_pass_assets,
        "schema_distribution": schema_distribution,
        "timestamp_unit_distribution": timestamp_distribution,
        "duplicate_timestamps_total": duplicates_material,
    }


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(value).replace("|", "\\|") for value in row) + " |")
    return "\n".join(lines)


def write_report(summary: dict[str, Any], inventory: list[dict[str, Any]], qa_rows: list[dict[str, Any]]) -> None:
    raw_files = [ROOT / r["local_path"] for r in inventory if r["checksum_match"]]
    report = {
        "program": "Discovery V2",
        "study": "V2-H01 D1 acquisition and structural QA",
        "generated_utc": utc_now(),
        "mechanical_result": summary["mechanical_result"],
        "h01_state": "SELECTED_PENDING_DATA",
        "active_hypotheses": [],
        "tested_hypotheses": [],
        "outcomes_inspected": False,
        "economic_values_reported": False,
        "d1_scope_complete": True,
        "raw": {
            "location": str(RAW_DIR), "file_count": len(raw_files),
            "bytes": sum(path.stat().st_size for path in raw_files),
            "immutable_read_only_requested": True,
        },
        "downloads": {
            "inventory_rows": len(inventory),
            "checksum_match": sum(bool(r["checksum_match"]) for r in inventory),
            "downloaded_valid": sum(r["download_status"] == "downloaded_valid" for r in inventory),
            "reused_valid": sum(r["download_status"] == "reused_valid" for r in inventory),
            "failed": sum(not bool(r["checksum_match"]) for r in inventory),
        },
        "qa": {
            "matrix_rows": len(qa_rows),
            "zip_valid": sum(bool(r["zip_valid"]) for r in qa_rows),
            "qa_pass": sum(r["qa_status"] == "PASS" for r in qa_rows),
            "qa_fail": sum(r["qa_status"] != "PASS" for r in qa_rows),
            "duplicate_timestamps": summary["duplicate_timestamps_total"],
        },
        "structural_summary": summary,
        "holdout": {
            "state": "SEALED",
            "development": "2024-07-01T00:00:00Z/2025-12-31T23:59:59.999Z",
            "sealed_historical_holdout": "2026-01-01T00:00:00Z/2026-06-30T23:59:59.999Z",
            "economic_analysis_permitted": False,
            "prospective_replication_still_required": True,
        },
        "prohibitions_observed": {
            "returns_calculated": False, "carry_calculated": False,
            "pnl_calculated": False, "correlations_calculated": False,
            "regressions_calculated": False, "funding_values_aggregated": False,
            "gaps_filled": False, "raw_corrected": False,
        },
        "interpretation": "Mechanical QA only. No scientific interpretation or H01 activation.",
    }
    atomic_json(REPORT_JSON_PATH, report)
    family_rows = []
    for family in FAMILY_ORDER:
        value = summary["by_family"][family]
        family_rows.append([
            family, value["objects"], value["checksum_match"], value["zip_valid"],
            value["qa_pass"], value["duplicate_timestamps"],
            "NA" if value["missing_grid_rows"] is None else value["missing_grid_rows"],
            value["irregular_intervals"],
        ])
    asset_rows = []
    for symbol in SYMBOLS:
        value = summary["by_asset"][symbol]
        sync = summary["synchronization"][symbol]
        funding = summary["funding"][symbol]
        asset_rows.append([
            symbol, value["checksum_match"], value["zip_valid"], value["qa_pass"],
            f"{sync['common_proportion']:.6%}", "PASS" if sync["passes_99_5pct"] else "FAIL",
            "PASS" if funding["passes"] else "FAIL",
        ])
    criteria_rows = [[key, "PASS" if value else "FAIL"] for key, value in summary["criteria"].items()]
    schema_rows = []
    for family in FAMILY_ORDER:
        schema_rows.append([family, json.dumps(summary["schema_distribution"][family], ensure_ascii=False), json.dumps(summary["timestamp_unit_distribution"][family], ensure_ascii=False)])
    md = f"""# DISCOVERY V2 — V2-H01 D1 ACQUISITION AND STRUCTURAL QA

## Resultado mecânico

**{summary['mechanical_result']}**

Este resultado é exclusivamente mecânico. H01 continua `SELECTED_PENDING_DATA`, não ativa e não testada.

## Aquisição

- Objetos no inventário: **{len(inventory)}**
- Checksum válido: **{sum(bool(r['checksum_match']) for r in inventory)}**
- Downloads válidos nesta execução: **{sum(r['download_status'] == 'downloaded_valid' for r in inventory)}**
- Raw reutilizado e revalidado: **{sum(r['download_status'] == 'reused_valid' for r in inventory)}**
- Falhas: **{sum(not bool(r['checksum_match']) for r in inventory)}**
- Raw: `{RAW_DIR}`
- Arquivos raw válidos: **{len(raw_files)}**
- Bytes raw: **{sum(path.stat().st_size for path in raw_files)}**

## QA por família

{markdown_table(['Família','Objetos','Checksum','ZIP válido','QA PASS','Duplicatas','Missing 5m','Intervalos irregulares'], family_rows)}

`Missing 5m` é `NA` para funding, que não possui grade de cinco minutos.

## QA por ativo

{markdown_table(['Ativo','Checksum','ZIP válido','QA PASS','Sincronização comum','Sync gate','Funding gate'], asset_rows)}

## Critérios pré-registrados

{markdown_table(['Critério','Resultado'], criteria_rows)}

## Schema e timestamp

{markdown_table(['Família','Schemas detectados','Unidades detectadas'], schema_rows)}

A mudança documentada de timestamp spot a partir de 2025-01 foi detectada por arquivo e registrada na matriz. Futures não herdou essa premissa: sua unidade foi detectada independentemente.

## Holdout

- Development: `2024-07-01T00:00:00Z` a `2025-12-31T23:59:59.999Z`.
- `SEALED_HISTORICAL_HOLDOUT`: `2026-01-01T00:00:00Z` a `2026-06-30T23:59:59.999Z`.
- Holdout permanece selado para qualquer análise econômica.
- Replicação prospectiva futura continua necessária.

## Limites observados

- Nenhum retorno, carry, PnL, correlação ou regressão foi calculado.
- Nenhuma média/distribuição de preço ou funding foi produzida.
- Funding foi lido apenas para schema, parseabilidade numérica e timestamps.
- Nenhum gap foi preenchido e nenhum raw foi corrigido.
- D1 não ativa H01 e não inicia protocolo experimental.
"""
    atomic_text(REPORT_MD_PATH, md)


def write_provenance(state: RunState, inventory: list[dict[str, Any]]) -> None:
    raw_files = [ROOT / r["local_path"] for r in inventory if r["checksum_match"]]
    five_paths = [INVENTORY_PATH, QA_PATH, HOLDOUT_PATH, REPORT_JSON_PATH, REPORT_MD_PATH]
    artifact_hashes: dict[str, Any] = {path.name: {"sha256": sha256_file(path), "scope": "full_file"} for path in five_paths}
    base = {
        "program": "Discovery V2",
        "study": "V2-H01 D1 acquisition and structural QA",
        "authorization_text": AUTHORIZATION_TEXT,
        "permanent_authorization_scope": PERMANENT_SCOPE,
        "authorization_exclusions": ["paid data", "private/authenticated source", "credentials", "destructive action", "external spend", "material hypothesis change", "bot/orders/live operation"],
        "start_utc": state.started,
        "end_utc": utc_now(),
        "source_urls": [SOURCE_BASE],
        "source_domains": [SOURCE_HOST],
        "private_endpoints_used": False,
        "credentials_used": False,
        "script": {"path": str(SCRIPT.relative_to(ROOT)), "version": VERSION, "sha256": sha256_file(SCRIPT)},
        "network": {
            "requests": state.request_count, "http_status_counts": dict(state.http_status),
            "retries": state.retries, "bytes_downloaded": state.network_bytes,
        },
        "raw": {"count": len(raw_files), "bytes": sum(path.stat().st_size for path in raw_files), "location": str(RAW_DIR)},
        "initial_free_bytes": state.initial_free,
        "final_free_bytes": free_space(ROOT),
        "errors": state.errors,
        "no_outcome_analysis_declaration": "No returns, carry, PnL, correlations, regressions, price statistics, or funding-value aggregates were calculated.",
        "artifact_hashes": artifact_hashes,
        "provenance_self_hash_method": "canonical JSON payload excluding artifact_hashes and self hash",
    }
    canonical = dict(base)
    canonical.pop("artifact_hashes", None)
    canonical.pop("provenance_self_hash_method", None)
    self_hash = hashlib.sha256(json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
    base["artifact_hashes"][PROVENANCE_PATH.name] = {"sha256": self_hash, "scope": "canonical_payload_excluding_artifact_hashes"}
    atomic_json(PROVENANCE_PATH, base)


def run_command(command: str) -> int:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ensure_holdout()
    d0_rows = load_d0()
    state = RunState()
    if command in {"acquire", "run"}:
        inventory = acquire(d0_rows, state)
    else:
        inventory = inventory_from_raw(d0_rows)
    if command == "acquire":
        log("ACQUIRE_COMPLETE; QA not requested.")
        return 0 if all(r["checksum_match"] for r in inventory) else 2
    if not all(r["checksum_match"] for r in inventory):
        atomic_csv(INVENTORY_PATH, INVENTORY_FIELDS, inventory)
        log("QA_BLOCKED: not all raw archives passed checksum.")
        return 2
    qa_rows, sync_rows, aux = qa(inventory)
    summary = summarize(inventory, qa_rows, sync_rows, aux)
    write_report(summary, inventory, qa_rows)
    write_provenance(state, inventory)
    log(f"D1_COMPLETE result={summary['mechanical_result']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Acquire D0-manifested Binance public archives and run structural QA only.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("acquire", help="Download and checksum-validate the 1,440 D0 objects.")
    subparsers.add_parser("qa", help="Run structural QA on already validated raw archives.")
    subparsers.add_parser("run", help="Seal holdout, acquire/resume, run structural QA, and write reports.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run_command(args.command)
    except KeyboardInterrupt:
        log("INTERRUPTED: rerun the same command to resume from validated raw files.")
        return 130
    except Exception as exc:  # noqa: BLE001 - top-level failure must be logged for resumption.
        log(f"FATAL {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
