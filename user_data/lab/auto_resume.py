from __future__ import annotations

from typing import Any

try:
    from .experiment_database import ExperimentDatabase
except ImportError:
    from experiment_database import ExperimentDatabase


class AutoResume:
    def __init__(self, database: ExperimentDatabase | None = None) -> None:
        self.database = database or ExperimentDatabase()

    def resumable_sessions(self) -> list[dict[str, Any]]:
        return [
            session
            for session in self.database.list_sessions()
            if session["status"] in {"running", "paused"}
        ]

    def resume_plan(self, session_id: str) -> dict[str, Any]:
        session = self.database.get_session(session_id)
        if not session:
            raise ValueError(f"Research session {session_id} not found.")

        experiments = self.database.session_experiments(session_id)
        grouped: dict[str, list[str]] = {}
        for experiment in experiments:
            grouped.setdefault(experiment["status"], []).append(experiment["id"])

        return {
            "session": session,
            "total_experiments": len(experiments),
            "pending": grouped.get("pending", []),
            "running": grouped.get("running", []),
            "completed": grouped.get("completed", []),
            "error": grouped.get("error", []),
            "next_action": self._next_action(grouped),
        }

    def resume(self, session_id: str, *, reset_running: bool = True) -> dict[str, Any]:
        if reset_running:
            for experiment_id in self.resume_plan(session_id)["running"]:
                self.database.update_status(
                    experiment_id,
                    "error",
                    error="Interrupted",
                )

        self.database.update_session_status(session_id, "running")
        return self.resume_plan(session_id)

    def _next_action(self, grouped: dict[str, list[str]]) -> str:
        if grouped.get("pending") or grouped.get("running"):
            return "continue_pending_experiments"
        if grouped.get("error"):
            return "review_or_retry_errors"
        return "plan_more_experiments"
