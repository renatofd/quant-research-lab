"""Validated hypothesis registry with anti-recycling enforcement."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Iterable

from config import MAX_HYPOTHESES, REGISTRY_DIR
from models import Hypothesis


EXPECTED_IDS = [*(f"A{index:02d}" for index in range(1, 12)), *(f"B{index:02d}" for index in range(12, 27))]
VALID_ID = re.compile(r"^[A-Z][0-9]{2}$")


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


class HypothesisRegistry:
    def __init__(self, source: Path) -> None:
        self.source = source
        self._hypotheses: list[Hypothesis] = []

    def load(self) -> list[Hypothesis]:
        raw = json.loads(self.source.read_text(encoding="utf-8-sig"))
        if not isinstance(raw, list):
            raise ValueError("Hypothesis registry must be a JSON list.")
        hypotheses = [Hypothesis(**item) for item in raw]
        self.validate(hypotheses)
        self._hypotheses = hypotheses
        return list(hypotheses)

    def validate(self, hypotheses: Iterable[Hypothesis]) -> None:
        items = list(hypotheses)
        if len(items) > MAX_HYPOTHESES:
            raise ValueError(f"Scientific budget exceeded: {len(items)} > {MAX_HYPOTHESES} hypotheses.")
        ids = [item.id for item in items]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate hypothesis ID detected.")
        if any(not VALID_ID.fullmatch(item.id) for item in items):
            raise ValueError("Every hypothesis must use a stable letter-plus-two-digits ID.")
        if ids != EXPECTED_IDS:
            raise ValueError(f"Frozen registry IDs/order changed. Expected {EXPECTED_IDS}, got {ids}.")
        families = [item.family_key.strip().lower() for item in items]
        if len(families) != len(set(families)):
            raise ValueError("Duplicate family_key detected; renamed variants are forbidden.")
        for item in items:
            if not 0.0 <= item.estimated_success_probability <= 1.0:
                raise ValueError(f"{item.id}: invalid success probability.")
            required = (
                item.description,
                item.economic_hypothesis,
                item.protocol,
                item.success_criteria,
                item.rejection_criteria,
                item.pause_criteria,
            )
            if any(not value for value in required):
                raise ValueError(f"{item.id}: incomplete scientific contract.")

    @property
    def hypotheses(self) -> list[Hypothesis]:
        if not self._hypotheses:
            return self.load()
        return list(self._hypotheses)

    def snapshot(self) -> dict[str, object]:
        payload = [item.as_dict() for item in self.hypotheses]
        canonical = canonical_json(payload)
        snapshot = {
            "count": len(payload),
            "maximum": MAX_HYPOTHESES,
            "remaining_budget": MAX_HYPOTHESES - len(payload),
            "sha256": sha256_text(canonical),
            "hypotheses": payload,
        }
        atomic_write(
            REGISTRY_DIR / "registry_snapshot.json",
            json.dumps(snapshot, ensure_ascii=False, indent=2),
        )
        return snapshot

    def assert_new_family_allowed(self, hypothesis_id: str, family_key: str) -> None:
        if len(self.hypotheses) >= MAX_HYPOTHESES:
            raise RuntimeError("Hypothesis budget exhausted; hypothesis 31 is forbidden.")
        if any(item.id == hypothesis_id for item in self.hypotheses):
            raise RuntimeError(f"Hypothesis ID {hypothesis_id} already exists.")
        normalized = family_key.strip().lower()
        if any(item.family_key.strip().lower() == normalized for item in self.hypotheses):
            raise RuntimeError(f"Family {family_key} already exists; renamed recycling is forbidden.")

