#!/usr/bin/env python3
"""Outcome-blind V2-H02 official manifest audit. Never downloads market ZIP content."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
H02 = HERE.parent
ROOT = H02.parents[2]
SYMBOLS = ["ADAUSDT", "AVAXUSDT", "BNBUSDT", "BTCUSDT", "DOGEUSDT", "ETHUSDT", "LINKUSDT", "LTCUSDT", "SOLUSDT", "XRPUSDT"]
START = date(2024, 7, 1)
END = date(2026, 6, 30)
LISTING = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
USER_AGENT = "DiscoveryV2-H02-D0-ManifestOnly/1.0"


def days() -> list[date]:
    values = []
    current = START
    while current <= END:
        values.append(current); current += timedelta(days=1)
    return values


def list_prefix(prefix: str) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    objects: dict[str, dict[str, Any]] = {}
    requests: list[dict[str, Any]] = []
    token = None
    while True:
        query = {"list-type": "2", "prefix": prefix, "max-keys": "1000"}
        if token: query["continuation-token"] = token
        url = LISTING + "/?" + urllib.parse.urlencode(query)
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/xml"})
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = response.read()
            requests.append({"url": url, "http_status": response.status, "response_bytes": len(payload)})
        root = ET.fromstring(payload)
        namespace = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
        for item in root.findall("s3:Contents", namespace):
            key = item.findtext("s3:Key", namespaces=namespace)
            objects[key] = {
                "size": int(item.findtext("s3:Size", "0", namespace)),
                "etag": (item.findtext("s3:ETag", "", namespace) or "").strip('"'),
                "last_modified": item.findtext("s3:LastModified", namespaces=namespace),
            }
        truncated = root.findtext("s3:IsTruncated", "false", namespace).lower() == "true"
        if not truncated: break
        token = root.findtext("s3:NextContinuationToken", namespaces=namespace)
        if not token: raise RuntimeError("truncated listing without continuation token")
    return objects, requests


def write_new(path: Path, content: str) -> None:
    if path.exists(): raise FileExistsError(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def csv_text(rows: list[dict[str, Any]]) -> str:
    import io
    buffer = io.StringIO(); writer = csv.DictWriter(buffer, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows); return buffer.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description="V2-H02 D0 manifest-only official metrics audit")
    parser.add_argument("audit", nargs="?", default="audit")
    args = parser.parse_args()
    expected_days = days(); rows = []; request_log = []
    for symbol in SYMBOLS:
        prefix = f"data/futures/um/daily/metrics/{symbol}/"
        objects, requests = list_prefix(prefix); request_log.extend(requests)
        for current in expected_days:
            stem = f"{prefix}{symbol}-metrics-{current.isoformat()}.zip"
            archive = objects.get(stem); checksum = objects.get(stem + ".CHECKSUM")
            rows.append({
                "symbol": symbol, "date": current.isoformat(), "archive_key": stem,
                "archive_present": archive is not None, "archive_size": archive["size"] if archive else None,
                "archive_etag": archive["etag"] if archive else None, "archive_last_modified": archive["last_modified"] if archive else None,
                "checksum_key": stem + ".CHECKSUM", "checksum_present": checksum is not None,
                "checksum_size": checksum["size"] if checksum else None, "checksum_last_modified": checksum["last_modified"] if checksum else None,
            })
    complete_assets = []
    by_asset = {}
    for symbol in SYMBOLS:
        subset = [row for row in rows if row["symbol"] == symbol]
        archives = sum(row["archive_present"] for row in subset); checksums = sum(row["checksum_present"] for row in subset)
        by_asset[symbol] = {"expected_days": len(expected_days), "archives_present": archives, "checksums_present": checksums, "complete": archives == len(expected_days) and checksums == len(expected_days)}
        if by_asset[symbol]["complete"]: complete_assets.append(symbol)
    result = "D0_MANIFEST_PASS" if len(complete_assets) >= 8 else "D0_MANIFEST_FAIL"
    report = {
        "program": "Discovery V2", "hypothesis": "V2-H02", "stage": "D0 manifest-only", "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "mechanical_result": result, "outcomes_inspected": False, "market_zip_content_downloaded": False,
        "source": "Official Binance Data Collection S3 listing metadata",
        "window": {"start": START.isoformat(), "end": END.isoformat(), "days": len(expected_days)},
        "required_new_family": "usd_m_daily_metrics", "expected_objects": len(rows),
        "archives_present": sum(row["archive_present"] for row in rows), "checksums_present": sum(row["checksum_present"] for row in rows),
        "complete_assets": complete_assets, "minimum_complete_assets": 8, "by_asset": by_asset,
        "existing_reusable_data": {"funding_basis_mark_index": "H01 immutable raw", "taker_flow": "H01 USD-M perpetual kline taker fields"},
        "limitations": ["Listing metadata proves object presence, not CSV schema or content quality.", "D1 must validate downloaded checksums, schemas, timestamps, duplicates, gaps and synchronization before outcomes."],
        "next_action": "H02_D1_ACQUIRE_AND_STRUCTURAL_QA" if result == "D0_MANIFEST_PASS" else "H02_STOP_DATA_UNAVAILABLE",
    }
    provenance = {"program": "Discovery V2", "hypothesis": "V2-H02", "user_agent": USER_AGENT, "requests": request_log, "request_count": len(request_log), "outcomes_inspected": False, "zip_content_bytes": 0}
    manifest_path = HERE / "H02_D0_MANIFEST.csv"; report_path = HERE / "H02_D0_REPORT.json"; provenance_path = HERE / "H02_D0_PROVENANCE.json"
    write_new(manifest_path, csv_text(rows)); write_new(report_path, json.dumps(report, indent=2, ensure_ascii=False) + "\n"); write_new(provenance_path, json.dumps(provenance, indent=2) + "\n")
    markdown = f"# Discovery V2 H02 — D0 Manifest Audit\n\nDecision: `{result}`\n\n- expected daily metric objects: {len(rows)}\n- archives present: {report['archives_present']}\n- checksum objects present: {report['checksums_present']}\n- complete assets: {len(complete_assets)}/10 (minimum 8)\n- market ZIP content downloaded: no\n- outcomes inspected: no\n\nD0 establishes presence only. D1 checksum and structural QA remain mandatory.\n"
    write_new(HERE / "H02_D0_REPORT.md", markdown)
    print(result); return 0


if __name__ == "__main__": raise SystemExit(main())
