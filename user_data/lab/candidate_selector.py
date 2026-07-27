from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from .experiment_database import ExperimentDatabase
    from .ranking_engine import RankingEngine
except ImportError:
    from experiment_database import ExperimentDatabase
    from ranking_engine import RankingEngine


class CandidateSelector:
    def __init__(
        self,
        database: ExperimentDatabase | None = None,
        ranking: RankingEngine | None = None,
    ) -> None:
        self.database = database or ExperimentDatabase()
        self.ranking = ranking or RankingEngine(self.database)

    def select(
        self,
        *,
        limit: int = 10,
        order_by: str = "score",
        constraints: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        experiments = (
            self.database.session_experiments(session_id)
            if session_id
            else self.database.list_experiments(status="completed")
        )
        completed = [item for item in experiments if item["status"] == "completed"]
        filtered = [
            experiment
            for experiment in completed
            if self._passes_constraints(experiment, constraints or {})
        ]

        for experiment in filtered:
            experiment["computed_score"] = self.ranking.composite_score(
                experiment.get("metrics", {})
            )

        return sorted(
            filtered,
            key=lambda item: self._sort_value(item, order_by),
            reverse=True,
        )[:limit]

    def export(
        self,
        output_path: Path | str,
        *,
        limit: int = 10,
        order_by: str = "score",
        constraints: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        candidates = self.select(
            limit=limit,
            order_by=order_by,
            constraints=constraints,
            session_id=session_id,
        )
        payload = {
            "generated_at": datetime.now(UTC).isoformat(),
            "session_id": session_id,
            "order_by": order_by,
            "constraints": constraints or {},
            "candidates": [
                {
                    "id": candidate["id"],
                    "strategy_name": candidate["strategy_name"],
                    "strategy_hash": candidate["strategy_hash"],
                    "score": candidate.get("computed_score") or candidate.get("score"),
                    "parameters": candidate["parameters"],
                    "metrics": candidate["metrics"],
                }
                for candidate in candidates
            ],
        }
        output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return output_path

    def _passes_constraints(
        self,
        experiment: dict[str, Any],
        constraints: dict[str, Any],
    ) -> bool:
        metrics = experiment.get("metrics", {})
        for name, expected in constraints.items():
            value = self._number(metrics.get(name))
            if isinstance(expected, dict):
                if "min" in expected and value < float(expected["min"]):
                    return False
                if "max" in expected and value > float(expected["max"]):
                    return False
            elif value != float(expected):
                return False
        return True

    def _sort_value(self, experiment: dict[str, Any], order_by: str) -> float:
        if order_by == "score":
            return self._number(experiment.get("computed_score") or experiment.get("score"))
        return self._number(experiment.get("metrics", {}).get(order_by))

    def _number(self, value: Any) -> float:
        try:
            if value is None:
                return 0.0
            return float(value)
        except (TypeError, ValueError):
            return 0.0
