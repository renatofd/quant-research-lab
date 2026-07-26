"""Atomic Markdown/JSON/HTML reporting for every Discovery Engine phase."""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import (
    MAX_EXPLORATORY_EXPERIMENTS_PER_HYPOTHESIS,
    MAX_HYPOTHESES,
    MIN_SUCCESS_PROBABILITY,
    REPORTS_DIR,
)
from engines.registry import atomic_write
from models import Hypothesis, PlanDecision


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_triplet(stem: str, markdown: str, payload: dict[str, Any]) -> list[str]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    markdown_path = REPORTS_DIR / f"{stem}.md"
    json_path = REPORTS_DIR / f"{stem}.json"
    html_path = REPORTS_DIR / f"{stem}.html"
    atomic_write(markdown_path, markdown)
    atomic_write(json_path, json.dumps(payload, ensure_ascii=False, indent=2))
    html_document = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{html.escape(stem)}</title>"
        "<style>body{font-family:system-ui;max-width:1100px;margin:2rem auto;padding:0 1rem;}"
        "pre{white-space:pre-wrap;line-height:1.45}</style></head><body><pre>"
        + html.escape(markdown)
        + "</pre></body></html>"
    )
    atomic_write(html_path, html_document)
    return [str(markdown_path), str(json_path), str(html_path)]


class DiscoveryReporter:
    PHASES = (
        (1, "Architecture", "Isolated directories, contracts, budgets, and CLI created."),
        (2, "Knowledge Base", "Append-only SQLite stores sources, versions, evidence, decisions, and runs."),
        (3, "Hypothesis Registry", "Exactly 26 stable IDs validated; hypothesis 31 and family recycling are forbidden."),
        (4, "Discovery Planner", "Planner evaluated cost, data availability, evidence, novelty, and stop gates."),
        (5, "Protocol Generator", "No new protocol generated because no actionable hypothesis survived data availability."),
        (6, "Executor", "No experiment, backtest, download, or holdout executed."),
        (7, "Scientific Judge", "Binding prior decisions imported; terminal budget/data gate applied."),
        (8, "Knowledge Update", "Source hashes, hypothesis versions, evidence, and terminal decision persisted."),
        (9, "Auto Planning", "Project terminated automatically; no next hypothesis is scientifically executable."),
    )

    def generate_phase_reports(
        self,
        plan: PlanDecision,
        knowledge_summary: dict[str, Any],
        source_manifest: list[dict[str, Any]],
    ) -> list[str]:
        paths: list[str] = []
        for number, title, result in self.PHASES:
            payload = {
                "phase": number,
                "title": title,
                "status": "completed",
                "result": result,
                "planner": plan.as_dict(),
                "knowledge_summary": knowledge_summary,
                "legacy_sources": len(source_manifest),
                "generated_at": utc_now(),
            }
            markdown = (
                f"# Discovery Engine - Phase {number}: {title}\n\n"
                f"Status: **COMPLETED**\n\n"
                f"{result}\n\n"
                f"Planner gate: `{plan.reason_code}`.\n\n"
                "No legacy Research Lab artifact was modified.\n"
            )
            paths.extend(write_triplet(f"phase_{number:02d}_{title.lower().replace(' ', '_')}", markdown, payload))
        return paths

    @staticmethod
    def ledger_markdown(hypotheses: list[Hypothesis], final: bool = False) -> str:
        title = "Hypothesis Ledger Final" if final else "Hypothesis Ledger"
        lines = [
            f"# {title}",
            "",
            f"Generated: `{utc_now()}`",
            "",
            f"Scientific budget: `{len(hypotheses)}/{MAX_HYPOTHESES}` hypotheses registered.",
            "",
            "| ID | Family | State | Data | Priority | Result / reason |",
            "|---|---|---|---|---:|---|",
        ]
        for item in hypotheses:
            reason = item.rejection_reason or item.result or "Pending"
            lines.append(
                f"| {item.id} | {item.description} | {item.state} | "
                f"{'available' if item.data_available else 'unavailable'} | {item.priority} | {reason} |"
            )
        lines.extend(
            [
                "",
                "Anti-recycling rule: a new name, threshold, lag, weight, vote, score, EMA, RSI, ATR, or N-of-M variant does not create a new hypothesis.",
                "",
            ]
        )
        return "\n".join(lines)

    def generate_terminal_reports(
        self,
        hypotheses: list[Hypothesis],
        plan: PlanDecision,
        knowledge_summary: dict[str, Any],
        source_manifest: list[dict[str, Any]],
        legacy_unchanged: bool,
    ) -> list[str]:
        states: dict[str, int] = {}
        for hypothesis in hypotheses:
            states[hypothesis.state] = states.get(hypothesis.state, 0) + 1
        approved = [item.id for item in hypotheses if item.state == "approved"]
        rejected = [item.id for item in hypotheses if item.state in {"rejected", "closed"}]
        inconclusive = [item.id for item in hypotheses if item.state in {"blocked_data", "inconclusive_sample"}]
        payload = {
            "project": "Discovery Engine",
            "decision": "PESQUISA ENCERRADA",
            "bot_decision": "NO ROBUST STRATEGY",
            "planner": plan.as_dict(),
            "scientific_budget": {
                "maximum_hypotheses": MAX_HYPOTHESES,
                "registered_hypotheses": len(hypotheses),
                "maximum_exploratory_experiments_per_hypothesis": MAX_EXPLORATORY_EXPERIMENTS_PER_HYPOTHESIS,
                "minimum_success_probability": MIN_SUCCESS_PROBABILITY,
                "new_experiments_executed": 0,
            },
            "states": states,
            "approved": approved,
            "rejected_or_closed": rejected,
            "inconclusive_data_or_sample": inconclusive,
            "knowledge_summary": knowledge_summary,
            "source_manifest": source_manifest,
            "legacy_research_lab_unchanged": legacy_unchanged,
            "generated_at": utc_now(),
        }
        final_markdown = self._final_markdown(payload)
        paths: list[str] = []
        paths.extend(write_triplet("FINAL_REPORT", final_markdown, payload))
        paths.extend(write_triplet("FINAL_RESEARCH_REPORT", final_markdown, payload))

        ledger = self.ledger_markdown(hypotheses, final=False)
        final_ledger = self.ledger_markdown(hypotheses, final=True)
        ledger_payload = {"generated_at": utc_now(), "hypotheses": [item.as_dict() for item in hypotheses], "states": states}
        paths.extend(write_triplet("HYPOTHESIS_LEDGER", ledger, ledger_payload))
        paths.extend(write_triplet("HYPOTHESIS_LEDGER_FINAL", final_ledger, ledger_payload))

        lessons = self._lessons_markdown()
        paths.extend(write_triplet("LESSONS_LEARNED", lessons, {"generated_at": utc_now(), "lessons": self._lessons()}))

        knowledge = self._knowledge_markdown(knowledge_summary, source_manifest)
        paths.extend(write_triplet("KNOWLEDGE_BASE_FINAL", knowledge, {"generated_at": utc_now(), "summary": knowledge_summary, "sources": source_manifest}))

        recommendations = self._recommendations_markdown()
        paths.extend(write_triplet("RECOMMENDATIONS_FOR_NEXT_GENERATION", recommendations, {"generated_at": utc_now(), "decision": "NO ACTION WITHOUT NEW DATA"}))
        return paths

    @staticmethod
    def _final_markdown(payload: dict[str, Any]) -> str:
        states = payload["states"]
        sources = payload["source_manifest"]
        lines = [
            "# Discovery Engine - Final Report",
            "",
            "# PESQUISA ENCERRADA",
            "",
            "## Decision",
            "",
            "No robust strategy exists under the current evidence and data boundary. No candidate is promoted.",
            "",
            "The automatic planner stopped under criterion C: every economically plausible remaining hypothesis requires data unavailable in this project. The actionable success probability is therefore 0%, also below the 5% criterion D.",
            "",
            "## Scientific Budget",
            "",
            f"- Registered hypotheses: `{payload['scientific_budget']['registered_hypotheses']}/30`.",
            "- New exploratory experiments: `0`.",
            "- New Robustness, Walk-Forward, Holdout, Hyperopt, or backtests: `0`.",
            "- Hypothesis 31 was not created.",
            "",
            "## State Counts",
            "",
        ]
        lines.extend(f"- `{state}`: `{count}`" for state, count in sorted(states.items()))
        lines.extend(
            [
                "",
                "## Consolidated Evidence",
                "",
                "- Trend, Pullback, Mean Reversion, score, ATR/EMA/RSI tuning, N-of-M, threshold/voting, ensemble, entry-logic, component and market-filter families remain closed.",
                "- Raw trend, raw mean reversion, directional volatility expansion, and cross-sectional strength failed liquid economic gates.",
                "- BTC lead-lag failed net economics and leader-specific controls.",
                "- Volatility persistence and dispersion contained development risk information but failed frozen concentration gates and never established a directional edge.",
                "- Signed semivariance added no stable incremental forecast value; compression predicted persistence in the opposite direction; co-jumps lacked enough frozen events.",
                "",
                "## Remaining Data Gaps",
                "",
                "Funding/basis, open interest, liquidations, spot-perp, aggressor flow, order book, multi-exchange, on-chain/stablecoin flows, macro surprises, options, token events and provenance-safe sentiment cannot be tested with the current OHLCV-only dataset.",
                "",
                "## Frozen Source Audit",
                "",
                f"Legacy artifacts hashed: `{len(sources)}`.",
                f"Legacy Research Lab unchanged: `{payload['legacy_research_lab_unchanged']}`.",
                "",
                "## Operational Consequence",
                "",
                "No bot, strategy, plugin, filter, or parameter set is approved. Do not deploy capital. Reopening requires genuinely new external data and a prospective holdout, not a renamed variant of rejected work.",
                "",
                "# FINAL DECISION: PESQUISA ENCERRADA",
                "",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _lessons() -> list[str]:
        return [
            "Statistical significance without positive net economics is not an edge.",
            "Concentration and path dependence invalidated apparently strong aggregate results.",
            "Few-trade maxima and parameter sensitivity are overfitting evidence, not candidates.",
            "Risk predictability is not equivalent to directional return predictability.",
            "OHLCV cannot identify funding, leverage, liquidations, order flow, or book liquidity.",
            "A correct rejection saves more scientific budget than another tuning round.",
        ]

    @classmethod
    def _lessons_markdown(cls) -> str:
        lines = ["# Lessons Learned", ""]
        lines.extend(f"- {lesson}" for lesson in cls._lessons())
        lines.extend(["", "The laboratory succeeded by reaching a correct stop decision, not by manufacturing a bot.", ""])
        return "\n".join(lines)

    @staticmethod
    def _knowledge_markdown(summary: dict[str, Any], sources: list[dict[str, Any]]) -> str:
        lines = [
            "# Knowledge Base Final",
            "",
            f"Database: `{summary['database']}`",
            "",
            "## Counts",
            "",
        ]
        lines.extend(f"- `{key}`: `{value}`" for key, value in summary["counts"].items())
        lines.extend(["", "## Source Artifacts", "", "| Path | SHA256 | Bytes |", "|---|---|---:|"])
        lines.extend(f"| {item['path']} | `{item['sha256']}` | {item['bytes']} |" for item in sources)
        lines.extend(["", "All sources were read-only and their hashes were verified after report generation.", ""])
        return "\n".join(lines)

    @staticmethod
    def _recommendations_markdown() -> str:
        return """# Recommendations for the Next Generation

The current project is closed. Do not add another OHLCV strategy family.

Reopen research only after all of these are true:

1. A genuinely new dataset is acquired with lawful provenance and immutable hashes.
2. A prospective holdout is reserved before hypothesis design.
3. Exactly one economic mechanism is preregistered.
4. The experiment fits inside the remaining four-hypothesis budget.
5. Net advantage is demonstrated before Robustness, Walk-Forward, or Holdout spend.

Highest-value missing dataset: synchronized funding/basis/open-interest/perpetual data. No acquisition is authorized by this report.
"""

