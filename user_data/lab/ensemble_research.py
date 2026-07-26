from __future__ import annotations

import argparse
import html
import json
import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from .experiment_database import DEFAULT_DB_PATH
    from .experiment_manager import ExperimentManager
    from .market_regime_profiler import MarketRegimeProfiler, TradeRecord
except ImportError:
    from experiment_database import DEFAULT_DB_PATH
    from experiment_manager import ExperimentManager
    from market_regime_profiler import MarketRegimeProfiler, TradeRecord


DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent
DEFAULT_TIMEFRAME = "5m"
DEFAULT_EXPERTS = {
    "TrendStrategy": {
        "session_id": "trend-session-af05d9d01d-690d21",
        "strategy_filter": "TrendStrategy",
    },
    "PullbackStrategy": {
        "session_id": "pullback-session-20260706200002-f0751337",
        "strategy_filter": "PullbackStrategy",
    },
    "NOfMTrendConfirmation": {
        "session_id": "synth-nom-session-20260709-8c7f32c5",
        "strategy_filter": "NOfMTrendConfirmationStrategy",
    },
}
ENSEMBLE_ARCHITECTURES = [
    "majority_voting",
    "weighted_voting",
    "confidence_voting",
    "best_expert",
    "dynamic_expert_selection",
    "regime_based_expert_selection",
    "pair_based_expert_selection",
    "time_based_expert_selection",
    "multi_armed_bandit",
    "performance_decay_weighting",
]


@dataclass(frozen=True)
class ExpertConfig:
    name: str
    session_id: str
    strategy_filter: str | None = None
    experiment_id: str | None = None


@dataclass(frozen=True)
class ExpertTrade:
    expert: str
    experiment_id: str
    pair: str
    open_date: datetime | None
    close_date: datetime | None
    profit_abs: float
    profit_ratio: float
    duration_minutes: float
    regimes: dict[str, str]
    confidence: float


class EnsembleResearch:
    """Offline ensemble research over existing strategy experiment results."""

    def __init__(
        self,
        *,
        db_path: Path | str = DEFAULT_DB_PATH,
        output_dir: Path | str = DEFAULT_OUTPUT_DIR,
        project_root: Path | str | None = None,
        timeframe: str = DEFAULT_TIMEFRAME,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.project_root = Path(project_root or Path(__file__).resolve().parents[2])
        self.profiler = MarketRegimeProfiler(
            db_path=db_path,
            output_dir=output_dir,
            project_root=self.project_root,
            timeframe=timeframe,
        )
        self.timeframe = timeframe

    def analyze(
        self,
        *,
        experts: list[ExpertConfig] | None = None,
        top_experiments_per_expert: int = 5,
        decision_window_minutes: int = 60,
        min_trades: int = 10,
    ) -> dict[str, Path]:
        expert_configs = experts or self._default_experts()
        expert_trades = self._load_expert_trades(
            expert_configs,
            top_experiments_per_expert=top_experiments_per_expert,
        )
        report = self._build_report(
            expert_configs=expert_configs,
            expert_trades=expert_trades,
            top_experiments_per_expert=top_experiments_per_expert,
            decision_window_minutes=decision_window_minutes,
            min_trades=min_trades,
        )
        return self._write_reports(report)

    def queue_experiments(
        self,
        *,
        count: int,
        mode: str = "random",
        experiment_kind: str = "plugin",
    ) -> list[str]:
        manager = ExperimentManager(strategy_name="LabPluginStrategy")
        return manager.generate_experiments(
            count=count,
            mode=mode,
            experiment_kind=experiment_kind,
        )

    def _default_experts(self) -> list[ExpertConfig]:
        return [
            ExpertConfig(
                name=name,
                session_id=str(config["session_id"]),
                strategy_filter=str(config["strategy_filter"]),
            )
            for name, config in DEFAULT_EXPERTS.items()
        ]

    def _load_expert_trades(
        self,
        configs: list[ExpertConfig],
        *,
        top_experiments_per_expert: int,
    ) -> dict[str, list[ExpertTrade]]:
        result: dict[str, list[ExpertTrade]] = {}
        for config in configs:
            experiments = self.profiler._load_experiments(
                session_id=config.session_id,
                strategy=config.strategy_filter,
                experiment_id=config.experiment_id,
            )
            experiments = self._select_top_experiments(
                experiments,
                limit=top_experiments_per_expert,
            )
            trades = self.profiler._load_trades(experiments, session_id=config.session_id)
            result[config.name] = [
                self._expert_trade(config.name, trade, experiments)
                for trade in trades
            ]
        return result

    def _select_top_experiments(
        self,
        experiments: list[dict[str, Any]],
        *,
        limit: int,
    ) -> list[dict[str, Any]]:
        if limit <= 0:
            return experiments

        def quality(experiment: dict[str, Any]) -> tuple[float, float, float, float]:
            metrics = experiment.get("metrics") or {}
            return (
                float(metrics.get("profit_factor") or 0.0),
                float(metrics.get("sharpe") or 0.0),
                -float(metrics.get("max_drawdown_abs") or 0.0),
                float(metrics.get("total_trades") or 0.0),
            )

        return sorted(experiments, key=quality, reverse=True)[:limit]

    def _expert_trade(
        self,
        expert: str,
        trade: TradeRecord,
        experiments: list[dict[str, Any]],
    ) -> ExpertTrade:
        by_id = {experiment["id"]: experiment for experiment in experiments}
        metrics = by_id.get(trade.experiment_id, {}).get("metrics", {})
        confidence = self._expert_confidence(metrics)
        return ExpertTrade(
            expert=expert,
            experiment_id=trade.experiment_id,
            pair=trade.pair,
            open_date=trade.open_date,
            close_date=trade.close_date,
            profit_abs=trade.profit_abs,
            profit_ratio=trade.profit_ratio,
            duration_minutes=trade.duration_minutes,
            regimes=dict(trade.regimes),
            confidence=confidence,
        )

    def _expert_confidence(self, metrics: dict[str, Any]) -> float:
        pf = float(metrics.get("profit_factor") or 0.0)
        sharpe = float(metrics.get("sharpe") or 0.0)
        trades = float(metrics.get("total_trades") or 0.0)
        drawdown = float(metrics.get("max_drawdown_abs") or 0.0)
        return max(
            0.05,
            min(
                1.0,
                0.25 * self._normalize(pf, center=1.0, width=2.0)
                + 0.25 * self._normalize(sharpe, center=0.0, width=4.0)
                + 0.25 * min(1.0, trades / 100.0)
                + 0.25 * (1.0 / (1.0 + drawdown / 100.0)),
            ),
        )

    def _build_report(
        self,
        *,
        expert_configs: list[ExpertConfig],
        expert_trades: dict[str, list[ExpertTrade]],
        top_experiments_per_expert: int,
        decision_window_minutes: int,
        min_trades: int,
    ) -> dict[str, Any]:
        events = self._events(expert_trades, decision_window_minutes)
        individual_metrics = {
            expert: self._metrics(trades)
            for expert, trades in expert_trades.items()
        }
        expert_weights = self._expert_weights(individual_metrics)
        ensemble_results = []
        for architecture in ENSEMBLE_ARCHITECTURES:
            selected = self._simulate_architecture(
                architecture,
                events,
                expert_weights=expert_weights,
            )
            metrics = self._metrics(selected)
            metrics["architecture"] = architecture
            metrics["robustness_score"] = self._robustness_score(metrics)
            metrics["stability_index"] = self._stability_index(selected)
            metrics["walk_forward_survival_rate"] = self._survival_proxy(selected)
            metrics["selected_trade_count"] = len(selected)
            metrics["experts_used"] = sorted({trade.expert for trade in selected})
            ensemble_results.append(metrics)

        ranking = sorted(
            ensemble_results,
            key=lambda row: (
                row["robustness_score"],
                row["profit_factor"],
                row["expectancy"],
            ),
            reverse=True,
        )
        expert_importance = self._expert_importance(ranking, expert_trades)
        contribution = self._expert_contribution(expert_trades)
        correlation = self._correlation_matrix(expert_trades, decision_window_minutes)
        diversity = self._diversity(correlation, expert_trades)
        gains = self._ensemble_gains(ranking, individual_metrics)
        candidates = self._candidates(ranking, individual_metrics, min_trades=min_trades)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "scope": "Offline ensemble simulation over existing SQLite results and backtest artifacts.",
            "experts": [
                {
                    "name": config.name,
                    "session_id": config.session_id,
                    "strategy_filter": config.strategy_filter,
                    "experiment_id": config.experiment_id,
                }
                for config in expert_configs
            ],
            "config": {
                "top_experiments_per_expert": top_experiments_per_expert,
                "decision_window_minutes": decision_window_minutes,
                "min_trades": min_trades,
                "architectures": ENSEMBLE_ARCHITECTURES,
            },
            "individual_metrics": individual_metrics,
            "ranking": ranking,
            "expert_importance": expert_importance,
            "expert_contribution": contribution,
            "correlation_matrix": correlation,
            "diversity": diversity,
            "ensemble_gains": gains,
            "candidates": candidates,
            "notes": [
                "This module does not alter strategy code or operational settings.",
                "Ensemble decisions are simulated from closed-trade opportunities grouped by pair and time window.",
                "Walk-forward survival rate is a proxy unless explicit ensemble walk-forward experiments are later queued and executed through existing lab infrastructure.",
            ],
        }

    def _events(
        self,
        expert_trades: dict[str, list[ExpertTrade]],
        window_minutes: int,
    ) -> list[list[ExpertTrade]]:
        groups: dict[tuple[str, datetime], list[ExpertTrade]] = defaultdict(list)
        for trades in expert_trades.values():
            for trade in trades:
                if trade.open_date is None:
                    continue
                groups[(trade.pair, self._bucket_time(trade.open_date, window_minutes))].append(trade)
        return [
            sorted(group, key=lambda trade: (trade.open_date or datetime.min.replace(tzinfo=timezone.utc), trade.expert))
            for _, group in sorted(groups.items(), key=lambda item: item[0])
        ]

    def _bucket_time(self, value: datetime, window_minutes: int) -> datetime:
        timestamp = value.astimezone(timezone.utc)
        window = max(1, window_minutes)
        minute = timestamp.minute - (timestamp.minute % window)
        return timestamp.replace(minute=minute, second=0, microsecond=0)

    def _simulate_architecture(
        self,
        architecture: str,
        events: list[list[ExpertTrade]],
        *,
        expert_weights: dict[str, float],
    ) -> list[ExpertTrade]:
        if architecture == "majority_voting":
            return self._majority_voting(events)
        if architecture == "weighted_voting":
            return self._weighted_voting(events, expert_weights)
        if architecture == "confidence_voting":
            return self._confidence_voting(events)
        if architecture == "best_expert":
            return self._best_expert(events, expert_weights)
        if architecture == "dynamic_expert_selection":
            return self._dynamic_selection(events)
        if architecture == "regime_based_expert_selection":
            return self._segment_selection(events, "regime")
        if architecture == "pair_based_expert_selection":
            return self._segment_selection(events, "pair")
        if architecture == "time_based_expert_selection":
            return self._segment_selection(events, "time")
        if architecture == "multi_armed_bandit":
            return self._bandit(events)
        if architecture == "performance_decay_weighting":
            return self._decay_weighting(events)
        raise ValueError(f"Unknown architecture: {architecture}")

    def _majority_voting(self, events: list[list[ExpertTrade]]) -> list[ExpertTrade]:
        selected = []
        expert_count = len({trade.expert for event in events for trade in event})
        threshold = max(1, math.ceil(expert_count / 2))
        for event in events:
            by_expert = self._best_trade_per_expert(event)
            if len(by_expert) >= threshold:
                selected.append(self._best_trade(list(by_expert.values())))
        return selected

    def _weighted_voting(
        self,
        events: list[list[ExpertTrade]],
        expert_weights: dict[str, float],
    ) -> list[ExpertTrade]:
        selected = []
        total = sum(expert_weights.values()) or 1.0
        threshold = total * 0.45
        for event in events:
            by_expert = self._best_trade_per_expert(event)
            weight = sum(expert_weights.get(expert, 0.0) for expert in by_expert)
            if weight >= threshold:
                selected.append(
                    self._best_trade(
                        list(by_expert.values()),
                        weights=expert_weights,
                    )
                )
        return selected

    def _confidence_voting(self, events: list[list[ExpertTrade]]) -> list[ExpertTrade]:
        selected = []
        for event in events:
            by_expert = self._best_trade_per_expert(event)
            confidence = sum(trade.confidence for trade in by_expert.values())
            if confidence >= max(0.55, 0.35 * len(by_expert)):
                selected.append(max(by_expert.values(), key=lambda trade: trade.confidence))
        return selected

    def _best_expert(
        self,
        events: list[list[ExpertTrade]],
        expert_weights: dict[str, float],
    ) -> list[ExpertTrade]:
        if not expert_weights:
            return []
        best = max(expert_weights, key=expert_weights.get)
        selected = []
        for event in events:
            trades = [trade for trade in event if trade.expert == best]
            if trades:
                selected.append(self._best_trade(trades))
        return selected

    def _dynamic_selection(self, events: list[list[ExpertTrade]]) -> list[ExpertTrade]:
        selected = []
        scores: dict[str, float] = defaultdict(float)
        counts: dict[str, int] = defaultdict(int)
        for event in events:
            by_expert = self._best_trade_per_expert(event)
            if not by_expert:
                continue
            expert = max(
                by_expert,
                key=lambda name: scores[name] / counts[name] if counts[name] else by_expert[name].confidence,
            )
            trade = by_expert[expert]
            selected.append(trade)
            scores[expert] += trade.profit_abs
            counts[expert] += 1
        return selected

    def _segment_selection(
        self,
        events: list[list[ExpertTrade]],
        segment_type: str,
    ) -> list[ExpertTrade]:
        selected = []
        segment_scores: dict[tuple[str, str], float] = defaultdict(float)
        segment_counts: dict[tuple[str, str], int] = defaultdict(int)
        for event in events:
            by_expert = self._best_trade_per_expert(event)
            if not by_expert:
                continue
            segment = self._segment_key(event[0], segment_type)
            expert = max(
                by_expert,
                key=lambda name: (
                    segment_scores[(segment, name)] / segment_counts[(segment, name)]
                    if segment_counts[(segment, name)]
                    else by_expert[name].confidence
                ),
            )
            trade = by_expert[expert]
            selected.append(trade)
            segment_scores[(segment, expert)] += trade.profit_abs
            segment_counts[(segment, expert)] += 1
        return selected

    def _segment_key(self, trade: ExpertTrade, segment_type: str) -> str:
        if segment_type == "pair":
            return trade.pair
        if segment_type == "time":
            if trade.open_date is None:
                return "UNKNOWN"
            return f"H{trade.open_date.astimezone(timezone.utc).hour:02d}"
        regime = trade.regimes.get("ema200_direction", "UNKNOWN")
        adx = trade.regimes.get("adx_bucket", "UNKNOWN")
        atr = trade.regimes.get("atr_bucket", "UNKNOWN")
        return f"{regime}|{adx}|{atr}"

    def _bandit(self, events: list[list[ExpertTrade]]) -> list[ExpertTrade]:
        selected = []
        rewards: dict[str, float] = defaultdict(float)
        counts: dict[str, int] = defaultdict(int)
        total = 0
        for event in events:
            by_expert = self._best_trade_per_expert(event)
            if not by_expert:
                continue
            total += 1
            expert = max(
                by_expert,
                key=lambda name: (
                    float("inf")
                    if counts[name] == 0
                    else rewards[name] / counts[name] + math.sqrt(2.0 * math.log(max(2, total)) / counts[name])
                ),
            )
            trade = by_expert[expert]
            selected.append(trade)
            rewards[expert] += trade.profit_abs
            counts[expert] += 1
        return selected

    def _decay_weighting(self, events: list[list[ExpertTrade]]) -> list[ExpertTrade]:
        selected = []
        weights: dict[str, float] = defaultdict(lambda: 1.0)
        decay = 0.96
        for event in events:
            by_expert = self._best_trade_per_expert(event)
            if not by_expert:
                continue
            expert = max(by_expert, key=lambda name: weights[name] * by_expert[name].confidence)
            trade = by_expert[expert]
            selected.append(trade)
            weights[expert] = weights[expert] * decay + max(-1.0, min(1.0, trade.profit_abs)) * (1.0 - decay)
        return selected

    def _best_trade_per_expert(self, trades: list[ExpertTrade]) -> dict[str, ExpertTrade]:
        result: dict[str, ExpertTrade] = {}
        for trade in trades:
            current = result.get(trade.expert)
            if current is None or trade.confidence > current.confidence:
                result[trade.expert] = trade
        return result

    def _best_trade(
        self,
        trades: list[ExpertTrade],
        *,
        weights: dict[str, float] | None = None,
    ) -> ExpertTrade:
        weights = weights or {}
        return max(
            trades,
            key=lambda trade: (
                weights.get(trade.expert, 1.0) * trade.confidence,
                trade.profit_abs,
            ),
        )

    def _expert_weights(self, metrics: dict[str, dict[str, Any]]) -> dict[str, float]:
        raw = {}
        for expert, row in metrics.items():
            score = self._robustness_score(row)
            raw[expert] = max(0.05, score)
        total = sum(raw.values()) or 1.0
        return {expert: value / total for expert, value in raw.items()}

    def _metrics(self, trades: list[ExpertTrade]) -> dict[str, Any]:
        profits = [trade.profit_abs for trade in trades]
        ratios = [trade.profit_ratio for trade in trades]
        gross_profit = sum(value for value in profits if value > 0)
        gross_loss = abs(sum(value for value in profits if value < 0))
        wins = sum(1 for value in profits if value > 0)
        losses = sum(1 for value in profits if value < 0)
        return {
            "profit_factor": gross_profit / gross_loss if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0),
            "sharpe": self._sharpe(ratios),
            "max_drawdown_abs": self._max_drawdown(profits),
            "expectancy": statistics.mean(profits) if profits else 0.0,
            "win_rate": wins / len(trades) if trades else 0.0,
            "trades": len(trades),
            "wins": wins,
            "losses": losses,
            "profit_total_abs": sum(profits),
        }

    def _robustness_score(self, metrics: dict[str, Any]) -> float:
        pf = self._normalize(float(metrics.get("profit_factor") or 0.0), center=1.0, width=2.0)
        sharpe = self._normalize(float(metrics.get("sharpe") or 0.0), center=0.0, width=5.0)
        drawdown = 1.0 / (1.0 + max(0.0, float(metrics.get("max_drawdown_abs") or 0.0)) / 100.0)
        expectancy = self._normalize(float(metrics.get("expectancy") or 0.0), center=0.0, width=2.0)
        trades = min(1.0, float(metrics.get("trades") or 0.0) / 100.0)
        return max(0.0, min(1.0, 0.30 * pf + 0.20 * sharpe + 0.20 * drawdown + 0.20 * expectancy + 0.10 * trades))

    def _stability_index(self, trades: list[ExpertTrade]) -> float:
        if not trades:
            return 0.0
        monthly: dict[str, list[ExpertTrade]] = defaultdict(list)
        for trade in trades:
            if trade.open_date is None:
                key = "UNKNOWN"
            else:
                key = trade.open_date.astimezone(timezone.utc).strftime("%Y-%m")
            monthly[key].append(trade)
        pfs = [self._metrics(group)["profit_factor"] for group in monthly.values() if group]
        if len(pfs) < 2:
            return 0.0
        avg = statistics.mean(pfs)
        std = statistics.pstdev(pfs)
        if avg <= 0:
            return 0.0
        return max(0.0, min(1.0, 1.0 - std / (avg + std)))

    def _survival_proxy(self, trades: list[ExpertTrade]) -> float:
        if not trades:
            return 0.0
        folds: dict[int, list[ExpertTrade]] = defaultdict(list)
        sorted_trades = sorted(trades, key=lambda trade: trade.open_date or datetime.min.replace(tzinfo=timezone.utc))
        for index, trade in enumerate(sorted_trades):
            fold = int(index * 5 / max(1, len(sorted_trades)))
            folds[fold].append(trade)
        survived = sum(1 for group in folds.values() if self._metrics(group)["profit_factor"] > 1.0)
        return survived / len(folds) if folds else 0.0

    def _expert_importance(
        self,
        ranking: list[dict[str, Any]],
        expert_trades: dict[str, list[ExpertTrade]],
    ) -> list[dict[str, Any]]:
        usage = Counter()
        for architecture in ranking:
            for expert in architecture.get("experts_used", []):
                usage[expert] += architecture["robustness_score"]
        total = sum(usage.values()) or 1.0
        return [
            {
                "expert": expert,
                "importance": usage.get(expert, 0.0) / total,
                "trade_count": len(trades),
            }
            for expert, trades in sorted(expert_trades.items())
        ]

    def _expert_contribution(self, expert_trades: dict[str, list[ExpertTrade]]) -> list[dict[str, Any]]:
        rows = []
        for expert, trades in expert_trades.items():
            metrics = self._metrics(trades)
            rows.append({"expert": expert, **metrics, "robustness_score": self._robustness_score(metrics)})
        return sorted(rows, key=lambda row: row["robustness_score"], reverse=True)

    def _correlation_matrix(
        self,
        expert_trades: dict[str, list[ExpertTrade]],
        window_minutes: int,
    ) -> list[dict[str, Any]]:
        series = {}
        keys = set()
        for expert, trades in expert_trades.items():
            values: dict[tuple[str, datetime], float] = defaultdict(float)
            for trade in trades:
                if trade.open_date is None:
                    continue
                key = (trade.pair, self._bucket_time(trade.open_date, window_minutes))
                values[key] += trade.profit_abs
                keys.add(key)
            series[expert] = values
        ordered_keys = sorted(keys)
        rows = []
        experts = sorted(expert_trades)
        for left in experts:
            for right in experts:
                x = [series[left].get(key, 0.0) for key in ordered_keys]
                y = [series[right].get(key, 0.0) for key in ordered_keys]
                rows.append({"left": left, "right": right, "correlation": self._correlation(x, y)})
        return rows

    def _diversity(
        self,
        correlation: list[dict[str, Any]],
        expert_trades: dict[str, list[ExpertTrade]],
    ) -> dict[str, Any]:
        off_diagonal = [
            abs(row["correlation"])
            for row in correlation
            if row["left"] != row["right"]
        ]
        avg_corr = statistics.mean(off_diagonal) if off_diagonal else 0.0
        trade_counts = [len(trades) for trades in expert_trades.values()]
        return {
            "average_abs_correlation": avg_corr,
            "diversity_score": max(0.0, min(1.0, 1.0 - avg_corr)),
            "expert_count": len(expert_trades),
            "trade_count_min": min(trade_counts) if trade_counts else 0,
            "trade_count_max": max(trade_counts) if trade_counts else 0,
        }

    def _ensemble_gains(
        self,
        ranking: list[dict[str, Any]],
        individual_metrics: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        rows = []
        for architecture in ranking:
            for expert, metrics in individual_metrics.items():
                rows.append(
                    {
                        "architecture": architecture["architecture"],
                        "expert": expert,
                        "profit_factor_gain": architecture["profit_factor"] - metrics["profit_factor"],
                        "expectancy_gain": architecture["expectancy"] - metrics["expectancy"],
                        "drawdown_delta": architecture["max_drawdown_abs"] - metrics["max_drawdown_abs"],
                        "sharpe_gain": architecture["sharpe"] - metrics["sharpe"],
                    }
                )
        return rows

    def _candidates(
        self,
        ranking: list[dict[str, Any]],
        individual_metrics: dict[str, dict[str, Any]],
        *,
        min_trades: int,
    ) -> list[dict[str, Any]]:
        best_individual_pf = max((row["profit_factor"] for row in individual_metrics.values()), default=0.0)
        candidates = []
        for row in ranking:
            if row["trades"] < min_trades:
                classification = "insufficient_trades"
            elif row["profit_factor"] > best_individual_pf and row["walk_forward_survival_rate"] >= 0.6:
                classification = "promising"
            elif row["profit_factor"] > 1.0 and row["robustness_score"] >= 0.6:
                classification = "research_candidate"
            else:
                classification = "reject"
            candidates.append(
                {
                    "architecture": row["architecture"],
                    "classification": classification,
                    "profit_factor": row["profit_factor"],
                    "robustness_score": row["robustness_score"],
                    "stability_index": row["stability_index"],
                    "walk_forward_survival_rate": row["walk_forward_survival_rate"],
                    "trades": row["trades"],
                }
            )
        return candidates

    def _sharpe(self, values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        avg = statistics.mean(values)
        std = statistics.pstdev(values)
        if std == 0:
            return 0.0
        return math.sqrt(len(values)) * avg / std

    def _max_drawdown(self, profits: list[float]) -> float:
        peak = 0.0
        equity = 0.0
        drawdown = 0.0
        for profit in profits:
            equity += profit
            peak = max(peak, equity)
            drawdown = max(drawdown, peak - equity)
        return drawdown

    def _correlation(self, x: list[float], y: list[float]) -> float:
        if len(x) < 2 or len(y) < 2:
            return 0.0
        avg_x = statistics.mean(x)
        avg_y = statistics.mean(y)
        num = sum((a - avg_x) * (b - avg_y) for a, b in zip(x, y))
        den_x = math.sqrt(sum((a - avg_x) ** 2 for a in x))
        den_y = math.sqrt(sum((b - avg_y) ** 2 for b in y))
        if den_x == 0 or den_y == 0:
            return 0.0
        return num / (den_x * den_y)

    def _normalize(self, value: float, *, center: float, width: float) -> float:
        if width <= 0:
            return 0.0
        return max(0.0, min(1.0, 0.5 + (value - center) / (2.0 * width)))

    def _write_reports(self, report: dict[str, Any]) -> dict[str, Path]:
        json_path = self.output_dir / "ensemble_report.json"
        markdown_path = self.output_dir / "ensemble_report.md"
        html_path = self.output_dir / "ensemble_report.html"
        candidates_path = self.output_dir / "ensemble_candidates.json"
        json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        markdown_path.write_text(self._markdown(report), encoding="utf-8")
        html_path.write_text(self._html(report), encoding="utf-8")
        candidates_path.write_text(
            json.dumps(report["candidates"], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return {
            "json": json_path,
            "markdown": markdown_path,
            "html": html_path,
            "candidates": candidates_path,
        }

    def _markdown(self, report: dict[str, Any]) -> str:
        lines = [
            "# Ensemble Research",
            "",
            "## Summary",
            f"- Experts: {', '.join(expert['name'] for expert in report['experts'])}",
            f"- Architectures: {len(report['ranking'])}",
            f"- Diversity score: {report['diversity']['diversity_score']:.3f}",
            "",
            "## Architecture Ranking",
            "| Architecture | PF | Sharpe | DD | Expectancy | Win Rate | Trades | Robustness | Stability | Survival |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for row in report["ranking"]:
            lines.append(
                f"| {row['architecture']} | {row['profit_factor']:.3f} | {row['sharpe']:.3f} | "
                f"{row['max_drawdown_abs']:.3f} | {row['expectancy']:.3f} | "
                f"{row['win_rate']:.3f} | {row['trades']} | {row['robustness_score']:.3f} | "
                f"{row['stability_index']:.3f} | {row['walk_forward_survival_rate']:.3f} |"
            )
        lines.extend(["", "## Expert Contribution"])
        lines.append("| Expert | PF | Sharpe | DD | Expectancy | Trades | Robustness |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|")
        for row in report["expert_contribution"]:
            lines.append(
                f"| {row['expert']} | {row['profit_factor']:.3f} | {row['sharpe']:.3f} | "
                f"{row['max_drawdown_abs']:.3f} | {row['expectancy']:.3f} | "
                f"{row['trades']} | {row['robustness_score']:.3f} |"
            )
        lines.extend(["", "## Candidates"])
        for row in report["candidates"]:
            lines.append(
                f"- {row['architecture']}: {row['classification']} "
                f"(PF={row['profit_factor']:.3f}, robustness={row['robustness_score']:.3f})"
            )
        lines.extend(["", "## Notes"])
        lines.extend(f"- {note}" for note in report["notes"])
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
                        value = f"{value:.4f}"
                    parts.append(f"<td>{html.escape(str(value))}</td>")
                parts.append("</tr>")
            parts.append("</tbody></table>")
            return "".join(parts)

        parts = [
            "<!doctype html><html><head><meta charset='utf-8'>",
            "<title>Ensemble Research</title>",
            "<style>body{font-family:Segoe UI,Arial,sans-serif;margin:32px;color:#202124;line-height:1.45}"
            "table{border-collapse:collapse;width:100%;font-size:13px;margin:16px 0}"
            "td,th{border:1px solid #ddd;padding:6px;text-align:right}"
            "td:first-child,th:first-child{text-align:left}th{background:#f4f6f8}</style></head><body>",
            "<h1>Ensemble Research</h1>",
            f"<p>Diversity score: <b>{report['diversity']['diversity_score']:.3f}</b></p>",
            "<h2>Architecture Ranking</h2>",
            table(
                report["ranking"],
                [
                    ("Architecture", "architecture"),
                    ("PF", "profit_factor"),
                    ("Sharpe", "sharpe"),
                    ("DD", "max_drawdown_abs"),
                    ("Expectancy", "expectancy"),
                    ("Trades", "trades"),
                    ("Robustness", "robustness_score"),
                    ("Stability", "stability_index"),
                    ("Survival", "walk_forward_survival_rate"),
                ],
            ),
            "<h2>Expert Contribution</h2>",
            table(
                report["expert_contribution"],
                [
                    ("Expert", "expert"),
                    ("PF", "profit_factor"),
                    ("Sharpe", "sharpe"),
                    ("DD", "max_drawdown_abs"),
                    ("Expectancy", "expectancy"),
                    ("Trades", "trades"),
                    ("Robustness", "robustness_score"),
                ],
            ),
            "<h2>Candidates</h2>",
            table(
                report["candidates"],
                [
                    ("Architecture", "architecture"),
                    ("Classification", "classification"),
                    ("PF", "profit_factor"),
                    ("Robustness", "robustness_score"),
                    ("Survival", "walk_forward_survival_rate"),
                    ("Trades", "trades"),
                ],
            ),
            "</body></html>",
        ]
        return "\n".join(parts)


def parse_experts(value: str | None) -> list[ExpertConfig] | None:
    if not value:
        return None
    parsed = json.loads(Path(value).read_text(encoding="utf-8"))
    return [
        ExpertConfig(
            name=str(row["name"]),
            session_id=str(row["session_id"]),
            strategy_filter=row.get("strategy_filter"),
            experiment_id=row.get("experiment_id"),
        )
        for row in parsed
    ]


def command_analyze(args: argparse.Namespace) -> dict[str, str]:
    research = EnsembleResearch(
        db_path=args.db_path,
        output_dir=args.output_dir,
        project_root=args.project_root,
        timeframe=args.timeframe,
    )
    paths = research.analyze(
        experts=parse_experts(args.experts_json),
        top_experiments_per_expert=args.top_experiments_per_expert,
        decision_window_minutes=args.decision_window_minutes,
        min_trades=args.min_trades,
    )
    return {key: str(path.resolve()) for key, path in paths.items()}


def command_queue(args: argparse.Namespace) -> dict[str, Any]:
    research = EnsembleResearch(
        db_path=args.db_path,
        output_dir=args.output_dir,
        project_root=args.project_root,
        timeframe=args.timeframe,
    )
    experiment_ids = research.queue_experiments(
        count=args.count,
        mode=args.mode,
        experiment_kind=args.experiment_kind,
    )
    return {"queued_experiments": experiment_ids, "count": len(experiment_ids)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Research strategy ensembles using existing lab results.",
    )
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--timeframe", default=DEFAULT_TIMEFRAME)
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser("analyze", help="Generate ensemble reports from existing results.")
    analyze.add_argument("--experts-json", help="Optional JSON list of expert configs.")
    analyze.add_argument("--top-experiments-per-expert", type=int, default=5)
    analyze.add_argument("--decision-window-minutes", type=int, default=60)
    analyze.add_argument("--min-trades", type=int, default=20)
    analyze.set_defaults(func=command_analyze)

    queue = subparsers.add_parser("queue", help="Delegate experiment creation to ExperimentManager.")
    queue.add_argument("--count", type=int, required=True)
    queue.add_argument("--mode", choices=["random", "grid"], default="random")
    queue.add_argument("--experiment-kind", choices=["plugin", "parameters"], default="plugin")
    queue.set_defaults(func=command_queue)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    result = args.func(args)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
