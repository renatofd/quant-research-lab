"""Append-only scientific evidence and decision store."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from models import Hypothesis, PlanDecision


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class KnowledgeBase:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("pragma foreign_keys = on")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                create table if not exists metadata (
                    key text primary key,
                    value_json text not null,
                    updated_at text not null
                );
                create table if not exists hypotheses (
                    id text primary key,
                    family_key text not null unique,
                    current_state text not null,
                    created_at text not null,
                    updated_at text not null
                );
                create table if not exists hypothesis_versions (
                    version_id integer primary key autoincrement,
                    hypothesis_id text not null references hypotheses(id),
                    payload_hash text not null,
                    payload_json text not null,
                    created_at text not null,
                    unique(hypothesis_id, payload_hash)
                );
                create table if not exists source_artifacts (
                    source_id integer primary key autoincrement,
                    path text not null,
                    sha256 text not null,
                    bytes integer not null,
                    modified_utc text,
                    imported_at text not null,
                    unique(path, sha256)
                );
                create table if not exists evidence (
                    evidence_id integer primary key autoincrement,
                    hypothesis_id text references hypotheses(id),
                    source_path text not null,
                    source_hash text not null,
                    evidence_type text not null,
                    summary text not null,
                    payload_json text not null,
                    created_at text not null,
                    unique(hypothesis_id, source_path, source_hash, evidence_type)
                );
                create table if not exists decisions (
                    decision_id integer primary key autoincrement,
                    hypothesis_id text references hypotheses(id),
                    decision text not null,
                    reason text not null,
                    criteria_json text not null,
                    created_at text not null
                );
                create table if not exists experiments (
                    experiment_id text primary key,
                    hypothesis_id text not null references hypotheses(id),
                    status text not null,
                    payload_json text not null,
                    created_at text not null,
                    completed_at text
                );
                create table if not exists runs (
                    run_id text primary key,
                    started_at text not null,
                    completed_at text,
                    status text not null,
                    plan_json text not null
                );
                """
            )

    def set_metadata(self, key: str, value: Any) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                insert into metadata(key, value_json, updated_at) values (?, ?, ?)
                on conflict(key) do update set value_json=excluded.value_json, updated_at=excluded.updated_at
                """,
                (key, canonical_json(value), utc_now()),
            )

    def register_hypotheses(self, hypotheses: Iterable[Hypothesis]) -> None:
        now = utc_now()
        with self.connect() as connection:
            for hypothesis in hypotheses:
                payload = canonical_json(hypothesis.as_dict())
                payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
                connection.execute(
                    """
                    insert into hypotheses(id, family_key, current_state, created_at, updated_at)
                    values (?, ?, ?, ?, ?)
                    on conflict(id) do update set
                        current_state=excluded.current_state,
                        updated_at=excluded.updated_at
                    """,
                    (hypothesis.id, hypothesis.family_key, hypothesis.state, now, now),
                )
                connection.execute(
                    """
                    insert or ignore into hypothesis_versions(
                        hypothesis_id, payload_hash, payload_json, created_at
                    ) values (?, ?, ?, ?)
                    """,
                    (hypothesis.id, payload_hash, payload, now),
                )

    def register_source(self, artifact: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                insert or ignore into source_artifacts(
                    path, sha256, bytes, modified_utc, imported_at
                ) values (?, ?, ?, ?, ?)
                """,
                (
                    artifact["path"], artifact["sha256"], artifact["bytes"],
                    artifact.get("modified_utc"), utc_now(),
                ),
            )

    def add_evidence(
        self,
        hypothesis_id: str | None,
        artifact: dict[str, Any],
        evidence_type: str,
        summary: str,
        payload: dict[str, Any],
    ) -> None:
        with self.connect() as connection:
            existing = connection.execute(
                """
                select 1 from evidence
                where hypothesis_id is ? and source_path = ? and source_hash = ?
                  and evidence_type = ?
                limit 1
                """,
                (
                    hypothesis_id,
                    artifact["path"],
                    artifact["sha256"],
                    evidence_type,
                ),
            ).fetchone()
            if existing is not None:
                return
            connection.execute(
                """
                insert or ignore into evidence(
                    hypothesis_id, source_path, source_hash, evidence_type,
                    summary, payload_json, created_at
                ) values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    hypothesis_id,
                    artifact["path"],
                    artifact["sha256"],
                    evidence_type,
                    summary,
                    canonical_json(payload),
                    utc_now(),
                ),
            )

    def append_decision(
        self,
        hypothesis_id: str | None,
        decision: str,
        reason: str,
        criteria: dict[str, Any],
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                insert into decisions(hypothesis_id, decision, reason, criteria_json, created_at)
                values (?, ?, ?, ?, ?)
                """,
                (hypothesis_id, decision, reason, canonical_json(criteria), utc_now()),
            )

    def experiment_count(self, hypothesis_id: str) -> int:
        with self.connect() as connection:
            row = connection.execute(
                "select count(*) as count from experiments where hypothesis_id = ?",
                (hypothesis_id,),
            ).fetchone()
        return int(row["count"])

    def start_run(self, run_id: str, plan: PlanDecision) -> None:
        with self.connect() as connection:
            connection.execute(
                "insert into runs(run_id, started_at, status, plan_json) values (?, ?, ?, ?)",
                (run_id, utc_now(), "running", canonical_json(plan.as_dict())),
            )

    def finish_run(self, run_id: str, status: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "update runs set status=?, completed_at=? where run_id=?",
                (status, utc_now(), run_id),
            )

    def status_counts(self) -> dict[str, int]:
        with self.connect() as connection:
            rows = connection.execute(
                "select current_state, count(*) as count from hypotheses group by current_state"
            ).fetchall()
        return {str(row["current_state"]): int(row["count"]) for row in rows}

    def source_rows(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "select path, sha256, bytes, modified_utc, imported_at from source_artifacts order by path"
            ).fetchall()
        return [dict(row) for row in rows]

    def summary(self) -> dict[str, Any]:
        with self.connect() as connection:
            counts = {
                "hypotheses": connection.execute("select count(*) from hypotheses").fetchone()[0],
                "hypothesis_versions": connection.execute("select count(*) from hypothesis_versions").fetchone()[0],
                "sources": connection.execute("select count(*) from source_artifacts").fetchone()[0],
                "evidence": connection.execute("select count(*) from evidence").fetchone()[0],
                "decisions": connection.execute("select count(*) from decisions").fetchone()[0],
                "experiments": connection.execute("select count(*) from experiments").fetchone()[0],
                "runs": connection.execute("select count(*) from runs").fetchone()[0],
            }
        return {"counts": counts, "states": self.status_counts(), "database": str(self.path)}
