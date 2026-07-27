from __future__ import annotations

import argparse
import html
import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_LAB_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = DEFAULT_LAB_DIR
DEFAULT_MIN_PROPOSALS = 5
DEFAULT_MAX_PROPOSALS = 20

REPORT_PATTERNS = {
    "trend_research": ["trend_research*.json", "trend_scientific*.json"],
    "pullback_research": ["pullback*.json"],
    "robustness": ["robustness_report*.json"],
    "neighborhood": ["neighborhood*.json"],
    "ablation": ["ablation*.json"],
    "walk_forward": ["walk_forward_report*.json"],
    "market_regime": ["market_regime_profile*.json"],
    "entry_logic": ["entry_logic_report*.json", "entry_logic_scientific_comparison*.json"],
    "component_variant": ["component_variant*.json"],
    "trade_pattern": ["trade_pattern_discovery*.json"],
}


@dataclass
class EvidenceItem:
    source_type: str
    source_path: str
    topic: str
    metric: str
    value: Any
    weight: float
    note: str


@dataclass
class StrategyHypothesis:
    name: str
    description: str
    entry_logic: list[str]
    exit_logic: list[str]
    filters: list[str]
    mandatory_components: list[str]
    optional_components: list[str]
    weights: dict[str, float]
    regime_rules: list[str]
    risk_management: list[str]
    parameters: dict[str, Any]
    pseudo_code: list[str]
    flowchart: list[str]
    justification: list[str]
    confidence: float
    scores: dict[str, float]
    source_evidence: list[str] = field(default_factory=list)


class StrategySynthesizer:
    """Build technical strategy proposals from existing lab reports only."""

    def __init__(
        self,
        *,
        lab_dir: Path | str = DEFAULT_LAB_DIR,
        output_dir: Path | str = DEFAULT_OUTPUT_DIR,
    ) -> None:
        self.lab_dir = Path(lab_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def synthesize(
        self,
        *,
        report_paths: list[Path] | None = None,
        min_proposals: int = DEFAULT_MIN_PROPOSALS,
        max_proposals: int = DEFAULT_MAX_PROPOSALS,
    ) -> dict[str, Path]:
        reports = self._load_reports(report_paths)
        evidence = self._extract_evidence(reports)
        hypotheses = self._build_hypotheses(evidence, min_proposals=min_proposals)
        ranked = self._rank_hypotheses(hypotheses)[:max_proposals]
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "lab_dir": str(self.lab_dir.resolve()),
            "report_count": len(reports),
            "evidence_count": len(evidence),
            "proposal_count": len(ranked),
            "inputs": [
                {
                    "type": item["type"],
                    "path": item["path"],
                    "loaded": item["loaded"],
                }
                for item in reports
            ],
            "methodology": {
                "scope": "Technical strategy specifications only. No Python strategy code is generated.",
                "ranking": (
                    "Composite score from robustness, scientific evidence, generalization, "
                    "simplicity, and inverse overfitting risk."
                ),
                "constraints": [
                    "No backtests executed.",
                    "No strategy files modified.",
                    "No SQLite writes.",
                    "Only existing reports are consumed.",
                ],
            },
            "evidence_summary": self._evidence_summary(evidence),
            "proposals": [self._hypothesis_to_dict(item) for item in ranked],
        }
        return self._write_reports(report)

    def _load_reports(self, report_paths: list[Path] | None) -> list[dict[str, Any]]:
        paths = report_paths or self._discover_reports()
        loaded: list[dict[str, Any]] = []
        seen: set[Path] = set()
        for path in paths:
            resolved = Path(path)
            if not resolved.is_absolute():
                resolved = self.lab_dir / resolved
            resolved = resolved.resolve()
            if resolved in seen or not resolved.exists() or resolved.suffix.lower() != ".json":
                continue
            seen.add(resolved)
            report_type = self._report_type(resolved)
            data: Any = None
            ok = False
            try:
                data = json.loads(resolved.read_text(encoding="utf-8"))
                ok = isinstance(data, dict)
            except Exception:
                data = None
            loaded.append(
                {
                    "type": report_type,
                    "path": str(resolved),
                    "loaded": ok,
                    "data": data if ok else {},
                }
            )
        return loaded

    def _discover_reports(self) -> list[Path]:
        paths: list[Path] = []
        for patterns in REPORT_PATTERNS.values():
            for pattern in patterns:
                paths.extend(self.lab_dir.glob(pattern))
        return sorted(paths, key=lambda path: path.stat().st_mtime, reverse=True)

    def _report_type(self, path: Path) -> str:
        name = path.name.lower()
        for report_type, patterns in REPORT_PATTERNS.items():
            for pattern in patterns:
                regex = "^" + re.escape(pattern.lower()).replace("\\*", ".*") + "$"
                if re.match(regex, name):
                    return report_type
        return "unknown"

    def _extract_evidence(self, reports: list[dict[str, Any]]) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []
        for report in reports:
            data = report["data"]
            source_type = report["type"]
            source_path = report["path"]
            if source_type == "entry_logic":
                evidence.extend(self._entry_logic_evidence(data, source_type, source_path))
            elif source_type == "walk_forward":
                evidence.extend(self._walk_forward_evidence(data, source_type, source_path))
            elif source_type == "robustness":
                evidence.extend(self._robustness_evidence(data, source_type, source_path))
            elif source_type == "market_regime":
                evidence.extend(self._market_regime_evidence(data, source_type, source_path))
            elif source_type == "trade_pattern":
                evidence.extend(self._trade_pattern_evidence(data, source_type, source_path))
            elif source_type == "component_variant":
                evidence.extend(self._component_variant_evidence(data, source_type, source_path))
            elif source_type == "ablation":
                evidence.extend(self._ablation_evidence(data, source_type, source_path))
            elif source_type == "neighborhood":
                evidence.extend(self._neighborhood_evidence(data, source_type, source_path))
            else:
                evidence.extend(self._generic_evidence(data, source_type, source_path))
        return sorted(evidence, key=lambda item: item.weight, reverse=True)

    def _entry_logic_evidence(
        self,
        data: dict[str, Any],
        source_type: str,
        source_path: str,
    ) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []
        for row in data.get("summary", []) or data.get("rows", []):
            variant = str(row.get("label") or row.get("variant") or row.get("strategy") or "entry_logic")
            score = self._number(row.get("scientific_score"), self._number(row.get("score")))
            oos_pf = self._number(row.get("wf_pf_oos_mean"), self._number(row.get("profit_factor")))
            survival = self._number(row.get("wf_survival_rate"), self._number(row.get("survival_rate")))
            zero_folds = self._number(row.get("wf_zero_trade_folds"), 0.0)
            evidence.append(
                EvidenceItem(
                    source_type,
                    source_path,
                    topic=variant,
                    metric="entry_logic_scientific_score",
                    value={
                        "score": score,
                        "oos_profit_factor": oos_pf,
                        "survival_rate": survival,
                        "zero_trade_folds": zero_folds,
                    },
                    weight=max(score, 0.0) + survival + max(oos_pf - 1.0, 0.0) - zero_folds * 0.05,
                    note=f"Entry logic evidence for {variant}.",
                )
            )
        for variant, rows in (data.get("component_importance") or {}).items():
            for row in rows[:5]:
                feature = str(row.get("parameter") or row.get("feature") or "component")
                corr = self._number(row.get("correlation_with_pf"))
                evidence.append(
                    EvidenceItem(
                        source_type,
                        source_path,
                        topic=str(variant),
                        metric="component_correlation",
                        value={"feature": feature, "correlation": corr},
                        weight=abs(corr),
                        note=f"{feature} correlation with Profit Factor in {variant}.",
                    )
                )
        return evidence

    def _walk_forward_evidence(
        self,
        data: dict[str, Any],
        source_type: str,
        source_path: str,
    ) -> list[EvidenceItem]:
        generalization = data.get("generalization") or {}
        session_id = str(data.get("session_id") or Path(source_path).stem)
        survival = self._number(generalization.get("survival_rate"))
        stability = self._number(generalization.get("stability_index"))
        pf = self._number(generalization.get("test_profit_factor_mean"))
        degradation = self._number(generalization.get("average_profit_factor_degradation_pct"))
        return [
            EvidenceItem(
                source_type,
                source_path,
                topic=session_id,
                metric="walk_forward_generalization",
                value={
                    "survival_rate": survival,
                    "stability_index": stability,
                    "test_profit_factor_mean": pf,
                    "degradation_pct": degradation,
                },
                weight=survival + stability + max(pf - 1.0, 0.0) - max(degradation, 0.0) / 100.0,
                note="Out-of-sample generalization evidence.",
            )
        ]

    def _robustness_evidence(
        self,
        data: dict[str, Any],
        source_type: str,
        source_path: str,
    ) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []
        for row in (data.get("robustness_ranking") or [])[:50]:
            score = self._number(row.get("robustness_score"))
            pf = self._number(row.get("profit_factor"))
            drawdown = self._number(row.get("drawdown"))
            evidence.append(
                EvidenceItem(
                    source_type,
                    source_path,
                    topic=str(row.get("id") or "experiment"),
                    metric="robustness_score",
                    value={"robustness_score": score, "profit_factor": pf, "drawdown": drawdown},
                    weight=score + max(pf - 1.0, 0.0) - min(drawdown / 1000.0, 1.0),
                    note="Local robustness ranking.",
                )
            )
        for region in data.get("optimal_regions") or []:
            evidence.append(
                EvidenceItem(
                    source_type,
                    source_path,
                    topic=f"cluster_{region.get('cluster_id', 'unknown')}",
                    metric="optimal_region",
                    value=region.get("parameter_ranges", {}),
                    weight=max(self._number(region.get("profit_factor_mean")), 0.0),
                    note="Continuous robust parameter region.",
                )
            )
        return evidence

    def _market_regime_evidence(
        self,
        data: dict[str, Any],
        source_type: str,
        source_path: str,
    ) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []
        for feature, rows in (data.get("regime_metrics") or {}).items():
            for row in rows[:5]:
                pf = self._number(row.get("profit_factor"))
                profit = self._number(row.get("profit_total_abs"))
                trades = self._number(row.get("trades"))
                evidence.append(
                    EvidenceItem(
                        source_type,
                        source_path,
                        topic=str(feature),
                        metric="regime_performance",
                        value={
                            "feature": feature,
                            "value": row.get("value"),
                            "profit_factor": pf,
                            "profit_total_abs": profit,
                            "trades": trades,
                        },
                        weight=max(pf - 1.0, 0.0) + max(profit, 0.0) / 100.0 + min(trades / 100.0, 1.0),
                        note=f"Regime performance for {feature}={row.get('value')}.",
                    )
                )
        for item in data.get("recommendations") or []:
            evidence.append(
                EvidenceItem(
                    source_type,
                    source_path,
                    topic="recommendation",
                    metric="regime_recommendation",
                    value=str(item),
                    weight=0.5,
                    note=str(item),
                )
            )
        return evidence

    def _trade_pattern_evidence(
        self,
        data: dict[str, Any],
        source_type: str,
        source_path: str,
    ) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []
        for rule in data.get("association_rules") or []:
            lift = self._number(rule.get("lift"))
            confidence = self._number(rule.get("confidence"))
            support = self._number(rule.get("support"))
            evidence.append(
                EvidenceItem(
                    source_type,
                    source_path,
                    topic=str(rule.get("then") or "outcome"),
                    metric="association_rule",
                    value={
                        "if": rule.get("if", []),
                        "then": rule.get("then"),
                        "support": support,
                        "confidence": confidence,
                        "lift": lift,
                    },
                    weight=lift * confidence * max(support, 0.01),
                    note="Association rule from winning/losing trade patterns.",
                )
            )
        for row in data.get("feature_importance") or []:
            importance = self._number(row.get("feature_importance"))
            evidence.append(
                EvidenceItem(
                    source_type,
                    source_path,
                    topic=str(row.get("feature") or "feature"),
                    metric="pattern_feature_importance",
                    value=row,
                    weight=importance,
                    note=f"Trade pattern feature importance for {row.get('feature')}.",
                )
            )
        return evidence

    def _component_variant_evidence(
        self,
        data: dict[str, Any],
        source_type: str,
        source_path: str,
    ) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []
        rows = data.get("variants") or data.get("summary") or data.get("rows") or []
        for row in rows:
            variant = str(row.get("variant") or row.get("label") or row.get("name") or "component_variant")
            robustness = self._number(row.get("robustness_score"))
            survival = self._number(row.get("survival_rate"))
            pf = self._number(row.get("profit_factor_mean"), self._number(row.get("best_profit_factor")))
            evidence.append(
                EvidenceItem(
                    source_type,
                    source_path,
                    topic=variant,
                    metric="component_variant",
                    value=row,
                    weight=robustness + survival + max(pf - 1.0, 0.0),
                    note=f"Component variant evidence for {variant}.",
                )
            )
        return evidence

    def _ablation_evidence(
        self,
        data: dict[str, Any],
        source_type: str,
        source_path: str,
    ) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []
        rows = data.get("components") or data.get("results") or data.get("summary") or []
        for row in rows:
            component = str(row.get("component") or row.get("name") or "component")
            score = self._number(row.get("component_importance_score"), self._number(row.get("importance")))
            classification = str(row.get("classification") or row.get("effect") or "")
            evidence.append(
                EvidenceItem(
                    source_type,
                    source_path,
                    topic=component,
                    metric="ablation_component_importance",
                    value=row,
                    weight=score,
                    note=f"Ablation evidence for {component}: {classification}.",
                )
            )
        return evidence

    def _neighborhood_evidence(
        self,
        data: dict[str, Any],
        source_type: str,
        source_path: str,
    ) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []
        rows = data.get("parameters") or data.get("sensitivity") or data.get("summary") or []
        if isinstance(rows, dict):
            rows = rows.values()
        for row in rows:
            if not isinstance(row, dict):
                continue
            parameter = str(row.get("parameter") or row.get("name") or "parameter")
            radius = self._number(row.get("robustness_radius"))
            sensitivity = abs(self._number(row.get("sensitivity_score")))
            evidence.append(
                EvidenceItem(
                    source_type,
                    source_path,
                    topic=parameter,
                    metric="neighborhood_sensitivity",
                    value=row,
                    weight=radius - sensitivity * 0.1,
                    note=f"Neighborhood evidence for {parameter}.",
                )
            )
        return evidence

    def _generic_evidence(
        self,
        data: dict[str, Any],
        source_type: str,
        source_path: str,
    ) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []
        for key in ("recommendations", "conclusions", "notes"):
            values = data.get(key)
            if isinstance(values, list):
                for value in values[:20]:
                    evidence.append(
                        EvidenceItem(
                            source_type,
                            source_path,
                            topic=key,
                            metric="text_evidence",
                            value=str(value),
                            weight=0.2,
                            note=str(value),
                        )
                    )
        return evidence

    def _build_hypotheses(
        self,
        evidence: list[EvidenceItem],
        *,
        min_proposals: int,
    ) -> list[StrategyHypothesis]:
        context = EvidenceContext(evidence)
        hypotheses = [
            self._hypothesis_regime_gated_trend(context),
            self._hypothesis_n_of_m_trend(context),
            self._hypothesis_voting_confirmation(context),
            self._hypothesis_low_trade_high_quality(context),
            self._hypothesis_loss_avoidance(context),
            self._hypothesis_btc_regime_filter(context),
            self._hypothesis_volume_breakout(context),
            self._hypothesis_adaptive_threshold(context),
            self._hypothesis_pullback_regime(context),
            self._hypothesis_simplicity_baseline(context),
        ]
        while len(hypotheses) < min_proposals:
            hypotheses.append(self._fallback_hypothesis(context, len(hypotheses) + 1))
        return hypotheses

    def _hypothesis_regime_gated_trend(self, context: "EvidenceContext") -> StrategyHypothesis:
        regimes = context.best_regime_rules(limit=4)
        return StrategyHypothesis(
            name="Regime-Gated Trend Continuation",
            description="Trend-following idea that only activates in historically favorable market regimes.",
            entry_logic=[
                "Require bullish trend structure: fast EMA above slow EMA and slow EMA above long trend EMA.",
                "Require ADX to be in a historically favorable momentum bucket.",
                "Require volume state or breakout state to match profitable regimes from reports.",
                "Enter only when composite score passes a moderate threshold.",
            ],
            exit_logic=[
                "Exit on loss of EMA trend alignment.",
                "Exit on ADX deterioration below the profitable momentum regime.",
                "Keep ROI/stoploss as externally configurable research parameters, not hard-coded strategy code.",
            ],
            filters=[
                "Block trades in regimes explicitly associated with losses.",
                "Block low-liquidity volume regimes.",
                "Block BTC regime if historical evidence indicates broad-market headwind.",
            ],
            mandatory_components=["EMA trend", "ADX momentum", "market regime gate"],
            optional_components=["ATR filter", "volume confirmation", "breakout confirmation"],
            weights={"trend": 0.30, "momentum": 0.25, "regime": 0.25, "volume": 0.10, "breakout": 0.10},
            regime_rules=regimes or ["Use only regimes with PF > 1 and positive net profit in MarketRegimeProfiler."],
            risk_management=[
                "Prefer lower stake in regimes with high drawdown contribution.",
                "Disable entries when out-of-sample survival evidence is weak.",
            ],
            parameters={
                "entry_score_threshold": "medium",
                "adx_threshold": "derived from profitable ADX bucket",
                "atr_mode": "optional gate, not mandatory until ablation supports it",
            },
            pseudo_code=[
                "IF regime_allowed",
                "AND ema_fast > ema_slow > ema_trend",
                "AND adx_bucket in profitable_momentum_buckets",
                "AND score(trend, momentum, regime, volume, breakout) >= threshold",
                "THEN enter long",
                "EXIT when trend alignment fails OR momentum regime deteriorates OR configured risk exit triggers",
            ],
            flowchart=[
                "Start -> Regime gate",
                "Regime gate -> Trend alignment",
                "Trend alignment -> Momentum confirmation",
                "Momentum confirmation -> Composite score",
                "Composite score -> Entry",
                "Entry -> Risk/Trend exit",
            ],
            justification=context.justifications(["regime_performance", "walk_forward_generalization", "robustness_score"]),
            confidence=0.0,
            scores={},
            source_evidence=context.sources(["market_regime", "walk_forward", "robustness"]),
        )

    def _hypothesis_n_of_m_trend(self, context: "EvidenceContext") -> StrategyHypothesis:
        return StrategyHypothesis(
            name="N-of-M Trend Confirmation",
            description="Trend strategy using a required count of confirmations instead of a pure weighted sum.",
            entry_logic=[
                "Define confirmation set: EMA trend, ADX, RSI healthy zone, volume, ATR, breakout.",
                "Enter when at least N of M confirmations are active.",
                "Keep core trend condition mandatory only if evidence supports it.",
            ],
            exit_logic=[
                "Exit when confirmation count drops below a defensive threshold.",
                "Exit on trend reversal or configured risk exit.",
            ],
            filters=[
                "Reject trades when N-of-M evidence cluster is associated with OOS loss.",
                "Avoid zero-trade configurations by allowing enough optional confirmations.",
            ],
            mandatory_components=["confirmation count", "trend context"],
            optional_components=["ATR", "breakout", "volume", "RSI"],
            weights={"confirmation_count": 0.45, "trend": 0.25, "regime": 0.20, "simplicity": 0.10},
            regime_rules=context.best_regime_rules(limit=3),
            risk_management=[
                "Use smaller risk when only N confirmations are present and no extra confirmation exists.",
                "Require higher N in unfavorable BTC or volatility regimes.",
            ],
            parameters={
                "n_required": "research range around best N-of-M reports",
                "m_components": ["EMA", "ADX", "RSI", "Volume", "ATR", "Breakout"],
                "exit_confirmation_floor": "N - 2",
            },
            pseudo_code=[
                "confirmations = count(active components)",
                "IF confirmations >= n_required AND regime_allowed THEN enter",
                "IF confirmations < exit_floor OR ema_fast < ema_slow THEN exit",
            ],
            flowchart=[
                "Start -> Count confirmations",
                "Count confirmations -> Regime validation",
                "Regime validation -> Entry",
                "Open trade -> Recount confirmations",
                "Recount confirmations -> Exit if count deteriorates",
            ],
            justification=context.justifications(["entry_logic_scientific_score", "walk_forward_generalization"]),
            confidence=0.0,
            scores={},
            source_evidence=context.sources(["entry_logic", "walk_forward"]),
        )

    def _hypothesis_voting_confirmation(self, context: "EvidenceContext") -> StrategyHypothesis:
        return StrategyHypothesis(
            name="Voting-Based Multi-Signal Trend",
            description="Each component votes for or against entry; only strong majority signals are accepted.",
            entry_logic=[
                "Assign one vote each to trend, ADX, RSI, volume, ATR, breakout, and BTC regime.",
                "Enter when positive votes exceed negative/neutral votes by a configurable margin.",
                "Use regime-specific vote thresholds if reports show different behavior by regime.",
            ],
            exit_logic=[
                "Exit when vote balance turns neutral or negative.",
                "Exit immediately if trend vote flips bearish and ADX remains high.",
            ],
            filters=[
                "Reject trades with high-confidence loss association rules.",
                "Require at least one momentum or breakout vote in addition to trend vote.",
            ],
            mandatory_components=["vote engine", "loss-rule veto"],
            optional_components=["regime-specific thresholds", "BTC vote"],
            weights={"vote_balance": 0.40, "loss_veto": 0.25, "regime": 0.20, "simplicity": 0.15},
            regime_rules=context.best_regime_rules(limit=3),
            risk_management=[
                "Reduce stake when vote margin is small.",
                "Skip entries when association rules indicate high loss confidence.",
            ],
            parameters={
                "vote_threshold": "majority plus margin",
                "loss_rule_confidence_block": ">= 0.60",
                "regime_vote_adjustment": "optional",
            },
            pseudo_code=[
                "votes = collect component votes",
                "IF loss_rule_triggered THEN ignore",
                "IF positive_votes - negative_votes >= vote_threshold THEN enter",
                "IF vote_balance <= exit_threshold THEN exit",
            ],
            flowchart=[
                "Start -> Loss-rule veto",
                "Loss-rule veto -> Vote collection",
                "Vote collection -> Vote threshold",
                "Vote threshold -> Entry",
                "Entry -> Vote deterioration exit",
            ],
            justification=context.justifications(["association_rule", "entry_logic_scientific_score"]),
            confidence=0.0,
            scores={},
            source_evidence=context.sources(["trade_pattern", "entry_logic"]),
        )

    def _hypothesis_low_trade_high_quality(self, context: "EvidenceContext") -> StrategyHypothesis:
        return StrategyHypothesis(
            name="Low-Frequency Quality Filter",
            description="A conservative strategy that accepts fewer trades and prioritizes high-confidence regimes.",
            entry_logic=[
                "Require top profitable regime cluster.",
                "Require strongest association-rule conditions linked to winners.",
                "Require trend and momentum agreement.",
            ],
            exit_logic=[
                "Exit on first break of the quality conditions.",
                "Avoid holding through regime transition.",
            ],
            filters=[
                "Strictly block unfavorable regimes.",
                "Reject entries without winner-pattern support.",
            ],
            mandatory_components=["profitable regime", "winner association rule", "trend agreement"],
            optional_components=["volume surge", "ATR medium/high"],
            weights={"quality": 0.45, "winner_pattern": 0.25, "regime": 0.20, "simplicity": 0.10},
            regime_rules=context.best_regime_rules(limit=5),
            risk_management=[
                "Keep risk per trade low because sample size may be smaller.",
                "Track zero-trade folds explicitly before production consideration.",
            ],
            parameters={
                "minimum_rule_confidence": ">= 0.70",
                "minimum_rule_lift": "> 1.10",
                "minimum_regime_pf": "> 1.00",
            },
            pseudo_code=[
                "IF winner_rule_confidence >= minimum_rule_confidence",
                "AND regime_pf > minimum_regime_pf",
                "AND trend_agrees",
                "THEN enter",
                "EXIT when winner pattern disappears or regime changes",
            ],
            flowchart=[
                "Start -> Winner pattern",
                "Winner pattern -> Regime PF check",
                "Regime PF check -> Trend check",
                "Trend check -> Entry",
            ],
            justification=context.justifications(["association_rule", "regime_performance"]),
            confidence=0.0,
            scores={},
            source_evidence=context.sources(["trade_pattern", "market_regime"]),
        )

    def _hypothesis_loss_avoidance(self, context: "EvidenceContext") -> StrategyHypothesis:
        return StrategyHypothesis(
            name="Loss-Avoidance Overlay",
            description="A base trend strategy with explicit veto rules learned from losing trades.",
            entry_logic=[
                "Compute normal trend entry signal.",
                "Before entry, evaluate loss association rules.",
                "Enter only if no high-confidence loss rule is active.",
            ],
            exit_logic=[
                "Exit early if an active trade enters a historically harmful regime.",
                "Exit on trend reversal or configured risk exit.",
            ],
            filters=[
                "High-confidence loss combinations.",
                "Regimes responsible for largest drawdown contribution.",
            ],
            mandatory_components=["base entry signal", "loss veto"],
            optional_components=["drawdown regime monitor", "outlier-loss block"],
            weights={"loss_veto": 0.45, "base_signal": 0.25, "drawdown_control": 0.20, "simplicity": 0.10},
            regime_rules=context.worst_regime_rules(limit=4),
            risk_management=[
                "Lower risk after any loss-veto near miss.",
                "Use hard trade rejection for loss rules with high lift.",
            ],
            parameters={
                "loss_rule_confidence": ">= 0.60",
                "loss_rule_lift": "> 1.10",
                "drawdown_regime_block": "enabled",
            },
            pseudo_code=[
                "IF base_signal",
                "AND NOT loss_rule_triggered",
                "AND NOT high_drawdown_regime",
                "THEN enter",
                "IF high_drawdown_regime appears while open THEN defensive exit",
            ],
            flowchart=[
                "Start -> Base signal",
                "Base signal -> Loss veto",
                "Loss veto -> Drawdown regime veto",
                "Drawdown regime veto -> Entry or Ignore",
            ],
            justification=context.justifications(["association_rule", "regime_recommendation"]),
            confidence=0.0,
            scores={},
            source_evidence=context.sources(["trade_pattern", "market_regime"]),
        )

    def _hypothesis_btc_regime_filter(self, context: "EvidenceContext") -> StrategyHypothesis:
        return StrategyHypothesis(
            name="BTC-Regime Filtered Alt Trend",
            description="Altcoin trend strategy gated by BTC market state.",
            entry_logic=[
                "Evaluate altcoin trend signal.",
                "Allow entries only when BTC regime supports historical profitability.",
                "Tighten confirmation count when BTC is lateral or bearish.",
            ],
            exit_logic=[
                "Exit if BTC regime flips into historically harmful state.",
                "Exit on local pair trend loss.",
            ],
            filters=["BTC bearish/lateral block if evidence shows negative expectancy."],
            mandatory_components=["local trend", "BTC regime filter"],
            optional_components=["volume confirmation", "ADX confirmation"],
            weights={"btc_regime": 0.35, "local_trend": 0.30, "momentum": 0.20, "volume": 0.15},
            regime_rules=[rule for rule in context.best_regime_rules(limit=8) if "btc" in rule.lower()] or context.best_regime_rules(limit=2),
            risk_management=[
                "Reduce stake during BTC lateral regime.",
                "Disable new alt entries during BTC bearish regime unless evidence contradicts.",
            ],
            parameters={
                "btc_bullish_mode": "normal threshold",
                "btc_lateral_mode": "strict threshold",
                "btc_bearish_mode": "block or very strict threshold",
            },
            pseudo_code=[
                "IF pair_trend_signal",
                "AND btc_regime in allowed_btc_regimes",
                "AND confirmation_score >= regime_adjusted_threshold",
                "THEN enter",
            ],
            flowchart=["Start -> Pair trend", "Pair trend -> BTC regime", "BTC regime -> Adjusted threshold", "Adjusted threshold -> Entry"],
            justification=context.justifications(["regime_performance"]),
            confidence=0.0,
            scores={},
            source_evidence=context.sources(["market_regime"]),
        )

    def _hypothesis_volume_breakout(self, context: "EvidenceContext") -> StrategyHypothesis:
        return StrategyHypothesis(
            name="Volume-Confirmed Breakout Trend",
            description="Breakout continuation idea that requires expansion plus volume confirmation.",
            entry_logic=[
                "Require price expansion or candle breakout.",
                "Require volume above normal regime.",
                "Require trend context to avoid countertrend breakouts.",
            ],
            exit_logic=[
                "Exit when breakout state returns to compression and trend weakens.",
                "Exit on loss of volume confirmation after failed breakout.",
            ],
            filters=["Avoid breakout rules with low ADX if reports show poor expectancy."],
            mandatory_components=["breakout", "volume", "trend context"],
            optional_components=["ADX high", "ATR medium/high", "BTC filter"],
            weights={"breakout": 0.30, "volume": 0.25, "trend": 0.25, "momentum": 0.20},
            regime_rules=[rule for rule in context.best_regime_rules(limit=8) if "volume" in rule.lower() or "breakout" in rule.lower()],
            risk_management=[
                "Use tighter invalidation after breakout failure.",
                "Avoid entries in high drawdown expansion clusters.",
            ],
            parameters={
                "volume_state": "above average",
                "breakout_state": "expansion",
                "adx_mode": "medium/high preferred",
            },
            pseudo_code=[
                "IF breakout_expansion",
                "AND volume_above_average",
                "AND trend_context_positive",
                "THEN enter",
                "EXIT if expansion fails and trend weakens",
            ],
            flowchart=["Start -> Expansion", "Expansion -> Volume", "Volume -> Trend", "Trend -> Entry"],
            justification=context.justifications(["regime_performance", "association_rule"]),
            confidence=0.0,
            scores={},
            source_evidence=context.sources(["market_regime", "trade_pattern"]),
        )

    def _hypothesis_adaptive_threshold(self, context: "EvidenceContext") -> StrategyHypothesis:
        return StrategyHypothesis(
            name="Adaptive Threshold Trend Score",
            description="Composite score strategy with threshold adjusted by regime and volatility.",
            entry_logic=[
                "Calculate score from trend, ADX, RSI, volume, ATR, and breakout.",
                "Raise threshold in unfavorable regimes.",
                "Lower threshold only in historically robust regimes.",
            ],
            exit_logic=[
                "Exit when adaptive score falls below exit floor.",
                "Exit on trend loss.",
            ],
            filters=["No threshold relaxation unless robustness evidence supports the regime."],
            mandatory_components=["composite score", "adaptive threshold", "regime state"],
            optional_components=["loss-rule veto", "BTC adjustment"],
            weights={"score": 0.35, "regime_adjustment": 0.30, "robustness": 0.20, "simplicity": 0.15},
            regime_rules=context.best_regime_rules(limit=3),
            risk_management=[
                "Use strict threshold when robustness score is low.",
                "Do not increase risk solely because in-sample PF is high.",
            ],
            parameters={
                "base_threshold": "from robust region",
                "favorable_regime_delta": "-small",
                "unfavorable_regime_delta": "+medium",
            },
            pseudo_code=[
                "threshold = base_threshold + regime_delta",
                "IF score >= threshold AND no loss veto THEN enter",
                "IF score < exit_floor THEN exit",
            ],
            flowchart=["Start -> Compute score", "Compute score -> Regime delta", "Regime delta -> Threshold", "Threshold -> Entry"],
            justification=context.justifications(["entry_logic_scientific_score", "robustness_score", "regime_performance"]),
            confidence=0.0,
            scores={},
            source_evidence=context.sources(["entry_logic", "robustness", "market_regime"]),
        )

    def _hypothesis_pullback_regime(self, context: "EvidenceContext") -> StrategyHypothesis:
        return StrategyHypothesis(
            name="Regime-Aware Pullback Continuation",
            description="Pullback strategy that only buys controlled retracements in favorable trend regimes.",
            entry_logic=[
                "Require long-term trend positive.",
                "Wait for pullback toward fast/mid EMA.",
                "Enter only after resumption confirmation and favorable regime evidence.",
            ],
            exit_logic=[
                "Exit when pullback becomes trend failure.",
                "Exit when price loses long-term trend support.",
            ],
            filters=["Avoid high-volatility pullbacks if drawdown contribution is high."],
            mandatory_components=["long-term trend", "controlled pullback", "resumption candle"],
            optional_components=["volume confirmation", "RSI healthy zone", "BTC regime"],
            weights={"trend": 0.30, "pullback_quality": 0.30, "resumption": 0.20, "regime": 0.20},
            regime_rules=context.best_regime_rules(limit=4),
            risk_management=[
                "Use invalidation below pullback low.",
                "Reduce stake in high ATR drawdown regimes.",
            ],
            parameters={
                "pullback_depth": "near EMA fast/mid",
                "resumption_confirmation": "close above previous candle high or momentum recovery",
                "volatility_filter": "avoid extreme ATR unless evidence supports it",
            },
            pseudo_code=[
                "IF trend_positive",
                "AND pullback_to_ema",
                "AND resumption_confirmed",
                "AND regime_allowed",
                "THEN enter",
            ],
            flowchart=["Start -> Trend", "Trend -> Pullback", "Pullback -> Resumption", "Resumption -> Regime", "Regime -> Entry"],
            justification=context.justifications(["regime_performance", "generic"]),
            confidence=0.0,
            scores={},
            source_evidence=context.sources(["pullback_research", "market_regime"]),
        )

    def _hypothesis_simplicity_baseline(self, context: "EvidenceContext") -> StrategyHypothesis:
        return StrategyHypothesis(
            name="Minimal Robust Trend Baseline",
            description="Simple reference specification designed to reduce overfitting risk.",
            entry_logic=[
                "Use only EMA trend, ADX momentum, and one volume/regime confirmation.",
                "Avoid many tunable weights.",
                "Prefer fixed components that ablation and robustness do not reject.",
            ],
            exit_logic=["Exit on EMA trend loss.", "Exit on configured risk exit."],
            filters=["One regime veto for largest loss source only."],
            mandatory_components=["EMA trend", "ADX", "single veto"],
            optional_components=["volume"],
            weights={"trend": 0.40, "adx": 0.30, "veto": 0.20, "volume": 0.10},
            regime_rules=context.worst_regime_rules(limit=1),
            risk_management=[
                "Keep parameter count minimal.",
                "Reject any added component without out-of-sample evidence.",
            ],
            parameters={
                "max_free_parameters": 6,
                "entry_rule": "all mandatory components true",
                "veto_rule": "one high-confidence loss regime",
            },
            pseudo_code=[
                "IF ema_trend AND adx_ok AND NOT loss_veto THEN enter",
                "IF ema_trend_lost THEN exit",
            ],
            flowchart=["Start -> EMA trend", "EMA trend -> ADX", "ADX -> Veto", "Veto -> Entry"],
            justification=context.justifications(["walk_forward_generalization", "robustness_score"]),
            confidence=0.0,
            scores={},
            source_evidence=context.sources(["walk_forward", "robustness"]),
        )

    def _fallback_hypothesis(self, context: "EvidenceContext", index: int) -> StrategyHypothesis:
        return StrategyHypothesis(
            name=f"Evidence-Driven Candidate {index}",
            description="Generic candidate derived from available recommendations.",
            entry_logic=["Use strongest positive evidence items as entry filters."],
            exit_logic=["Exit when positive evidence no longer applies."],
            filters=["Avoid strongest negative evidence items."],
            mandatory_components=["evidence gate"],
            optional_components=[],
            weights={"evidence": 1.0},
            regime_rules=context.best_regime_rules(limit=2),
            risk_management=["Keep risk low until tested out-of-sample."],
            parameters={"source": "existing reports"},
            pseudo_code=["IF positive_evidence AND NOT negative_evidence THEN enter"],
            flowchart=["Start -> Evidence gate -> Entry/Ignore"],
            justification=context.justifications([], limit=3),
            confidence=0.0,
            scores={},
            source_evidence=context.sources([], limit=3),
        )

    def _rank_hypotheses(self, hypotheses: list[StrategyHypothesis]) -> list[StrategyHypothesis]:
        for hypothesis in hypotheses:
            robustness = self._score_from_justification(hypothesis, ["robust", "robustez", "stability"])
            scientific = self._score_from_justification(hypothesis, ["evidence", "scientific", "associ", "regime"])
            generalization = self._score_from_justification(hypothesis, ["walk", "oos", "survival", "generalization"])
            simplicity = 1.0 / (1.0 + len(hypothesis.parameters) / 8.0 + len(hypothesis.weights) / 10.0)
            overfitting_risk = min(1.0, (len(hypothesis.parameters) + len(hypothesis.weights)) / 25.0)
            score = (
                robustness * 0.25
                + scientific * 0.25
                + generalization * 0.25
                + simplicity * 0.15
                - overfitting_risk * 0.10
            )
            hypothesis.scores = {
                "robustness": robustness,
                "scientific_evidence": scientific,
                "generalization": generalization,
                "simplicity": simplicity,
                "overfitting_risk": overfitting_risk,
                "composite": score,
            }
            hypothesis.confidence = max(0.0, min(1.0, score))
        return sorted(hypotheses, key=lambda item: item.scores["composite"], reverse=True)

    def _score_from_justification(self, hypothesis: StrategyHypothesis, keywords: list[str]) -> float:
        text = " ".join(hypothesis.justification + hypothesis.source_evidence).lower()
        if not text:
            return 0.1
        hits = sum(1 for keyword in keywords if keyword in text)
        return min(1.0, 0.15 + hits * 0.20 + len(hypothesis.justification) * 0.03)

    def _hypothesis_to_dict(self, hypothesis: StrategyHypothesis) -> dict[str, Any]:
        return {
            "name": hypothesis.name,
            "description": hypothesis.description,
            "entry_logic": hypothesis.entry_logic,
            "exit_logic": hypothesis.exit_logic,
            "filters": hypothesis.filters,
            "mandatory_components": hypothesis.mandatory_components,
            "optional_components": hypothesis.optional_components,
            "weights": hypothesis.weights,
            "regime_rules": hypothesis.regime_rules,
            "risk_management": hypothesis.risk_management,
            "parameters": hypothesis.parameters,
            "pseudo_code": hypothesis.pseudo_code,
            "flowchart": hypothesis.flowchart,
            "justification": hypothesis.justification,
            "confidence": hypothesis.confidence,
            "scores": hypothesis.scores,
            "source_evidence": hypothesis.source_evidence,
        }

    def _evidence_summary(self, evidence: list[EvidenceItem]) -> dict[str, Any]:
        counts: dict[str, int] = {}
        top_by_type: dict[str, list[dict[str, Any]]] = {}
        for item in evidence:
            counts[item.source_type] = counts.get(item.source_type, 0) + 1
            top_by_type.setdefault(item.source_type, [])
            if len(top_by_type[item.source_type]) < 10:
                top_by_type[item.source_type].append(self._evidence_to_dict(item))
        return {"counts_by_source_type": counts, "top_evidence_by_type": top_by_type}

    def _evidence_to_dict(self, item: EvidenceItem) -> dict[str, Any]:
        return {
            "source_type": item.source_type,
            "source_path": item.source_path,
            "topic": item.topic,
            "metric": item.metric,
            "value": item.value,
            "weight": item.weight,
            "note": item.note,
        }

    def _write_reports(self, report: dict[str, Any]) -> dict[str, Path]:
        stem = f"strategy_synthesis_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        json_path = self.output_dir / f"{stem}.json"
        markdown_path = self.output_dir / f"{stem}.md"
        html_path = self.output_dir / f"{stem}.html"
        json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        markdown_path.write_text(self._markdown(report), encoding="utf-8")
        html_path.write_text(self._html(report), encoding="utf-8")
        return {"json": json_path, "markdown": markdown_path, "html": html_path}

    def _markdown(self, report: dict[str, Any]) -> str:
        lines = [
            "# Strategy Synthesizer",
            "",
            "## Scope",
            "- This report contains technical specifications only.",
            "- It does not contain Python strategy code.",
            "- It is based exclusively on existing lab reports.",
            "",
            "## Inputs",
            f"- Reports loaded: {report['report_count']}",
            f"- Evidence items: {report['evidence_count']}",
            f"- Proposals: {report['proposal_count']}",
            "",
            "## Proposal Ranking",
            "| Rank | Name | Confidence | Composite | Robustness | Generalization | Simplicity | Overfit Risk |",
            "|---:|---|---:|---:|---:|---:|---:|---:|",
        ]
        for index, proposal in enumerate(report["proposals"], start=1):
            scores = proposal["scores"]
            lines.append(
                f"| {index} | {proposal['name']} | {proposal['confidence']:.3f} | "
                f"{scores['composite']:.3f} | {scores['robustness']:.3f} | "
                f"{scores['generalization']:.3f} | {scores['simplicity']:.3f} | "
                f"{scores['overfitting_risk']:.3f} |"
            )
        for index, proposal in enumerate(report["proposals"], start=1):
            lines.extend(
                [
                    "",
                    f"## {index}. {proposal['name']}",
                    "",
                    proposal["description"],
                    "",
                    "### Entry Logic",
                ]
            )
            lines.extend(f"- {item}" for item in proposal["entry_logic"])
            lines.append("")
            lines.append("### Exit Logic")
            lines.extend(f"- {item}" for item in proposal["exit_logic"])
            lines.append("")
            lines.append("### Filters")
            lines.extend(f"- {item}" for item in proposal["filters"])
            lines.append("")
            lines.append("### Components")
            lines.append("- Mandatory: " + ", ".join(proposal["mandatory_components"]))
            lines.append("- Optional: " + ", ".join(proposal["optional_components"]))
            lines.append("")
            lines.append("### Parameters")
            for key, value in proposal["parameters"].items():
                lines.append(f"- {key}: {value}")
            lines.append("")
            lines.append("### Pseudo-code")
            lines.extend(f"- {item}" for item in proposal["pseudo_code"])
            lines.append("")
            lines.append("### Flowchart")
            lines.extend(f"- {item}" for item in proposal["flowchart"])
            lines.append("")
            lines.append("### Justification")
            lines.extend(f"- {item}" for item in proposal["justification"][:10])
        return "\n".join(lines) + "\n"

    def _html(self, report: dict[str, Any]) -> str:
        markdown = self._markdown(report)
        return (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<title>Strategy Synthesizer</title>"
            "<style>body{font-family:Arial,sans-serif;margin:32px;line-height:1.45;color:#1f2937}"
            "pre{white-space:pre-wrap;background:#f6f8fa;padding:16px;border-radius:6px}"
            "h1,h2{color:#111827}</style></head><body>"
            "<h1>Strategy Synthesizer</h1>"
            f"<p><strong>Generated:</strong> {html.escape(report['generated_at'])}</p>"
            f"<pre>{html.escape(markdown)}</pre>"
            "</body></html>"
        )

    def _number(self, value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            result = float(value)
            if math.isnan(result) or math.isinf(result):
                return default
            return result
        except (TypeError, ValueError):
            return default


class EvidenceContext:
    def __init__(self, evidence: list[EvidenceItem]) -> None:
        self.evidence = evidence

    def justifications(self, metrics: list[str], *, limit: int = 8) -> list[str]:
        selected = [
            item
            for item in self.evidence
            if not metrics or item.metric in metrics or item.source_type in metrics
        ]
        if not selected:
            selected = self.evidence
        return [item.note for item in selected[:limit]]

    def sources(self, source_types: list[str], *, limit: int = 8) -> list[str]:
        selected = [
            item
            for item in self.evidence
            if not source_types or item.source_type in source_types
        ]
        if not selected:
            selected = self.evidence
        paths = []
        for item in selected:
            if item.source_path not in paths:
                paths.append(item.source_path)
            if len(paths) >= limit:
                break
        return paths

    def best_regime_rules(self, *, limit: int) -> list[str]:
        rows = [
            item
            for item in self.evidence
            if item.metric == "regime_performance"
            and isinstance(item.value, dict)
            and float(item.value.get("profit_total_abs") or 0.0) > 0
        ]
        rules = []
        for item in rows[:limit]:
            value = item.value
            rules.append(
                f"Prefer {value.get('feature')}={value.get('value')} "
                f"(PF={float(value.get('profit_factor') or 0.0):.3f})."
            )
        return rules

    def worst_regime_rules(self, *, limit: int) -> list[str]:
        rows = [
            item
            for item in self.evidence
            if item.metric == "regime_performance"
            and isinstance(item.value, dict)
            and float(item.value.get("profit_total_abs") or 0.0) < 0
        ]
        rows.sort(key=lambda item: float(item.value.get("profit_total_abs") or 0.0))
        rules = []
        for item in rows[:limit]:
            value = item.value
            rules.append(
                f"Avoid {value.get('feature')}={value.get('value')} "
                f"(net={float(value.get('profit_total_abs') or 0.0):.3f})."
            )
        return rules


def parse_report_paths(values: list[str] | None) -> list[Path] | None:
    if not values:
        return None
    paths: list[Path] = []
    for value in values:
        path = Path(value)
        if any(char in value for char in "*?[]"):
            paths.extend(Path().glob(value))
        else:
            paths.append(path)
    return paths


def command_synthesize(args: argparse.Namespace) -> dict[str, str]:
    synthesizer = StrategySynthesizer(lab_dir=args.lab_dir, output_dir=args.output_dir)
    paths = synthesizer.synthesize(
        report_paths=parse_report_paths(args.report),
        min_proposals=args.min_proposals,
        max_proposals=args.max_proposals,
    )
    return {key: str(path.resolve()) for key, path in paths.items()}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Synthesize technical strategy proposals from existing lab reports only.",
    )
    parser.add_argument("--lab-dir", type=Path, default=DEFAULT_LAB_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)

    subparsers = parser.add_subparsers(dest="command", required=True)
    synthesize = subparsers.add_parser("synthesize", help="Generate strategy proposal reports.")
    synthesize.add_argument("--report", action="append", help="Specific report JSON path or glob. Can be repeated.")
    synthesize.add_argument("--min-proposals", type=int, default=DEFAULT_MIN_PROPOSALS)
    synthesize.add_argument("--max-proposals", type=int, default=DEFAULT_MAX_PROPOSALS)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "synthesize":
        result = command_synthesize(args)
    else:
        parser.error("Unknown command.")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
