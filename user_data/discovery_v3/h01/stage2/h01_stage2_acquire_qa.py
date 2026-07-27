#!/usr/bin/env python3
"""Discovery V3 H01 Stage 2 acquisition and mechanical QA.

This instrument downloads only official public Binance archives, verifies
provider checksums and ZIP integrity, inventories schemas/timestamps, and seals
a chronological holdout before any price archive is opened. It never computes
returns, event responses, PnL, correlations, regressions, or economic outcomes.
"""

from __future__ import annotations

import argparse
import calendar
import csv
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from itertools import chain
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


VERSION = "1.0.0"
SOURCE_BASE = "https://data.binance.vision/"
S3_BASE = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
USER_AGENT = "DiscoveryV3-H01-Stage2/1.0 mechanical-qa-only"
TIMEOUT = 90
ATTEMPTS = 4
WORKERS = 12
CHUNK = 1024 * 1024
SYMBOLS = [
    "BTCUSD_PERP",
    "ETHUSD_PERP",
    "BNBUSD_PERP",
    "ADAUSD_PERP",
    "LINKUSD_PERP",
    "LTCUSD_PERP",
]
PAIR = {symbol: symbol.split("USD_")[0] + "USD" for symbol in SYMBOLS}
SPOT = {symbol: symbol.split("USD_")[0] + "USDT" for symbol in SYMBOLS}

SCRIPT = Path(__file__).resolve()
BASE = SCRIPT.parent
RAW = BASE / "raw"
EVIDENCE = BASE / "evidence"
LOGS = BASE / "logs"
MANIFEST = BASE / "H01_STAGE2_MANIFEST.csv"
INVENTORY = BASE / "H01_STAGE2_SOURCE_INVENTORY.json"
SEAL = BASE / "H01_STAGE2_HOLDOUT_SEAL.json"
QA_JSON = BASE / "H01_STAGE2_QA_REPORT.json"
QA_MD = BASE / "H01_STAGE2_QA_REPORT.md"
QA_MATRIX = BASE / "H01_STAGE2_QA_MATRIX.csv"
NORMALIZED_EVENTS = BASE / "normalized" / "liquidation_events.csv.gz"
NORMALIZATION_REPORT = BASE / "H01_STAGE2_NORMALIZATION_REPORT.json"
COVERAGE_JSON = BASE / "H01_STAGE2_COVERAGE_REPORT.json"
COVERAGE_MD = BASE / "H01_STAGE2_COVERAGE_REPORT.md"
REPAIR_MANIFEST = BASE / "H01_STAGE2_REPAIR_MANIFEST.csv"
REPAIR_REPORT = BASE / "H01_STAGE2_REPAIR_REPORT.json"
RUN_LOG = LOGS / "run.log"

FAMILIES = {
    "liquidation": ("futures/cm/daily/liquidationSnapshot", "daily"),
    "perp_1m": ("futures/cm/monthly/klines", "monthly"),
    "mark_1m": ("futures/cm/monthly/markPriceKlines", "monthly"),
    "index_1m": ("futures/cm/monthly/indexPriceKlines", "monthly"),
    "metrics_5m": ("futures/cm/daily/metrics", "daily"),
    "spot_1m": ("spot/monthly/klines", "monthly"),
}
PRICE_FAMILIES = {"perp_1m", "mark_1m", "index_1m", "spot_1m"}
MANIFEST_FIELDS = [
    "family",
    "symbol",
    "period",
    "object_key",
    "source_url",
    "expected_size",
    "etag",
    "provider_sha256",
    "local_path",
    "download_status",
    "actual_size",
    "local_sha256",
    "checksum_match",
]
QA_FIELDS = [
    "family",
    "symbol",
    "period",
    "zip_valid",
    "csv_members",
    "row_count",
    "timestamp_column",
    "min_timestamp_utc",
    "max_timestamp_utc",
    "sorted",
    "duplicate_timestamps",
    "exact_duplicate_rows",
    "max_exact_multiplicity",
    "schema_status",
    "qa_status",
    "notes",
]

_log_lock = threading.Lock()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def log(message: str) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    line = f"{utc_now()} {message}"
    with _log_lock:
        print(line, flush=True)
        with RUN_LOG.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


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
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})
    os.replace(temp, path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def request_bytes(url: str) -> bytes:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {
        "data.binance.vision",
        "s3-ap-northeast-1.amazonaws.com",
    }:
        raise RuntimeError(f"Forbidden source URL: {url}")
    last_error: Exception | None = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
                return response.read()
        except (OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            last_error = exc
            if attempt < ATTEMPTS:
                time.sleep(min(2 ** (attempt - 1), 8))
    raise RuntimeError(f"Request failed after {ATTEMPTS} attempts: {url}: {last_error}")


def list_objects(prefix: str) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    marker = ""
    while True:
        query = {"prefix": prefix, "max-keys": "1000"}
        if marker:
            query["marker"] = marker
        url = S3_BASE + "?" + urllib.parse.urlencode(query)
        root = ET.fromstring(request_bytes(url))
        ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
        page: list[dict[str, Any]] = []
        for node in root.findall("s3:Contents", ns):
            key = node.findtext("s3:Key", default="", namespaces=ns)
            page.append(
                {
                    "key": key,
                    "size": int(node.findtext("s3:Size", default="0", namespaces=ns)),
                    "etag": node.findtext("s3:ETag", default="", namespaces=ns).strip('"'),
                    "last_modified": node.findtext(
                        "s3:LastModified", default="", namespaces=ns
                    ),
                }
            )
        objects.extend(page)
        truncated = root.findtext("s3:IsTruncated", default="false", namespaces=ns)
        if truncated.lower() != "true":
            break
        if not page:
            raise RuntimeError(f"Truncated empty S3 page for {prefix}")
        marker = page[-1]["key"]
    return objects


def daily_prefix(family: str, symbol: str) -> str:
    root = FAMILIES[family][0]
    return f"data/{root}/{symbol}/"


def monthly_prefix(family: str, symbol: str) -> str:
    root = FAMILIES[family][0]
    if family == "index_1m":
        native = PAIR[symbol]
    elif family == "spot_1m":
        native = SPOT[symbol]
    else:
        native = symbol
    return f"data/{root}/{native}/1m/"


def object_period(key: str) -> str | None:
    match = re.search(r"-(\d{4}-\d{2}(?:-\d{2})?)\.zip$", key)
    return match.group(1) if match else None


def dates(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def months(start: date, end: date) -> list[str]:
    values: list[str] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        values.append(f"{year:04d}-{month:02d}")
        month += 1
        if month == 13:
            year += 1
            month = 1
    return values


def load_manifest() -> list[dict[str, str]]:
    if not MANIFEST.exists():
        raise RuntimeError("Manifest is missing; run inventory first.")
    with MANIFEST.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_all_manifests() -> list[dict[str, str]]:
    rows = load_manifest()
    if REPAIR_MANIFEST.exists():
        with REPAIR_MANIFEST.open("r", encoding="utf-8", newline="") as handle:
            rows.extend(csv.DictReader(handle))
    return rows


def build_inventory() -> dict[str, Any]:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    source_objects: dict[tuple[str, str], list[dict[str, Any]]] = {}
    event_dates: dict[str, set[date]] = {}

    for symbol in SYMBOLS:
        prefix = daily_prefix("liquidation", symbol)
        objects = list_objects(prefix)
        source_objects[("liquidation", symbol)] = objects
        event_dates[symbol] = {
            date.fromisoformat(period)
            for item in objects
            if item["key"].endswith(".zip")
            and (period := object_period(item["key"]))
            and len(period) == 10
        }
        log(f"INVENTORY liquidation {symbol} dates={len(event_dates[symbol])}")

    if any(not values for values in event_dates.values()):
        missing = [symbol for symbol, values in event_dates.items() if not values]
        raise RuntimeError(f"No liquidation archive for: {missing}")

    common_start = max(min(values) for values in event_dates.values())
    common_end = min(max(values) for values in event_dates.values())
    all_days = list(dates(common_start, common_end))
    if len(all_days) < 365:
        raise RuntimeError("Common event interval is shorter than one year.")
    split_index = int(len(all_days) * 0.80)
    holdout_start = all_days[split_index]
    development_end = holdout_start - timedelta(days=1)

    for family in ["metrics_5m"]:
        for symbol in SYMBOLS:
            source_objects[(family, symbol)] = list_objects(daily_prefix(family, symbol))
            log(f"INVENTORY {family} {symbol}")
    for family in ["perp_1m", "mark_1m", "index_1m", "spot_1m"]:
        for symbol in SYMBOLS:
            source_objects[(family, symbol)] = list_objects(monthly_prefix(family, symbol))
            log(f"INVENTORY {family} {symbol}")

    wanted_days = {item.isoformat() for item in all_days}
    wanted_months = set(months(common_start, common_end))
    selected: list[dict[str, Any]] = []
    pending_checksums: list[
        tuple[str, str, str, dict[str, Any], dict[str, Any]]
    ] = []
    coverage: dict[str, dict[str, Any]] = {}

    for (family, symbol), objects in source_objects.items():
        cadence = FAMILIES[family][1]
        wanted = wanted_days if cadence == "daily" else wanted_months
        zips = {
            object_period(item["key"]): item
            for item in objects
            if item["key"].endswith(".zip") and object_period(item["key"]) in wanted
        }
        sidecars = {item["key"][:-9]: item for item in objects if item["key"].endswith(".zip.CHECKSUM")}
        expected = len(wanted)
        present = len(zips)
        coverage.setdefault(symbol, {})[family] = {
            "expected_periods": expected,
            "present_periods": present,
            "period_coverage": present / expected if expected else 0.0,
        }
        for period, item in sorted(zips.items()):
            checksum_object = sidecars.get(item["key"])
            if checksum_object is None:
                raise RuntimeError(f"Missing provider checksum: {item['key']}")
            pending_checksums.append(
                (family, symbol, period, item, checksum_object)
            )

    def fetch_checksum(
        pending: tuple[str, str, str, dict[str, Any], dict[str, Any]]
    ) -> dict[str, Any]:
        family, symbol, period, item, checksum_object = pending
        checksum_url = SOURCE_BASE + urllib.parse.quote(
            checksum_object["key"], safe="/"
        )
        checksum_payload = request_bytes(checksum_url)
        checksum_text = checksum_payload.decode("utf-8", errors="strict").strip()
        match = re.fullmatch(r"([0-9a-fA-F]{64})\s+\*?(.+\.zip)", checksum_text)
        if not match or PurePosixPath(match.group(2)).name != PurePosixPath(
            item["key"]
        ).name:
            raise RuntimeError(f"Invalid checksum sidecar for {item['key']}")
        evidence_path = EVIDENCE / family / symbol / (
            PurePosixPath(item["key"]).name + ".CHECKSUM"
        )
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        if not evidence_path.exists():
            evidence_path.write_bytes(checksum_payload)
        local = RAW / family / symbol / PurePosixPath(item["key"]).name
        return {
            "family": family,
            "symbol": symbol,
            "period": period,
            "object_key": item["key"],
            "source_url": SOURCE_BASE + urllib.parse.quote(item["key"], safe="/"),
            "expected_size": item["size"],
            "etag": item["etag"],
            "provider_sha256": match.group(1).lower(),
            "local_path": str(local.relative_to(BASE)),
            "download_status": "PENDING",
            "actual_size": "",
            "local_sha256": "",
            "checksum_match": "",
        }

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(fetch_checksum, item) for item in pending_checksums]
        for index, future in enumerate(as_completed(futures), start=1):
            selected.append(future.result())
            if index % 500 == 0:
                log(f"CHECKSUM inventory={index}/{len(futures)}")

    selected.sort(key=lambda row: (row["family"], row["symbol"], row["period"]))
    atomic_csv(MANIFEST, MANIFEST_FIELDS, selected)
    manifest_hash = sha256_file(MANIFEST)
    inventory = {
        "program": "Discovery V3",
        "hypothesis": "H01",
        "stage": 2,
        "created_utc": utc_now(),
        "source": "Binance Data Vision official public S3 archive",
        "symbols": SYMBOLS,
        "common_start": common_start.isoformat(),
        "common_end": common_end.isoformat(),
        "common_calendar_days": len(all_days),
        "development_start": common_start.isoformat(),
        "development_end": development_end.isoformat(),
        "holdout_start": holdout_start.isoformat(),
        "holdout_end": common_end.isoformat(),
        "manifest_rows": len(selected),
        "manifest_sha256": manifest_hash,
        "coverage": coverage,
        "outcomes_inspected": False,
    }
    atomic_json(INVENTORY, inventory)
    seal = {
        "program": "Discovery V3",
        "hypothesis": "H01",
        "state": "SEALED",
        "created_utc": utc_now(),
        "sealed_before_any_price_archive_opened": True,
        "development": {
            "start": common_start.isoformat(),
            "end": development_end.isoformat(),
            "economic_analysis_permitted": True,
        },
        "historical_holdout": {
            "start": holdout_start.isoformat(),
            "end": common_end.isoformat(),
            "economic_analysis_permitted": False,
        },
        "split_rule": "last 20% of common calendar interval, chronological",
        "manifest_sha256": manifest_hash,
        "outcome_calculation_permitted_in_stage2": False,
        "prospective_confirmation_required": True,
    }
    if SEAL.exists():
        existing = json.loads(SEAL.read_text(encoding="utf-8"))
        stable = ["state", "development", "historical_holdout", "split_rule", "manifest_sha256"]
        if any(existing.get(key) != seal.get(key) for key in stable):
            raise RuntimeError("Existing holdout seal differs from current inventory.")
    else:
        atomic_json(SEAL, seal)
    log(f"HOLDOUT_SEALED manifest_sha256={manifest_hash}")
    return inventory


def download_one(row: dict[str, str]) -> dict[str, str]:
    destination = BASE / row["local_path"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    expected_hash = row["provider_sha256"]
    expected_size = int(row["expected_size"])
    if destination.exists():
        actual_hash = sha256_file(destination)
        if destination.stat().st_size == expected_size and actual_hash == expected_hash:
            row.update(
                {
                    "download_status": "CACHED",
                    "actual_size": str(destination.stat().st_size),
                    "local_sha256": actual_hash,
                    "checksum_match": "true",
                }
            )
            return row
    temp = destination.with_suffix(destination.suffix + ".part")
    payload = request_bytes(row["source_url"])
    if len(payload) != expected_size:
        raise RuntimeError(f"Size mismatch for {row['object_key']}")
    actual_hash = sha256_bytes(payload)
    if actual_hash != expected_hash:
        raise RuntimeError(f"SHA-256 mismatch for {row['object_key']}")
    temp.write_bytes(payload)
    os.replace(temp, destination)
    row.update(
        {
            "download_status": "DOWNLOADED",
            "actual_size": str(len(payload)),
            "local_sha256": actual_hash,
            "checksum_match": "true",
        }
    )
    return row


def acquire() -> list[dict[str, str]]:
    if not SEAL.exists():
        raise RuntimeError("Holdout must be sealed before archive acquisition.")
    rows = load_manifest()
    completed: list[dict[str, str]] = []
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(download_one, dict(row)): row for row in rows}
        for index, future in enumerate(as_completed(futures), start=1):
            try:
                completed.append(future.result())
            except Exception as exc:  # each error is retained in the run log
                source = futures[future]
                errors.append(f"{source['object_key']}: {exc}")
            if index % 250 == 0:
                log(f"ACQUIRE progress={index}/{len(rows)} errors={len(errors)}")
    completed_keys = {(row["family"], row["symbol"], row["period"]): row for row in completed}
    merged = [
        completed_keys.get((row["family"], row["symbol"], row["period"]), row)
        for row in rows
    ]
    atomic_csv(MANIFEST, MANIFEST_FIELDS, merged)
    if errors:
        atomic_json(
            BASE / "H01_STAGE2_ACQUISITION_ERRORS.json",
            {"created_utc": utc_now(), "errors": errors},
        )
        raise RuntimeError(f"Acquisition failed for {len(errors)} objects.")
    log(f"ACQUIRE complete files={len(merged)}")
    return merged


def timestamp_to_ms(value: str) -> int:
    try:
        number = int(float(value))
    except ValueError:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return int(parsed.timestamp() * 1000)
    else:
        if number > 10**15:
            return number // 1000
        if number < 10**11:
            return number * 1000
        return number


def inspect_zip(row: dict[str, str]) -> dict[str, Any]:
    path = BASE / row["local_path"]
    result: dict[str, Any] = {
        "family": row["family"],
        "symbol": row["symbol"],
        "period": row["period"],
        "zip_valid": False,
        "csv_members": 0,
        "row_count": 0,
        "timestamp_column": "",
        "min_timestamp_utc": "",
        "max_timestamp_utc": "",
        "sorted": True,
        "duplicate_timestamps": 0,
        "exact_duplicate_rows": 0,
        "max_exact_multiplicity": 1,
        "schema_status": "UNKNOWN",
        "qa_status": "FAIL",
        "notes": "",
    }
    try:
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None:
                result["notes"] = "ZIP CRC failure"
                return result
            members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            result["zip_valid"] = True
            result["csv_members"] = len(members)
            if len(members) != 1:
                result["notes"] = "Expected exactly one CSV member"
                return result
            with archive.open(members[0]) as raw:
                text = (line.decode("utf-8-sig").strip() for line in raw)
                reader = csv.reader(text)
                first = next(reader, None)
                if first is None:
                    result["notes"] = "Empty CSV"
                    return result
                family = row["family"]
                header = any(re.search(r"[A-Za-z_]", cell or "") for cell in first)
                if family in PRICE_FAMILIES:
                    expected_min = 12
                    timestamp_index = 0
                    data_rows = reader if header else chain([first], reader)
                elif family == "metrics_5m":
                    expected_min = 4
                    timestamp_index = 0
                    data_rows = reader if header else chain([first], reader)
                else:
                    expected_min = 7
                    timestamp_index = 0
                    data_rows = reader if header else chain([first], reader)
                if len(first) < expected_min:
                    result["notes"] = f"Schema has {len(first)} columns, expected >= {expected_min}"
                    return result
                result["schema_status"] = "PASS"
                result["timestamp_column"] = str(timestamp_index)
                previous: int | None = None
                seen: set[int] = set()
                seen_rows: Counter[tuple[str, ...]] = Counter()
                minimum: int | None = None
                maximum: int | None = None
                count = 0
                duplicates = 0
                sorted_rows = True
                for values in data_rows:
                    if not values or len(values) <= timestamp_index:
                        continue
                    try:
                        stamp = timestamp_to_ms(values[timestamp_index])
                    except (TypeError, ValueError):
                        result["notes"] = "Unparseable timestamp"
                        return result
                    count += 1
                    seen_rows[tuple(values)] += 1
                    if stamp in seen:
                        duplicates += 1
                    else:
                        seen.add(stamp)
                    if previous is not None and stamp < previous:
                        sorted_rows = False
                    previous = stamp
                    minimum = stamp if minimum is None else min(minimum, stamp)
                    maximum = stamp if maximum is None else max(maximum, stamp)
                result["row_count"] = count
                result["duplicate_timestamps"] = duplicates
                result["exact_duplicate_rows"] = sum(
                    multiplicity - 1 for multiplicity in seen_rows.values()
                )
                result["max_exact_multiplicity"] = max(
                    seen_rows.values(), default=1
                )
                result["sorted"] = sorted_rows
                if minimum is not None:
                    result["min_timestamp_utc"] = datetime.fromtimestamp(
                        minimum / 1000, tz=timezone.utc
                    ).isoformat().replace("+00:00", "Z")
                    result["max_timestamp_utc"] = datetime.fromtimestamp(
                        maximum / 1000, tz=timezone.utc
                    ).isoformat().replace("+00:00", "Z")
                # Zero liquidation rows is a valid no-event day.
                valid_empty = family == "liquidation" and count == 0
                duplicates_allowed = family == "liquidation" or duplicates == 0
                result["qa_status"] = (
                    "PASS"
                    if result["zip_valid"]
                    and result["schema_status"] == "PASS"
                    and sorted_rows
                    and duplicates_allowed
                    and (count > 0 or valid_empty)
                    else "FAIL"
                )
                if family == "liquidation" and result["exact_duplicate_rows"]:
                    result["notes"] = (
                        "Raw provider rows contain exact duplicates; raw ZIP is "
                        "immutable and analysis must use the hashed normalized layer."
                    )
    except (OSError, zipfile.BadZipFile, UnicodeDecodeError) as exc:
        result["notes"] = str(exc)
    return result


def normalize_liquidations(rows: list[dict[str, str]]) -> dict[str, Any]:
    """Collapse only byte-equivalent CSV rows within the same source partition."""
    source_rows = sorted(
        (row for row in rows if row["family"] == "liquidation"),
        key=lambda row: (row["symbol"], row["period"]),
    )
    NORMALIZED_EVENTS.parent.mkdir(parents=True, exist_ok=True)
    temp = NORMALIZED_EVENTS.with_suffix(NORMALIZED_EVENTS.suffix + ".tmp")
    raw_count = 0
    unique_count = 0
    duplicates_removed = 0
    header_contract: list[str] | None = None
    by_symbol: dict[str, dict[str, int]] = {}
    with temp.open("wb") as binary:
        with gzip.GzipFile(fileobj=binary, mode="wb", mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding="utf-8", newline="") as text:
                writer = csv.writer(text, lineterminator="\n")
                for source in source_rows:
                    path = BASE / source["local_path"]
                    with zipfile.ZipFile(path) as archive:
                        members = [
                            name
                            for name in archive.namelist()
                            if name.lower().endswith(".csv")
                        ]
                        if len(members) != 1:
                            raise RuntimeError(f"Invalid liquidation ZIP: {path}")
                        with archive.open(members[0]) as raw:
                            decoded = (
                                line.decode("utf-8-sig").strip() for line in raw
                            )
                            reader = csv.reader(decoded)
                            header = next(reader, None)
                            if not header:
                                raise RuntimeError(f"Missing liquidation header: {path}")
                            if header_contract is None:
                                header_contract = header
                                writer.writerow(
                                    [
                                        "symbol",
                                        "source_period",
                                        "source_zip_sha256",
                                        *header_contract,
                                    ]
                                )
                            elif header != header_contract:
                                raise RuntimeError(
                                    f"Liquidation schema drift in {source['object_key']}"
                                )
                            seen: set[tuple[str, ...]] = set()
                            stats = by_symbol.setdefault(
                                source["symbol"],
                                {"raw_rows": 0, "unique_rows": 0, "duplicates_removed": 0},
                            )
                            for values in reader:
                                if not values:
                                    continue
                                key = tuple(values)
                                raw_count += 1
                                stats["raw_rows"] += 1
                                if key in seen:
                                    duplicates_removed += 1
                                    stats["duplicates_removed"] += 1
                                    continue
                                seen.add(key)
                                unique_count += 1
                                stats["unique_rows"] += 1
                                writer.writerow(
                                    [
                                        source["symbol"],
                                        source["period"],
                                        source["local_sha256"],
                                        *values,
                                    ]
                                )
    os.replace(temp, NORMALIZED_EVENTS)
    report = {
        "program": "Discovery V3",
        "hypothesis": "H01",
        "stage": 2,
        "created_utc": utc_now(),
        "rule": "Collapse exact full-row duplicates within each immutable provider ZIP; preserve distinct rows even when timestamps collide.",
        "raw_archives_modified": False,
        "raw_rows": raw_count,
        "unique_rows": unique_count,
        "exact_duplicates_removed": duplicates_removed,
        "by_symbol": by_symbol,
        "normalized_path": str(NORMALIZED_EVENTS.relative_to(BASE)),
        "normalized_sha256": sha256_file(NORMALIZED_EVENTS),
    }
    atomic_json(NORMALIZATION_REPORT, report)
    return report


def archive_timestamps(
    source: dict[str, str], lower_ms: int, upper_ms: int
) -> set[int]:
    stamps: set[int] = set()
    path = BASE / source["local_path"]
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(members) != 1:
            raise RuntimeError(f"Invalid ZIP member count: {path}")
        with archive.open(members[0]) as raw:
            decoded = (line.decode("utf-8-sig").strip() for line in raw)
            reader = csv.reader(decoded)
            first = next(reader, None)
            if first is None:
                return stamps
            header = any(re.search(r"[A-Za-z_]", cell or "") for cell in first)
            data_rows = reader if header else chain([first], reader)
            for values in data_rows:
                if not values:
                    continue
                stamp = timestamp_to_ms(values[0])
                if lower_ms <= stamp <= upper_ms:
                    stamps.add(stamp)
    return stamps


def missing_blocks(
    observed: set[int], lower_ms: int, upper_ms: int, step_ms: int
) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    block_start: int | None = None
    previous: int | None = None
    stamp = lower_ms
    while stamp <= upper_ms:
        if stamp not in observed:
            if block_start is None:
                block_start = stamp
            previous = stamp
        elif block_start is not None and previous is not None:
            blocks.append(
                {
                    "start_utc": datetime.fromtimestamp(
                        block_start / 1000, tz=timezone.utc
                    ).isoformat().replace("+00:00", "Z"),
                    "end_utc": datetime.fromtimestamp(
                        previous / 1000, tz=timezone.utc
                    ).isoformat().replace("+00:00", "Z"),
                    "missing_rows": (previous - block_start) // step_ms + 1,
                }
            )
            block_start = None
            previous = None
        stamp += step_ms
    if block_start is not None and previous is not None:
        blocks.append(
            {
                "start_utc": datetime.fromtimestamp(
                    block_start / 1000, tz=timezone.utc
                ).isoformat().replace("+00:00", "Z"),
                "end_utc": datetime.fromtimestamp(
                    previous / 1000, tz=timezone.utc
                ).isoformat().replace("+00:00", "Z"),
                "missing_rows": (previous - block_start) // step_ms + 1,
            }
        )
    return blocks


def coverage_audit() -> dict[str, Any]:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    rows = load_all_manifests()
    start = datetime.fromisoformat(inventory["common_start"] + "T00:00:00+00:00")
    end = datetime.fromisoformat(inventory["common_end"] + "T23:59:00+00:00")
    lower_ms = int(start.timestamp() * 1000)
    upper_ms = int(end.timestamp() * 1000)
    expected_minutes = (upper_ms - lower_ms) // 60_000 + 1
    datasets: dict[str, dict[str, Any]] = {}
    alignment: dict[str, Any] = {}
    observed_cache: dict[tuple[str, str], set[int]] = {}

    for symbol in SYMBOLS:
        for family in ["perp_1m", "mark_1m", "index_1m", "spot_1m"]:
            observed: set[int] = set()
            for source in rows:
                if source["symbol"] == symbol and source["family"] == family:
                    observed.update(archive_timestamps(source, lower_ms, upper_ms))
            observed_cache[(symbol, family)] = observed
            blocks = missing_blocks(observed, lower_ms, upper_ms, 60_000)
            key = f"{symbol}:{family}"
            datasets[key] = {
                "expected_rows": expected_minutes,
                "observed_rows": len(observed),
                "coverage": len(observed) / expected_minutes,
                "missing_rows": expected_minutes - len(observed),
                "missing_blocks": blocks,
                "max_missing_block_minutes": max(
                    (block["missing_rows"] for block in blocks), default=0
                ),
            }
        common = set.intersection(
            *(observed_cache[(symbol, family)] for family in [
                "perp_1m",
                "mark_1m",
                "index_1m",
                "spot_1m",
            ])
        )
        blocks = missing_blocks(common, lower_ms, upper_ms, 60_000)
        coverage = len(common) / expected_minutes
        if coverage >= 0.999:
            state = "PASS"
        elif coverage >= 0.995 and max(
            (block["missing_rows"] for block in blocks), default=0
        ) <= 1440:
            state = "CONDITIONAL_PASS_DOCUMENTED_DATASET_LIMITATION"
        else:
            state = "FAIL"
        alignment[symbol] = {
            "expected_rows": expected_minutes,
            "common_rows": len(common),
            "coverage": coverage,
            "missing_rows": expected_minutes - len(common),
            "missing_blocks": blocks,
            "max_missing_block_minutes": max(
                (block["missing_rows"] for block in blocks), default=0
            ),
            "admission_state": state,
        }
        log(f"COVERAGE {symbol} coverage={coverage:.9f} state={state}")

    overall = (
        "STAGE2_COVERAGE_PASS"
        if all(value["admission_state"] == "PASS" for value in alignment.values())
        else "STAGE2_COVERAGE_CONDITIONAL"
        if all(value["admission_state"] != "FAIL" for value in alignment.values())
        else "STAGE2_COVERAGE_FAIL"
    )
    report = {
        "program": "Discovery V3",
        "hypothesis": "H01",
        "stage": 2,
        "created_utc": utc_now(),
        "status": overall,
        "window": {
            "start": inventory["common_start"],
            "end": inventory["common_end"],
            "expected_minutes_per_asset": expected_minutes,
        },
        "policy": {
            "pass_minimum": 0.999,
            "conditional_minimum": 0.995,
            "conditional_max_contiguous_gap_minutes": 1440,
            "imputation_permitted": False,
        },
        "datasets": datasets,
        "four_way_price_alignment": alignment,
        "holdout_state": "SEALED",
        "economic_outcomes_computed": False,
    }
    atomic_json(COVERAGE_JSON, report)
    lines = [
        "# H01 — Stage 2 Minute-Coverage Audit",
        "",
        f"Status: **{overall}**",
        "",
        "The audit uses the frozen common interval and the permanent conservative "
        "data-admissibility thresholds. No values were filled or reconstructed.",
        "",
        "| Symbol | Four-way coverage | Missing minutes | Longest gap | State |",
        "|---|---:|---:|---:|---|",
    ]
    for symbol, values in alignment.items():
        lines.append(
            f"| {symbol} | {values['coverage']:.6%} | {values['missing_rows']} | "
            f"{values['max_missing_block_minutes']} min | {values['admission_state']} |"
        )
    lines.extend(
        [
            "",
            "Four-way alignment requires perpetual, mark, index and spot prices at "
            "the same minute. The holdout remains sealed.",
        ]
    )
    atomic_text(COVERAGE_MD, "\n".join(lines) + "\n")
    return report


def daily_repair_key(family: str, symbol: str, day: str) -> str:
    if family == "perp_1m":
        native = symbol
        root = "futures/cm/daily/klines"
    elif family == "mark_1m":
        native = symbol
        root = "futures/cm/daily/markPriceKlines"
    elif family == "index_1m":
        native = PAIR[symbol]
        root = "futures/cm/daily/indexPriceKlines"
    else:
        raise RuntimeError(f"Unsupported repair family: {family}")
    return f"data/{root}/{native}/1m/{native}-1m-{day}.zip"


def repair_missing_daily_prices() -> dict[str, Any]:
    if not COVERAGE_JSON.exists():
        raise RuntimeError("Coverage report is missing; run coverage first.")
    coverage = json.loads(COVERAGE_JSON.read_text(encoding="utf-8"))
    if coverage.get("economic_outcomes_computed") is not False:
        raise RuntimeError("Repair is allowed only before outcomes.")
    required: set[tuple[str, str, str]] = set()
    for key, values in coverage["datasets"].items():
        symbol, family = key.split(":", 1)
        if family not in {"perp_1m", "mark_1m", "index_1m"}:
            continue
        for block in values["missing_blocks"]:
            start = date.fromisoformat(block["start_utc"][:10])
            end = date.fromisoformat(block["end_utc"][:10])
            for day in dates(start, end):
                required.add((family, symbol, day.isoformat()))

    repaired: list[dict[str, Any]] = []
    unavailable: list[dict[str, Any]] = []
    for index, (family, symbol, day) in enumerate(sorted(required), start=1):
        key = daily_repair_key(family, symbol, day)
        url = SOURCE_BASE + urllib.parse.quote(key, safe="/")
        checksum_url = url + ".CHECKSUM"
        try:
            checksum_payload = request_bytes(checksum_url)
            checksum_text = checksum_payload.decode("utf-8", errors="strict").strip()
            match = re.fullmatch(r"([0-9a-fA-F]{64})\s+\*?(.+\.zip)", checksum_text)
            if not match or PurePosixPath(match.group(2)).name != PurePosixPath(key).name:
                raise RuntimeError("Invalid checksum sidecar")
            payload = request_bytes(url)
            actual_hash = sha256_bytes(payload)
            if actual_hash != match.group(1).lower():
                raise RuntimeError("Provider SHA-256 mismatch")
            destination = (
                BASE / "repair" / "raw" / family / symbol / PurePosixPath(key).name
            )
            destination.parent.mkdir(parents=True, exist_ok=True)
            temp = destination.with_suffix(destination.suffix + ".part")
            temp.write_bytes(payload)
            os.replace(temp, destination)
            sidecar = destination.with_suffix(destination.suffix + ".CHECKSUM")
            sidecar.write_bytes(checksum_payload)
            row = {
                "family": family,
                "symbol": symbol,
                "period": day,
                "object_key": key,
                "source_url": url,
                "expected_size": len(payload),
                "etag": "",
                "provider_sha256": actual_hash,
                "local_path": str(destination.relative_to(BASE)),
                "download_status": "REPAIR_DOWNLOADED",
                "actual_size": len(payload),
                "local_sha256": actual_hash,
                "checksum_match": "true",
            }
            qa_result = inspect_zip({field: str(row.get(field, "")) for field in MANIFEST_FIELDS})
            if qa_result["qa_status"] != "PASS":
                raise RuntimeError(f"Mechanical QA failed: {qa_result}")
            repaired.append(row)
        except Exception as exc:
            unavailable.append(
                {
                    "family": family,
                    "symbol": symbol,
                    "day": day,
                    "object_key": key,
                    "error": str(exc),
                }
            )
        if index % 20 == 0:
            log(f"REPAIR progress={index}/{len(required)} unavailable={len(unavailable)}")

    repaired.sort(key=lambda row: (row["family"], row["symbol"], row["period"]))
    atomic_csv(REPAIR_MANIFEST, MANIFEST_FIELDS, repaired)
    report = {
        "program": "Discovery V3",
        "hypothesis": "H01",
        "stage": 2,
        "created_utc": utc_now(),
        "status": "REPAIR_COMPLETE" if not unavailable else "REPAIR_INCOMPLETE",
        "same_provider": True,
        "same_schema": True,
        "raw_monthly_archives_modified": False,
        "holdout_state": "SEALED",
        "economic_outcomes_computed": False,
        "requested_objects": len(required),
        "repaired_objects": len(repaired),
        "unavailable_objects": unavailable,
        "repair_manifest_sha256": sha256_file(REPAIR_MANIFEST),
    }
    atomic_json(REPAIR_REPORT, report)
    log(report["status"])
    return report


def qa() -> dict[str, Any]:
    rows = load_manifest()
    not_ready = [row for row in rows if row.get("checksum_match") != "true"]
    if not_ready:
        raise RuntimeError(f"{len(not_ready)} manifest rows are not checksum-valid.")
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(2, WORKERS // 2)) as pool:
        futures = [pool.submit(inspect_zip, row) for row in rows]
        for index, future in enumerate(as_completed(futures), start=1):
            results.append(future.result())
            if index % 250 == 0:
                log(f"QA progress={index}/{len(rows)}")
    results.sort(key=lambda row: (row["family"], row["symbol"], row["period"]))
    atomic_csv(QA_MATRIX, QA_FIELDS, results)

    by_family: dict[str, dict[str, Any]] = {}
    for family in FAMILIES:
        subset = [row for row in results if row["family"] == family]
        by_family[family] = {
            "files": len(subset),
            "passed": sum(row["qa_status"] == "PASS" for row in subset),
            "failed": sum(row["qa_status"] != "PASS" for row in subset),
            "rows": sum(int(row["row_count"]) for row in subset),
        }
    failures = [row for row in results if row["qa_status"] != "PASS"]
    normalization = normalize_liquidations(rows) if not failures else None
    report = {
        "program": "Discovery V3",
        "hypothesis": "H01",
        "stage": 2,
        "created_utc": utc_now(),
        "status": "STAGE2_QA_PASS" if not failures else "STAGE2_QA_FAIL",
        "files": len(results),
        "failures": len(failures),
        "by_family": by_family,
        "holdout_state": "SEALED",
        "economic_outcomes_computed": False,
        "forward_returns_computed": False,
        "manifest_sha256_after_acquisition": sha256_file(MANIFEST),
        "qa_matrix_sha256": sha256_file(QA_MATRIX),
        "normalization": normalization,
    }
    atomic_json(QA_JSON, report)
    lines = [
        "# H01 — Stage 2 Acquisition and Mechanical QA",
        "",
        f"Status: **{report['status']}**",
        "",
        f"- Official archives inspected: {len(results)}",
        f"- QA failures: {len(failures)}",
        "- Holdout: SEALED",
        "- Economic outcomes computed: no",
        "- Forward returns computed: no",
        "",
        "| Family | Files | Passed | Failed | Rows |",
        "|---|---:|---:|---:|---:|",
    ]
    for family, values in by_family.items():
        lines.append(
            f"| {family} | {values['files']} | {values['passed']} | "
            f"{values['failed']} | {values['rows']} |"
        )
    if failures:
        lines.extend(["", "Stage 3 remains blocked until every failure is resolved."])
    else:
        lines.extend(
            [
                "",
                "Exact provider duplicates in liquidation partitions were removed only "
                "in a hashed derived layer; raw archives remain immutable.",
                f"Normalized liquidation rows: {normalization['unique_rows']}",
                f"Exact duplicates removed: {normalization['exact_duplicates_removed']}",
                "",
                "Stage 2 passed. Stage 3 may inspect development outcomes only.",
            ]
        )
    atomic_text(QA_MD, "\n".join(lines) + "\n")
    log(report["status"])
    return report


def run() -> dict[str, Any]:
    inventory = build_inventory()
    free = shutil.disk_usage(BASE).free
    expected = sum(int(row["expected_size"]) for row in load_manifest())
    if free < expected * 2 + 1024**3:
        raise RuntimeError(
            f"Insufficient free space: need safety margin for {expected} bytes."
        )
    acquire()
    report = qa()
    return {"inventory": inventory, "qa": report}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Discovery V3 H01 Stage 2 official-data acquisition and mechanical QA"
    )
    parser.add_argument(
        "command",
        choices=["inventory", "acquire", "qa", "coverage", "repair", "run"],
        help="Stage-2 action; run performs inventory, sealing, acquisition and QA",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "inventory":
        result: Any = build_inventory()
    elif args.command == "acquire":
        result = {"files": len(acquire())}
    elif args.command == "qa":
        result = qa()
    elif args.command == "coverage":
        result = coverage_audit()
    elif args.command == "repair":
        result = repair_missing_daily_prices()
    else:
        result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
