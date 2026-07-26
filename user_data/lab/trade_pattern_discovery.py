from __future__ import annotations

import argparse
import csv
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
    from .market_regime_profiler import MarketRegimeProfiler, REGIME_FEATURES, TradeRecord
except ImportError:
    from experiment_database import DEFAULT_DB_PATH
    from market_regime_profiler import MarketRegimeProfiler, REGIME_FEATURES, TradeRecord


DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent
OUTCOME_WIN = "WIN"
OUTCOME_LOSS = "LOSS"


@dataclass(frozen=True)
class PatternTrade:
    experiment_id: str
    pair: str
    outcome: str
    profit_abs: float
    profit_ratio: float
    duration_minutes: float
    drawdown_proxy: float
    features: dict[str, str]
    transaction: frozenset[str]


class TradePatternDiscovery:
    """Read-only pattern discovery over already completed lab trades."""

    def __init__(
        self,
        *,
        db_path: Path | str = DEFAULT_DB_PATH,
        output_dir: Path | str = DEFAULT_OUTPUT_DIR,
        project_root: Path | str | None = None,
        timeframe: str = "5m",
    ) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.profiler = MarketRegimeProfiler(
            db_path=db_path,
            output_dir=output_dir,
            project_root=project_root,
            timeframe=timeframe,
        )

    def analyze(
        self,
        *,
        session_id: str,
        strategy: str | None = None,
        experiment_id: str | None = None,
        trades_csv: Path | None = None,
        min_support: float = 0.05,
        min_confidence: float = 0.6,
        max_itemset_size: int = 3,
        export_csv: bool = False,
    ) -> dict[str, Path]:
        trades = self._load_pattern_trades(
            session_id=session_id,
            strategy=strategy,
            experiment_id=experiment_id,
            trades_csv=trades_csv,
        )
        report = self._build_report(
            session_id=session_id,
            strategy=strategy,
            experiment_id=experiment_id,
            trades=trades,
            min_support=min_support,
            min_confidence=min_confidence,
            max_itemset_size=max_itemset_size,
        )
        paths = self._write_reports(report)
        if export_csv:
            paths["csv"] = self._write_trade_csv(report, trades)
        return paths

    def _load_pattern_trades(
        self,
        *,
        session_id: str,
        strategy: str | None,
        experiment_id: str | None,
        trades_csv: Path | None,
    ) -> list[PatternTrade]:
        if trades_csv:
            return self._load_pattern_trades_from_csv(trades_csv)
        experiments = self.profiler._load_experiments(
            session_id=session_id,
            strategy=strategy,
            experiment_id=experiment_id,
        )
        raw_trades = self.profiler._load_trades(experiments, session_id=session_id)
        experiment_params = {
            experiment["id"]: experiment.get("parameters", {})
            for experiment in experiments
        }
        return [
            self._to_pattern_trade(trade, experiment_params.get(trade.experiment_id, {}))
            for trade in raw_trades
        ]

    def _load_pattern_trades_from_csv(self, path: Path) -> list[PatternTrade]:
        trades: list[PatternTrade] = []
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                profit_abs = self._number(row.get("profit_abs"))
                profit_ratio = self._number(row.get("profit_ratio"))
                features = {
                    key: str(value)
                    for key, value in row.items()
                    if key not in {"experiment_id", "profit_abs", "profit_ratio", "duration_minutes"}
                    and value not in {None, ""}
                }
                outcome = OUTCOME_WIN if profit_abs > 0 else OUTCOME_LOSS
                transaction = self._transaction(features)
                trades.append(
                    PatternTrade(
                        experiment_id=str(row.get("experiment_id", "")),
                        pair=str(row.get("pair", "")),
                        outcome=outcome,
                        profit_abs=profit_abs,
                        profit_ratio=profit_ratio,
                        duration_minutes=self._number(row.get("duration_minutes")),
                        drawdown_proxy=max(0.0, -profit_abs),
                        features=features,
                        transaction=transaction,
                    )
                )
        return trades

    def _to_pattern_trade(
        self,
        trade: TradeRecord,
        parameters: dict[str, Any],
    ) -> PatternTrade:
        outcome = OUTCOME_WIN if trade.profit_abs > 0 else OUTCOME_LOSS
        features: dict[str, str] = {
            "pair": trade.pair,
            "exit_reason": trade.exit_reason or "UNKNOWN",
            "enter_tag": trade.enter_tag or "EMPTY",
            "duration_bucket": self._duration_bucket(trade.duration_minutes),
            "profit_ratio_bucket": self._profit_ratio_bucket(trade.profit_ratio),
            "stake_bucket": self._stake_bucket(trade.stake_amount),
        }
        features.update({feature: trade.regimes.get(feature, "UNKNOWN") for feature in REGIME_FEATURES})
        features.update(self._parameter_features(parameters))
        transaction = self._transaction(features)
        return PatternTrade(
            experiment_id=trade.experiment_id,
            pair=trade.pair,
            outcome=outcome,
            profit_abs=trade.profit_abs,
            profit_ratio=trade.profit_ratio,
            duration_minutes=trade.duration_minutes,
            drawdown_proxy=max(0.0, -trade.profit_abs),
            features=features,
            transaction=transaction,
        )

    def _parameter_features(self, parameters: dict[str, Any]) -> dict[str, str]:
        flat = self._flatten(parameters)
        selected: dict[str, str] = {}
        for key, value in flat.items():
            if isinstance(value, bool):
                selected[f"param_{key}"] = str(value).upper()
            elif isinstance(value, (int, float)):
                selected[f"param_{key}"] = self._numeric_param_bucket(key, float(value))
            elif isinstance(value, str) and value:
                selected[f"param_{key}"] = value
        return selected

    def _build_report(
        self,
        *,
        session_id: str,
        strategy: str | None,
        experiment_id: str | None,
        trades: list[PatternTrade],
        min_support: float,
        min_confidence: float,
        max_itemset_size: int,
    ) -> dict[str, Any]:
        frequent_itemsets = self._frequent_itemsets(
            trades,
            min_support=min_support,
            max_size=max_itemset_size,
        )
        association_rules = self._association_rules(
            trades,
            frequent_itemsets=frequent_itemsets,
            min_confidence=min_confidence,
        )
        feature_importance = self._feature_importance(trades)
        tree = self._decision_tree(trades, max_depth=4, min_samples=20)
        clusters = self._clusters(trades)
        outliers = self._outliers(trades)
        shap_values = self._shap_values_when_possible(trades)
        recommendations = self._recommendations(
            trades=trades,
            rules=association_rules,
            importance=feature_importance,
            clusters=clusters,
            outliers=outliers,
        )
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "strategy": strategy,
            "experiment_id": experiment_id,
            "trade_count": len(trades),
            "outcome_counts": dict(Counter(trade.outcome for trade in trades)),
            "overall": self._metrics(trades),
            "winning_characteristics_80pct": self._class_characteristics(trades, OUTCOME_WIN, threshold=0.8),
            "losing_characteristics_80pct": self._class_characteristics(trades, OUTCOME_LOSS, threshold=0.8),
            "frequent_itemsets": frequent_itemsets[:250],
            "association_rules": association_rules[:250],
            "decision_tree": tree,
            "feature_importance": feature_importance,
            "shap_values": shap_values,
            "mutual_information": [
                {
                    "feature": row["feature"],
                    "mutual_information": row["mutual_information"],
                }
                for row in feature_importance
            ],
            "clusters": clusters,
            "outliers": outliers,
            "charts": self._chart_payload(
                feature_importance=feature_importance,
                tree=tree,
                clusters=clusters,
                rules=association_rules,
                trades=trades,
            ),
            "recommendations": recommendations,
            "notes": [
                "This module is read-only and does not execute backtests.",
                "SHAP values are populated only when optional ML dependencies are available.",
                "Drawdown is estimated per trade as realized loss proxy because per-trade intra-trade equity is not available in standard backtest trade rows.",
            ],
        }

    def _frequent_itemsets(
        self,
        trades: list[PatternTrade],
        *,
        min_support: float,
        max_size: int,
    ) -> list[dict[str, Any]]:
        total = len(trades)
        if total == 0:
            return []
        min_count = max(1, math.ceil(total * min_support))
        counters: dict[int, Counter[tuple[str, ...]]] = {
            size: Counter()
            for size in range(1, max_size + 1)
        }
        for trade in trades:
            items = sorted(trade.transaction)
            for size in range(1, max_size + 1):
                if len(items) < size:
                    continue
                for combo in combinations(items, size):
                    counters[size][combo] += 1

        rows = []
        for size, counter in counters.items():
            for itemset, count in counter.items():
                if count < min_count:
                    continue
                matched = [trade for trade in trades if set(itemset).issubset(trade.transaction)]
                rows.append(
                    {
                        "items": list(itemset),
                        "size": size,
                        "count": count,
                        "support": count / total,
                        **self._metrics(matched),
                    }
                )
        return sorted(rows, key=lambda row: (row["support"], abs(row["profit_total_abs"])), reverse=True)

    def _association_rules(
        self,
        trades: list[PatternTrade],
        *,
        frequent_itemsets: list[dict[str, Any]],
        min_confidence: float,
    ) -> list[dict[str, Any]]:
        total = len(trades)
        if total == 0:
            return []
        base_win_rate = sum(1 for trade in trades if trade.outcome == OUTCOME_WIN) / total
        base_loss_rate = 1.0 - base_win_rate
        rules = []
        for itemset in frequent_itemsets:
            items = set(itemset["items"])
            matched = [trade for trade in trades if items.issubset(trade.transaction)]
            if not matched:
                continue
            win_rate = sum(1 for trade in matched if trade.outcome == OUTCOME_WIN) / len(matched)
            loss_rate = 1.0 - win_rate
            for outcome, confidence, base_rate in (
                (OUTCOME_WIN, win_rate, base_win_rate),
                (OUTCOME_LOSS, loss_rate, base_loss_rate),
            ):
                if confidence < min_confidence:
                    continue
                lift = confidence / base_rate if base_rate > 0 else 0.0
                rules.append(
                    {
                        "if": sorted(items),
                        "then": outcome,
                        "support": len(matched) / total,
                        "confidence": confidence,
                        "lift": lift,
                        "probability_of_profit": win_rate,
                        **self._metrics(matched),
                    }
                )
        return sorted(
            rules,
            key=lambda row: (row["lift"], row["confidence"], row["support"]),
            reverse=True,
        )

    def _feature_importance(self, trades: list[PatternTrade]) -> list[dict[str, Any]]:
        feature_names = sorted({key for trade in trades for key in trade.features})
        outcomes = [1 if trade.outcome == OUTCOME_WIN else 0 for trade in trades]
        profits = [trade.profit_abs for trade in trades]
        rows = []
        for feature in feature_names:
            values = [trade.features.get(feature, "UNKNOWN") for trade in trades]
            mi = self._mutual_information(values, outcomes)
            gain = self._information_gain(values, outcomes)
            separation = self._profit_separation(values, profits)
            permutation = self._permutation_importance(values, profits, separation)
            rows.append(
                {
                    "feature": feature,
                    "mutual_information": mi,
                    "information_gain": gain,
                    "permutation_importance": permutation,
                    "profit_separation": separation,
                    "feature_importance": (mi + gain + max(0.0, permutation) + separation) / 4.0,
                }
            )
        return sorted(rows, key=lambda row: row["feature_importance"], reverse=True)

    def _decision_tree(
        self,
        trades: list[PatternTrade],
        *,
        max_depth: int,
        min_samples: int,
    ) -> dict[str, Any]:
        features = sorted({key for trade in trades for key in trade.features})
        return self._tree_node(trades, features, depth=0, max_depth=max_depth, min_samples=min_samples)

    def _tree_node(
        self,
        trades: list[PatternTrade],
        features: list[str],
        *,
        depth: int,
        max_depth: int,
        min_samples: int,
    ) -> dict[str, Any]:
        metrics = self._metrics(trades)
        node = {
            "depth": depth,
            "trades": len(trades),
            "win_rate": metrics["win_rate"],
            "profit_total_abs": metrics["profit_total_abs"],
            "split_feature": None,
            "branches": [],
        }
        if depth >= max_depth or len(trades) < min_samples or metrics["win_rate"] in {0.0, 1.0}:
            return node
        split = self._best_split(trades, features)
        if split is None:
            return node
        feature, gain, groups = split
        node["split_feature"] = feature
        node["information_gain"] = gain
        for value, group in sorted(groups.items(), key=lambda item: len(item[1]), reverse=True):
            remaining = [name for name in features if name != feature]
            child = self._tree_node(
                group,
                remaining,
                depth=depth + 1,
                max_depth=max_depth,
                min_samples=min_samples,
            )
            child["condition"] = f"{feature}={value}"
            node["branches"].append(child)
        return node

    def _best_split(
        self,
        trades: list[PatternTrade],
        features: list[str],
    ) -> tuple[str, float, dict[str, list[PatternTrade]]] | None:
        outcomes = [1 if trade.outcome == OUTCOME_WIN else 0 for trade in trades]
        base_entropy = self._entropy(outcomes)
        best: tuple[str, float, dict[str, list[PatternTrade]]] | None = None
        for feature in features:
            groups: dict[str, list[PatternTrade]] = defaultdict(list)
            for trade in trades:
                groups[trade.features.get(feature, "UNKNOWN")].append(trade)
            if len(groups) <= 1:
                continue
            conditional = 0.0
            for group in groups.values():
                group_outcomes = [1 if trade.outcome == OUTCOME_WIN else 0 for trade in group]
                conditional += (len(group) / len(trades)) * self._entropy(group_outcomes)
            gain = base_entropy - conditional
            if gain <= 0:
                continue
            if best is None or gain > best[1]:
                best = (feature, gain, groups)
        return best

    def _clusters(self, trades: list[PatternTrade]) -> list[dict[str, Any]]:
        important = [
            "pair",
            "ema200_direction",
            "atr_bucket",
            "adx_bucket",
            "volume_state",
            "btc_regime",
            "duration_bucket",
        ]
        groups: dict[tuple[str, ...], list[PatternTrade]] = defaultdict(list)
        for trade in trades:
            signature = tuple(trade.features.get(feature, "UNKNOWN") for feature in important)
            groups[signature].append(trade)
        rows = []
        for index, (signature, group) in enumerate(groups.items(), start=1):
            if len(group) < 5:
                continue
            rows.append(
                {
                    "cluster_id": index,
                    "signature": dict(zip(important, signature, strict=False)),
                    **self._metrics(group),
                }
            )
        return sorted(rows, key=lambda row: abs(row["profit_total_abs"]), reverse=True)

    def _outliers(self, trades: list[PatternTrade]) -> dict[str, list[dict[str, Any]]]:
        if not trades:
            return {"large_winners": [], "large_losers": [], "duration_outliers": []}
        large_winners = sorted(trades, key=lambda trade: trade.profit_abs, reverse=True)[:25]
        large_losers = sorted(trades, key=lambda trade: trade.profit_abs)[:25]
        duration_outliers = sorted(trades, key=lambda trade: trade.duration_minutes, reverse=True)[:25]
        return {
            "large_winners": [self._trade_summary(trade) for trade in large_winners],
            "large_losers": [self._trade_summary(trade) for trade in large_losers],
            "duration_outliers": [self._trade_summary(trade) for trade in duration_outliers],
        }

    def _shap_values_when_possible(self, trades: list[PatternTrade]) -> dict[str, Any]:
        try:
            import numpy as np
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.inspection import permutation_importance
        except Exception:
            return {
                "available": False,
                "reason": "Optional ML dependencies are not available in this runtime.",
            }

        feature_names = sorted({key for trade in trades for key in trade.features})[:80]
        if len(trades) < 20 or not feature_names:
            return {"available": False, "reason": "Insufficient trades for optional ML importance."}
        categories = {
            feature: sorted({trade.features.get(feature, "UNKNOWN") for trade in trades})
            for feature in feature_names
        }
        encoded_names: list[str] = []
        matrix = []
        for trade in trades:
            row = []
            for feature in feature_names:
                values = categories[feature]
                current = trade.features.get(feature, "UNKNOWN")
                for value in values:
                    encoded_names.append(f"{feature}={value}") if not matrix else None
                    row.append(1.0 if current == value else 0.0)
            matrix.append(row)
        x = np.asarray(matrix)
        y = np.asarray([1 if trade.outcome == OUTCOME_WIN else 0 for trade in trades])
        if len(set(y.tolist())) < 2:
            return {"available": False, "reason": "Only one outcome class is present."}
        model = RandomForestClassifier(n_estimators=50, random_state=42, max_depth=5)
        model.fit(x, y)
        permutation = permutation_importance(model, x, y, n_repeats=3, random_state=42)
        importances = sorted(
            [
                {
                    "feature": encoded_names[index],
                    "importance": float(value),
                }
                for index, value in enumerate(permutation.importances_mean)
            ],
            key=lambda row: row["importance"],
            reverse=True,
        )
        return {
            "available": True,
            "method": "RandomForest permutation importance proxy; SHAP package was not required.",
            "values": importances[:50],
        }

    def _recommendations(
        self,
        *,
        trades: list[PatternTrade],
        rules: list[dict[str, Any]],
        importance: list[dict[str, Any]],
        clusters: list[dict[str, Any]],
        outliers: dict[str, list[dict[str, Any]]],
    ) -> list[str]:
        recommendations: list[str] = []
        win_rules = [rule for rule in rules if rule["then"] == OUTCOME_WIN]
        loss_rules = [rule for rule in rules if rule["then"] == OUTCOME_LOSS]
        if importance:
            recommendations.append(
                f"Condicao mais importante: {importance[0]['feature']} "
                f"(MI={importance[0]['mutual_information']:.5f})."
            )
        if win_rules:
            rule = win_rules[0]
            recommendations.append(
                "Maior causa de ganhos: "
                + " AND ".join(rule["if"])
                + f" -> P(lucro)={rule['probability_of_profit']:.2%}, "
                f"support={rule['support']:.2%}, lift={rule['lift']:.3f}."
            )
            recommendations.append(
                "Adicionar filtro candidato: exigir ou favorecer a combinacao "
                + " AND ".join(rule["if"])
                + "."
            )
        if loss_rules:
            rule = loss_rules[0]
            recommendations.append(
                "Maior causa de perdas: "
                + " AND ".join(rule["if"])
                + f" -> P(prejuizo)={rule['confidence']:.2%}, "
                f"support={rule['support']:.2%}, lift={rule['lift']:.3f}."
            )
            recommendations.append(
                "Remover filtro ou bloquear condicao candidata: evitar "
                + " AND ".join(rule["if"])
                + "."
            )
        if clusters:
            cluster = clusters[0]
            recommendations.append(
                "Cluster mais relevante por lucro absoluto: "
                + ", ".join(f"{k}={v}" for k, v in cluster["signature"].items())
                + f" (PF={cluster['profit_factor']:.3f}, trades={cluster['trades']})."
            )
        if outliers.get("large_losers"):
            loser = outliers["large_losers"][0]
            recommendations.append(
                "Investigar maior perda individual: "
                f"{loser['pair']} no experimento {loser['experiment_id']} "
                f"profit_abs={loser['profit_abs']:.3f}."
            )
        if not recommendations:
            recommendations.append("Amostra insuficiente para recomendacoes estatisticas confiaveis.")
        return recommendations

    def _class_characteristics(
        self,
        trades: list[PatternTrade],
        outcome: str,
        *,
        threshold: float,
    ) -> list[dict[str, Any]]:
        class_trades = [trade for trade in trades if trade.outcome == outcome]
        if not class_trades:
            return []
        counter: Counter[str] = Counter()
        for trade in class_trades:
            counter.update(trade.transaction)
        rows = [
            {
                "item": item,
                "count": count,
                "class_support": count / len(class_trades),
                "threshold": threshold,
            }
            for item, count in counter.items()
            if count / len(class_trades) >= threshold
        ]
        return sorted(rows, key=lambda row: row["class_support"], reverse=True)

    def _metrics(self, trades: list[PatternTrade]) -> dict[str, Any]:
        profits = [trade.profit_abs for trade in trades]
        ratios = [trade.profit_ratio for trade in trades]
        gross_profit = sum(value for value in profits if value > 0)
        gross_loss = abs(sum(value for value in profits if value < 0))
        wins = sum(1 for value in profits if value > 0)
        losses = sum(1 for value in profits if value < 0)
        return {
            "trades": len(trades),
            "wins": wins,
            "losses": losses,
            "profit_total_abs": sum(profits),
            "gross_profit_abs": gross_profit,
            "gross_loss_abs": gross_loss,
            "profit_factor": gross_profit / gross_loss if gross_loss else (999.0 if gross_profit else 0.0),
            "expectancy": statistics.mean(profits) if profits else 0.0,
            "sharpe": self._sharpe(ratios),
            "drawdown_proxy": sum(max(0.0, -value) for value in profits),
            "win_rate": wins / len(trades) if trades else 0.0,
            "avg_duration_minutes": statistics.mean([trade.duration_minutes for trade in trades]) if trades else 0.0,
        }

    def _chart_payload(
        self,
        *,
        feature_importance: list[dict[str, Any]],
        tree: dict[str, Any],
        clusters: list[dict[str, Any]],
        rules: list[dict[str, Any]],
        trades: list[PatternTrade],
    ) -> dict[str, Any]:
        return {
            "feature_importance": feature_importance,
            "decision_tree": tree,
            "clusters": clusters,
            "trade_embedding": self._trade_embedding(trades),
            "heatmaps": self._heatmaps(trades),
            "association_graph": self._association_graph(rules),
        }

    def _trade_embedding(self, trades: list[PatternTrade]) -> list[dict[str, Any]]:
        points = []
        for index, trade in enumerate(trades[:5000]):
            points.append(
                {
                    "x": trade.profit_ratio,
                    "y": trade.duration_minutes,
                    "outcome": trade.outcome,
                    "pair": trade.pair,
                    "experiment_id": trade.experiment_id,
                    "index": index,
                }
            )
        return points

    def _heatmaps(self, trades: list[PatternTrade]) -> dict[str, list[dict[str, Any]]]:
        heatmaps: dict[str, list[dict[str, Any]]] = {}
        pairs = [
            ("pair", "hour_session"),
            ("adx_bucket", "atr_bucket"),
            ("ema200_direction", "volume_state"),
            ("btc_regime", "pair"),
        ]
        for left, right in pairs:
            groups: dict[tuple[str, str], list[PatternTrade]] = defaultdict(list)
            for trade in trades:
                groups[
                    (
                        trade.features.get(left, "UNKNOWN"),
                        trade.features.get(right, "UNKNOWN"),
                    )
                ].append(trade)
            heatmaps[f"{left}__{right}"] = [
                {
                    "x": key[0],
                    "y": key[1],
                    **self._metrics(group),
                }
                for key, group in groups.items()
                if len(group) >= 3
            ]
        return heatmaps

    def _association_graph(self, rules: list[dict[str, Any]]) -> dict[str, Any]:
        nodes: dict[str, dict[str, Any]] = {}
        edges = []
        for index, rule in enumerate(rules[:100]):
            outcome = rule["then"]
            nodes.setdefault(outcome, {"id": outcome, "kind": "outcome"})
            for item in rule["if"]:
                nodes.setdefault(item, {"id": item, "kind": "condition"})
                edges.append(
                    {
                        "source": item,
                        "target": outcome,
                        "confidence": rule["confidence"],
                        "lift": rule["lift"],
                        "rule_index": index,
                    }
                )
        return {"nodes": list(nodes.values()), "edges": edges}

    def _write_reports(self, report: dict[str, Any]) -> dict[str, Path]:
        stem = self._stem(report)
        json_path = self.output_dir / f"{stem}.json"
        markdown_path = self.output_dir / f"{stem}.md"
        html_path = self.output_dir / f"{stem}.html"
        json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        markdown_path.write_text(self._markdown(report), encoding="utf-8")
        html_path.write_text(self._html(report), encoding="utf-8")
        return {"json": json_path, "markdown": markdown_path, "html": html_path}

    def _write_trade_csv(
        self,
        report: dict[str, Any],
        trades: list[PatternTrade],
    ) -> Path:
        path = self.output_dir / f"{self._stem(report)}_trades.csv"
        feature_names = sorted({key for trade in trades for key in trade.features})
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "experiment_id",
                    "pair",
                    "outcome",
                    "profit_abs",
                    "profit_ratio",
                    "duration_minutes",
                    "drawdown_proxy",
                    *feature_names,
                ],
            )
            writer.writeheader()
            for trade in trades:
                writer.writerow(
                    {
                        "experiment_id": trade.experiment_id,
                        "pair": trade.pair,
                        "outcome": trade.outcome,
                        "profit_abs": trade.profit_abs,
                        "profit_ratio": trade.profit_ratio,
                        "duration_minutes": trade.duration_minutes,
                        "drawdown_proxy": trade.drawdown_proxy,
                        **{feature: trade.features.get(feature, "") for feature in feature_names},
                    }
                )
        return path

    def _markdown(self, report: dict[str, Any]) -> str:
        lines = [
            f"# Trade Pattern Discovery - {report['session_id']}",
            "",
            "## Summary",
            f"- Trades: {report['trade_count']}",
            f"- Wins: {report['overall']['wins']}",
            f"- Losses: {report['overall']['losses']}",
            f"- Profit Factor: {report['overall']['profit_factor']:.3f}",
            f"- Net Profit: {report['overall']['profit_total_abs']:.3f}",
            "",
            "## Feature Importance",
            "| Feature | MI | Info Gain | Permutation | Importance |",
            "|---|---:|---:|---:|---:|",
        ]
        for row in report["feature_importance"][:30]:
            lines.append(
                f"| {row['feature']} | {row['mutual_information']:.5f} | "
                f"{row['information_gain']:.5f} | {row['permutation_importance']:.5f} | "
                f"{row['feature_importance']:.5f} |"
            )
        lines.extend(["", "## 80 Percent Winner Characteristics"])
        for row in report["winning_characteristics_80pct"][:50]:
            lines.append(f"- {row['item']}: {row['class_support']:.2%}")
        lines.extend(["", "## 80 Percent Loser Characteristics"])
        for row in report["losing_characteristics_80pct"][:50]:
            lines.append(f"- {row['item']}: {row['class_support']:.2%}")
        lines.extend(["", "## Association Rules"])
        lines.append("| IF | THEN | Support | Confidence | Lift | P(profit) | PF | Trades |")
        lines.append("|---|---|---:|---:|---:|---:|---:|---:|")
        for rule in report["association_rules"][:50]:
            lines.append(
                f"| {' AND '.join(rule['if'])} | {rule['then']} | "
                f"{rule['support']:.2%} | {rule['confidence']:.2%} | "
                f"{rule['lift']:.3f} | {rule['probability_of_profit']:.2%} | "
                f"{rule['profit_factor']:.3f} | {rule['trades']} |"
            )
        lines.extend(["", "## Clusters"])
        lines.append("| Cluster | Trades | PF | Win Rate | Profit | Signature |")
        lines.append("|---:|---:|---:|---:|---:|---|")
        for cluster in report["clusters"][:30]:
            signature = ", ".join(f"{key}={value}" for key, value in cluster["signature"].items())
            lines.append(
                f"| {cluster['cluster_id']} | {cluster['trades']} | "
                f"{cluster['profit_factor']:.3f} | {cluster['win_rate']:.2%} | "
                f"{cluster['profit_total_abs']:.3f} | {signature} |"
            )
        lines.extend(["", "## Recommendations"])
        for item in report["recommendations"]:
            lines.append(f"- {item}")
        lines.extend(["", "## Notes"])
        for note in report["notes"]:
            lines.append(f"- {note}")
        return "\n".join(lines) + "\n"

    def _html(self, report: dict[str, Any]) -> str:
        markdown = self._markdown(report)
        return (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<title>Trade Pattern Discovery</title>"
            "<style>body{font-family:Arial,sans-serif;margin:32px;line-height:1.45;color:#1f2937}"
            "pre{white-space:pre-wrap;background:#f6f8fa;padding:16px;border-radius:6px}"
            "h1,h2{color:#111827}</style></head><body>"
            "<h1>Trade Pattern Discovery</h1>"
            f"<p><strong>Session:</strong> {html.escape(report['session_id'])}</p>"
            f"<pre>{html.escape(markdown)}</pre>"
            "</body></html>"
        )

    def _stem(self, report: dict[str, Any]) -> str:
        parts = ["trade_pattern_discovery", report["session_id"]]
        if report.get("strategy"):
            parts.append(self._slug(str(report["strategy"])))
        if report.get("experiment_id"):
            parts.append(self._slug(str(report["experiment_id"])))
        return "_".join(parts)

    def _trade_summary(self, trade: PatternTrade) -> dict[str, Any]:
        return {
            "experiment_id": trade.experiment_id,
            "pair": trade.pair,
            "outcome": trade.outcome,
            "profit_abs": trade.profit_abs,
            "profit_ratio": trade.profit_ratio,
            "duration_minutes": trade.duration_minutes,
            "top_features": sorted(trade.transaction)[:20],
        }

    def _transaction(self, features: dict[str, str]) -> frozenset[str]:
        return frozenset(
            f"{key}={value}"
            for key, value in features.items()
            if value not in {"", "UNKNOWN", "nan", "None"}
        )

    def _flatten(self, value: dict[str, Any], prefix: str = "") -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in value.items():
            name = f"{prefix}_{key}" if prefix else str(key)
            if isinstance(item, dict):
                result.update(self._flatten(item, name))
            else:
                result[name] = item
        return result

    def _duration_bucket(self, minutes: float) -> str:
        if minutes < 30:
            return "DURATION_VERY_SHORT"
        if minutes < 180:
            return "DURATION_SHORT"
        if minutes < 720:
            return "DURATION_MEDIUM"
        if minutes < 1440:
            return "DURATION_LONG"
        return "DURATION_VERY_LONG"

    def _profit_ratio_bucket(self, value: float) -> str:
        if value < -0.03:
            return "LOSS_LARGE"
        if value < 0:
            return "LOSS_SMALL"
        if value < 0.005:
            return "WIN_SMALL"
        if value < 0.02:
            return "WIN_MEDIUM"
        return "WIN_LARGE"

    def _stake_bucket(self, value: float) -> str:
        if value <= 0:
            return "STAKE_UNKNOWN"
        if value < 20:
            return "STAKE_LOW"
        if value < 50:
            return "STAKE_MEDIUM"
        return "STAKE_HIGH"

    def _numeric_param_bucket(self, key: str, value: float) -> str:
        key_lower = key.lower()
        if "stoploss" in key_lower:
            if value <= -0.08:
                return "STOPLOSS_WIDE"
            if value <= -0.04:
                return "STOPLOSS_MEDIUM"
            return "STOPLOSS_TIGHT"
        if "roi" in key_lower:
            if value < 0.01:
                return "ROI_LOW"
            if value < 0.03:
                return "ROI_MEDIUM"
            return "ROI_HIGH"
        if "weight" in key_lower or "threshold" in key_lower or "multiplier" in key_lower:
            if value < 1:
                return "LOW"
            if value < 3:
                return "MEDIUM"
            return "HIGH"
        if value < 10:
            return "LOW"
        if value < 50:
            return "MEDIUM"
        return "HIGH"

    def _mutual_information(self, x: list[str], y: list[int]) -> float:
        if not x or not y or len(x) != len(y):
            return 0.0
        total = len(x)
        joint = Counter(zip(x, y, strict=False))
        x_count = Counter(x)
        y_count = Counter(y)
        score = 0.0
        for (x_value, y_value), count in joint.items():
            pxy = count / total
            px = x_count[x_value] / total
            py = y_count[y_value] / total
            if pxy > 0 and px > 0 and py > 0:
                score += pxy * math.log2(pxy / (px * py))
        return score

    def _information_gain(self, x: list[str], y: list[int]) -> float:
        if not x or not y or len(x) != len(y):
            return 0.0
        base = self._entropy(y)
        groups: dict[str, list[int]] = defaultdict(list)
        for x_value, y_value in zip(x, y, strict=False):
            groups[x_value].append(y_value)
        conditional = sum((len(group) / len(y)) * self._entropy(group) for group in groups.values())
        return base - conditional

    def _entropy(self, values: list[int]) -> float:
        if not values:
            return 0.0
        total = len(values)
        score = 0.0
        for count in Counter(values).values():
            probability = count / total
            if probability > 0:
                score -= probability * math.log2(probability)
        return score

    def _profit_separation(self, x: list[str], profits: list[float]) -> float:
        if not x or not profits or len(x) != len(profits):
            return 0.0
        overall = statistics.mean(profits)
        groups: dict[str, list[float]] = defaultdict(list)
        for value, profit in zip(x, profits, strict=False):
            groups[value].append(profit)
        return sum(
            (len(group) / len(profits)) * abs(statistics.mean(group) - overall)
            for group in groups.values()
        )

    def _permutation_importance(
        self,
        x: list[str],
        profits: list[float],
        baseline: float,
    ) -> float:
        if len(x) < 2 or baseline <= 0:
            return 0.0
        rotated = x[1:] + x[:1]
        return baseline - self._profit_separation(rotated, profits)

    def _sharpe(self, ratios: list[float]) -> float:
        if len(ratios) < 2:
            return 0.0
        std = statistics.pstdev(ratios)
        if std == 0:
            return 0.0
        return math.sqrt(len(ratios)) * statistics.mean(ratios) / std

    def _number(self, value: Any) -> float:
        try:
            if value is None:
                return 0.0
            result = float(value)
            if math.isnan(result) or math.isinf(result):
                return 0.0
            return result
        except (TypeError, ValueError):
            return 0.0

    def _slug(self, value: str) -> str:
        return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value).strip("_")


def command_analyze(args: argparse.Namespace) -> dict[str, str]:
    discovery = TradePatternDiscovery(
        db_path=args.db_path,
        output_dir=args.output_dir,
        project_root=args.project_root,
        timeframe=args.timeframe,
    )
    paths = discovery.analyze(
        session_id=args.session_id,
        strategy=args.strategy,
        experiment_id=args.experiment_id,
        trades_csv=args.trades_csv,
        min_support=args.min_support,
        min_confidence=args.min_confidence,
        max_itemset_size=args.max_itemset_size,
        export_csv=args.export_csv,
    )
    return {key: str(path.resolve()) for key, path in paths.items()}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Discover patterns in existing winning and losing trades without running backtests.",
    )
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--timeframe", default="5m")

    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser("analyze", help="Generate pattern discovery reports.")
    analyze.add_argument("session_id")
    analyze.add_argument("--strategy")
    analyze.add_argument("--experiment-id")
    analyze.add_argument("--trades-csv", type=Path)
    analyze.add_argument("--min-support", type=float, default=0.05)
    analyze.add_argument("--min-confidence", type=float, default=0.6)
    analyze.add_argument("--max-itemset-size", type=int, default=3)
    analyze.add_argument("--export-csv", action="store_true")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "analyze":
        result = command_analyze(args)
    else:
        parser.error("Unknown command.")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
