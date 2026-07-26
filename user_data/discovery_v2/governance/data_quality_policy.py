#!/usr/bin/env python3
"""Permanent, outcome-blind Discovery V2 data-quality classification policy."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

PASS = "PASS"
FAIL = "FAIL"
CONDITIONAL = "CONDITIONAL_PASS_DOCUMENTED_DATASET_LIMITATION"
POLICY_PATH = Path(__file__).with_name("DATA_QUALITY_POLICY_V1.json")

BOOL_FIELDS = {
    "C01": "official_source_gap_confirmed",
    "C02": "reproducible_provenance",
    "C03": "pipeline_integrity_pass",
    "C04": "missing_timestamps_enumerated_immutable",
    "C05": "classification_pre_outcome",
    "C06": "same_source_recovery_unavailable",
    "C07": "no_imputation_or_synthetic_reconstruction",
    "C11": "symmetric_common_intersection_policy_frozen",
    "C12": "gap_not_hypothesis_defining_event",
    "C13": "sample_and_replication_minima_preserved",
    "C14": "holdout_sealed",
    "C15": "sensitivity_preregistered",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    policy = json.loads(path.read_text(encoding="utf-8"))
    if policy["version"] != "1.0.0":
        raise ValueError("unsupported policy version")
    if policy["unconditional_coverage_gate"] != 0.999:
        raise ValueError("the 99.9% gate is immutable")
    if policy["conditional_coverage_floor"] != 0.995:
        raise ValueError("unexpected conditional coverage floor")
    if len(policy["conditional_criteria"]) != 15:
        raise ValueError("the permanent policy requires exactly 15 criteria")
    return policy


def evaluate_criteria(evidence: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for criterion_id, field in BOOL_FIELDS.items():
        value = evidence.get(field)
        results.append({"id": criterion_id, "field": field, "value": value, "pass": value is True})

    coverage = evidence.get("coverage_proportion")
    results.append({
        "id": "C08",
        "field": "coverage_proportion",
        "value": coverage,
        "pass": isinstance(coverage, (int, float))
        and policy["conditional_coverage_floor"] <= coverage < policy["unconditional_coverage_gate"],
    })
    gap_hours = evidence.get("max_contiguous_gap_hours")
    results.append({
        "id": "C09",
        "field": "max_contiguous_gap_hours",
        "value": gap_hours,
        "pass": isinstance(gap_hours, (int, float)) and gap_hours <= policy["max_contiguous_gap_hours"],
    })
    sessions = evidence.get("max_affected_sessions_per_rolling_12m")
    results.append({
        "id": "C10",
        "field": "max_affected_sessions_per_rolling_12m",
        "value": sessions,
        "pass": isinstance(sessions, int) and sessions <= policy["max_affected_sessions_per_rolling_12m"],
    })
    return sorted(results, key=lambda item: int(item["id"][1:]))


def classify(evidence: dict[str, Any], policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or load_policy()
    threshold = evidence.get("mechanical_coverage_gate")
    if threshold != policy["unconditional_coverage_gate"]:
        raise ValueError("mechanical coverage gate must remain exactly 0.999")
    coverage = evidence.get("coverage_proportion")
    if not isinstance(coverage, (int, float)):
        raise ValueError("coverage_proportion must be numeric")
    mechanical_pass = coverage >= threshold
    if evidence.get("mechanical_coverage_pass") is not mechanical_pass:
        raise ValueError("mechanical_coverage_pass is inconsistent with observed coverage")

    hard_integrity = evidence.get("hard_integrity_gates_pass") is True
    criteria = evaluate_criteria(evidence, policy)
    all_conditional = all(item["pass"] for item in criteria)

    if mechanical_pass and hard_integrity:
        classification = PASS
    elif not mechanical_pass and hard_integrity and all_conditional:
        classification = CONDITIONAL
    else:
        classification = FAIL

    return {
        "policy_version": policy["version"],
        "policy_sha256": sha256(POLICY_PATH),
        "mechanical_subgate": {
            "threshold": threshold,
            "coverage": coverage,
            "result": PASS if mechanical_pass else FAIL,
            "unchanged": True,
        },
        "conditional_criteria": criteria,
        "all_15_conditional_criteria_pass": all_conditional,
        "global_data_admissibility": classification,
        "hypothesis_status": "UNTESTED",
        "scientific_effect": {
            "confirms_hypothesis": False,
            "rejects_hypothesis": False,
            "permits_threshold_relaxation": False,
            "requires_block_matched_sensitivity": classification == CONDITIONAL,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify a Discovery V2 dataset under the permanent QA policy.")
    parser.add_argument("evidence", type=Path, help="Outcome-blind evidence JSON")
    parser.add_argument("--output", type=Path, required=True, help="New JSON output; existing files are refused")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    result = classify(evidence)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(result["global_data_admissibility"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
