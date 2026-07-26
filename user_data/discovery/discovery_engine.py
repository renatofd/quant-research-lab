"""Autonomous, budget-aware Discovery Engine CLI."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DISCOVERY_ROOT = Path(__file__).resolve().parent
if str(DISCOVERY_ROOT) not in sys.path:
    sys.path.insert(0, str(DISCOVERY_ROOT))

from config import (  # noqa: E402
    DATABASE_PATH,
    DATASETS_DIR,
    DATA_MANIFEST_FILE,
    DISCOVERY_ROOT,
    HYPOTHESES_FILE,
    KNOWLEDGE_DIR,
    LEGACY_LAB_ROOT,
    LEGACY_SOURCE_ARTIFACTS,
    MAX_EXPLORATORY_EXPERIMENTS_PER_HYPOTHESIS,
    MAX_HYPOTHESES,
    MIN_SUCCESS_PROBABILITY,
    PLUGINS_DIR,
    PROTOCOLS_DIR,
    REGISTRY_DIR,
    REPORTS_DIR,
    SOURCE_MANIFEST_FILE,
)
from engines.knowledge_base import KnowledgeBase, utc_now  # noqa: E402
from engines.planner import DiscoveryPlanner  # noqa: E402
from engines.registry import HypothesisRegistry, atomic_write  # noqa: E402
from engines.reporter import DiscoveryReporter  # noqa: E402


SOURCE_HYPOTHESIS_MAP: dict[str, list[str]] = {
    "btc_leadership_report.json": ["A01"],
    "ph4_a02_volatility_persistence_report.json": ["A02"],
    "ph4_a03_signed_volatility_report.json": ["A03"],
    "ph4_a04_cojump_propagation_report.json": ["A04"],
    "ph4_a05_dispersion_risk_report.json": ["A05"],
    "ph4_a07_volatility_compression_report.json": ["A07"],
    "market_eligibility_final_report.json": ["A09", "A11"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Autonomous Discovery Engine. It enforces a 30-hypothesis and "
            "500-experiment budget and never modifies the frozen Research Lab."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("initialize", help="Initialize registry, knowledge base, and source manifests.")
    subparsers.add_parser("run", help="Run one autonomous plan cycle and terminate when a stop gate applies.")
    subparsers.add_parser("status", help="Print current Discovery Engine status as JSON.")
    subparsers.add_parser("finalize", help="Regenerate terminal reports from the frozen knowledge state.")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_decision(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    decision = payload.get("decision")
    if isinstance(decision, dict):
        return decision.get("decision")
    if isinstance(decision, str):
        return decision
    return payload.get("final_decision")


def collect_legacy_manifest() -> list[dict[str, Any]]:
    manifest: list[dict[str, Any]] = []
    for name in LEGACY_SOURCE_ARTIFACTS:
        path = LEGACY_LAB_ROOT / name
        if not path.exists():
            raise FileNotFoundError(f"Required frozen source is missing: {path}")
        stat = path.stat()
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        manifest.append(
            {
                "path": str(path),
                "name": name,
                "sha256": sha256_file(path),
                "bytes": stat.st_size,
                "modified_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                "decision": extract_decision(payload),
            }
        )
    return manifest


def ensure_directories() -> None:
    for path in (
        DISCOVERY_ROOT,
        DATASETS_DIR,
        KNOWLEDGE_DIR,
        PLUGINS_DIR,
        PROTOCOLS_DIR,
        REGISTRY_DIR,
        REPORTS_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)


def initialize_engine() -> tuple[HypothesisRegistry, KnowledgeBase, list[dict[str, Any]]]:
    ensure_directories()
    registry = HypothesisRegistry(HYPOTHESES_FILE)
    hypotheses = registry.load()
    snapshot = registry.snapshot()
    knowledge = KnowledgeBase(DATABASE_PATH)
    knowledge.register_hypotheses(hypotheses)
    knowledge.set_metadata(
        "scientific_budget",
        {
            "maximum_hypotheses": MAX_HYPOTHESES,
            "maximum_exploratory_experiments_per_hypothesis": MAX_EXPLORATORY_EXPERIMENTS_PER_HYPOTHESIS,
            "minimum_success_probability": MIN_SUCCESS_PROBABILITY,
        },
    )
    knowledge.set_metadata("registry_snapshot", {"sha256": snapshot["sha256"], "count": snapshot["count"]})

    manifest = collect_legacy_manifest()
    for artifact in manifest:
        knowledge.register_source(artifact)
        payload = json.loads(Path(artifact["path"]).read_text(encoding="utf-8-sig"))
        hypothesis_ids = SOURCE_HYPOTHESIS_MAP.get(artifact["name"], [None])
        for hypothesis_id in hypothesis_ids:
            knowledge.add_evidence(
                hypothesis_id,
                artifact,
                "legacy_final_artifact",
                artifact.get("decision") or "Final legacy evidence artifact",
                {"decision": artifact.get("decision"), "source_name": artifact["name"]},
            )
    source_payload = {
        "generated_at": utc_now(),
        "mode": "read_only",
        "legacy_lab_root": str(LEGACY_LAB_ROOT),
        "artifacts": manifest,
    }
    atomic_write(SOURCE_MANIFEST_FILE, json.dumps(source_payload, ensure_ascii=False, indent=2))

    data_manifest = {
        "generated_at": utc_now(),
        "available": {
            "exchange": "Binance",
            "market": "spot",
            "timeframe": "5m",
            "format": "Feather",
            "pairs": ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "ADA/USDT", "DOGE/USDT", "LINK/USDT", "AVAX/USDT", "LTC/USDT"],
            "holdout": "none; all current periods are development-consumed",
        },
        "unavailable": [
            "funding", "basis", "open_interest", "liquidations", "perpetuals",
            "aggressor_trades", "order_book", "multi_exchange", "options",
            "onchain_flows", "macro_surprises", "token_events", "sentiment",
        ],
        "legacy_data_mutated": False,
    }
    atomic_write(DATA_MANIFEST_FILE, json.dumps(data_manifest, ensure_ascii=False, indent=2))
    return registry, knowledge, manifest


def run_cycle() -> dict[str, Any]:
    before = collect_legacy_manifest()
    registry, knowledge, manifest = initialize_engine()
    hypotheses = registry.hypotheses
    plan = DiscoveryPlanner().decide(hypotheses)
    run_id = "discovery-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    knowledge.start_run(run_id, plan)
    reporter = DiscoveryReporter()
    try:
        if plan.action == "execute":
            raise RuntimeError("Current registry unexpectedly contains an actionable hypothesis; explicit runner is absent.")
        knowledge.append_decision(
            None,
            "PESQUISA ENCERRADA",
            plan.reason,
            {
                "reason_code": plan.reason_code,
                "criterion_c": plan.reason_code == "C_REQUIRED_DATA_UNAVAILABLE",
                "criterion_d": plan.expected_success_probability < MIN_SUCCESS_PROBABILITY,
                "no_candidate_promoted": True,
            },
        )
        summary = knowledge.summary()
        phase_paths = reporter.generate_phase_reports(plan, summary, manifest)
        after = collect_legacy_manifest()
        legacy_unchanged = {
            item["path"]: item["sha256"] for item in before
        } == {
            item["path"]: item["sha256"] for item in after
        }
        if not legacy_unchanged:
            raise RuntimeError("Frozen Research Lab artifact hash changed during Discovery Engine run.")
        final_paths = reporter.generate_terminal_reports(
            hypotheses, plan, knowledge.summary(), manifest, legacy_unchanged
        )
        knowledge.finish_run(run_id, "closed")
        result = {
            "run_id": run_id,
            "status": "PESQUISA ENCERRADA",
            "plan": plan.as_dict(),
            "phase_reports": phase_paths,
            "final_reports": final_paths,
            "legacy_research_lab_unchanged": legacy_unchanged,
            "knowledge": knowledge.summary(),
        }
        atomic_write(REPORTS_DIR / "execution_inventory.json", json.dumps(result, ensure_ascii=False, indent=2))
        return result
    except Exception:
        knowledge.finish_run(run_id, "error")
        raise


def status() -> dict[str, Any]:
    registry, knowledge, manifest = initialize_engine()
    plan = DiscoveryPlanner().decide(registry.hypotheses)
    return {
        "project": "Discovery Engine",
        "plan": plan.as_dict(),
        "knowledge": knowledge.summary(),
        "source_count": len(manifest),
    }


def finalize() -> dict[str, Any]:
    registry, knowledge, manifest = initialize_engine()
    hypotheses = registry.hypotheses
    plan = DiscoveryPlanner().decide(hypotheses)
    paths = DiscoveryReporter().generate_terminal_reports(
        hypotheses, plan, knowledge.summary(), manifest, True
    )
    return {"status": "PESQUISA ENCERRADA", "reports": paths}


def main() -> int:
    args = parse_args()
    if args.command == "initialize":
        registry, knowledge, manifest = initialize_engine()
        output = {"status": "initialized", "hypotheses": len(registry.hypotheses), "sources": len(manifest), "knowledge": knowledge.summary()}
    elif args.command == "run":
        output = run_cycle()
    elif args.command == "status":
        output = status()
    elif args.command == "finalize":
        output = finalize()
    else:
        raise RuntimeError(f"Unsupported command: {args.command}")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

