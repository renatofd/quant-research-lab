from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

try:
    from .experiment_database import ExperimentDatabase
    from .experiment_manager import ExperimentManager
    from .search_strategy import SearchStrategy
except ImportError:
    from experiment_database import ExperimentDatabase
    from experiment_manager import ExperimentManager
    from search_strategy import SearchStrategy


class ResearchSession:
    def __init__(
        self,
        *,
        database: ExperimentDatabase | None = None,
        manager: ExperimentManager | None = None,
        search_strategy: SearchStrategy | None = None,
    ) -> None:
        self.database = database or ExperimentDatabase()
        self.manager = manager or ExperimentManager(database=self.database)
        self.search_strategy = search_strategy or SearchStrategy()

    def create(
        self,
        *,
        objective: str,
        strategy_name: str = "EmaRsiVolumeStrategy",
        search_method: str = "random",
        goals: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        start: bool = False,
    ) -> str:
        session_id = self._session_id(objective, strategy_name)
        self.database.create_session(
            session_id=session_id,
            objective=objective,
            strategy_name=strategy_name,
            search_method=search_method,
            goals=goals,
            metadata=metadata,
            status="running" if start else "paused",
        )
        return session_id

    def pause(self, session_id: str) -> None:
        self.database.update_session_status(session_id, "paused")

    def resume(self, session_id: str) -> None:
        for experiment in self.database.session_experiments(session_id):
            if experiment["status"] == "running":
                self.database.update_status(
                    experiment["id"],
                    "error",
                    error="Interrupted",
                    log_path=experiment.get("log_path"),
                    runtime_seconds=experiment.get("runtime_seconds"),
                )
        self.database.update_session_status(session_id, "running")

    def finish(self, session_id: str, *, metadata: dict[str, Any] | None = None) -> None:
        self.database.update_session_status(session_id, "finished", metadata=metadata)

    def status(self, session_id: str) -> dict[str, Any]:
        session = self.database.get_session(session_id)
        if not session:
            raise ValueError(f"Research session {session_id} not found.")

        experiments = self.history(session_id)
        counts: dict[str, int] = {}
        for experiment in experiments:
            counts[experiment["status"]] = counts.get(experiment["status"], 0) + 1

        return {
            "session": session,
            "experiment_count": len(experiments),
            "status_counts": counts,
        }

    def history(self, session_id: str) -> list[dict[str, Any]]:
        return self.database.session_experiments(session_id)

    def plan_experiments(
        self,
        session_id: str,
        *,
        count: int,
        optimize_metric: str = "score",
    ) -> list[str]:
        session = self.database.get_session(session_id)
        if not session:
            raise ValueError(f"Research session {session_id} not found.")

        completed = self.database.list_experiments(status="completed")
        parameter_sets = self.search_strategy.generate(
            session["search_method"],
            count,
            completed_experiments=completed,
            optimize_metric=optimize_metric,
        )

        experiment_ids = []
        strategy_hash = self.manager.strategy_hash()
        for parameters in parameter_sets:
            experiment_id = self._experiment_id(parameters)
            self.database.create_experiment(
                experiment_id=experiment_id,
                strategy_name=session["strategy_name"],
                strategy_hash=strategy_hash,
                parameters=parameters,
            )
            self.database.add_experiment_to_session(session_id, experiment_id)
            experiment_ids.append(experiment_id)

        self.database.update_session_status(
            session_id,
            session["status"],
            metadata={"last_planned_at": datetime.now(UTC).isoformat()},
        )
        return experiment_ids

    def attach_experiments(self, session_id: str, experiment_ids: list[str]) -> None:
        for experiment_id in experiment_ids:
            self.database.add_experiment_to_session(session_id, experiment_id)

    def _session_id(self, objective: str, strategy_name: str) -> str:
        payload = f"{datetime.now(UTC).isoformat()}:{strategy_name}:{objective}"
        digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:10]
        return f"session-{digest}-{uuid.uuid4().hex[:6]}"

    def _experiment_id(self, parameters: dict[str, Any]) -> str:
        payload = json.dumps(parameters, sort_keys=True)
        prefix = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]
        return f"exp-{prefix}-{uuid.uuid4().hex[:8]}"
