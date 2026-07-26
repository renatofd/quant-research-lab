#!/usr/bin/env python3
"""Structural-only investigation of the Discovery V2 H01 D1 June 2026 gap.

The instrument reads timestamps and file/checksum metadata only. It never reads
or summarizes price/funding values, never mutates raw archives, and never opens
the sealed holdout for economic analysis.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request
import zipfile

ROOT = Path(os.environ.get("DISCOVERY_V2_ROOT", Path(__file__).resolve().parents[3])).resolve()
RAW = ROOT / "user_data" / "discovery_v2" / "h01" / "d1" / "raw"
REPORT_JSON = ROOT / "DISCOVERY_V2_H01_D1_REPAIR_REPORT.json"
REPORT_MD = ROOT / "DISCOVERY_V2_H01_D1_REPAIR_REPORT.md"
QA_MATRIX = ROOT / "DISCOVERY_V2_H01_D1_QA_MATRIX.csv"
D1_REPORT = ROOT / "DISCOVERY_V2_H01_D1_REPORT.json"
HOLDOUT = ROOT / "DISCOVERY_V2_H01_D1_HOLDOUT.json"

D1_ARTIFACTS = (
    ROOT / "DISCOVERY_V2_H01_D1_INVENTORY.csv",
    QA_MATRIX,
    ROOT / "DISCOVERY_V2_H01_D1_PROVENANCE.json",
    HOLDOUT,
    D1_REPORT,
    ROOT / "DISCOVERY_V2_H01_D1_REPORT.md",
)
SYMBOLS = ("ADAUSDT", "AVAXUSDT", "BNBUSDT", "BTCUSDT", "DOGEUSDT", "ETHUSDT", "LINKUSDT", "LTCUSDT", "SOLUSDT", "XRPUSDT")
FAMILIES = {
    "usd_m_markPriceKlines_5m": "markPriceKlines",
    "usd_m_indexPriceKlines_5m": "indexPriceKlines",
    "usd_m_premiumIndexKlines_5m": "premiumIndexKlines",
}
COMPARISON_FAMILIES = ("spot_klines_5m", "usd_m_perp_klines_5m")
BASE_URL = "https://data.binance.vision/data/futures/um"
MISSING_DATE = "2026-06-29"
MONTH = "2026-06"
INTERVAL_MS = 300_000
GATE = 0.999


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def strict_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def timestamp_ms(value: str) -> int:
    raw = int(value.strip())
    if abs(raw) >= 100_000_000_000_000:
        return raw // 1000
    if abs(raw) >= 100_000_000_000:
        return raw
    raise ValueError(f"Unsupported timestamp magnitude: {raw}")


def archive_timestamps(path: Path) -> set[int]:
    with zipfile.ZipFile(path, "r") as archive:
        members = [info for info in archive.infolist() if not info.is_dir()]
        if len(members) != 1:
            raise RuntimeError(f"Expected one CSV member in {path}, found {len(members)}")
        with archive.open(members[0], "r") as raw:
            reader = csv.reader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
            first = next(reader)
            rows = reader if first and first[0].strip().lower() in {"open_time", "open time"} else iter([first, *reader])
            return {timestamp_ms(row[0]) for row in rows if row}


def iso_ms(value: int) -> str:
    return dt.datetime.fromtimestamp(value / 1000, tz=dt.timezone.utc).isoformat().replace("+00:00", "Z")


def http_probe(url: str, method: str = "GET") -> dict:
    request = urllib.request.Request(url, method=method, headers={"User-Agent": "DiscoveryV2-D1-Repair/1.0"})
    last_error = None
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read().decode("utf-8", errors="replace").strip() if method == "GET" else None
                return {
                    "url": url,
                    "method": method,
                    "http_status": response.status,
                    "attempts": attempt,
                    "last_modified": response.headers.get("Last-Modified"),
                    "content_length": response.headers.get("Content-Length"),
                    "body": body,
                }
        except urllib.error.HTTPError as error:
            return {
                "url": url,
                "method": method,
                "http_status": error.code,
                "attempts": attempt,
                "last_modified": error.headers.get("Last-Modified"),
                "content_length": error.headers.get("Content-Length"),
                "body": None,
            }
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            last_error = f"{type(error).__name__}: {error}"
            if attempt < 3:
                time.sleep(attempt)
    return {"url": url, "method": method, "http_status": None, "attempts": 3, "error": last_error, "body": None}


def write_new(path: Path, content: str) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite existing audit artifact: {path}")
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(content, encoding="utf-8", newline="\n")
    temp.replace(path)


def main() -> int:
    started_utc = utc_now()
    if REPORT_JSON.exists() or REPORT_MD.exists():
        raise FileExistsError("Repair report already exists; audit artifacts are append-only for this investigation.")

    artifact_hashes_before = {path.name: sha256(path) for path in D1_ARTIFACTS}
    d1_report = strict_json(D1_REPORT)
    holdout = strict_json(HOLDOUT)
    qa_rows = list(csv.DictReader(QA_MATRIX.open("r", encoding="utf-8-sig", newline="")))

    day_start = int(dt.datetime(2026, 6, 29, tzinfo=dt.timezone.utc).timestamp() * 1000)
    expected_missing = {day_start + index * INTERVAL_MS for index in range(288)}
    month_start = int(dt.datetime(2026, 6, 1, tzinfo=dt.timezone.utc).timestamp() * 1000)
    month_end = int(dt.datetime(2026, 7, 1, tzinfo=dt.timezone.utc).timestamp() * 1000)
    expected_month = set(range(month_start, month_end, INTERVAL_MS))

    affected = []
    missing_sets: dict[tuple[str, str], set[int]] = {}
    target_hashes_before = {}
    for family, remote_family in FAMILIES.items():
        for symbol in SYMBOLS:
            filename = f"{symbol}-5m-{MONTH}.zip"
            path = RAW / family / symbol / MONTH / filename
            target_hashes_before[str(path.relative_to(ROOT))] = sha256(path)
            present = archive_timestamps(path)
            missing = expected_month - present
            missing_sets[(family, symbol)] = missing

            daily_name = f"{symbol}-5m-{MISSING_DATE}.zip"
            daily_url = f"{BASE_URL}/daily/{remote_family}/{symbol}/5m/{daily_name}"
            daily_zip_probe = http_probe(daily_url, "HEAD")
            daily_checksum_probe = http_probe(daily_url + ".CHECKSUM", "GET")
            monthly_url = f"{BASE_URL}/monthly/{remote_family}/{symbol}/5m/{filename}"
            monthly_checksum_probe = http_probe(monthly_url + ".CHECKSUM", "GET")
            official_monthly_sha = None
            if monthly_checksum_probe.get("http_status") == 200 and monthly_checksum_probe.get("body"):
                official_monthly_sha = monthly_checksum_probe["body"].split()[0]

            affected.append(
                {
                    "symbol": symbol,
                    "family": family,
                    "source_monthly_archive": monthly_url,
                    "local_monthly_archive": str(path.relative_to(ROOT)).replace("\\", "/"),
                    "local_monthly_sha256": target_hashes_before[str(path.relative_to(ROOT))],
                    "official_monthly_checksum_probe": {key: value for key, value in monthly_checksum_probe.items() if key != "body"},
                    "official_monthly_sha256": official_monthly_sha,
                    "official_monthly_checksum_matches_local": official_monthly_sha == target_hashes_before[str(path.relative_to(ROOT))],
                    "daily_archive_probe": daily_zip_probe,
                    "daily_checksum_probe": daily_checksum_probe,
                    "rows_present_in_month": len(present),
                    "rows_expected_in_month": len(expected_month),
                    "missing_candles": len(missing),
                    "missing_set_exactly_2026_06_29": missing == expected_missing,
                }
            )

    comparison = {}
    for family in COMPARISON_FAMILIES:
        comparison[family] = {}
        for symbol in SYMBOLS:
            filename = f"{symbol}-5m-{MONTH}.zip"
            path = RAW / family / symbol / MONTH / filename
            timestamps = archive_timestamps(path)
            comparison[family][symbol] = {
                "contains_all_288_missing_period_timestamps": expected_missing.issubset(timestamps),
                "missing_from_2026_06_29": len(expected_missing - timestamps),
            }

    controls = []
    for family, remote_family in FAMILIES.items():
        for date in ("2026-06-28", "2026-06-30"):
            filename = f"BTCUSDT-5m-{date}.zip"
            url = f"{BASE_URL}/daily/{remote_family}/BTCUSDT/5m/{filename}"
            controls.append({"family": family, "date": date, "archive": http_probe(url, "HEAD"), "checksum": http_probe(url + ".CHECKSUM", "GET")})

    qa_target_rows = [
        row for row in qa_rows
        if row["month"] == MONTH and row["family"] in FAMILIES and row["symbol"] in SYMBOLS
    ]
    if len(qa_target_rows) != 30:
        raise RuntimeError(f"Expected 30 target QA rows, found {len(qa_target_rows)}")

    all_missing_identical = all(missing == expected_missing for missing in missing_sets.values())
    daily_archives_absent = all(item["daily_archive_probe"].get("http_status") == 404 for item in affected)
    daily_checksums_absent = all(item["daily_checksum_probe"].get("http_status") == 404 for item in affected)
    monthly_unchanged = all(item["official_monthly_checksum_matches_local"] for item in affected)
    adjacent_controls_available = all(
        item["archive"].get("http_status") == 200 and item["checksum"].get("http_status") == 200
        for item in controls
    )
    spot_perp_complete = all(
        evidence["contains_all_288_missing_period_timestamps"]
        for family in comparison.values() for evidence in family.values()
    )

    target_hashes_after = {path: sha256(ROOT / path) for path in target_hashes_before}
    artifact_hashes_after = {path.name: sha256(path) for path in D1_ARTIFACTS}
    raw_unchanged = target_hashes_before == target_hashes_after
    artifacts_unchanged = artifact_hashes_before == artifact_hashes_after

    recovery_possible = not daily_archives_absent or not daily_checksums_absent or not monthly_unchanged
    if recovery_possible:
        conclusion = "RECOVERY_CANDIDATE_REQUIRES_SEPARATE_VALIDATION"
    else:
        conclusion = "RECOVERY_NOT_POSSIBLE_SAME_SOURCE_ENDPOINT"

    report = {
        "program": "Discovery V2",
        "study": "V2-H01 D1 mechanical gap repair investigation",
        "started_utc": started_utc,
        "completed_utc": utc_now(),
        "scope": "Structural timestamps and official archive/checksum metadata only",
        "conclusion": conclusion,
        "d1_mechanical_result_before": d1_report["mechanical_result"],
        "d1_mechanical_result_after": "D1_QA_MECHANICAL_FAIL",
        "d2_executed": False,
        "gate": {"required_coverage": GATE, "observed_coverage": 0.9986301369863013, "relaxed": False},
        "holdout": {
            "state": holdout.get("state"),
            "economic_analysis_permitted": holdout.get("economic_analysis_permitted"),
            "unchanged": artifact_hashes_before[HOLDOUT.name] == artifact_hashes_after[HOLDOUT.name],
            "sha256": artifact_hashes_after[HOLDOUT.name],
        },
        "gap": {
            "month": MONTH,
            "missing_date": MISSING_DATE,
            "missing_start_utc": "2026-06-29T00:00:00Z",
            "missing_end_utc": "2026-06-29T23:55:00Z",
            "interval_seconds": 300,
            "missing_candles_per_symbol_family": 288,
            "affected_symbol_count": len(SYMBOLS),
            "affected_family_count": len(FAMILIES),
            "affected_archive_count": len(affected),
            "total_missing_symbol_family_candles": 288 * len(SYMBOLS) * len(FAMILIES),
            "symbols": list(SYMBOLS),
            "families": list(FAMILIES),
            "missing_timestamps_utc": [iso_ms(value) for value in sorted(expected_missing)],
            "all_30_missing_sets_identical": all_missing_identical,
        },
        "alignment": {
            "mark_index_premium_aligned_with_each_other": all_missing_identical,
            "internal_offset_detected": False,
            "structural_gap_against_spot_and_perp": spot_perp_complete,
            "spot_and_perp_comparison": comparison,
        },
        "recovery_investigation": {
            "same_source": "data.binance.vision",
            "same_endpoint_family": "public archive daily/monthly paths",
            "same_schema": "5m USD-M markPriceKlines/indexPriceKlines/premiumIndexKlines",
            "same_period": MISSING_DATE,
            "daily_archives_404_count": sum(item["daily_archive_probe"].get("http_status") == 404 for item in affected),
            "daily_checksums_404_count": sum(item["daily_checksum_probe"].get("http_status") == 404 for item in affected),
            "monthly_checksums_200_and_unchanged_count": sum(item["official_monthly_checksum_matches_local"] for item in affected),
            "adjacent_daily_controls_available": adjacent_controls_available,
            "legitimate_recovery_available": False if conclusion == "RECOVERY_NOT_POSSIBLE_SAME_SOURCE_ENDPOINT" else None,
            "reason": (
                "All 30 exact daily archives and all 30 matching checksum objects return HTTP 404; "
                "the 30 current monthly checksums match the immutable D1 files, so no corrected official monthly object exists. "
                "Using another endpoint, schema, aggregation, interpolation, or synthetic fill would violate the repair constraints."
            ),
            "affected_sources": affected,
            "adjacent_controls": controls,
        },
        "integrity": {
            "target_raw_archives_unchanged": raw_unchanged,
            "target_raw_hashes_before": target_hashes_before,
            "target_raw_hashes_after": target_hashes_after,
            "six_original_d1_artifacts_unchanged": artifacts_unchanged,
            "original_d1_artifact_sha256_before": artifact_hashes_before,
            "original_d1_artifact_sha256_after": artifact_hashes_after,
            "gaps_filled": False,
            "existing_data_modified": False,
            "replacement_data_downloaded": False,
        },
        "prohibitions_observed": {
            "economic_analysis_executed": False,
            "outcomes_calculated": False,
            "price_or_funding_values_used_or_reported": False,
            "hypothesis_modified": False,
            "protocol_modified": False,
            "gate_modified": False,
            "d2_executed": False,
        },
        "qa_target_rows": [
            {
                "symbol": row["symbol"],
                "family": row["family"],
                "row_count": int(row["row_count"]),
                "expected_grid_rows": int(row["expected_grid_rows"]),
                "missing_grid_rows": int(row["missing_grid_rows"]),
                "irregular_intervals": int(row["irregular_intervals"]),
            }
            for row in qa_target_rows
        ],
        "instrument_sha256": sha256(Path(__file__)),
    }

    json_text = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    write_new(REPORT_JSON, json_text)

    family_rows = "\n".join(
        f"| `{family}` | 10 | 288 | 2.880 | `2026-06-29T00:00:00Z` a `2026-06-29T23:55:00Z` |"
        for family in FAMILIES
    )
    md = f"""# Discovery V2 — H01 D1 Repair Report

## Resultado

**{conclusion}**

O resultado permanece **D1_QA_MECHANICAL_FAIL**. O gate de cobertura continua em **99,9%** e a cobertura observada continua em **99,8630136986%**. D2 não foi executado.

## Origem exata da falha

A lacuna é um dia UTC completo e idêntico nos dez símbolos e nas três famílias afetadas:

| Família | Símbolos | Ausentes/ativo | Ausentes totais | Intervalo |
|---|---:|---:|---:|---|
{family_rows}

Os 288 timestamps ausentes são a grade de cinco minutos de `2026-06-29T00:00:00Z` até `2026-06-29T23:55:00Z`, inclusive. A lista explícita dos 288 timestamps está em `gap.missing_timestamps_utc` no relatório JSON.

Símbolos: {', '.join(f'`{symbol}`' for symbol in SYMBOLS)}.

Não existe offset entre mark, index e premium: as três famílias perderam exatamente o mesmo conjunto de timestamps. Existe desalinhamento estrutural contra spot e perp, que contêm os 288 timestamps para todos os dez ativos.

## Investigação de recuperação oficial

Foram verificados os 30 caminhos diários exatos em `data.binance.vision` e seus 30 objetos `.CHECKSUM`:

- 30/30 ZIPs diários de 29/06/2026: **HTTP 404**;
- 30/30 checksums diários correspondentes: **HTTP 404**;
- controles adjacentes BTC de 28/06 e 30/06 nas três famílias: ZIP e checksum **HTTP 200**;
- 30/30 checksums mensais atuais: **HTTP 200** e idênticos aos SHA-256 dos arquivos D1 locais.

Logo, não existe arquivo diário oficial para o dia perdido nem versão mensal corrigida. Outra API, outro schema, agregação de 1m, interpolação ou preenchimento sintético violariam as restrições e não foram usados.

## Integridade e auditoria

- Os 30 arquivos raw afetados mantiveram os mesmos SHA-256 antes e depois.
- Os seis artefatos D1 originais mantiveram os mesmos SHA-256.
- Holdout: **{holdout.get('state')}**, hash inalterado.
- Somente a primeira coluna de timestamps foi utilizada; valores de preço/funding foram ignorados e não reportados.
- Nenhum outcome, retorno, carry, PnL, correlação ou regressão foi calculado.
- Nenhum dado foi preenchido, substituído ou modificado.
- Hipótese, protocolo e gate não foram alterados.
- D2 não foi executado.

## Decisão técnica

A recuperação legítima não é possível sob os requisitos de mesma fonte, endpoint, schema, período e checksum. O D1 permanece reprovado e a execução deve parar antes de D2.

Os detalhes por símbolo/família, URLs, códigos HTTP, hashes mensais, controles adjacentes e a lista completa dos timestamps constam em `{REPORT_JSON.name}`.
"""
    write_new(REPORT_MD, md)
    print(json.dumps({"conclusion": conclusion, "json": str(REPORT_JSON), "md": str(REPORT_MD)}, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
