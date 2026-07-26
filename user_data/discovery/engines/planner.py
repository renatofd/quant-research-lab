"""Budget-aware automatic scientific planner."""

from __future__ import annotations

from config import MAX_HYPOTHESES, MIN_SUCCESS_PROBABILITY
from models import Hypothesis, PlanDecision


TERMINAL_TESTED = {"approved", "rejected", "closed", "inconclusive_sample"}
COST_ORDER = {"low": 0, "medium": 1, "high": 2}
RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "very_high": 3}


class DiscoveryPlanner:
    def decide(self, hypotheses: list[Hypothesis]) -> PlanDecision:
        registered = len(hypotheses)
        tested = sum(item.state in TERMINAL_TESTED for item in hypotheses)
        actionable = [
            item for item in hypotheses if item.state in {"queued", "planned"} and item.data_available
        ]
        blocked = [item for item in hypotheses if item.state == "blocked_data" or (not item.data_available and item.state not in TERMINAL_TESTED)]
        expected = max(
            (item.estimated_success_probability for item in actionable),
            default=0.0,
        )

        if tested >= MAX_HYPOTHESES:
            return PlanDecision(
                "terminate", "A_MAX_HYPOTHESES",
                "Scientific budget reached 30 tested hypotheses; hypothesis 31 is forbidden.",
                None, tested, registered, len(actionable), len(blocked), expected,
            )
        if not actionable and blocked:
            return PlanDecision(
                "terminate", "C_REQUIRED_DATA_UNAVAILABLE",
                "Every scientifically plausible remaining hypothesis requires data absent from the project.",
                None, tested, registered, 0, len(blocked), 0.0,
            )
        if not actionable:
            return PlanDecision(
                "terminate", "B_NO_PLAUSIBLE_HYPOTHESIS",
                "No untested hypothesis with an explicit economic mechanism remains.",
                None, tested, registered, 0, len(blocked), 0.0,
            )
        if expected < MIN_SUCCESS_PROBABILITY:
            return PlanDecision(
                "terminate", "D_EXPECTED_SUCCESS_BELOW_5_PERCENT",
                "Expected scientific success under available resources is below 5%.",
                None, tested, registered, len(actionable), len(blocked), expected,
            )

        candidate = sorted(
            actionable,
            key=lambda item: (
                item.priority,
                COST_ORDER.get(item.computational_cost, 9),
                RISK_ORDER.get(item.overfitting_risk, 9),
                -item.estimated_success_probability,
                item.id,
            ),
        )[0]
        return PlanDecision(
            "execute", "NEXT_HIGHEST_SCIENTIFIC_VALUE",
            "Selected by priority, cost, overfitting risk, data availability, and expected knowledge gain.",
            candidate.id, tested, registered, len(actionable), len(blocked), expected,
        )
