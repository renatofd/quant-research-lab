from __future__ import annotations

import argparse
import html
import json
import math
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_LAB_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = DEFAULT_LAB_DIR


RESEARCH_LINES = [
    {
        "name": "Mean Reversion",
        "potential": 0.72,
        "implementation_cost": 0.45,
        "overfitting_risk": 0.48,
        "infrastructure_dependency": 0.30,
        "rationale": "Current trend and pullback ideas underperform broadly; a structurally different return-to-mean hypothesis is underexplored.",
    },
    {
        "name": "Statistical Arbitrage",
        "potential": 0.68,
        "implementation_cost": 0.78,
        "overfitting_risk": 0.62,
        "infrastructure_dependency": 0.72,
        "rationale": "Pair relationships and BTC correlation appeared repeatedly, but no spread/pair strategy has been tested.",
    },
    {
        "name": "Cointegration",
        "potential": 0.65,
        "implementation_cost": 0.82,
        "overfitting_risk": 0.64,
        "infrastructure_dependency": 0.76,
        "rationale": "No cointegration tests or spread stationarity research are present in the reports.",
    },
    {
        "name": "Market Microstructure",
        "potential": 0.58,
        "implementation_cost": 0.88,
        "overfitting_risk": 0.70,
        "infrastructure_dependency": 0.85,
        "rationale": "Would require order book, slippage and execution data not evidenced in current artifacts.",
    },
    {
        "name": "Volatility Expansion",
        "potential": 0.74,
        "implementation_cost": 0.42,
        "overfitting_risk": 0.50,
        "infrastructure_dependency": 0.34,
        "rationale": "ATR variants failed alone, but breakout/volatility expansion as a complete idea remains only partially tested.",
    },
    {
        "name": "Regime Switching",
        "potential": 0.76,
        "implementation_cost": 0.55,
        "overfitting_risk": 0.55,
        "infrastructure_dependency": 0.42,
        "rationale": "Regime and eligibility reports show timing/regime effects, but no full switching system has been validated.",
    },
    {
        "name": "Machine Learning supervisionado",
        "potential": 0.63,
        "implementation_cost": 0.74,
        "overfitting_risk": 0.82,
        "infrastructure_dependency": 0.68,
        "rationale": "Research datasets and pattern discovery exist, but walk-forward fragility makes supervised ML high risk without strict validation.",
    },
    {
        "name": "Reinforcement Learning",
        "potential": 0.42,
        "implementation_cost": 0.95,
        "overfitting_risk": 0.92,
        "infrastructure_dependency": 0.92,
        "rationale": "No evidence that simpler hypotheses generalize yet; RL should be deprioritized.",
    },
    {
        "name": "Meta-labeling",
        "potential": 0.70,
        "implementation_cost": 0.60,
        "overfitting_risk": 0.68,
        "infrastructure_dependency": 0.54,
        "rationale": "Pattern and market eligibility reports expose conditions that could label when to accept/reject base signals.",
    },
    {
        "name": "Portfolio Allocation",
        "potential": 0.61,
        "implementation_cost": 0.50,
        "overfitting_risk": 0.44,
        "infrastructure_dependency": 0.48,
        "rationale": "Pair-level losses are consistent, but no allocation layer has been researched.",
    },
    {
        "name": "Pair Selection",
        "potential": 0.78,
        "implementation_cost": 0.32,
        "overfitting_risk": 0.38,
        "infrastructure_dependency": 0.22,
        "rationale": "Market eligibility repeatedly flags pair differences and permanent exclusion candidates.",
    },
    {
        "name": "Dynamic Position Sizing",
        "potential": 0.57,
        "implementation_cost": 0.52,
        "overfitting_risk": 0.58,
        "infrastructure_dependency": 0.44,
        "rationale": "Current research focuses entries; stake and risk overlays remain underexplored.",
    },
    {
        "name": "Position Management",
        "potential": 0.66,
        "implementation_cost": 0.50,
        "overfitting_risk": 0.52,
        "infrastructure_dependency": 0.40,
        "rationale": "Trade pattern reports emphasize exit_reason effects, but position management is not yet isolated.",
    },
    {
        "name": "Exit Optimization",
        "potential": 0.75,
        "implementation_cost": 0.40,
        "overfitting_risk": 0.50,
        "infrastructure_dependency": 0.32,
        "rationale": "Most tested ideas focus entry logic; losing trades and ROI exits suggest exit research may have high leverage.",
    },
    {
        "name": "Time-series Forecasting",
        "potential": 0.50,
        "implementation_cost": 0.80,
        "overfitting_risk": 0.86,
        "infrastructure_dependency": 0.72,
        "rationale": "No forecasting infrastructure exists and current signal families do not yet generalize reliably.",
    },
]


@dataclass(frozen=True)
class ReportArtifact:
    path: Path
    kind: str
    data: Any


class ResearchGapAnalyzer:
    """Build a research map from existing scientific reports only."""

    def __init__(
        self,
        *,
        lab_dir: Path | str = DEFAULT_LAB_DIR,
        output_dir: Path | str = DEFAULT_OUTPUT_DIR,
    ) -> None:
        self.lab_dir = Path(lab_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def analyze(self) -> dict[str, Path]:
        artifacts = self._load_artifacts()
        hypotheses = self._hypotheses(artifacts)
        gaps = self._research_gaps(hypotheses, artifacts)
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "scope": "Read-only analysis of existing scientific report artifacts. No backtests were executed.",
            "artifact_count": len(artifacts),
            "artifact_inventory": [
                {"file": artifact.path.name, "kind": artifact.kind}
                for artifact in artifacts
            ],
            "hypotheses": hypotheses,
            "research_gaps": gaps,
            "recommended_phase2_focus": gaps[:5],
            "global_conclusions": self._global_conclusions(hypotheses, gaps),
        }
        return self._write_reports(report)

    def _load_artifacts(self) -> list[ReportArtifact]:
        artifacts: list[ReportArtifact] = []
        for path in sorted(self.lab_dir.glob("*.json")):
            if path.name.startswith("optimal_regions_"):
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            kind = self._kind(path.name)
            if kind:
                artifacts.append(ReportArtifact(path=path, kind=kind, data=data))
        return artifacts

    def _kind(self, filename: str) -> str | None:
        mapping = [
            ("trend_research_", "trend_research"),
            ("robustness_report_", "robustness"),
            ("neighborhood_report_", "neighborhood"),
            ("walk_forward_report_", "walk_forward"),
            ("ablation_report_", "ablation"),
            ("component_variant_", "component_variant"),
            ("entry_logic_", "entry_logic"),
            ("ensemble_", "ensemble"),
            ("market_eligibility_", "market_eligibility"),
            ("trade_pattern_discovery_", "trade_pattern_discovery"),
            ("strategy_synthesis_", "strategy_synthesizer"),
            ("synthesized_strategy_validation_", "strategy_synthesizer"),
            ("market_regime_profile_", "market_regime_profiler"),
            ("strategy_comparison_", "strategy_comparison"),
            ("research_report_", "parameter_research"),
        ]
        for prefix, kind in mapping:
            if filename.startswith(prefix):
                return kind
        return None

    def _hypotheses(self, artifacts: list[ReportArtifact]) -> list[dict[str, Any]]:
        builders = [
            self._trend_hypothesis,
            self._pullback_hypothesis,
            self._n_of_m_hypothesis,
            self._entry_logic_hypothesis,
            self._component_variant_hypothesis,
            self._ensemble_hypothesis,
            self._market_eligibility_hypothesis,
            self._regime_hypothesis,
            self._ablation_hypothesis,
            self._neighborhood_hypothesis,
            self._strategy_synthesis_hypothesis,
            self._parameter_optimization_hypothesis,
        ]
        hypotheses = [builder(artifacts) for builder in builders]
        return [hypothesis for hypothesis in hypotheses if hypothesis]

    def _trend_hypothesis(self, artifacts: list[ReportArtifact]) -> dict[str, Any]:
        trend = self._first(artifacts, "trend_research", "trend-session-af05d9d01d-690d21")
        robustness = self._first(artifacts, "robustness", "trend-session-af05d9d01d-690d21")
        walk = self._first(artifacts, "walk_forward", "walk-forward-20260707191800")
        favorable = []
        contrary = []
        confidence = 0.45
        if trend:
            top = (trend.data.get("top_100") or [{}])[0]
            if top:
                favorable.append(f"Found at least one high-PF Trend experiment: {self._metric_text(top)}.")
        if robustness:
            optimal = robustness.data.get("optimal_regions") or []
            pareto = robustness.data.get("pareto_frontier") or []
            favorable.append(f"Robustness report found {len(pareto)} Pareto candidates and {len(optimal)} optimal regions.")
            if robustness.data.get("recommendations"):
                contrary.extend(robustness.data["recommendations"][:2])
        if walk:
            gen = walk.data.get("generalization") or {}
            contrary.append(
                f"Walk-forward generalization weak: survival={gen.get('survival_rate')}, PF OOS={gen.get('test_profit_factor_mean')}."
            )
            confidence += 0.10
        return self._hypothesis(
            "TrendStrategy multi-confirmation trend following",
            favorable,
            contrary,
            confidence,
            "descartar",
        )

    def _pullback_hypothesis(self, artifacts: list[ReportArtifact]) -> dict[str, Any]:
        comparison = self._first(artifacts, "strategy_comparison")
        robustness = self._first(artifacts, "robustness", "pullback-session")
        favorable = []
        contrary = []
        if comparison:
            strategies = comparison.data.get("strategies") or []
            pullback = next((row for row in strategies if row.get("label") == "PullbackStrategy"), None)
            if pullback:
                best = pullback.get("best_by_profit_factor") or {}
                favorable.append(f"Best Pullback PF observed: {best.get('profit_factor')} with {best.get('trades')} trades.")
                contrary.append("Strategy comparison did not show robust superiority over TrendStrategy.")
        if robustness:
            contrary.extend((robustness.data.get("recommendations") or [])[:3])
        return self._hypothesis(
            "PullbackStrategy trend pullback continuation",
            favorable,
            contrary,
            0.55,
            "descartar",
        )

    def _n_of_m_hypothesis(self, artifacts: list[ReportArtifact]) -> dict[str, Any]:
        validation = self._first(artifacts, "strategy_synthesizer", "synthesized_strategy_validation")
        favorable = []
        contrary = []
        decision = "descartar"
        confidence = 0.70
        if validation:
            comparison = validation.data.get("comparison") or []
            selected = validation.data.get("selected_hypothesis") or {}
            favorable.append(f"Synthesizer selected {selected.get('name', 'N-of-M Trend Confirmation')} as best generated hypothesis.")
            for row in comparison:
                if row.get("strategy") == "NOfMTrendConfirmationStrategy":
                    favorable.append(
                        f"N-of-M distribution: PF mean={row.get('pf_mean')}, PF median={row.get('pf_median')}."
                    )
            contrary.extend(validation.data.get("conclusions") or [])
            decision = str(validation.data.get("recommendation") or "descartar").lower()
        return self._hypothesis(
            "N-of-M synthesized trend confirmation",
            favorable,
            contrary,
            confidence,
            self._normalize_decision(decision),
        )

    def _entry_logic_hypothesis(self, artifacts: list[ReportArtifact]) -> dict[str, Any]:
        comparison = self._first(artifacts, "entry_logic", "scientific_comparison")
        walk_reports = [artifact for artifact in artifacts if artifact.kind == "walk_forward" and "entry-logic" in artifact.path.name]
        favorable = []
        contrary = []
        if comparison:
            answers = comparison.data.get("answers") or {}
            if answers:
                favorable.append("Entry logic variants were compared across multiple architectures.")
                contrary.extend(self._stringify(value) for value in list(answers.values())[:4])
        poor_wf = 0
        for artifact in walk_reports:
            gen = artifact.data.get("generalization") or {}
            if (gen.get("survival_rate") or 0) < 0.6:
                poor_wf += 1
        if poor_wf:
            contrary.append(f"{poor_wf} entry-logic walk-forward reports failed the 60% survival threshold.")
        return self._hypothesis(
            "Alternative entry logic architectures",
            favorable,
            contrary,
            0.72,
            "congelar",
        )

    def _component_variant_hypothesis(self, artifacts: list[ReportArtifact]) -> dict[str, Any]:
        comparison = self._first(artifacts, "component_variant", "comparison")
        walk_reports = [artifact for artifact in artifacts if artifact.kind == "walk_forward" and "component-variant" in artifact.path.name]
        favorable = []
        contrary = []
        if comparison:
            favorable.append("ATR component variants were compared with the same broad methodology.")
            summary = comparison.data.get("summary") or {}
            if summary:
                favorable.append(f"Component variant summary available for {len(summary)} variants.")
            contrary.append(
                f"Variants reducing zero-trade folds: {comparison.data.get('variants_reducing_zero_trade_folds', [])}."
            )
        failures = [
            artifact.path.name
            for artifact in walk_reports
            if (artifact.data.get("generalization") or {}).get("survival_rate", 0) < 0.6
        ]
        if failures:
            contrary.append(f"{len(failures)} component walk-forward variants failed generalization.")
        return self._hypothesis(
            "ATR component structural variants",
            favorable,
            contrary,
            0.70,
            "descartar",
        )

    def _ensemble_hypothesis(self, artifacts: list[ReportArtifact]) -> dict[str, Any]:
        ensemble = self._first(artifacts, "ensemble")
        favorable = []
        contrary = []
        decision = "descartar"
        if ensemble:
            summary = ensemble.data.get("summary") or {}
            favorable.append(
                f"Ensemble architectures fully ranked; best PF={summary.get('profit_factor_best')}."
            )
            contrary.extend(ensemble.data.get("conclusion") or [])
            decision = str(ensemble.data.get("recommendation") or "descartar").lower()
        return self._hypothesis(
            "Strategy ensemble of existing specialists",
            favorable,
            contrary,
            0.78,
            self._normalize_decision(decision),
        )

    def _market_eligibility_hypothesis(self, artifacts: list[ReportArtifact]) -> dict[str, Any]:
        eligibility = self._first(artifacts, "market_eligibility")
        filters = self._first(artifacts, "market_eligibility", "recommended_filters")
        favorable = []
        contrary = []
        if eligibility:
            conclusion = eligibility.data.get("statistical_conclusion") or {}
            favorable.append(str(conclusion.get("best_research_direction", "Market timing filters show repeated but incomplete evidence.")))
            answers = eligibility.data.get("answers") or {}
            for value in list(answers.values())[:3]:
                favorable.extend(self._as_list(value)[:1])
        if filters:
            contrary.append(str(filters.data.get("conclusion", "No production filters were recommended.")))
        return self._hypothesis(
            "Market eligibility filters",
            favorable,
            contrary,
            0.80,
            "continuar pesquisando",
        )

    def _regime_hypothesis(self, artifacts: list[ReportArtifact]) -> dict[str, Any]:
        regime = self._first(artifacts, "market_regime_profiler")
        favorable = []
        contrary = []
        if regime:
            overall = regime.data.get("overall") or {}
            favorable.append(f"Regime profiler covered {regime.data.get('trade_count')} trades with PF={overall.get('profit_factor')}.")
            favorable.extend((regime.data.get("recommendations") or [])[:2])
            coverage = regime.data.get("coverage") or {}
            unknown = [
                key for key, value in coverage.items()
                if isinstance(value, dict) and value.get("known_ratio", 1) < 0.5
            ]
            if unknown:
                contrary.append(f"Low regime coverage for: {', '.join(unknown[:6])}.")
        return self._hypothesis(
            "Market regime gating",
            favorable,
            contrary,
            0.58,
            "continuar pesquisando",
        )

    def _ablation_hypothesis(self, artifacts: list[ReportArtifact]) -> dict[str, Any]:
        ablation = self._first(artifacts, "ablation")
        favorable = []
        contrary = []
        if ablation:
            summary = ablation.data.get("summary") or {}
            favorable.append(f"Ablation completed with status counts {ablation.data.get('status_counts')}.")
            if summary:
                favorable.append(self._stringify(summary)[:400])
            components = ablation.data.get("component_results") or []
            neutral = [row for row in components if str(row.get("classification", "")).lower() == "neutral"]
            if neutral:
                contrary.append(f"{len(neutral)} components classified neutral.")
        return self._hypothesis(
            "Component ablation of TrendStrategy",
            favorable,
            contrary,
            0.66,
            "congelar",
        )

    def _neighborhood_hypothesis(self, artifacts: list[ReportArtifact]) -> dict[str, Any]:
        neighborhood = self._first(artifacts, "neighborhood")
        favorable = []
        contrary = []
        if neighborhood:
            favorable.extend((neighborhood.data.get("recommendations") or [])[:3])
            curves = neighborhood.data.get("parameter_curves") or {}
            favorable.append(f"Neighborhood explored {len(curves)} parameter curves.")
            contrary.append("Local neighborhood evidence did not remove walk-forward generalization concerns.")
        return self._hypothesis(
            "Local robustness around best Trend experiment",
            favorable,
            contrary,
            0.68,
            "congelar",
        )

    def _strategy_synthesis_hypothesis(self, artifacts: list[ReportArtifact]) -> dict[str, Any]:
        synthesis = self._first(artifacts, "strategy_synthesizer", "strategy_synthesis")
        favorable = []
        contrary = []
        if synthesis:
            proposals = synthesis.data.get("proposals") or []
            favorable.append(f"Strategy Synthesizer generated {len(proposals)} hypotheses.")
            if proposals:
                favorable.append(f"Top hypothesis: {proposals[0].get('name')}.")
            contrary.append("Top synthesized hypothesis later failed validation as production candidate.")
        return self._hypothesis(
            "Automatic strategy synthesis from research reports",
            favorable,
            contrary,
            0.62,
            "continuar pesquisando",
        )

    def _parameter_optimization_hypothesis(self, artifacts: list[ReportArtifact]) -> dict[str, Any]:
        parameter = self._first(artifacts, "parameter_research")
        trend = self._first(artifacts, "trend_research", "phase2_plan")
        favorable = []
        contrary = []
        if parameter:
            favorable.append(f"Initial parameter research completed {parameter.data.get('completed_count')} experiments.")
        if trend:
            favorable.append(f"Phase 2 eligibility: {trend.data.get('eligible_for_phase2')}.")
            contrary.append(str(trend.data.get("recommended_action", "No automatic Phase 2 execution recommended.")))
        return self._hypothesis(
            "Pure parameter optimization",
            favorable,
            contrary,
            0.60,
            "descartar",
        )

    def _hypothesis(
        self,
        name: str,
        favorable: list[str],
        contrary: list[str],
        confidence: float,
        decision: str,
    ) -> dict[str, Any]:
        favorable = [item for item in favorable if item]
        contrary = [item for item in contrary if item]
        confidence = max(0.0, min(1.0, confidence + 0.03 * min(4, len(favorable) + len(contrary))))
        return {
            "name": name,
            "favorable_evidence": favorable[:8],
            "contrary_evidence": contrary[:10],
            "confidence": confidence,
            "decision": self._normalize_decision(decision),
            "evidence_balance": len(favorable) - len(contrary),
        }

    def _research_gaps(
        self,
        hypotheses: list[dict[str, Any]],
        artifacts: list[ReportArtifact],
    ) -> list[dict[str, Any]]:
        tested_names = " ".join(hypothesis["name"].lower() for hypothesis in hypotheses)
        report_names = " ".join(artifact.path.name.lower() for artifact in artifacts)
        gaps = []
        for line in RESEARCH_LINES:
            name = line["name"]
            lowered = name.lower()
            explored = lowered in tested_names or lowered.replace(" ", "_") in report_names
            novelty = 0.25 if explored else 1.0
            scientific_priority = (
                line["potential"] * 0.38
                + (1.0 - line["implementation_cost"]) * 0.18
                + (1.0 - line["overfitting_risk"]) * 0.20
                + (1.0 - line["infrastructure_dependency"]) * 0.14
                + novelty * 0.10
            )
            gaps.append(
                {
                    **line,
                    "already_explored": explored,
                    "scientific_priority": max(0.0, min(1.0, scientific_priority)),
                    "recommended_status": self._gap_status(scientific_priority, line),
                }
            )
        return sorted(gaps, key=lambda row: row["scientific_priority"], reverse=True)

    def _gap_status(self, priority: float, line: dict[str, Any]) -> str:
        if priority >= 0.66:
            return "high_priority"
        if priority >= 0.55:
            return "medium_priority"
        if line["overfitting_risk"] > 0.80 or line["implementation_cost"] > 0.85:
            return "defer"
        return "low_priority"

    def _global_conclusions(
        self,
        hypotheses: list[dict[str, Any]],
        gaps: list[dict[str, Any]],
    ) -> list[str]:
        decisions = defaultdict(int)
        for hypothesis in hypotheses:
            decisions[hypothesis["decision"]] += 1
        return [
            f"Tested hypotheses mapped: {len(hypotheses)}.",
            f"Decision counts: {dict(decisions)}.",
            f"Highest-priority unexplored line: {gaps[0]['name']} (priority={gaps[0]['scientific_priority']:.3f}).",
            "Current evidence favors changing research direction rather than further optimizing the same trend/pullback family.",
            "Production promotion remains unsupported by the reports consumed.",
        ]

    def _first(
        self,
        artifacts: list[ReportArtifact],
        kind: str,
        contains: str | None = None,
    ) -> ReportArtifact | None:
        for artifact in artifacts:
            if artifact.kind != kind:
                continue
            if contains and contains not in artifact.path.name:
                continue
            return artifact
        return None

    def _metric_text(self, row: dict[str, Any]) -> str:
        parts = []
        for key in ["id", "profit_factor", "sharpe", "max_drawdown_abs", "total_trades", "trades"]:
            if key in row:
                parts.append(f"{key}={row[key]}")
        return ", ".join(parts) if parts else self._stringify(row)[:200]

    def _normalize_decision(self, decision: str) -> str:
        lowered = decision.strip().lower()
        if "continuar" in lowered or "pesquis" in lowered:
            return "continuar pesquisando"
        if "congel" in lowered or "fix" in lowered:
            return "congelar"
        if "desc" in lowered or "reject" in lowered:
            return "descartar"
        if "produção" in lowered or "produc" in lowered:
            return "continuar pesquisando"
        return lowered if lowered in {"continuar pesquisando", "congelar", "descartar"} else "congelar"

    def _stringify(self, value: Any) -> str:
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    def _as_list(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return [self._stringify(item) for item in value]
        return [self._stringify(value)]

    def _write_reports(self, report: dict[str, Any]) -> dict[str, Path]:
        json_path = self.output_dir / "research_gap_report.json"
        markdown_path = self.output_dir / "research_gap_report.md"
        html_path = self.output_dir / "research_gap_report.html"
        json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        markdown_path.write_text(self._markdown(report), encoding="utf-8")
        html_path.write_text(self._html(report), encoding="utf-8")
        return {"json": json_path, "markdown": markdown_path, "html": html_path}

    def _markdown(self, report: dict[str, Any]) -> str:
        lines = [
            "# Research Gap Report",
            "",
            report["scope"],
            "",
            "## Hypotheses Tested",
            "| Hypothesis | Confidence | Decision | Evidence Balance |",
            "|---|---:|---|---:|",
        ]
        for hypothesis in report["hypotheses"]:
            lines.append(
                f"| {hypothesis['name']} | {hypothesis['confidence']:.3f} | "
                f"{hypothesis['decision']} | {hypothesis['evidence_balance']} |"
            )
        for hypothesis in report["hypotheses"]:
            lines.extend(["", f"### {hypothesis['name']}", "Favorable evidence:"])
            lines.extend(f"- {item}" for item in hypothesis["favorable_evidence"] or ["None."])
            lines.append("Contrary evidence:")
            lines.extend(f"- {item}" for item in hypothesis["contrary_evidence"] or ["None."])
        lines.extend(["", "## Research Gaps"])
        lines.append("| Line | Priority | Potential | Cost | Overfit Risk | Infra Dependency | Status |")
        lines.append("|---|---:|---:|---:|---:|---:|---|")
        for gap in report["research_gaps"]:
            lines.append(
                f"| {gap['name']} | {gap['scientific_priority']:.3f} | {gap['potential']:.3f} | "
                f"{gap['implementation_cost']:.3f} | {gap['overfitting_risk']:.3f} | "
                f"{gap['infrastructure_dependency']:.3f} | {gap['recommended_status']} |"
            )
        lines.extend(["", "## Global Conclusions"])
        lines.extend(f"- {item}" for item in report["global_conclusions"])
        return "\n".join(lines) + "\n"

    def _html(self, report: dict[str, Any]) -> str:
        def table(rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> str:
            parts = ["<table><thead><tr>"]
            for title, _ in columns:
                parts.append(f"<th>{html.escape(title)}</th>")
            parts.append("</tr></thead><tbody>")
            for row in rows:
                parts.append("<tr>")
                for _, key in columns:
                    value = row.get(key, "")
                    if isinstance(value, float):
                        value = f"{value:.3f}"
                    parts.append(f"<td>{html.escape(str(value))}</td>")
                parts.append("</tr>")
            parts.append("</tbody></table>")
            return "".join(parts)

        parts = [
            "<!doctype html><html><head><meta charset='utf-8'>",
            "<title>Research Gap Report</title>",
            "<style>body{font-family:Segoe UI,Arial,sans-serif;margin:32px;color:#202124;line-height:1.45}"
            "table{border-collapse:collapse;width:100%;font-size:13px;margin:16px 0}"
            "td,th{border:1px solid #ddd;padding:6px;text-align:right}"
            "td:first-child,th:first-child{text-align:left}th{background:#f4f6f8}</style></head><body>",
            "<h1>Research Gap Report</h1>",
            f"<p>{html.escape(report['scope'])}</p>",
            "<h2>Hypotheses Tested</h2>",
            table(
                report["hypotheses"],
                [
                    ("Hypothesis", "name"),
                    ("Confidence", "confidence"),
                    ("Decision", "decision"),
                    ("Evidence Balance", "evidence_balance"),
                ],
            ),
            "<h2>Research Gaps</h2>",
            table(
                report["research_gaps"],
                [
                    ("Line", "name"),
                    ("Priority", "scientific_priority"),
                    ("Potential", "potential"),
                    ("Cost", "implementation_cost"),
                    ("Overfit Risk", "overfitting_risk"),
                    ("Infra Dependency", "infrastructure_dependency"),
                    ("Status", "recommended_status"),
                ],
            ),
            "<h2>Global Conclusions</h2><ul>",
        ]
        parts.extend(f"<li>{html.escape(item)}</li>" for item in report["global_conclusions"])
        parts.append("</ul></body></html>")
        return "\n".join(parts)


def command_analyze(args: argparse.Namespace) -> dict[str, str]:
    analyzer = ResearchGapAnalyzer(lab_dir=args.lab_dir, output_dir=args.output_dir)
    paths = analyzer.analyze()
    return {key: str(path.resolve()) for key, path in paths.items()}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze tested hypotheses and remaining research gaps from existing lab reports.",
    )
    parser.add_argument("--lab-dir", type=Path, default=DEFAULT_LAB_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    subparsers = parser.add_subparsers(dest="command", required=True)
    analyze = subparsers.add_parser("analyze", help="Generate research gap reports.")
    analyze.set_defaults(func=command_analyze)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    result = args.func(args)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
