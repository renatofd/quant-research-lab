#!/usr/bin/env python3
"""Additive, outcome-blind H01 D1 reclassification under policy v1.0.0."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
GOVERNANCE = HERE.parent / "governance"
sys.path.insert(0, str(GOVERNANCE))

from data_quality_policy import CONDITIONAL, classify  # noqa: E402

INPUT_NAMES = [
    "DISCOVERY_V2_H01_D1_REPORT.json",
    "DISCOVERY_V2_H01_D1_REPAIR_REPORT.json",
    "DISCOVERY_V2_H01_D1_HOLDOUT.json",
    "DISCOVERY_V2_H01_D0_SCIENTIFIC_DECISION.json",
    "DISCOVERY_V2_RESEARCH_CATALOG.json",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_new(path: Path, content: str) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite historical/additive artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def build_evidence(d1: dict[str, Any], repair: dict[str, Any], holdout: dict[str, Any], sensitivity: dict[str, Any]) -> dict[str, Any]:
    structural = d1["structural_summary"]
    criteria = structural["criteria"]
    coverage_values = [
        feed["coverage_proportion"]
        for asset in structural["coverage"].values()
        for feed in asset.values()
    ]
    min_coverage = min(coverage_values)
    gap = repair["gap"]
    recovery = repair["recovery_investigation"]
    integrity = repair["integrity"]

    hard_names = [name for name in criteria if name != "all_kline_symbol_family_coverage_ge_99_9pct"]
    hard_integrity = all(criteria[name] is True for name in hard_names)
    missing = gap["missing_timestamps_utc"]
    require(len(missing) == 288 and len(set(missing)) == 288, "missing timestamp enumeration is not exact")
    require(gap["all_30_missing_sets_identical"] is True, "missing sets are not symmetric")
    require(repair["conclusion"] == "RECOVERY_NOT_POSSIBLE_SAME_SOURCE_ENDPOINT", "official recovery conclusion changed")
    require(recovery["daily_archives_404_count"] == 30, "expected 30 official archive 404s")
    require(recovery["daily_checksums_404_count"] == 30, "expected 30 official checksum 404s")
    require(recovery["monthly_checksums_200_and_unchanged_count"] == 30, "monthly official objects are not unchanged")
    require(integrity["target_raw_archives_unchanged"] is True, "raw archives changed")
    require(integrity["six_original_d1_artifacts_unchanged"] is True, "historical D1 artifacts changed")
    require(holdout["state"] == "SEALED" and holdout["outcome_calculation_permitted"] is False, "holdout is not sealed")
    require(d1["outcomes_inspected"] is False and d1["economic_values_reported"] is False, "outcomes were inspected")
    require(sensitivity["outcome_blind"] is True and sensitivity["holdout_state_at_registration"] == "SEALED", "sensitivity was not preregistered outcome-blind")

    return {
        "mechanical_coverage_gate": 0.999,
        "mechanical_coverage_pass": criteria["all_kline_symbol_family_coverage_ge_99_9pct"],
        "hard_integrity_gates_pass": hard_integrity,
        "official_source_gap_confirmed": repair["conclusion"] == "RECOVERY_NOT_POSSIBLE_SAME_SOURCE_ENDPOINT",
        "reproducible_provenance": recovery["daily_archives_404_count"] == 30 and recovery["daily_checksums_404_count"] == 30,
        "pipeline_integrity_pass": hard_integrity and integrity["target_raw_archives_unchanged"] is True,
        "missing_timestamps_enumerated_immutable": len(missing) == 288 and gap["all_30_missing_sets_identical"] is True,
        "classification_pre_outcome": d1["outcomes_inspected"] is False and d1["economic_values_reported"] is False,
        "same_source_recovery_unavailable": recovery["legitimate_recovery_available"] is False,
        "no_imputation_or_synthetic_reconstruction": integrity["gaps_filled"] is False and integrity["replacement_data_downloaded"] is False,
        "coverage_proportion": min_coverage,
        "max_contiguous_gap_hours": 24,
        "max_affected_sessions_per_rolling_12m": 1,
        "symmetric_common_intersection_policy_frozen": gap["all_30_missing_sets_identical"] is True and sensitivity["analysis_intersection"].startswith("Exclude the documented block globally"),
        "gap_not_hypothesis_defining_event": sensitivity["gap_not_hypothesis_defining_event"] is True,
        "sample_and_replication_minima_preserved": len(structural["sync_pass_assets"]) >= 8 and len(structural["funding_pass_assets"]) >= 8,
        "holdout_sealed": holdout["state"] == "SEALED" and holdout["outcome_calculation_permitted"] is False,
        "sensitivity_preregistered": sensitivity["outcome_blind"] is True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Reclassify H01 D1 without modifying the original mechanical report.")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.root.resolve()
    output_dir = root / "user_data" / "discovery_v2" / "h01" / "d1_reclassification"
    sensitivity_path = root / "user_data" / "discovery_v2" / "h01" / "H01_CONDITIONAL_SENSITIVITY_PREREGISTRATION.json"
    policy_path = root / "user_data" / "discovery_v2" / "governance" / "DATA_QUALITY_POLICY_V1.json"
    source_paths = [root / name for name in INPUT_NAMES] + [sensitivity_path, policy_path]
    for path in source_paths:
        require(path.is_file(), f"required input missing: {path}")
    hashes_before = {str(path.relative_to(root)).replace("\\", "/"): sha256(path) for path in source_paths}

    d1 = load_json(root / INPUT_NAMES[0])
    repair = load_json(root / INPUT_NAMES[1])
    holdout = load_json(root / INPUT_NAMES[2])
    sensitivity = load_json(sensitivity_path)
    evidence = build_evidence(d1, repair, holdout, sensitivity)
    decision = classify(evidence)
    require(decision["global_data_admissibility"] == CONDITIONAL, "H01 does not satisfy every conditional-admission criterion")
    hashes_after = {str(path.relative_to(root)).replace("\\", "/"): sha256(path) for path in source_paths}
    require(hashes_before == hashes_after, "an input changed during reclassification")

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    report = {
        "program": "Discovery V2",
        "hypothesis": "V2-H01",
        "stage": "D1 additive policy reclassification",
        "generated_utc": now,
        "outcomes_inspected": False,
        "economic_analysis_executed": False,
        "historical_d1_artifacts_modified": False,
        "raw_data_modified": False,
        "mechanical_result_original_and_unchanged": d1["mechanical_result"],
        "cause": "DOCUMENTED_OFFICIAL_DATASET_LIMITATION",
        "evidence": evidence,
        "policy_decision": decision,
        "d1_global_state": CONDITIONAL,
        "h01_scientific_status": "UNTESTED",
        "next_state": "D1_CONDITIONAL_PASS_AWAITING_D2_D4_PREREGISTRATION",
        "mandatory_next_controls": ["global common-intersection exclusion", "block-matched sensitivity", "frozen D2-D4 protocol before outcomes"],
    }
    manifest = {
        "program": "Discovery V2",
        "hypothesis": "V2-H01",
        "generated_utc": now,
        "inputs_sha256_before": hashes_before,
        "inputs_sha256_after": hashes_after,
        "inputs_unchanged": hashes_before == hashes_after,
        "output_mode": "ADDITIVE_ONLY_NO_OVERWRITE",
    }
    markdown = f"""# Discovery V2 H01 — D1 Policy Reclassification\n\n+## Decision\n\n+`{CONDITIONAL}`\n\n+The original mechanical coverage subgate remains **FAIL**: {evidence['coverage_proportion']:.12%} versus the unchanged 99.9% requirement. The global D1 state is conditional because every permanent criterion C01–C15 passed. This is a documented official dataset limitation, not a mechanical pass, experimental failure, hypothesis rejection or hypothesis confirmation.\n\n+H01 remains `UNTESTED`; no economic value or holdout outcome was inspected. Historical D1 reports and raw data were not modified.\n\n+## Mandatory continuation controls\n\n+- exclude 29 June 2026 globally from every asset and required feed;\n+- use no filling, interpolation or reconstruction;\n+- freeze D2–D4 before any outcome is opened;\n+- run every pre-registered block-matched deletion;\n+- classify H01 `INCONCLUSIVE` if any matched deletion changes the final conclusion.\n+"""

    write_new(output_dir / "D1_RECLASSIFICATION_INPUT_MANIFEST.json", json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    write_new(output_dir / "D1_RECLASSIFICATION.json", json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    write_new(output_dir / "D1_RECLASSIFICATION.md", markdown)
    print(CONDITIONAL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
