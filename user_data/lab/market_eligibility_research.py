from __future__ import annotations

import argparse
import html
import json
import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any

try:
    from .experiment_database import DEFAULT_DB_PATH
    from .market_regime_profiler import IndicatorCache, MarketRegimeProfiler, TradeRecord
except ImportError:
    from experiment_database import DEFAULT_DB_PATH
    from market_regime_profiler import IndicatorCache, MarketRegimeProfiler, TradeRecord


DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent
DEFAULT_TIMEFRAME = "5m"

ELIGIBILITY_FEATURES = [
    "hour_of_day",
    "day_of_week",
    "session",
    "ema200_direction",
    "ema200_slope",
    "ema200_distance",
    "adx",
    "atr",
    "volatility_pct",
    "relative_volume",
    "recent_breakout",
    "btc_trend",
    "btc_volatility",
    "pair_btc_correlation",
    "trend_vs_range",
    "high_volatility_regime",
    "low_volatility_regime",
    "pair",
    "pair_group",
]

DEFAULT_WEIGHTS = {
    "robustness": 0.25,
    "repeatability": 0.20,
    "net_gain": 0.20,
    "walk_forward_stability": 0.15,
    "simplicity": 0.10,
    "overfitting_risk": 0.10,
}


@dataclass(frozen=True)
class EligibilityTrade:
    experiment_id: str
    pair: str
    open_date: datetime | None
    close_date: datetime | None
    profit_abs: float
    profit_ratio: float
    duration_minutes: float
    features: dict[str, str]


class MarketEligibilityResearch:
    """Research when a strategy should stay eligible to trade.

    The analyzer is intentionally read-only for existing strategy code. It can
    read completed experiments and official backtest artifacts, then produces
    filter candidates. Backtest execution, when a future workflow needs it,
    should remain delegated to the existing lab runners.
    """

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
        self.timeframe = timeframe
        self.profiler = MarketRegimeProfiler(
            db_path=db_path,
            output_dir=output_dir,
            project_root=self.project_root,
            timeframe=timeframe,
        )
        self.indicators = IndicatorCache(self.project_root, timeframe=timeframe)

    def analyze(
        self,
        *,
        session_id: str,
        strategy: str | None = None,
        experiment_id: str | None = None,
        min_trades: int = 20,
        max_combination_size: int = 3,
        min_support: float = 0.03,
        min_confidence: float = 0.55,
    ) -> dict[str, Path]:
        experiments = self.profiler._load_experiments(
            session_id=session_id,
            strategy=strategy,
            experiment_id=experiment_id,
        )
        raw_trades = self.profiler._load_trades(experiments, session_id=session_id)
        trades = [self._eligibility_trade(trade) for trade in raw_trades]
        report = self._build_report(
            session_id=session_id,
            strategy=strategy,
            experiment_id=experiment_id,
            experiments=experiments,
            trades=trades,
            min_trades=min_trades,
            max_combination_size=max_combination_size,
            min_support=min_support,
            min_confidence=min_confidence,
        )
        return self._write_reports(report)

    def _eligibility_trade(self, trade: TradeRecord) -> EligibilityTrade:
        row = self.indicators._row_at(trade.pair, trade.open_date) if trade.open_date else None
        btc_row = self.indicators._row_at("BTC/USDT", trade.open_date) if trade.open_date else None
        features = {
            "hour_of_day": self._hour_bucket(trade.open_date),
            "day_of_week": self._weekday(trade.open_date),
            "session": trade.regimes.get("hour_session", "UNKNOWN"),
            "ema200_direction": trade.regimes.get("ema200_direction", "UNKNOWN"),
            "ema200_slope": trade.regimes.get("ema200_slope_bucket", "UNKNOWN"),
            "ema200_distance": trade.regimes.get("ema200_distance_bucket", "UNKNOWN"),
            "adx": trade.regimes.get("adx_bucket", "UNKNOWN"),
            "atr": trade.regimes.get("atr_bucket", "UNKNOWN"),
            "volatility_pct": self._volatility_bucket(row),
            "relative_volume": trade.regimes.get("volume_state", "UNKNOWN"),
            "recent_breakout": trade.regimes.get("breakout_state", "UNKNOWN"),
            "btc_trend": trade.regimes.get("btc_regime", "UNKNOWN"),
            "btc_volatility": self._volatility_bucket(btc_row),
            "pair_btc_correlation": self._btc_correlation_bucket(trade.pair, trade.open_date),
            "trend_vs_range": self._trend_vs_range(trade.regimes),
            "high_volatility_regime": self._yes_no(trade.regimes.get("atr_bucket") == "ATR_HIGH"),
            "low_volatility_regime": self._yes_no(trade.regimes.get("atr_bucket") == "ATR_LOW"),
            "pair": trade.pair,
            "pair_group": self._pair_group(trade.pair),
        }
        return EligibilityTrade(
            experiment_id=trade.experiment_id,
            pair=trade.pair,
            open_date=trade.open_date,
            close_date=trade.close_date,
            profit_abs=trade.profit_abs,
            profit_ratio=trade.profit_ratio,
            duration_minutes=trade.duration_minutes,
            features=features,
        )

    def _build_report(
        self,
        *,
        session_id: str,
        strategy: str | None,
        experiment_id: str | None,
        experiments: list[dict[str, Any]],
        trades: list[EligibilityTrade],
        min_trades: int,
        max_combination_size: int,
        min_support: float,
        min_confidence: float,
    ) -> dict[str, Any]:
        overall = self._metrics(trades)
        filter_rankings = self._filter_rankings(trades, overall=overall, min_trades=min_trades)
        combination_rankings = self._combination_rankings(
            trades,
            overall=overall,
            min_trades=min_trades,
            max_size=max_combination_size,
        )
        interaction_matrix = self._interaction_matrix(trades, min_trades=min_trades)
        feature_importance = self._feature_importance(trades)
        decision_tree = self._decision_tree(trades, max_depth=4, min_samples=min_trades)
        association_rules = self._association_rules(
            trades,
            min_support=min_support,
            min_confidence=min_confidence,
            max_size=max_combination_size,
        )
        clusters = self._clusters(trades, min_trades=min_trades)
        heatmaps = self._heatmaps(trades, min_trades=min_trades)
        favorable_regions = [
            row for row in combination_rankings
            if row["profit_factor"] > max(1.0, overall["profit_factor"])
            and row["trades"] >= min_trades
            and row["expectancy"] > 0
        ][:50]
        forbidden_regions = [
            row for row in combination_rankings
            if row["profit_factor"] < min(0.9, overall["profit_factor"])
            and row["trades"] >= min_trades
            and row["profit_total_abs"] < 0
        ][:50]
        filter_candidates = self._classify_candidates(filter_rankings, overall)
        recommended = [
            row for row in filter_candidates
            if row["classification"] in {"mandatory", "recommended"}
            and row["evidence_score"] > 0.55
            and row["trades"] >= min_trades
        ]

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "strategy": strategy,
            "experiment_id": experiment_id,
            "experiment_count": len(experiments),
            "trade_count": len(trades),
            "timeframe": self.timeframe,
            "config": {
                "min_trades": min_trades,
                "max_combination_size": max_combination_size,
                "min_support": min_support,
                "min_confidence": min_confidence,
                "weights": DEFAULT_WEIGHTS,
            },
            "overall": overall,
            "filter_rankings": filter_rankings,
            "combination_rankings": combination_rankings,
            "interaction_matrix": interaction_matrix,
            "decision_tree": decision_tree,
            "feature_importance": feature_importance,
            "mutual_information": [
                {
                    "feature": row["feature"],
                    "mutual_information": row["mutual_information"],
                    "information_gain": row["information_gain"],
                }
                for row in feature_importance
            ],
            "association_rules": association_rules,
            "clusters": clusters,
            "heatmaps": heatmaps,
            "favorable_regions": favorable_regions,
            "forbidden_regions": forbidden_regions,
            "temporal_distribution": {
                "by_hour": self._feature_table(trades, "hour_of_day", overall, min_trades=1),
                "by_day": self._feature_table(trades, "day_of_week", overall, min_trades=1),
                "by_session": self._feature_table(trades, "session", overall, min_trades=1),
            },
            "pair_analysis": self._feature_table(trades, "pair", overall, min_trades=1),
            "regime_analysis": {
                "trend_vs_range": self._feature_table(trades, "trend_vs_range", overall, min_trades=1),
                "ema200_direction": self._feature_table(trades, "ema200_direction", overall, min_trades=1),
                "volatility_pct": self._feature_table(trades, "volatility_pct", overall, min_trades=1),
                "btc_trend": self._feature_table(trades, "btc_trend", overall, min_trades=1),
            },
            "filter_candidates": filter_candidates,
            "recommended_market_filters": recommended,
            "recommendations": self._recommendations(overall, filter_candidates, favorable_regions, forbidden_regions),
            "notes": self._notes(trades),
        }

    def _filter_rankings(
        self,
        trades: list[EligibilityTrade],
        *,
        overall: dict[str, Any],
        min_trades: int,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for feature in ELIGIBILITY_FEATURES:
            rows.extend(self._feature_table(trades, feature, overall, min_trades=min_trades))
        return sorted(rows, key=lambda row: row["evidence_score"], reverse=True)

    def _feature_table(
        self,
        trades: list[EligibilityTrade],
        feature: str,
        overall: dict[str, Any],
        *,
        min_trades: int,
    ) -> list[dict[str, Any]]:
        groups: dict[str, list[EligibilityTrade]] = defaultdict(list)
        for trade in trades:
            groups[trade.features.get(feature, "UNKNOWN")].append(trade)
        rows = []
        for value, group in groups.items():
            if len(group) < min_trades:
                continue
            metrics = self._metrics(group)
            rows.append(
                self._scored_row(
                    {
                        **metrics,
                        "type": "filter",
                        "feature": feature,
                        "value": value,
                        "label": f"{feature}={value}",
                        "features": [feature],
                        "values": [value],
                        "coverage": len(group) / len(trades) if trades else 0.0,
                    },
                    overall=overall,
                    combination_size=1,
                    experiment_count=self._experiment_count(group),
                )
            )
        return sorted(rows, key=lambda row: row["evidence_score"], reverse=True)

    def _combination_rankings(
        self,
        trades: list[EligibilityTrade],
        *,
        overall: dict[str, Any],
        min_trades: int,
        max_size: int,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        features = [feature for feature in ELIGIBILITY_FEATURES if feature not in {"hour_of_day"}]
        for size in range(2, max(2, max_size) + 1):
            for selected in combinations(features, size):
                groups: dict[tuple[str, ...], list[EligibilityTrade]] = defaultdict(list)
                for trade in trades:
                    key = tuple(trade.features.get(feature, "UNKNOWN") for feature in selected)
                    if "UNKNOWN" in key:
                        continue
                    groups[key].append(trade)
                for values, group in groups.items():
                    if len(group) < min_trades:
                        continue
                    metrics = self._metrics(group)
                    label = " + ".join(
                        f"{feature}={value}"
                        for feature, value in zip(selected, values)
                    )
                    rows.append(
                        self._scored_row(
                            {
                                **metrics,
                                "type": "combination",
                                "feature": "+".join(selected),
                                "value": "+".join(values),
                                "label": label,
                                "features": list(selected),
                                "values": list(values),
                                "coverage": len(group) / len(trades) if trades else 0.0,
                            },
                            overall=overall,
                            combination_size=size,
                            experiment_count=self._experiment_count(group),
                        )
                    )
        return sorted(rows, key=lambda row: row["evidence_score"], reverse=True)

    def _scored_row(
        self,
        row: dict[str, Any],
        *,
        overall: dict[str, Any],
        combination_size: int,
        experiment_count: int,
    ) -> dict[str, Any]:
        robustness = self._normalize(row["profit_factor"], center=1.0, width=1.5)
        repeatability = min(1.0, experiment_count / 8.0)
        net_gain = self._normalize(row["profit_total_abs"] - overall["expectancy"] * row["trades"], center=0.0, width=max(1.0, abs(overall["profit_total_abs"]) * 0.05))
        stability = 1.0 / (1.0 + max(0.0, row["max_drawdown_abs"] / max(1.0, abs(row["profit_total_abs"]))))
        simplicity = 1.0 / combination_size
        overfit_risk = 1.0 - min(1.0, row["trades"] / max(1.0, overall["trades"] * 0.08))
        score = (
            DEFAULT_WEIGHTS["robustness"] * robustness
            + DEFAULT_WEIGHTS["repeatability"] * repeatability
            + DEFAULT_WEIGHTS["net_gain"] * net_gain
            + DEFAULT_WEIGHTS["walk_forward_stability"] * stability
            + DEFAULT_WEIGHTS["simplicity"] * simplicity
            - DEFAULT_WEIGHTS["overfitting_risk"] * overfit_risk
        )
        row.update(
            {
                "experiment_count": experiment_count,
                "robustness_component": robustness,
                "repeatability_component": repeatability,
                "net_gain_component": net_gain,
                "walk_forward_stability_component": stability,
                "simplicity_component": simplicity,
                "overfitting_risk": overfit_risk,
                "evidence_score": max(0.0, min(1.0, score)),
            }
        )
        return row

    def _interaction_matrix(
        self,
        trades: list[EligibilityTrade],
        *,
        min_trades: int,
    ) -> list[dict[str, Any]]:
        rows = []
        for left, right in combinations(ELIGIBILITY_FEATURES, 2):
            left_rows = self._values_for_feature(trades, left, min_trades)
            right_rows = self._values_for_feature(trades, right, min_trades)
            if not left_rows or not right_rows:
                continue
            best_pair = None
            for left_value in left_rows[:6]:
                for right_value in right_rows[:6]:
                    group = [
                        trade for trade in trades
                        if trade.features.get(left) == left_value
                        and trade.features.get(right) == right_value
                    ]
                    if len(group) < min_trades:
                        continue
                    metrics = self._metrics(group)
                    candidate = {
                        "left": left,
                        "right": right,
                        "left_value": left_value,
                        "right_value": right_value,
                        "label": f"{left}={left_value} + {right}={right_value}",
                        **metrics,
                    }
                    if best_pair is None or candidate["profit_factor"] > best_pair["profit_factor"]:
                        best_pair = candidate
            if best_pair:
                rows.append(best_pair)
        return sorted(rows, key=lambda row: row["profit_factor"], reverse=True)

    def _values_for_feature(
        self,
        trades: list[EligibilityTrade],
        feature: str,
        min_trades: int,
    ) -> list[str]:
        counter = Counter(trade.features.get(feature, "UNKNOWN") for trade in trades)
        return [value for value, count in counter.most_common() if value != "UNKNOWN" and count >= min_trades]

    def _feature_importance(self, trades: list[EligibilityTrade]) -> list[dict[str, Any]]:
        y = [1 if trade.profit_abs > 0 else 0 for trade in trades]
        profits = [trade.profit_abs for trade in trades]
        rows = []
        for feature in ELIGIBILITY_FEATURES:
            x = [trade.features.get(feature, "UNKNOWN") for trade in trades]
            mutual_information = self._mutual_information(x, y)
            information_gain = self._information_gain(x, y)
            profit_separation = self._profit_separation(x, profits)
            permutation_importance = self._permutation_importance(x, profits, profit_separation)
            rows.append(
                {
                    "feature": feature,
                    "mutual_information": mutual_information,
                    "information_gain": information_gain,
                    "profit_separation": profit_separation,
                    "permutation_importance": permutation_importance,
                    "feature_importance": (
                        mutual_information
                        + information_gain
                        + profit_separation
                        + max(0.0, permutation_importance)
                    )
                    / 4.0,
                }
            )
        return sorted(rows, key=lambda row: row["feature_importance"], reverse=True)

    def _decision_tree(
        self,
        trades: list[EligibilityTrade],
        *,
        max_depth: int,
        min_samples: int,
    ) -> dict[str, Any]:
        return self._tree_node(trades, ELIGIBILITY_FEATURES, depth=0, max_depth=max_depth, min_samples=min_samples)

    def _tree_node(
        self,
        trades: list[EligibilityTrade],
        features: list[str],
        *,
        depth: int,
        max_depth: int,
        min_samples: int,
    ) -> dict[str, Any]:
        wins = sum(1 for trade in trades if trade.profit_abs > 0)
        node = {
            "depth": depth,
            "trades": len(trades),
            "win_rate": wins / len(trades) if trades else 0.0,
            "profit_factor": self._metrics(trades)["profit_factor"] if trades else 0.0,
            "profit_total_abs": sum(trade.profit_abs for trade in trades),
        }
        if depth >= max_depth or len(trades) < min_samples or not features:
            node["leaf"] = True
            return node
        parent_entropy = self._entropy([1 if trade.profit_abs > 0 else 0 for trade in trades])
        best_feature = None
        best_gain = 0.0
        best_groups: dict[str, list[EligibilityTrade]] = {}
        for feature in features:
            groups: dict[str, list[EligibilityTrade]] = defaultdict(list)
            for trade in trades:
                groups[trade.features.get(feature, "UNKNOWN")].append(trade)
            weighted_entropy = 0.0
            for group in groups.values():
                weighted_entropy += len(group) / len(trades) * self._entropy([1 if trade.profit_abs > 0 else 0 for trade in group])
            gain = parent_entropy - weighted_entropy
            if gain > best_gain:
                best_feature = feature
                best_gain = gain
                best_groups = groups
        if not best_feature or best_gain <= 0:
            node["leaf"] = True
            return node
        node.update({"leaf": False, "split_feature": best_feature, "information_gain": best_gain, "children": {}})
        remaining = [feature for feature in features if feature != best_feature]
        for value, group in sorted(best_groups.items(), key=lambda item: len(item[1]), reverse=True)[:8]:
            if len(group) < max(2, min_samples // 2):
                continue
            node["children"][value] = self._tree_node(group, remaining, depth=depth + 1, max_depth=max_depth, min_samples=min_samples)
        return node

    def _association_rules(
        self,
        trades: list[EligibilityTrade],
        *,
        min_support: float,
        min_confidence: float,
        max_size: int,
    ) -> list[dict[str, Any]]:
        if not trades:
            return []
        transactions = [self._transaction(trade) for trade in trades]
        winning = [trade.profit_abs > 0 for trade in trades]
        rules = []
        max_count = max(1, int(len(trades) * min_support))
        for size in range(1, max_size + 1):
            counts: Counter[tuple[str, ...]] = Counter()
            win_counts: Counter[tuple[str, ...]] = Counter()
            for transaction, is_win in zip(transactions, winning):
                for itemset in combinations(sorted(transaction), size):
                    counts[itemset] += 1
                    if is_win:
                        win_counts[itemset] += 1
            for itemset, count in counts.items():
                if count < max_count:
                    continue
                confidence = win_counts[itemset] / count if count else 0.0
                if confidence < min_confidence:
                    continue
                support = count / len(trades)
                base_rate = sum(winning) / len(winning)
                rules.append(
                    {
                        "if": list(itemset),
                        "then": "WIN",
                        "support": support,
                        "confidence": confidence,
                        "lift": confidence / base_rate if base_rate else 0.0,
                        "trades": count,
                    }
                )
        return sorted(rules, key=lambda row: (row["lift"], row["confidence"], row["support"]), reverse=True)[:100]

    def _transaction(self, trade: EligibilityTrade) -> frozenset[str]:
        return frozenset(f"{key}={value}" for key, value in trade.features.items() if value != "UNKNOWN")

    def _clusters(
        self,
        trades: list[EligibilityTrade],
        *,
        min_trades: int,
    ) -> list[dict[str, Any]]:
        cluster_features = [
            "session",
            "trend_vs_range",
            "volatility_pct",
            "relative_volume",
            "btc_trend",
            "pair_group",
        ]
        groups: dict[tuple[str, ...], list[EligibilityTrade]] = defaultdict(list)
        for trade in trades:
            key = tuple(trade.features.get(feature, "UNKNOWN") for feature in cluster_features)
            groups[key].append(trade)
        clusters = []
        for index, (signature, group) in enumerate(groups.items(), start=1):
            if len(group) < min_trades:
                continue
            metrics = self._metrics(group)
            clusters.append(
                {
                    "cluster_id": index,
                    "signature": dict(zip(cluster_features, signature)),
                    **metrics,
                }
            )
        return sorted(clusters, key=lambda row: row["profit_total_abs"], reverse=True)

    def _heatmaps(
        self,
        trades: list[EligibilityTrade],
        *,
        min_trades: int,
    ) -> dict[str, list[dict[str, Any]]]:
        pairs = [
            ("session", "trend_vs_range"),
            ("adx", "atr"),
            ("ema200_direction", "relative_volume"),
            ("btc_trend", "pair_group"),
            ("volatility_pct", "recent_breakout"),
            ("day_of_week", "session"),
        ]
        heatmaps: dict[str, list[dict[str, Any]]] = {}
        for left, right in pairs:
            cells = []
            groups: dict[tuple[str, str], list[EligibilityTrade]] = defaultdict(list)
            for trade in trades:
                groups[(trade.features.get(left, "UNKNOWN"), trade.features.get(right, "UNKNOWN"))].append(trade)
            for (left_value, right_value), group in groups.items():
                if len(group) < min_trades:
                    continue
                cells.append({"x": left_value, "y": right_value, **self._metrics(group)})
            heatmaps[f"{left}_x_{right}"] = sorted(cells, key=lambda row: row["profit_factor"], reverse=True)
        return heatmaps

    def _classify_candidates(
        self,
        filter_rankings: list[dict[str, Any]],
        overall: dict[str, Any],
    ) -> list[dict[str, Any]]:
        rows = []
        for row in filter_rankings:
            profit_lift = row["profit_factor"] - overall["profit_factor"]
            expectancy_lift = row["expectancy"] - overall["expectancy"]
            if row["evidence_score"] >= 0.72 and profit_lift > 0.2 and row["expectancy"] > 0:
                classification = "mandatory"
            elif row["evidence_score"] >= 0.58 and profit_lift > 0 and expectancy_lift >= 0:
                classification = "recommended"
            elif row["profit_factor"] < overall["profit_factor"] * 0.85 and row["profit_total_abs"] < 0:
                classification = "harmful"
            else:
                classification = "optional"
            rows.append({**row, "classification": classification})
        order = {"mandatory": 0, "recommended": 1, "optional": 2, "harmful": 3}
        return sorted(rows, key=lambda row: (order[row["classification"]], -row["evidence_score"]))

    def _recommendations(
        self,
        overall: dict[str, Any],
        candidates: list[dict[str, Any]],
        favorable_regions: list[dict[str, Any]],
        forbidden_regions: list[dict[str, Any]],
    ) -> list[str]:
        recommendations = []
        for label in ["mandatory", "recommended", "harmful"]:
            rows = [row for row in candidates if row["classification"] == label]
            if rows:
                top = rows[0]
                recommendations.append(
                    f"{label}: {top['label']} (PF={top['profit_factor']:.3f}, "
                    f"trades={top['trades']}, score={top['evidence_score']:.3f})."
                )
        if favorable_regions:
            top = favorable_regions[0]
            recommendations.append(
                f"Regiao favoravel mais forte: {top['label']} "
                f"(PF={top['profit_factor']:.3f}, profit={top['profit_total_abs']:.3f})."
            )
        if forbidden_regions:
            top = forbidden_regions[0]
            recommendations.append(
                f"Regiao proibida candidata: {top['label']} "
                f"(PF={top['profit_factor']:.3f}, profit={top['profit_total_abs']:.3f})."
            )
        if not recommendations:
            recommendations.append(
                f"Nenhum filtro atingiu evidencia suficiente; PF geral={overall['profit_factor']:.3f}."
            )
        return recommendations

    def _notes(self, trades: list[EligibilityTrade]) -> list[str]:
        unknown_counts = {
            feature: sum(1 for trade in trades if trade.features.get(feature) == "UNKNOWN")
            for feature in ELIGIBILITY_FEATURES
        }
        notes = []
        for feature, count in unknown_counts.items():
            if trades and count / len(trades) > 0.5:
                notes.append(f"{feature} possui mais de 50% de valores UNKNOWN; interpretar com cautela.")
        notes.append("Analise offline: nenhuma estrategia, plugin ou logica operacional foi alterada.")
        return notes

    def _metrics(self, trades: list[EligibilityTrade]) -> dict[str, Any]:
        profits = [trade.profit_abs for trade in trades]
        ratios = [trade.profit_ratio for trade in trades]
        gross_profit = sum(value for value in profits if value > 0)
        gross_loss = abs(sum(value for value in profits if value < 0))
        wins = sum(1 for value in profits if value > 0)
        losses = sum(1 for value in profits if value < 0)
        duration_hours = sum(max(0.0, trade.duration_minutes) for trade in trades) / 60.0
        profit_total = sum(profits)
        return {
            "trades": len(trades),
            "wins": wins,
            "losses": losses,
            "profit_factor": gross_profit / gross_loss if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0),
            "sharpe": self._sharpe(ratios),
            "max_drawdown_abs": self._max_drawdown(profits),
            "expectancy": statistics.mean(profits) if profits else 0.0,
            "win_rate": wins / len(trades) if trades else 0.0,
            "profit_total_abs": profit_total,
            "profit_per_hour": profit_total / duration_hours if duration_hours > 0 else 0.0,
            "profit_per_trade": profit_total / len(trades) if trades else 0.0,
            "avg_duration_minutes": statistics.mean([trade.duration_minutes for trade in trades]) if trades else 0.0,
        }

    def _experiment_count(self, trades: list[EligibilityTrade]) -> int:
        return len({trade.experiment_id for trade in trades})

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
        max_drawdown = 0.0
        for profit in profits:
            equity += profit
            peak = max(peak, equity)
            max_drawdown = max(max_drawdown, peak - equity)
        return max_drawdown

    def _mutual_information(self, x_values: list[str], y_values: list[int]) -> float:
        if not x_values or not y_values:
            return 0.0
        total = len(x_values)
        x_counts = Counter(x_values)
        y_counts = Counter(y_values)
        joint = Counter(zip(x_values, y_values))
        result = 0.0
        for (x_value, y_value), count in joint.items():
            pxy = count / total
            px = x_counts[x_value] / total
            py = y_counts[y_value] / total
            if pxy > 0 and px > 0 and py > 0:
                result += pxy * math.log(pxy / (px * py), 2)
        return result

    def _information_gain(self, x_values: list[str], y_values: list[int]) -> float:
        if not x_values or not y_values:
            return 0.0
        base = self._entropy(y_values)
        groups: dict[str, list[int]] = defaultdict(list)
        for x_value, y_value in zip(x_values, y_values):
            groups[x_value].append(y_value)
        weighted = sum(len(group) / len(y_values) * self._entropy(group) for group in groups.values())
        return max(0.0, base - weighted)

    def _entropy(self, values: list[int]) -> float:
        if not values:
            return 0.0
        counts = Counter(values)
        total = len(values)
        entropy = 0.0
        for count in counts.values():
            probability = count / total
            if probability > 0:
                entropy -= probability * math.log(probability, 2)
        return entropy

    def _profit_separation(self, x_values: list[str], profits: list[float]) -> float:
        if not x_values:
            return 0.0
        groups: dict[str, list[float]] = defaultdict(list)
        for x_value, profit in zip(x_values, profits):
            groups[x_value].append(profit)
        means = [statistics.mean(group) for group in groups.values() if group]
        if len(means) < 2:
            return 0.0
        spread = max(means) - min(means)
        scale = statistics.pstdev(profits) if len(profits) > 1 else 0.0
        return spread / (spread + scale) if spread + scale > 0 else 0.0

    def _permutation_importance(
        self,
        x_values: list[str],
        profits: list[float],
        baseline: float,
    ) -> float:
        if len(x_values) < 2:
            return 0.0
        shifted = x_values[1:] + x_values[:1]
        return baseline - self._profit_separation(shifted, profits)

    def _normalize(self, value: float, *, center: float, width: float) -> float:
        if width <= 0:
            return 0.0
        return max(0.0, min(1.0, 0.5 + (value - center) / (2.0 * width)))

    def _hour_bucket(self, value: datetime | None) -> str:
        if value is None:
            return "UNKNOWN"
        return f"H{value.astimezone(timezone.utc).hour:02d}"

    def _weekday(self, value: datetime | None) -> str:
        if value is None:
            return "UNKNOWN"
        return value.astimezone(timezone.utc).strftime("%A").upper()

    def _volatility_bucket(self, row: dict[str, Any] | None) -> str:
        if not row:
            return "UNKNOWN"
        atr_pct = self._number(row.get("atr_pct"))
        range_pct = self._number(row.get("range_pct"))
        value = max(atr_pct, range_pct)
        if value < 0.008:
            return "VOL_LOW"
        if value < 0.02:
            return "VOL_MEDIUM"
        return "VOL_HIGH"

    def _btc_correlation_bucket(self, pair: str, open_date: datetime | None) -> str:
        if open_date is None or pair == "BTC/USDT":
            return "BTC_SELF"
        corr = self._rolling_btc_correlation(pair, open_date)
        if corr is None:
            return "UNKNOWN"
        if corr < 0.25:
            return "BTC_CORR_LOW"
        if corr < 0.65:
            return "BTC_CORR_MEDIUM"
        return "BTC_CORR_HIGH"

    def _rolling_btc_correlation(self, pair: str, open_date: datetime) -> float | None:
        pd = self.indicators._pd()
        if pd is None:
            return None
        frame = self.indicators._frame(pair)
        btc_frame = self.indicators._frame("BTC/USDT")
        if frame is None or btc_frame is None:
            return None
        timestamp = pd.Timestamp(open_date).tz_convert("UTC")
        left_index = frame["date"].searchsorted(timestamp, side="right") - 1
        right_index = btc_frame["date"].searchsorted(timestamp, side="right") - 1
        if left_index < 30 or right_index < 30:
            return None
        left = frame.iloc[int(left_index) - 30 : int(left_index) + 1][["date", "close"]].copy()
        right = btc_frame.iloc[int(right_index) - 30 : int(right_index) + 1][["date", "close"]].copy()
        left["ret"] = left["close"].astype(float).pct_change()
        right["ret"] = right["close"].astype(float).pct_change()
        merged = left[["date", "ret"]].merge(right[["date", "ret"]], on="date", suffixes=("_pair", "_btc")).dropna()
        if len(merged) < 10:
            return None
        corr = merged["ret_pair"].corr(merged["ret_btc"])
        if corr is None or math.isnan(float(corr)):
            return None
        return float(corr)

    def _trend_vs_range(self, regimes: dict[str, str]) -> str:
        adx = regimes.get("adx_bucket")
        slope = regimes.get("ema200_slope_bucket")
        if adx == "ADX_HIGH" and slope in {"SLOPE_UP", "SLOPE_UP_STRONG", "SLOPE_DOWN", "SLOPE_DOWN_STRONG"}:
            return "TREND"
        if adx == "ADX_LOW" or slope == "SLOPE_FLAT":
            return "RANGE"
        return "MIXED"

    def _pair_group(self, pair: str) -> str:
        base = pair.split("/")[0].upper()
        if base in {"BTC", "ETH"}:
            return "MAJOR"
        if base in {"BNB", "SOL", "AVAX", "ADA", "LINK", "LTC", "XRP"}:
            return "LARGE_ALT"
        if base in {"DOGE", "SHIB", "PEPE"}:
            return "MEME"
        return "OTHER"

    def _yes_no(self, condition: bool) -> str:
        return "YES" if condition else "NO"

    def _number(self, value: Any) -> float:
        try:
            result = float(value)
            if math.isnan(result) or math.isinf(result):
                return 0.0
            return result
        except (TypeError, ValueError):
            return 0.0

    def _write_reports(self, report: dict[str, Any]) -> dict[str, Path]:
        json_path = self.output_dir / "market_eligibility_report.json"
        markdown_path = self.output_dir / "market_eligibility_report.md"
        html_path = self.output_dir / "market_eligibility_report.html"
        filters_path = self.output_dir / "recommended_market_filters.json"
        json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        markdown_path.write_text(self._markdown(report), encoding="utf-8")
        html_path.write_text(self._html(report), encoding="utf-8")
        filters_path.write_text(
            json.dumps(report["recommended_market_filters"], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return {
            "json": json_path,
            "markdown": markdown_path,
            "html": html_path,
            "recommended_filters": filters_path,
        }

    def _markdown(self, report: dict[str, Any]) -> str:
        lines = [
            "# Market Eligibility Research",
            "",
            "## Summary",
            f"- Session: {report['session_id']}",
            f"- Strategy: {report.get('strategy') or 'ALL'}",
            f"- Experiments: {report['experiment_count']}",
            f"- Trades: {report['trade_count']}",
            f"- Overall PF: {report['overall']['profit_factor']:.3f}",
            f"- Overall profit: {report['overall']['profit_total_abs']:.3f}",
            "",
            "## Candidate Filters",
            "| Classification | Filter | Trades | PF | Sharpe | Drawdown | Expectancy | Profit | Score |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for row in report["filter_candidates"][:50]:
            lines.append(
                f"| {row['classification']} | {row['label']} | {row['trades']} | "
                f"{row['profit_factor']:.3f} | {row['sharpe']:.3f} | "
                f"{row['max_drawdown_abs']:.3f} | {row['expectancy']:.3f} | "
                f"{row['profit_total_abs']:.3f} | {row['evidence_score']:.3f} |"
            )
        lines.extend(["", "## Top Combinations"])
        lines.append("| Combination | Trades | PF | Win Rate | Profit | Score |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for row in report["combination_rankings"][:50]:
            lines.append(
                f"| {row['label']} | {row['trades']} | {row['profit_factor']:.3f} | "
                f"{row['win_rate']:.3f} | {row['profit_total_abs']:.3f} | {row['evidence_score']:.3f} |"
            )
        lines.extend(["", "## Feature Importance"])
        lines.append("| Feature | MI | Information Gain | Importance |")
        lines.append("|---|---:|---:|---:|")
        for row in report["feature_importance"]:
            lines.append(
                f"| {row['feature']} | {row['mutual_information']:.5f} | "
                f"{row['information_gain']:.5f} | {row['feature_importance']:.5f} |"
            )
        lines.extend(["", "## Recommendations"])
        for recommendation in report["recommendations"]:
            lines.append(f"- {recommendation}")
        lines.extend(["", "## Notes"])
        for note in report["notes"]:
            lines.append(f"- {note}")
        return "\n".join(lines) + "\n"

    def _html(self, report: dict[str, Any]) -> str:
        def table(rows: list[dict[str, Any]], columns: list[tuple[str, str]], limit: int = 50) -> str:
            result = ["<table><thead><tr>"]
            for title, _ in columns:
                result.append(f"<th>{html.escape(title)}</th>")
            result.append("</tr></thead><tbody>")
            for row in rows[:limit]:
                result.append("<tr>")
                for _, key in columns:
                    value = row.get(key, "")
                    if isinstance(value, float):
                        value = f"{value:.4f}"
                    result.append(f"<td>{html.escape(str(value))}</td>")
                result.append("</tr>")
            result.append("</tbody></table>")
            return "".join(result)

        parts = [
            "<!doctype html><html><head><meta charset='utf-8'>",
            "<title>Market Eligibility Research</title>",
            "<style>body{font-family:Segoe UI,Arial,sans-serif;margin:32px;color:#202124;line-height:1.45}"
            "table{border-collapse:collapse;width:100%;margin:16px 0;font-size:13px}"
            "td,th{border:1px solid #ddd;padding:6px;text-align:right}td:first-child,th:first-child{text-align:left}"
            "th{background:#f4f6f8}code{background:#f4f6f8;padding:2px 4px}</style></head><body>",
            "<h1>Market Eligibility Research</h1>",
            f"<p>Session: <code>{html.escape(report['session_id'])}</code> | "
            f"Trades: <b>{report['trade_count']}</b> | "
            f"Overall PF: <b>{report['overall']['profit_factor']:.3f}</b></p>",
            "<h2>Candidate Filters</h2>",
            table(
                report["filter_candidates"],
                [
                    ("Class", "classification"),
                    ("Filter", "label"),
                    ("Trades", "trades"),
                    ("PF", "profit_factor"),
                    ("Sharpe", "sharpe"),
                    ("Drawdown", "max_drawdown_abs"),
                    ("Profit", "profit_total_abs"),
                    ("Score", "evidence_score"),
                ],
            ),
            "<h2>Top Combinations</h2>",
            table(
                report["combination_rankings"],
                [
                    ("Combination", "label"),
                    ("Trades", "trades"),
                    ("PF", "profit_factor"),
                    ("Win Rate", "win_rate"),
                    ("Profit", "profit_total_abs"),
                    ("Score", "evidence_score"),
                ],
            ),
            "<h2>Feature Importance</h2>",
            table(
                report["feature_importance"],
                [
                    ("Feature", "feature"),
                    ("MI", "mutual_information"),
                    ("Information Gain", "information_gain"),
                    ("Importance", "feature_importance"),
                ],
            ),
            "<h2>Recommendations</h2><ul>",
        ]
        parts.extend(f"<li>{html.escape(item)}</li>" for item in report["recommendations"])
        parts.append("</ul></body></html>")
        return "\n".join(parts)


def command_analyze(args: argparse.Namespace) -> dict[str, str]:
    analyzer = MarketEligibilityResearch(
        db_path=args.db_path,
        output_dir=args.output_dir,
        project_root=args.project_root,
        timeframe=args.timeframe,
    )
    paths = analyzer.analyze(
        session_id=args.session_id,
        strategy=args.strategy,
        experiment_id=args.experiment_id,
        min_trades=args.min_trades,
        max_combination_size=args.max_combination_size,
        min_support=args.min_support,
        min_confidence=args.min_confidence,
    )
    return {key: str(path.resolve()) for key, path in paths.items()}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Research market eligibility filters using existing lab results.",
    )
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--timeframe", default=DEFAULT_TIMEFRAME)
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser("analyze", help="Generate market eligibility reports.")
    analyze.add_argument("session_id")
    analyze.add_argument("--strategy")
    analyze.add_argument("--experiment-id")
    analyze.add_argument("--min-trades", type=int, default=20)
    analyze.add_argument("--max-combination-size", type=int, default=3)
    analyze.add_argument("--min-support", type=float, default=0.03)
    analyze.add_argument("--min-confidence", type=float, default=0.55)
    analyze.set_defaults(func=command_analyze)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    result = args.func(args)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
