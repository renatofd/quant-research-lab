from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DEFAULT_DB_PATH = Path(__file__).resolve().parent / "experiments.sqlite"


class ExperimentDatabase:
    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                create table if not exists experiments (
                    id text primary key,
                    created_at text not null,
                    updated_at text not null,
                    status text not null,
                    strategy_name text not null,
                    strategy_hash text not null,
                    parameters_json text not null,
                    metrics_json text,
                    score real,
                    runtime_seconds real,
                    result_path text,
                    log_path text,
                    error text
                )
                """
            )
            connection.execute(
                """
                create index if not exists idx_experiments_status
                on experiments(status)
                """
            )
            connection.execute(
                """
                create index if not exists idx_experiments_score
                on experiments(score)
                """
            )
            connection.execute(
                """
                create table if not exists research_sessions (
                    id text primary key,
                    created_at text not null,
                    updated_at text not null,
                    status text not null,
                    objective text not null,
                    strategy_name text not null,
                    search_method text not null,
                    goals_json text not null,
                    metadata_json text not null,
                    started_at text,
                    paused_at text,
                    finished_at text
                )
                """
            )
            connection.execute(
                """
                create index if not exists idx_research_sessions_status
                on research_sessions(status)
                """
            )
            connection.execute(
                """
                create table if not exists session_experiments (
                    session_id text not null,
                    experiment_id text not null,
                    created_at text not null,
                    position integer not null,
                    primary key (session_id, experiment_id),
                    foreign key (session_id) references research_sessions(id),
                    foreign key (experiment_id) references experiments(id)
                )
                """
            )

    def create_experiment(
        self,
        *,
        experiment_id: str,
        strategy_name: str,
        strategy_hash: str,
        parameters: dict[str, Any],
        status: str = "pending",
    ) -> None:
        now = datetime.now(UTC).isoformat()
        with self.connect() as connection:
            connection.execute(
                """
                insert into experiments (
                    id, created_at, updated_at, status, strategy_name,
                    strategy_hash, parameters_json
                ) values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    experiment_id,
                    now,
                    now,
                    status,
                    strategy_name,
                    strategy_hash,
                    json.dumps(parameters, sort_keys=True),
                ),
            )

    def update_status(
        self,
        experiment_id: str,
        status: str,
        *,
        error: str | None = None,
        result_path: Path | str | None = None,
        log_path: Path | str | None = None,
        runtime_seconds: float | None = None,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        with self.connect() as connection:
            connection.execute(
                """
                update experiments
                set status = ?,
                    updated_at = ?,
                    error = coalesce(?, error),
                    result_path = coalesce(?, result_path),
                    log_path = coalesce(?, log_path),
                    runtime_seconds = coalesce(?, runtime_seconds)
                where id = ?
                """,
                (
                    status,
                    now,
                    error,
                    str(result_path) if result_path is not None else None,
                    str(log_path) if log_path is not None else None,
                    runtime_seconds,
                    experiment_id,
                ),
            )

    def save_metrics(
        self,
        experiment_id: str,
        metrics: dict[str, Any],
        *,
        score: float | None = None,
        runtime_seconds: float | None = None,
        result_path: Path | str | None = None,
        log_path: Path | str | None = None,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        with self.connect() as connection:
            connection.execute(
                """
                update experiments
                set status = 'completed',
                    updated_at = ?,
                    metrics_json = ?,
                    score = ?,
                    runtime_seconds = coalesce(?, runtime_seconds),
                    result_path = coalesce(?, result_path),
                    log_path = coalesce(?, log_path),
                    error = null
                where id = ?
                """,
                (
                    now,
                    json.dumps(metrics, sort_keys=True),
                    score,
                    runtime_seconds,
                    str(result_path) if result_path is not None else None,
                    str(log_path) if log_path is not None else None,
                    experiment_id,
                ),
            )

    def get_experiment(self, experiment_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "select * from experiments where id = ?",
                (experiment_id,),
            ).fetchone()

        return self._row_to_dict(row) if row else None

    def list_experiments(
        self,
        *,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        query = "select * from experiments"
        params: list[Any] = []
        if status:
            query += " where status = ?"
            params.append(status)
        query += " order by created_at asc"
        if limit:
            query += " limit ?"
            params.append(limit)

        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()

        return [self._row_to_dict(row) for row in rows]

    def pending(self, limit: int | None = None) -> list[dict[str, Any]]:
        return self.list_experiments(status="pending", limit=limit)

    def create_session(
        self,
        *,
        session_id: str,
        objective: str,
        strategy_name: str,
        search_method: str,
        goals: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        status: str = "paused",
    ) -> None:
        now = datetime.now(UTC).isoformat()
        with self.connect() as connection:
            connection.execute(
                """
                insert into research_sessions (
                    id, created_at, updated_at, status, objective, strategy_name,
                    search_method, goals_json, metadata_json, started_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    now,
                    now,
                    status,
                    objective,
                    strategy_name,
                    search_method,
                    json.dumps(goals or {}, sort_keys=True),
                    json.dumps(metadata or {}, sort_keys=True),
                    now if status == "running" else None,
                ),
            )

    def update_session_status(
        self,
        session_id: str,
        status: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        session = self.get_session(session_id)
        merged_metadata = session["metadata"] if session else {}
        if metadata:
            merged_metadata.update(metadata)

        updates = {
            "running": ("started_at", now),
            "paused": ("paused_at", now),
            "finished": ("finished_at", now),
        }
        timestamp_column, timestamp_value = updates.get(status, (None, None))

        query = """
            update research_sessions
            set status = ?,
                updated_at = ?,
                metadata_json = ?
        """
        params: list[Any] = [
            status,
            now,
            json.dumps(merged_metadata, sort_keys=True),
        ]
        if timestamp_column:
            query += f", {timestamp_column} = ?"
            params.append(timestamp_value)
        query += " where id = ?"
        params.append(session_id)

        with self.connect() as connection:
            connection.execute(query, params)

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "select * from research_sessions where id = ?",
                (session_id,),
            ).fetchone()

        return self._session_row_to_dict(row) if row else None

    def list_sessions(
        self,
        *,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        query = "select * from research_sessions"
        params: list[Any] = []
        if status:
            query += " where status = ?"
            params.append(status)
        query += " order by created_at asc"
        if limit:
            query += " limit ?"
            params.append(limit)

        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()

        return [self._session_row_to_dict(row) for row in rows]

    def add_experiment_to_session(
        self,
        session_id: str,
        experiment_id: str,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        with self.connect() as connection:
            row = connection.execute(
                """
                select coalesce(max(position), -1) + 1 as next_position
                from session_experiments
                where session_id = ?
                """,
                (session_id,),
            ).fetchone()
            connection.execute(
                """
                insert or ignore into session_experiments (
                    session_id, experiment_id, created_at, position
                ) values (?, ?, ?, ?)
                """,
                (session_id, experiment_id, now, row["next_position"]),
            )

    def session_experiments(self, session_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                select e.*
                from session_experiments se
                join experiments e on e.id = se.experiment_id
                where se.session_id = ?
                order by se.position asc
                """,
                (session_id,),
            ).fetchall()

        return [self._row_to_dict(row) for row in rows]

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["parameters"] = json.loads(data.pop("parameters_json"))
        data["strategy_plugin"] = data["parameters"].get("strategy_plugin")
        metrics_json = data.pop("metrics_json")
        data["metrics"] = json.loads(metrics_json) if metrics_json else {}
        return data

    def _session_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["goals"] = json.loads(data.pop("goals_json"))
        data["metadata"] = json.loads(data.pop("metadata_json"))
        return data
