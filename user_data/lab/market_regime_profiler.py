from __future__ import annotations

import argparse
import csv
import html
import json
import math
import sqlite3
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any
from zipfile import ZipFile

try:
    from .experiment_database import DEFAULT_DB_PATH, ExperimentDatabase
except ImportError:
    from experiment_database import DEFAULT_DB_PATH, ExperimentDatabase


DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent
DEFAULT_TIMEFRAME = "5m"
PROFIT_FIELD = "profit_abs"
REGIME_FEATURES = [
    "ema200_direction",
    "ema200_distance_bucket",
    "ema200_slope_bucket",
    "atr_bucket",
    "adx_bucket",
    "breakout_state",
    "volume_state",
    "hour_session",
    "weekday",
    "btc_regime",
]


@dataclass(frozen=True)
class TradeRecord:
    experiment_id: str
    session_id: str | None
    strategy_name: str
    pair: str
    open_date: datetime | None
    close_date: datetime | None
    profit_abs: float
    profit_ratio: float
    duration_minutes: float
    stake_amount: float
    enter_tag: str
    exit_reason: str
    regimes: dict[str, str]


class MarketRegimeProfiler:
    """Offline profiler for regime performance using completed lab artifacts."""

    def __init__(
        self,
        *,
        db_path: Path | str = DEFAULT_DB_PATH,
        output_dir: Path | str = DEFAULT_OUTPUT_DIR,
        project_root: Path | str | None = None,
        timeframe: str = DEFAULT_TIMEFRAME,
    ) -> None:
        self.database = ExperimentDatabase(db_path)
        self.db_path = Path(db_path)
        self.output_dir = Path(output_dir)
        self.project_root = Path(project_root or Path(__file__).resolve().parents[2])
        self.user_data_dir = self.project_root / "user_data"
        self.timeframe = timeframe
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def analyze(
        self,
        *,
        session_id: str,
        strategy: str | None = None,
        experiment_id: str | None = None,
        min_trades: int = 5,
    ) -> dict[str, Path]:
        experiments = self._load_experiments(
            session_id=session_id,
            strategy=strategy,
            experiment_id=experiment_id,
        )
        trades = self._load_trades(experiments, session_id=session_id)
        report = self._build_report(
            session_id=session_id,
            strategy=strategy,
            experiment_id=experiment_id,
            experiments=experiments,
            trades=trades,
            min_trades=min_trades,
        )
        return self._write_reports(report)

    def _load_experiments(
        self,
        *,
        session_id: str,
        strategy: str | None,
        experiment_id: str | None,
    ) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            query = """
                select e.*
                from session_experiments se
                join experiments e on e.id = se.experiment_id
                where se.session_id = ?
                  and e.status = 'completed'
            """
            params: list[Any] = [session_id]
            if experiment_id:
                query += " and e.id = ?"
                params.append(experiment_id)
            if strategy:
                query += " and (e.strategy_name = ? or e.parameters_json like ?)"
                params.extend([strategy, f"%{strategy}%"])
            query += " order by e.created_at asc"
            rows = connection.execute(query, params).fetchall()

        experiments = [self._row_to_experiment(row) for row in rows]
        if not experiments:
            raise ValueError("No completed experiments matched the requested inputs.")
        return experiments

    def _row_to_experiment(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "strategy_name": row["strategy_name"],
            "parameters": self._loads(row["parameters_json"], {}),
            "metrics": self._loads(row["metrics_json"], {}),
            "result_path": row["result_path"],
            "runtime_seconds": row["runtime_seconds"],
            "score": row["score"],
        }

    def _load_trades(
        self,
        experiments: list[dict[str, Any]],
        *,
        session_id: str,
    ) -> list[TradeRecord]:
        indicator_cache = IndicatorCache(self.project_root, timeframe=self.timeframe)
        trades: list[TradeRecord] = []

        for experiment in experiments:
            result_path = self._host_path(experiment.get("result_path"))
            raw_trades = self._extract_trades(result_path, experiment["strategy_name"])
            for raw in raw_trades:
                pair = str(raw.get("pair", "UNKNOWN"))
                open_date = self._parse_datetime(raw.get("open_date"))
                close_date = self._parse_datetime(raw.get("close_date"))
                regimes = indicator_cache.classify(pair, open_date)
                regimes.update(
                    {
                        "hour_session": self._hour_session(open_date),
                        "weekday": self._weekday(open_date),
                    }
                )
                trades.append(
                    TradeRecord(
                        experiment_id=experiment["id"],
                        session_id=session_id,
                        strategy_name=experiment["strategy_name"],
                        pair=pair,
                        open_date=open_date,
                        close_date=close_date,
                        profit_abs=self._number(raw.get("profit_abs")),
                        profit_ratio=self._number(raw.get("profit_ratio")),
                        duration_minutes=self._number(raw.get("trade_duration")),
                        stake_amount=self._number(raw.get("stake_amount")),
                        enter_tag=str(raw.get("enter_tag") or ""),
                        exit_reason=str(raw.get("exit_reason") or ""),
                        regimes=regimes,
                    )
                )
        return trades

    def _extract_trades(
        self,
        result_path: Path | None,
        strategy_name: str,
    ) -> list[dict[str, Any]]:
        if result_path is None or not result_path.exists():
            return []
        result = self._load_result_json(result_path)
        strategies = result.get("strategy", {})
        strategy = strategies.get(strategy_name)
        if strategy is None and len(strategies) == 1:
            strategy = next(iter(strategies.values()))
        if not strategy:
            return []
        trades = strategy.get("trades", [])
        return trades if isinstance(trades, list) else []

    def _load_result_json(self, result_path: Path) -> dict[str, Any]:
        if result_path.suffix == ".json":
            return self._loads(result_path.read_text(encoding="utf-8"), {})
        with ZipFile(result_path) as archive:
            result_names = [
                name
                for name in archive.namelist()
                if name.endswith(".json") and not name.endswith("_config.json")
            ]
            for name in result_names:
                parsed = json.loads(archive.read(name))
                if isinstance(parsed, dict) and "strategy" in parsed:
                    return parsed
        return {}

    def _build_report(
        self,
        *,
        session_id: str,
        strategy: str | None,
        experiment_id: str | None,
        experiments: list[dict[str, Any]],
        trades: list[TradeRecord],
        min_trades: int,
    ) -> dict[str, Any]:
        regime_metrics = self._regime_metrics(trades, min_trades=min_trades)
        interactions = self._interaction_metrics(trades, min_trades=min_trades)
        importance = self._feature_importance(trades)
        clusters = self._cluster_trades(trades, min_trades=min_trades)
        recommendations = self._recommendations(
            trades=trades,
            regime_metrics=regime_metrics,
            interactions=interactions,
            importance=importance,
        )

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "strategy": strategy,
            "experiment_id": experiment_id,
            "experiment_count": len(experiments),
            "trade_count": len(trades),
            "timeframe": self.timeframe,
            "coverage": self._coverage(trades),
            "overall": self._metrics_for_trades(trades),
            "regime_metrics": regime_metrics,
            "interactions": interactions[:100],
            "importance": importance,
            "clusters": clusters,
            "charts": self._chart_payload(regime_metrics, interactions, importance, clusters),
            "recommendations": recommendations,
            "notes": [
                "This profiler is read-only and uses completed experiments plus existing OHLCV data.",
                "Feature importance is statistical evidence, not an automatic trading rule.",
                "If OHLCV libraries are unavailable, unavailable regimes are marked as UNKNOWN.",
            ],
        }

    def _regime_metrics(
        self,
        trades: list[TradeRecord],
        *,
        min_trades: int,
    ) -> dict[str, list[dict[str, Any]]]:
        result: dict[str, list[dict[str, Any]]] = {}
        for feature in REGIME_FEATURES:
            groups: dict[str, list[TradeRecord]] = defaultdict(list)
            for trade in trades:
                groups[trade.regimes.get(feature, "UNKNOWN")].append(trade)
            rows = []
            for value, group in groups.items():
                if len(group) < min_trades and value != "UNKNOWN":
                    continue
                metrics = self._metrics_for_trades(group)
                metrics.update({"feature": feature, "value": value})
                rows.append(metrics)
            result[feature] = sorted(
                rows,
                key=lambda row: (row["profit_total_abs"], row["trades"]),
                reverse=True,
            )
        return result

    def _interaction_metrics(
        self,
        trades: list[TradeRecord],
        *,
        min_trades: int,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for left, right in combinations(REGIME_FEATURES, 2):
            groups: dict[tuple[str, str], list[TradeRecord]] = defaultdict(list)
            for trade in trades:
                groups[
                    (
                        trade.regimes.get(left, "UNKNOWN"),
                        trade.regimes.get(right, "UNKNOWN"),
                    )
                ].append(trade)
            for (left_value, right_value), group in groups.items():
                if len(group) < min_trades:
                    continue
                metrics = self._metrics_for_trades(group)
                metrics.update(
                    {
                        "features": [left, right],
                        "values": [left_value, right_value],
                        "label": f"{left}={left_value} + {right}={right_value}",
                    }
                )
                rows.append(metrics)
        return sorted(rows, key=lambda row: abs(row["profit_total_abs"]), reverse=True)

    def _feature_importance(self, trades: list[TradeRecord]) -> list[dict[str, Any]]:
        y = [1 if trade.profit_abs > 0 else 0 for trade in trades]
        total_profit = [trade.profit_abs for trade in trades]
        rows = []
        for feature in REGIME_FEATURES:
            x = [trade.regimes.get(feature, "UNKNOWN") for trade in trades]
            mutual_information = self._mutual_information(x, y)
            information_gain = self._information_gain(x, y)
            feature_score = self._feature_profit_separation(x, total_profit)
            permutation_score = self._permutation_drop(x, total_profit, feature_score)
            rows.append(
                {
                    "feature": feature,
                    "mutual_information": mutual_information,
                    "information_gain": information_gain,
                    "permutation_importance": permutation_score,
                    "feature_importance": (
                        mutual_information
                        + information_gain
                        + max(0.0, permutation_score)
                        + feature_score
                    )
                    / 4.0,
                }
            )
        return sorted(rows, key=lambda row: row["feature_importance"], reverse=True)

    def _cluster_trades(
        self,
        trades: list[TradeRecord],
        *,
        min_trades: int,
    ) -> list[dict[str, Any]]:
        signatures: dict[tuple[str, ...], list[TradeRecord]] = defaultdict(list)
        cluster_features = [
            "ema200_direction",
            "atr_bucket",
            "adx_bucket",
            "breakout_state",
            "volume_state",
            "btc_regime",
        ]
        for trade in trades:
            signature = tuple(trade.regimes.get(feature, "UNKNOWN") for feature in cluster_features)
            signatures[signature].append(trade)

        clusters = []
        for index, (signature, group) in enumerate(signatures.items(), start=1):
            if len(group) < min_trades:
                continue
            metrics = self._metrics_for_trades(group)
            metrics.update(
                {
                    "cluster_id": index,
                    "signature": dict(zip(cluster_features, signature, strict=False)),
                }
            )
            clusters.append(metrics)
        return sorted(clusters, key=lambda row: row["profit_factor"], reverse=True)

    def _recommendations(
        self,
        *,
        trades: list[TradeRecord],
        regime_metrics: dict[str, list[dict[str, Any]]],
        interactions: list[dict[str, Any]],
        importance: list[dict[str, Any]],
    ) -> list[str]:
        recommendations: list[str] = []
        profitable = [
            row
            for rows in regime_metrics.values()
            for row in rows
            if row["trades"] >= 5 and row["profit_total_abs"] > 0
        ]
        harmful = [
            row
            for rows in regime_metrics.values()
            for row in rows
            if row["trades"] >= 5 and row["profit_total_abs"] < 0
        ]
        profitable.sort(key=lambda row: row["profit_total_abs"], reverse=True)
        harmful.sort(key=lambda row: row["profit_total_abs"])

        if profitable:
            top = profitable[0]
            recommendations.append(
                "Esta estrategia funciona melhor quando "
                f"{top['feature']}={top['value']} "
                f"(PF={top['profit_factor']:.3f}, trades={top['trades']})."
            )
        if harmful:
            worst = harmful[0]
            recommendations.append(
                "Evitar operar quando "
                f"{worst['feature']}={worst['value']} "
                f"(lucro liquido={worst['profit_total_abs']:.3f})."
            )

        total_positive = sum(max(0.0, trade.profit_abs) for trade in trades)
        if total_positive > 0:
            running = 0.0
            contributors = []
            for row in profitable:
                running += max(0.0, row["profit_total_abs"])
                contributors.append(f"{row['feature']}={row['value']}")
                if running / total_positive >= 0.8:
                    break
            if contributors:
                recommendations.append(
                    "80% do lucro bruto positivo se concentra em: "
                    + ", ".join(contributors[:8])
                    + "."
                )

        total_drawdown = self._metrics_for_trades(trades)["max_drawdown_abs"]
        if total_drawdown > 0 and harmful:
            drawdown_sources = [
                f"{row['feature']}={row['value']}"
                for row in sorted(harmful, key=lambda item: item["max_drawdown_abs"], reverse=True)
               [:8]
            ]
            recommendations.append(
                "80% do drawdown deve ser investigado primeiro nestes regimes: "
                + ", ".join(drawdown_sources)
                + "."
            )

        if importance:
            top_feature = importance[0]["feature"]
            recommendations.append(
                f"Sugestao de filtro: testar manualmente restricoes baseadas em {top_feature}, "
                "pois foi o regime com maior importancia estatistica."
            )
        if interactions:
            top_interaction = interactions[0]
            recommendations.append(
                "Sugestao de regime combinado: "
                f"{top_interaction['label']} "
                f"(PF={top_interaction['profit_factor']:.3f}, trades={top_interaction['trades']})."
            )
        return recommendations

    def _metrics_for_trades(self, trades: list[TradeRecord]) -> dict[str, Any]:
        profits = [trade.profit_abs for trade in trades]
        ratios = [trade.profit_ratio for trade in trades]
        gross_profit = sum(value for value in profits if value > 0)
        gross_loss = abs(sum(value for value in profits if value < 0))
        wins = sum(1 for value in profits if value > 0)
        losses = sum(1 for value in profits if value < 0)
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else (0.0 if gross_profit == 0 else 999.0)
        expectancy = statistics.mean(profits) if profits else 0.0
        sharpe = self._sharpe(ratios)
        drawdown = self._max_drawdown(profits)
        avg_duration = statistics.mean([trade.duration_minutes for trade in trades]) if trades else 0.0
        return {
            "trades": len(trades),
            "wins": wins,
            "losses": losses,
            "profit_total_abs": sum(profits),
            "gross_profit_abs": gross_profit,
            "gross_loss_abs": gross_loss,
            "profit_factor": profit_factor,
            "sharpe": sharpe,
            "expectancy": expectancy,
            "max_drawdown_abs": drawdown,
            "win_rate": wins / len(trades) if trades else 0.0,
            "avg_duration_minutes": avg_duration,
            "profit_contribution": 0.0,
            "drawdown_contribution": 0.0,
        }

    def _coverage(self, trades: list[TradeRecord]) -> dict[str, Any]:
        total = len(trades)
        return {
            feature: {
                "known": sum(1 for trade in trades if trade.regimes.get(feature) != "UNKNOWN"),
                "total": total,
                "known_ratio": (
                    sum(1 for trade in trades if trade.regimes.get(feature) != "UNKNOWN") / total
                    if total
                    else 0.0
                ),
            }
            for feature in REGIME_FEATURES
        }

    def _chart_payload(
        self,
        regime_metrics: dict[str, list[dict[str, Any]]],
        interactions: list[dict[str, Any]],
        importance: list[dict[str, Any]],
        clusters: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "distribution_by_regime": {
                feature: [
                    {"label": row["value"], "trades": row["trades"]}
                    for row in rows
                ]
                for feature, rows in regime_metrics.items()
            },
            "profit_by_regime": {
                feature: [
                    {"label": row["value"], "profit_total_abs": row["profit_total_abs"]}
                    for row in rows
                ]
                for feature, rows in regime_metrics.items()
            },
            "drawdown_by_regime": {
                feature: [
                    {"label": row["value"], "max_drawdown_abs": row["max_drawdown_abs"]}
                    for row in rows
                ]
                for feature, rows in regime_metrics.items()
            },
            "heatmaps": interactions[:50],
            "decision_tree": self._decision_tree_payload(regime_metrics, importance),
            "feature_importance": importance,
            "cluster_visualization": clusters,
        }

    def _decision_tree_payload(
        self,
        regime_metrics: dict[str, list[dict[str, Any]]],
        importance: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not importance:
            return {}
        root = importance[0]["feature"]
        rows = regime_metrics.get(root, [])
        return {
            "root_feature": root,
            "branches": [
                {
                    "condition": f"{root}={row['value']}",
                    "profit_factor": row["profit_factor"],
                    "trades": row["trades"],
                    "profit_total_abs": row["profit_total_abs"],
                }
                for row in rows
            ],
        }

    def _write_reports(self, report: dict[str, Any]) -> dict[str, Path]:
        stem = self._report_stem(report)
        json_path = self.output_dir / f"{stem}.json"
        markdown_path = self.output_dir / f"{stem}.md"
        html_path = self.output_dir / f"{stem}.html"

        json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        markdown_path.write_text(self._markdown(report), encoding="utf-8")
        html_path.write_text(self._html(report), encoding="utf-8")
        return {"json": json_path, "markdown": markdown_path, "html": html_path}

    def _report_stem(self, report: dict[str, Any]) -> str:
        parts = ["market_regime_profile", report["session_id"]]
        if report.get("strategy"):
            parts.append(self._slug(str(report["strategy"])))
        if report.get("experiment_id"):
            parts.append(self._slug(str(report["experiment_id"])))
        return "_".join(parts)

    def _markdown(self, report: dict[str, Any]) -> str:
        lines = [
            f"# Market Regime Profile - {report['session_id']}",
            "",
            "## Summary",
            f"- Experiments: {report['experiment_count']}",
            f"- Trades: {report['trade_count']}",
            f"- Timeframe: {report['timeframe']}",
            f"- Overall PF: {report['overall']['profit_factor']:.3f}",
            f"- Overall profit: {report['overall']['profit_total_abs']:.3f}",
            "",
            "## Feature Importance",
            "| Feature | Mutual Information | Information Gain | Permutation | Importance |",
            "|---|---:|---:|---:|---:|",
        ]
        for row in report["importance"]:
            lines.append(
                "| {feature} | {mutual_information:.5f} | {information_gain:.5f} | "
                "{permutation_importance:.5f} | {feature_importance:.5f} |".format(**row)
            )

        lines.extend(["", "## Best Regimes"])
        for feature, rows in report["regime_metrics"].items():
            lines.append(f"### {feature}")
            lines.append("| Value | Trades | PF | Sharpe | Expectancy | Drawdown | Win Rate | Profit |")
            lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
            for row in rows[:10]:
                lines.append(
                    f"| {row['value']} | {row['trades']} | {row['profit_factor']:.3f} | "
                    f"{row['sharpe']:.3f} | {row['expectancy']:.3f} | "
                    f"{row['max_drawdown_abs']:.3f} | {row['win_rate']:.3f} | "
                    f"{row['profit_total_abs']:.3f} |"
                )

        lines.extend(["", "## Top Interactions"])
        lines.append("| Interaction | Trades | PF | Drawdown | Expectancy | Profit |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for row in report["interactions"][:25]:
            lines.append(
                f"| {row['label']} | {row['trades']} | {row['profit_factor']:.3f} | "
                f"{row['max_drawdown_abs']:.3f} | {row['expectancy']:.3f} | "
                f"{row['profit_total_abs']:.3f} |"
            )

        lines.extend(["", "## Clusters"])
        lines.append("| Cluster | Trades | PF | Sharpe | Drawdown | Expectancy | Signature |")
        lines.append("|---:|---:|---:|---:|---:|---:|---|")
        for row in report["clusters"][:25]:
            signature = ", ".join(f"{key}={value}" for key, value in row["signature"].items())
            lines.append(
                f"| {row['cluster_id']} | {row['trades']} | {row['profit_factor']:.3f} | "
                f"{row['sharpe']:.3f} | {row['max_drawdown_abs']:.3f} | "
                f"{row['expectancy']:.3f} | {signature} |"
            )

        lines.extend(["", "## Recommendations"])
        for recommendation in report["recommendations"]:
            lines.append(f"- {recommendation}")
        lines.extend(["", "## Notes"])
        for note in report["notes"]:
            lines.append(f"- {note}")
        return "\n".join(lines) + "\n"

    def _html(self, report: dict[str, Any]) -> str:
        markdown = self._markdown(report)
        return (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<title>Market Regime Profile</title>"
            "<style>body{font-family:Arial,sans-serif;margin:32px;line-height:1.45;color:#1f2937}"
            "pre{white-space:pre-wrap;background:#f6f8fa;padding:16px;border-radius:6px}"
            "h1,h2,h3{color:#111827}</style></head><body>"
            "<h1>Market Regime Profile</h1>"
            f"<p><strong>Session:</strong> {html.escape(report['session_id'])}</p>"
            f"<pre>{html.escape(markdown)}</pre>"
            "</body></html>"
        )

    def _host_path(self, raw_path: str | None) -> Path | None:
        if not raw_path:
            return None
        path = Path(raw_path)
        if path.exists():
            return path
        raw = str(raw_path).replace("\\", "/")
        if raw.startswith("/freqtrade/"):
            mapped = self.project_root / raw.removeprefix("/freqtrade/")
            if mapped.exists():
                return mapped
        return path

    def _hour_session(self, value: datetime | None) -> str:
        if value is None:
            return "UNKNOWN"
        hour = value.hour
        if 0 <= hour < 8:
            return "ASIA"
        if 8 <= hour < 13:
            return "LONDON"
        if 13 <= hour < 21:
            return "NY"
        return "AFTER_HOURS"

    def _weekday(self, value: datetime | None) -> str:
        if value is None:
            return "UNKNOWN"
        return ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"][value.weekday()]

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

    def _feature_profit_separation(self, x: list[str], profits: list[float]) -> float:
        if not x or not profits or len(x) != len(profits):
            return 0.0
        overall = statistics.mean(profits) if profits else 0.0
        groups: dict[str, list[float]] = defaultdict(list)
        for feature_value, profit in zip(x, profits, strict=False):
            groups[feature_value].append(profit)
        return sum(
            (len(group) / len(profits)) * abs(statistics.mean(group) - overall)
            for group in groups.values()
        )

    def _permutation_drop(
        self,
        x: list[str],
        profits: list[float],
        baseline_score: float,
    ) -> float:
        if len(x) < 2 or baseline_score <= 0:
            return 0.0
        rotated = x[1:] + x[:1]
        permuted = self._feature_profit_separation(rotated, profits)
        return baseline_score - permuted

    def _entropy(self, values: list[int]) -> float:
        if not values:
            return 0.0
        total = len(values)
        score = 0.0
        for count in Counter(values).values():
            p = count / total
            if p > 0:
                score -= p * math.log2(p)
        return score

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

    def _parse_datetime(self, value: Any) -> datetime | None:
        if not value:
            return None
        text = str(value).replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            try:
                parsed = datetime.strptime(text.split("+")[0], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

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

    def _loads(self, value: str | None, default: Any) -> Any:
        if not value:
            return default
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default

    def _slug(self, value: str) -> str:
        clean = [char if char.isalnum() or char in {"-", "_"} else "_" for char in value]
        return "".join(clean).strip("_")


class IndicatorCache:
    def __init__(self, project_root: Path, *, timeframe: str) -> None:
        self.project_root = Path(project_root)
        self.data_dir = self.project_root / "user_data" / "data" / "binance"
        self.timeframe = timeframe
        self._frames: dict[str, Any] = {}
        self._pandas: Any | None = None

    def classify(self, pair: str, open_date: datetime | None) -> dict[str, str]:
        regimes = {
            "ema200_direction": "UNKNOWN",
            "ema200_distance_bucket": "UNKNOWN",
            "ema200_slope_bucket": "UNKNOWN",
            "atr_bucket": "UNKNOWN",
            "adx_bucket": "UNKNOWN",
            "breakout_state": "UNKNOWN",
            "volume_state": "UNKNOWN",
            "btc_regime": "UNKNOWN",
        }
        if open_date is None:
            return regimes
        row = self._row_at(pair, open_date)
        btc_row = self._row_at("BTC/USDT", open_date)
        if row:
            regimes.update(self._classify_row(row))
        if btc_row:
            regimes["btc_regime"] = self._btc_regime(btc_row)
        return regimes

    def _row_at(self, pair: str, open_date: datetime) -> dict[str, Any] | None:
        frame = self._frame(pair)
        if frame is None or len(frame) == 0:
            return None
        pd = self._pd()
        if pd is None:
            return None
        timestamp = pd.Timestamp(open_date).tz_convert("UTC")
        dates = frame["date"]
        if getattr(dates.dt, "tz", None) is None:
            timestamp = timestamp.tz_localize(None)
        index = dates.searchsorted(timestamp, side="right") - 1
        if index < 0:
            return None
        row = frame.iloc[int(index)]
        return row.to_dict()

    def _frame(self, pair: str) -> Any | None:
        if pair in self._frames:
            return self._frames[pair]
        pd = self._pd()
        if pd is None:
            self._frames[pair] = None
            return None
        filename = f"{pair.replace('/', '_').replace(':', '_')}-{self.timeframe}.feather"
        path = self.data_dir / filename
        if not path.exists():
            self._frames[pair] = None
            return None
        try:
            frame = pd.read_feather(path)
            frame["date"] = pd.to_datetime(frame["date"], utc=True)
            frame = self._with_indicators(frame)
        except Exception:
            frame = None
        self._frames[pair] = frame
        return frame

    def _with_indicators(self, frame: Any) -> Any:
        high = frame["high"].astype(float)
        low = frame["low"].astype(float)
        close = frame["close"].astype(float)
        volume = frame["volume"].astype(float)
        frame["ema200"] = close.ewm(span=200, adjust=False).mean()
        frame["ema200_slope"] = frame["ema200"].diff(12) / frame["ema200"]
        frame["ema200_distance"] = (close - frame["ema200"]) / frame["ema200"]
        previous_close = close.shift(1)
        true_range = self._max_columns(
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        )
        frame["atr"] = true_range.rolling(14, min_periods=1).mean()
        frame["atr_pct"] = frame["atr"] / close
        up_move = high.diff()
        down_move = -low.diff()
        plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
        minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
        atr = true_range.rolling(14, min_periods=1).mean()
        plus_di = 100 * plus_dm.rolling(14, min_periods=1).mean() / atr.replace(0, math.nan)
        minus_di = 100 * minus_dm.rolling(14, min_periods=1).mean() / atr.replace(0, math.nan)
        dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, math.nan)) * 100
        frame["adx"] = dx.rolling(14, min_periods=1).mean().fillna(0)
        frame["volume_ma"] = volume.rolling(20, min_periods=1).mean()
        frame["volume_ratio"] = volume / frame["volume_ma"].replace(0, math.nan)
        range_pct = (high - low) / close
        frame["range_pct"] = range_pct
        frame["range_ma"] = range_pct.rolling(20, min_periods=1).mean()
        return frame

    def _max_columns(self, *columns: Any) -> Any:
        pd = self._pd()
        return pd.concat(columns, axis=1).max(axis=1)

    def _classify_row(self, row: dict[str, Any]) -> dict[str, str]:
        distance = self._number(row.get("ema200_distance"))
        slope = self._number(row.get("ema200_slope"))
        atr_pct = self._number(row.get("atr_pct"))
        adx = self._number(row.get("adx"))
        volume_ratio = self._number(row.get("volume_ratio"))
        range_pct = self._number(row.get("range_pct"))
        range_ma = self._number(row.get("range_ma"))
        return {
            "ema200_direction": "EMA200_UP" if slope > 0.0005 else ("EMA200_DOWN" if slope < -0.0005 else "EMA200_FLAT"),
            "ema200_distance_bucket": self._bucket(distance, [(-0.03, "BELOW_FAR"), (-0.005, "BELOW_NEAR"), (0.005, "AT_EMA"), (0.03, "ABOVE_NEAR")], "ABOVE_FAR"),
            "ema200_slope_bucket": self._bucket(slope, [(-0.001, "SLOPE_DOWN_STRONG"), (-0.0002, "SLOPE_DOWN"), (0.0002, "SLOPE_FLAT"), (0.001, "SLOPE_UP")], "SLOPE_UP_STRONG"),
            "atr_bucket": self._bucket(atr_pct, [(0.01, "ATR_LOW"), (0.025, "ATR_MEDIUM")], "ATR_HIGH"),
            "adx_bucket": self._bucket(adx, [(18, "ADX_LOW"), (30, "ADX_MEDIUM")], "ADX_HIGH"),
            "breakout_state": self._breakout_state(range_pct, range_ma),
            "volume_state": self._bucket(volume_ratio, [(0.8, "VOLUME_BELOW_AVG"), (1.3, "VOLUME_NORMAL")], "VOLUME_ABOVE_AVG"),
        }

    def _btc_regime(self, row: dict[str, Any]) -> str:
        distance = self._number(row.get("ema200_distance"))
        slope = self._number(row.get("ema200_slope"))
        if distance > 0 and slope > 0:
            return "BTC_BULLISH"
        if distance < 0 and slope < 0:
            return "BTC_BEARISH"
        return "BTC_LATERAL"

    def _breakout_state(self, range_pct: float, range_ma: float) -> str:
        if range_ma <= 0:
            return "UNKNOWN"
        ratio = range_pct / range_ma
        if ratio < 0.75:
            return "COMPRESSION"
        if ratio > 1.25:
            return "EXPANSION"
        return "NORMAL_RANGE"

    def _bucket(self, value: float, thresholds: list[tuple[float, str]], default: str) -> str:
        for threshold, label in thresholds:
            if value < threshold:
                return label
        return default

    def _pd(self) -> Any | None:
        if self._pandas is not None:
            return self._pandas
        try:
            import pandas as pd
        except Exception:
            self._pandas = None
            return None
        self._pandas = pd
        return pd

    def _number(self, value: Any) -> float:
        try:
            result = float(value)
            if math.isnan(result) or math.isinf(result):
                return 0.0
            return result
        except (TypeError, ValueError):
            return 0.0


def command_analyze(args: argparse.Namespace) -> dict[str, str]:
    profiler = MarketRegimeProfiler(
        db_path=args.db_path,
        output_dir=args.output_dir,
        project_root=args.project_root,
        timeframe=args.timeframe,
    )
    paths = profiler.analyze(
        session_id=args.session_id,
        strategy=args.strategy,
        experiment_id=args.experiment_id,
        min_trades=args.min_trades,
    )
    return {key: str(path.resolve()) for key, path in paths.items()}


def command_export_trades(args: argparse.Namespace) -> dict[str, str]:
    profiler = MarketRegimeProfiler(
        db_path=args.db_path,
        output_dir=args.output_dir,
        project_root=args.project_root,
        timeframe=args.timeframe,
    )
    experiments = profiler._load_experiments(
        session_id=args.session_id,
        strategy=args.strategy,
        experiment_id=args.experiment_id,
    )
    trades = profiler._load_trades(experiments, session_id=args.session_id)
    path = Path(args.output_dir) / f"market_regime_trades_{args.session_id}.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "experiment_id",
                "pair",
                "open_date",
                "close_date",
                "profit_abs",
                "profit_ratio",
                "duration_minutes",
                *REGIME_FEATURES,
            ],
        )
        writer.writeheader()
        for trade in trades:
            writer.writerow(
                {
                    "experiment_id": trade.experiment_id,
                    "pair": trade.pair,
                    "open_date": trade.open_date.isoformat() if trade.open_date else "",
                    "close_date": trade.close_date.isoformat() if trade.close_date else "",
                    "profit_abs": trade.profit_abs,
                    "profit_ratio": trade.profit_ratio,
                    "duration_minutes": trade.duration_minutes,
                    **{feature: trade.regimes.get(feature, "UNKNOWN") for feature in REGIME_FEATURES},
                }
            )
    return {"csv": str(path.resolve())}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Profile market regimes for completed lab experiments without running backtests.",
    )
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--timeframe", default=DEFAULT_TIMEFRAME)

    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser("analyze", help="Generate HTML, Markdown, and JSON reports.")
    analyze.add_argument("session_id")
    analyze.add_argument("--strategy")
    analyze.add_argument("--experiment-id")
    analyze.add_argument("--min-trades", type=int, default=5)

    export = subparsers.add_parser("export-trades", help="Export classified trade rows to CSV.")
    export.add_argument("session_id")
    export.add_argument("--strategy")
    export.add_argument("--experiment-id")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "analyze":
        result = command_analyze(args)
    elif args.command == "export-trades":
        result = command_export_trades(args)
    else:
        parser.error("Unknown command.")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
