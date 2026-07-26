"""Immutable protocol generator for an approved planner decision."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import PROTOCOLS_DIR
from engines.registry import atomic_write, canonical_json
from models import Hypothesis, PlanDecision


class ProtocolGenerator:
    def generate(self, plan: PlanDecision, hypothesis: Hypothesis) -> dict[str, Any]:
        if plan.action != "execute" or plan.hypothesis_id != hypothesis.id:
            raise RuntimeError("A protocol can only be generated for the planner-selected hypothesis.")
        protocol = {
            "hypothesis_id": hypothesis.id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "economic_hypothesis": hypothesis.economic_hypothesis,
            "assumptions": hypothesis.assumptions,
            "required_data": hypothesis.required_data,
            "protocol": hypothesis.protocol,
            "negative_controls": ["temporal placebo", "baseline comparator", "leakage audit"],
            "success_criteria": hypothesis.success_criteria,
            "rejection_criteria": hypothesis.rejection_criteria,
            "pause_criteria": hypothesis.pause_criteria,
            "budget": {"maximum_exploratory_experiments": 500},
            "advanced_validation": {
                "allowed_only_after_positive_net_advantage": True,
                "gates": ["robustness", "walk_forward", "independent_holdout"],
            },
        }
        protocol_hash = hashlib.sha256(canonical_json(protocol).encode("utf-8")).hexdigest()
        protocol["sha256"] = protocol_hash
        path = PROTOCOLS_DIR / f"{hypothesis.id.lower()}_protocol.json"
        atomic_write(path, json.dumps(protocol, ensure_ascii=False, indent=2))
        return protocol

