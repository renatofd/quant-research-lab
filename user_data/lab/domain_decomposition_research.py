from __future__ import annotations

import argparse
import html
import json
import math
import sqlite3
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from random import Random
from typing import Any

try:
    from .experiment_database import DEFAULT_DB_PATH
    from .market_regime_profiler import IndicatorCache, MarketRegimeProfiler
except ImportError:
    from experiment_database import DEFAULT_DB_PATH
    from market_regime_profiler import IndicatorCache, MarketRegimeProfiler


DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent
DEFAULT_TIMEFRAME = "5m"
REPORT_STEM = "domain_decomposition_report"
CORE_STRATEGIES = (
    "TrendStrategy",
    "PullbackStrategy",
    "NOfMTrendConfirmationStrategy",
    "NOfMTrendConfirmation",
    "MeanReversionStrategy",
)
REGIME_KEYS = (
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
)


@dataclass(frozen=True)
class DomainTrade:
    experiment_id: str
    session_id: str | None
    strategy_plugin: str
    pair: str
    open_date: datetime | None
    close_date: datetime | None
    hour: int | None
    weekday: str
    session: str
    profit_abs: float
    profit_ratio: float
    duration_minutes: float
    regimes: dict[str, str]


class DomainDecompositionResearch:
    """Read-only domain decomposition over existing lab results.

    The analyzer tests whether pair behavior is heterogeneous enough to justify
    splitting the strategy problem by pair clusters or by individual pairs. It
    reads SQLite, official backtest artifacts and existing scientific reports.
    It never changes strategy code and never launches backtests.
    """

    def __init__(
        self,
        *,
        db_path: Path | str = DEFAULT_DB_PATH,
        output_dir: Path | str = DEFAULT_OUTPUT_DIR,
        project_root: Path | str | None = None,
        timeframe: str = DEFAULT_TIMEFRAME,
    ) -> None:
        self.db_path = Path(db_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.project_root = Path(project_root or Path(__file__).resolve().parents[2])
        self.timeframe = timeframe
        self.profiler = MarketRegimeProfiler(
            db_path=self.db_path,
            output_dir=self.output_dir,
            project_root=self.project_root,
            timeframe=timeframe,
        )
        self.indicators = IndicatorCache(self.project_root, timeframe=timeframe)

    def analyze(
        self,
        *,
        min_trades: int = 20,
        max_experiments: int | None = None,
        random_seed: int = 42,
    ) -> dict[str, Path]:
        experiments = self._load_experiments(max_experiments=max_experiments)
        session_map = self._session_map()
        trades = self._load_trades(experiments, session_map=session_map)
        scientific_reports = self._load_scientific_reports()
        report = self._build_report(
            experiments=experiments,
            trades=trades,
            scientific_reports=scientific_reports,
            min_trades=min_trades,
            random_seed=random_seed,
        )
        return self._write_reports(report)

    def _load_experiments(self, *, max_experiments: int | None) -> list[dict[str, Any]]:
        query = """
            select *
            from experiments
            where status = 'completed'
              and metrics_json is not null
            order by created_at asc
        """
        params: list[Any] = []
        if max_experiments:
            query += " limit ?"
            params.append(max_experiments)

        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(query, params).fetchall()

        experiments = []
        for row in rows:
            parameters = self._loads(row["parameters_json"], {})
            metrics = self._loads(row["metrics_json"], {})
            experiments.append(
                {
                    "id": row["id"],
                    "strategy_name": row["strategy_name"],
                    "strategy_plugin": self._strategy_plugin(row["strategy_name"], parameters),
                    "parameters": parameters,
                    "metrics": metrics,
                    "result_path": row["result_path"],
                    "runtime_seconds": row["runtime_seconds"],
                    "score": row["score"],
                }
            )
        return experiments

    def _session_map(self) -> dict[str, str]:
        query = "select session_id, experiment_id from session_experiments"
        with sqlite3.connect(self.db_path) as connection:
            rows = connection.execute(query).fetchall()
        return {experiment_id: session_id for session_id, experiment_id in rows}

    def _load_trades(
        self,
        experiments: list[dict[str, Any]],
        *,
        session_map: dict[str, str],
    ) -> list[DomainTrade]:
        trades: list[DomainTrade] = []
        for experiment in experiments:
            result_path = self.profiler._host_path(experiment.get("result_path"))
            raw_trades = self.profiler._extract_trades(
                result_path,
                experiment["strategy_name"],
            )
            for raw in raw_trades:
                pair = str(raw.get("pair") or "UNKNOWN")
                open_date = self.profiler._parse_datetime(raw.get("open_date"))
                close_date = self.profiler._parse_datetime(raw.get("close_date"))
                regimes = self.indicators.classify(pair, open_date)
                session = regimes.get("hour_session") or self._hour_session(open_date)
                regimes.update(
                    {
                        "weekday": self._weekday(open_date),
                        "pair": pair,
                        "strategy_plugin": experiment["strategy_plugin"],
                    }
                )
                trades.append(
                    DomainTrade(
                        experiment_id=experiment["id"],
                        session_id=session_map.get(experiment["id"]),
                        strategy_plugin=experiment["strategy_plugin"],
                        pair=pair,
                        open_date=open_date,
                        close_date=close_date,
                        hour=open_date.hour if open_date else None,
                        weekday=self._weekday(open_date),
                        session=session,
                        profit_abs=self._number(raw.get("profit_abs")),
                        profit_ratio=self._number(raw.get("profit_ratio")),
                        duration_minutes=self._number(raw.get("trade_duration")),
                        regimes=regimes,
                    )
                )
        return trades

    def _load_scientific_reports(self) -> dict[str, Any]:
        reports = {}
        patterns = (
            "*scientific_report*.json",
            "*research*.json",
            "*robustness_report*.json",
            "*walk_forward_report*.json",
            "*market_eligibility*.json",
            "*trade_pattern_discovery*.json",
            "*market_regime_profile*.json",
            "*strategy_synthesis*.json",
        )
        for pattern in patterns:
            for path in sorted(self.output_dir.glob(pattern)):
                if path.name == f"{REPORT_STEM}.json":
                    continue
                try:
                    reports[path.name] = self._compact_report(path)
                except (OSError, json.JSONDecodeError):
                    reports[path.name] = {"path": str(path), "read_error": True}
        return reports

    def _compact_report(self, path: Path) -> dict[str, Any]:
        payload = self._loads(path.read_text(encoding="utf-8"), {})
        return {
            "path": str(path),
            "top_level_keys": sorted(payload)[:20] if isinstance(payload, dict) else [],
            "decision": self._deep_find(payload, ("decisao_final", "final_decision", "decision")),
            "conclusion": self._deep_find(payload, ("conclusion", "integrity_decision")),
            "strategy": self._deep_find(payload, ("strategy_plugin", "strategy")),
            "session_id": self._deep_find(payload, ("session_id",)),
        }

    def _build_report(
        self,
        *,
        experiments: list[dict[str, Any]],
        trades: list[DomainTrade],
        scientific_reports: dict[str, Any],
        min_trades: int,
        random_seed: int,
    ) -> dict[str, Any]:
        pair_metrics = self._pair_metrics(trades)
        pair_strategy = self._pair_strategy_metrics(trades)
        pair_hour = self._pair_time_windows(trades, min_trades=min_trades)
        pair_regime = self._pair_regime_windows(trades, min_trades=min_trades)
        vectors = self._pair_vectors(pair_metrics, pair_strategy, pair_hour, pair_regime)
        normalized = self._normalize_vectors(vectors)
        pca = self._pca_projection(normalized)
        clustering = self._cluster_pairs(normalized, random_seed=random_seed)
        similarity = self._similarity_matrix(normalized)
        distribution_distances = self._distribution_distances(trades)
        strategy_specialization = self._strategy_specialization(pair_strategy, min_trades)
        exclusive_pairs = self._exclusive_pair_candidates(
            pair_strategy,
            pair_metrics,
            min_trades,
        )
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "scope": {
                "db_path": str(self.db_path),
                "experiment_count": len(experiments),
                "trade_count": len(trades),
                "pair_count": len(pair_metrics),
                "timeframe": self.timeframe,
                "min_trades": min_trades,
                "read_only": True,
                "backtests_executed": False,
            },
            "scientific_reports_loaded": scientific_reports,
            "pair_metrics": pair_metrics,
            "pair_strategy_metrics": pair_strategy,
            "pair_time_windows": pair_hour,
            "pair_regime_windows": pair_regime,
            "pair_vectors": vectors,
            "pca": pca,
            "manifold": self._optional_manifold(normalized),
            "clustering": clustering,
            "similarity_matrix": similarity,
            "distribution_distances": distribution_distances,
            "strategy_specialization": strategy_specialization,
            "exclusive_pair_candidates": exclusive_pairs,
            "domain_answers": self._domain_answers(
                pair_metrics=pair_metrics,
                pair_strategy=pair_strategy,
                pair_hour=pair_hour,
                pair_regime=pair_regime,
                clustering=clustering,
                distribution_distances=distribution_distances,
                strategy_specialization=strategy_specialization,
                exclusive_pairs=exclusive_pairs,
                min_trades=min_trades,
            ),
        }
        report["scientific_next_step"] = self._scientific_next_step(report)
        return report

    def _pair_metrics(self, trades: list[DomainTrade]) -> dict[str, dict[str, Any]]:
        grouped: dict[str, list[DomainTrade]] = defaultdict(list)
        for trade in trades:
            grouped[trade.pair].append(trade)
        return {
            pair: self._metrics(rows)
            for pair, rows in sorted(grouped.items())
        }

    def _pair_strategy_metrics(
        self,
        trades: list[DomainTrade],
    ) -> dict[str, dict[str, dict[str, Any]]]:
        grouped: dict[str, dict[str, list[DomainTrade]]] = defaultdict(lambda: defaultdict(list))
        for trade in trades:
            grouped[trade.pair][trade.strategy_plugin].append(trade)
        return {
            pair: {
                strategy: self._metrics(rows)
                for strategy, rows in sorted(strategies.items())
            }
            for pair, strategies in sorted(grouped.items())
        }

    def _pair_time_windows(
        self,
        trades: list[DomainTrade],
        *,
        min_trades: int,
    ) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[tuple[str, str], list[DomainTrade]] = defaultdict(list)
        for trade in trades:
            grouped[(trade.pair, f"{trade.session}:{trade.hour}")].append(trade)
        rows_by_pair: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for (pair, bucket), rows in grouped.items():
            metrics = self._metrics(rows)
            if metrics["trades"] >= min_trades:
                rows_by_pair[pair].append({"bucket": bucket, **metrics})
        return {
            pair: sorted(rows, key=lambda row: row["expectancy"], reverse=True)
            for pair, rows in sorted(rows_by_pair.items())
        }

    def _pair_regime_windows(
        self,
        trades: list[DomainTrade],
        *,
        min_trades: int,
    ) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[tuple[str, str, str], list[DomainTrade]] = defaultdict(list)
        for trade in trades:
            for key in REGIME_KEYS:
                grouped[(trade.pair, key, trade.regimes.get(key, "UNKNOWN"))].append(trade)
        output: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for (pair, feature, value), rows in grouped.items():
            metrics = self._metrics(rows)
            if metrics["trades"] >= min_trades:
                output[pair].append({"feature": feature, "value": value, **metrics})
        return {
            pair: sorted(rows, key=lambda row: row["expectancy"], reverse=True)
            for pair, rows in sorted(output.items())
        }

    def _pair_vectors(
        self,
        pair_metrics: dict[str, dict[str, Any]],
        pair_strategy: dict[str, dict[str, dict[str, Any]]],
        pair_hour: dict[str, list[dict[str, Any]]],
        pair_regime: dict[str, list[dict[str, Any]]],
    ) -> dict[str, dict[str, float]]:
        strategies = sorted(
            {
                strategy
                for strategy_rows in pair_strategy.values()
                for strategy in strategy_rows
            }
        )
        vectors = {}
        for pair, metrics in pair_metrics.items():
            vector = {
                "trades": float(metrics["trades"]),
                "profit_factor": metrics["profit_factor"],
                "expectancy": metrics["expectancy"],
                "win_rate": metrics["win_rate"],
                "avg_duration_minutes": metrics["avg_duration_minutes"],
                "drawdown": metrics["max_drawdown_abs"],
                "profit_total_abs": metrics["profit_total_abs"],
                "positive_hour_count": float(
                    sum(1 for row in pair_hour.get(pair, []) if row["expectancy"] > 0)
                ),
                "positive_regime_count": float(
                    sum(1 for row in pair_regime.get(pair, []) if row["expectancy"] > 0)
                ),
            }
            for strategy in strategies:
                item = pair_strategy.get(pair, {}).get(strategy, {})
                vector[f"strategy_pf:{strategy}"] = self._number(item.get("profit_factor"))
                vector[f"strategy_exp:{strategy}"] = self._number(item.get("expectancy"))
                vector[f"strategy_trades:{strategy}"] = self._number(item.get("trades"))
            vectors[pair] = vector
        return vectors

    def _normalize_vectors(
        self,
        vectors: dict[str, dict[str, float]],
    ) -> dict[str, list[float]]:
        keys = sorted({key for vector in vectors.values() for key in vector})
        columns = {
            key: [self._number(vector.get(key)) for vector in vectors.values()]
            for key in keys
        }
        means = {key: statistics.mean(values) if values else 0.0 for key, values in columns.items()}
        stdevs = {
            key: statistics.pstdev(values) if len(values) > 1 else 1.0
            for key, values in columns.items()
        }
        return {
            pair: [
                (self._number(vector.get(key)) - means[key])
                / (stdevs[key] if stdevs[key] > 1e-12 else 1.0)
                for key in keys
            ]
            for pair, vector in vectors.items()
        }

    def _pca_projection(self, normalized: dict[str, list[float]]) -> dict[str, Any]:
        pairs = sorted(normalized)
        matrix = [normalized[pair] for pair in pairs]
        if len(matrix) < 2 or not matrix[0]:
            return {"available": False, "reason": "insufficient pair vectors", "points": {}}
        first = self._principal_component(matrix)
        residual = self._remove_projection(matrix, first)
        second = self._principal_component(residual)
        points = {}
        for pair, row in zip(pairs, matrix, strict=False):
            points[pair] = {
                "pc1": self._dot(row, first),
                "pc2": self._dot(row, second),
            }
        return {
            "available": True,
            "method": "power_iteration_python_stdlib",
            "points": points,
        }

    def _optional_manifold(self, normalized: dict[str, list[float]]) -> dict[str, Any]:
        pairs = sorted(normalized)
        matrix = [normalized[pair] for pair in pairs]
        if len(matrix) < 4:
            return {"available": False, "method": None, "reason": "insufficient pairs"}
        try:
            from sklearn.manifold import TSNE

            perplexity = max(2, min(5, len(matrix) - 1))
            embedded = TSNE(
                n_components=2,
                random_state=42,
                perplexity=perplexity,
                init="random",
                learning_rate="auto",
            ).fit_transform(matrix)
            return {
                "available": True,
                "method": "sklearn_tsne",
                "points": {
                    pair: {"x": float(point[0]), "y": float(point[1])}
                    for pair, point in zip(pairs, embedded, strict=False)
                },
            }
        except Exception as exc:
            return {
                "available": False,
                "method": "tsne_or_umap",
                "reason": f"{exc.__class__.__name__}: {exc}",
            }

    def _cluster_pairs(
        self,
        normalized: dict[str, list[float]],
        *,
        random_seed: int,
    ) -> dict[str, Any]:
        pairs = sorted(normalized)
        matrix = [normalized[pair] for pair in pairs]
        if len(matrix) < 3:
            return {"available": False, "reason": "fewer than 3 pairs", "clusters": []}
        best: dict[str, Any] | None = None
        max_k = min(6, len(matrix) - 1)
        for k in range(2, max_k + 1):
            labels, centroids = self._kmeans(matrix, k=k, random_seed=random_seed)
            silhouette = self._silhouette(matrix, labels)
            clusters = self._cluster_rows(pairs, labels)
            candidate = {
                "k": k,
                "silhouette_score": silhouette,
                "clusters": clusters,
                "centroids": centroids,
            }
            if best is None or silhouette > best["silhouette_score"]:
                best = candidate
        return {"available": True, **(best or {})}

    def _cluster_rows(self, pairs: list[str], labels: list[int]) -> list[dict[str, Any]]:
        grouped: dict[int, list[str]] = defaultdict(list)
        for pair, label in zip(pairs, labels, strict=False):
            grouped[label].append(pair)
        return [
            {"cluster_id": label, "pairs": sorted(values), "pair_count": len(values)}
            for label, values in sorted(grouped.items())
        ]

    def _similarity_matrix(self, normalized: dict[str, list[float]]) -> list[dict[str, Any]]:
        pairs = sorted(normalized)
        rows = []
        for left in pairs:
            values = []
            for right in pairs:
                values.append(
                    {
                        "pair": right,
                        "cosine_similarity": self._cosine(normalized[left], normalized[right]),
                        "euclidean_distance": self._distance(normalized[left], normalized[right]),
                    }
                )
            rows.append({"pair": left, "values": values})
        return rows

    def _distribution_distances(self, trades: list[DomainTrade]) -> list[dict[str, Any]]:
        grouped: dict[str, list[float]] = defaultdict(list)
        for trade in trades:
            grouped[trade.pair].append(trade.profit_ratio)
        pairs = sorted(grouped)
        rows = []
        for i, left in enumerate(pairs):
            for right in pairs[i + 1 :]:
                rows.append(
                    {
                        "left": left,
                        "right": right,
                        "ks_distance": self._ks_distance(grouped[left], grouped[right]),
                        "mean_profit_delta": abs(
                            statistics.mean(grouped[left]) - statistics.mean(grouped[right])
                        ),
                    }
                )
        return sorted(rows, key=lambda row: row["ks_distance"], reverse=True)

    def _strategy_specialization(
        self,
        pair_strategy: dict[str, dict[str, dict[str, Any]]],
        min_trades: int,
    ) -> list[dict[str, Any]]:
        rows = []
        for pair, strategies in pair_strategy.items():
            candidates = [
                {"strategy": strategy, **metrics}
                for strategy, metrics in strategies.items()
                if metrics["trades"] >= min_trades
            ]
            if not candidates:
                continue
            candidates.sort(key=lambda row: row["expectancy"], reverse=True)
            best = candidates[0]
            second = candidates[1] if len(candidates) > 1 else None
            rows.append(
                {
                    "pair": pair,
                    "best_strategy": best["strategy"],
                    "best_expectancy": best["expectancy"],
                    "best_profit_factor": best["profit_factor"],
                    "best_trades": best["trades"],
                    "second_strategy": second["strategy"] if second else None,
                    "expectancy_gap": (
                        best["expectancy"] - second["expectancy"] if second else best["expectancy"]
                    ),
                    "profit_factor_gap": (
                        best["profit_factor"] - second["profit_factor"]
                        if second
                        else best["profit_factor"]
                    ),
                }
            )
        return sorted(rows, key=lambda row: row["expectancy_gap"], reverse=True)

    def _exclusive_pair_candidates(
        self,
        pair_strategy: dict[str, dict[str, dict[str, Any]]],
        pair_metrics: dict[str, dict[str, Any]],
        min_trades: int,
    ) -> list[dict[str, Any]]:
        candidates = []
        for item in self._strategy_specialization(pair_strategy, min_trades):
            pair = item["pair"]
            overall = pair_metrics.get(pair, {})
            if (
                item["best_trades"] >= min_trades
                and item["best_expectancy"] > 0
                and item["expectancy_gap"] > abs(self._number(overall.get("expectancy"))) * 0.50
            ):
                candidates.append({**item, "overall": overall})
        return candidates

    def _domain_answers(
        self,
        *,
        pair_metrics: dict[str, dict[str, Any]],
        pair_strategy: dict[str, dict[str, dict[str, Any]]],
        pair_hour: dict[str, list[dict[str, Any]]],
        pair_regime: dict[str, list[dict[str, Any]]],
        clustering: dict[str, Any],
        distribution_distances: list[dict[str, Any]],
        strategy_specialization: list[dict[str, Any]],
        exclusive_pairs: list[dict[str, Any]],
        min_trades: int,
    ) -> dict[str, Any]:
        pf_values = [row["profit_factor"] for row in pair_metrics.values()]
        expectancy_values = [row["expectancy"] for row in pair_metrics.values()]
        pair_variance = statistics.pstdev(expectancy_values) if len(expectancy_values) > 1 else 0.0
        silhouette = self._number(clustering.get("silhouette_score"))
        distinct_pairs = [
            pair
            for pair, metrics in pair_metrics.items()
            if metrics["trades"] >= min_trades
            and abs(metrics["expectancy"] - statistics.mean(expectancy_values or [0.0]))
            > pair_variance
        ]
        return {
            "1_pares_com_comportamento_diferente": {
                "answer": bool(distinct_pairs or silhouette > 0.20),
                "evidence": {
                    "distinct_pairs": distinct_pairs,
                    "pair_expectancy_std": pair_variance,
                    "pf_range": [min(pf_values or [0.0]), max(pf_values or [0.0])],
                    "top_distribution_distances": distribution_distances[:10],
                },
            },
            "2_grupos_naturais_de_pares": {
                "answer": bool(clustering.get("available") and silhouette > 0.15),
                "evidence": {
                    "silhouette_score": silhouette,
                    "clusters": clustering.get("clusters", []),
                },
            },
            "3_clusterizacao_dos_pares": {
                "answer": bool(clustering.get("available")),
                "evidence": clustering,
            },
            "4_horarios_especificos_por_par": {
                "answer": any(pair_hour.values()),
                "evidence": {
                    pair: rows[:5]
                    for pair, rows in pair_hour.items()
                    if any(row["expectancy"] > 0 for row in rows)
                },
            },
            "5_regimes_negociaveis_apenas_para_alguns_pares": {
                "answer": any(pair_regime.values()),
                "evidence": {
                    pair: rows[:8]
                    for pair, rows in pair_regime.items()
                    if any(row["expectancy"] > 0 for row in rows)
                },
            },
            "6_estrategias_funcionam_somente_em_determinados_pares": {
                "answer": bool(strategy_specialization),
                "evidence": strategy_specialization[:20],
            },
            "7_pares_com_estrategias_exclusivas": {
                "answer": bool(exclusive_pairs),
                "evidence": exclusive_pairs[:20],
            },
            "8_modelo_unico_inadequado": {
                "answer": bool(silhouette > 0.20 or exclusive_pairs),
                "evidence": {
                    "silhouette_score": silhouette,
                    "exclusive_pair_candidates": len(exclusive_pairs),
                    "strategy_specialization_count": len(strategy_specialization),
                    "pair_expectancy_std": pair_variance,
                },
            },
        }

    def _scientific_next_step(self, report: dict[str, Any]) -> dict[str, Any]:
        answers = report["domain_answers"]
        clustering = report["clustering"]
        pair_metrics = report["pair_metrics"]
        exclusive = report["exclusive_pair_candidates"]
        silhouette = self._number(clustering.get("silhouette_score"))
        profitable_pairs = [
            pair
            for pair, metrics in pair_metrics.items()
            if metrics["trades"] >= 20 and metrics["expectancy"] > 0
        ]
        if not profitable_pairs and not exclusive:
            choice = "D"
            reason = "No pair-level pocket shows enough positive expectancy to justify more specialization."
        elif len(exclusive) >= max(2, len(pair_metrics) // 3):
            choice = "C"
            reason = "Several pairs show strategy-specific behavior strong enough for pair-level research."
        elif answers["8_modelo_unico_inadequado"]["answer"] and silhouette > 0.15:
            choice = "B"
            reason = "Pair clusters are visible; grouped strategies are the lowest-complexity specialization path."
        else:
            choice = "A"
            reason = "Domain evidence is not strong enough to abandon a single-strategy research path."
        return {
            "choice": choice,
            "label": {
                "A": "continuar pesquisando estrategia unica",
                "B": "uma estrategia por grupo de pares",
                "C": "uma estrategia por par",
                "D": "abandonar esse universo de ativos",
            }[choice],
            "reason": reason,
        }

    def _metrics(self, trades: list[DomainTrade]) -> dict[str, Any]:
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
            "win_rate": wins / len(trades) if trades else 0.0,
            "sharpe": self._sharpe(ratios),
            "max_drawdown_abs": self._max_drawdown(profits),
            "avg_duration_minutes": statistics.mean([t.duration_minutes for t in trades]) if trades else 0.0,
        }

    def _kmeans(
        self,
        matrix: list[list[float]],
        *,
        k: int,
        random_seed: int,
        iterations: int = 80,
    ) -> tuple[list[int], list[list[float]]]:
        random = Random(random_seed + k)
        centroids = [list(row) for row in random.sample(matrix, k)]
        labels = [0] * len(matrix)
        for _ in range(iterations):
            changed = False
            for index, row in enumerate(matrix):
                distances = [self._distance(row, centroid) for centroid in centroids]
                label = min(range(k), key=lambda item: distances[item])
                if label != labels[index]:
                    labels[index] = label
                    changed = True
            grouped: dict[int, list[list[float]]] = defaultdict(list)
            for label, row in zip(labels, matrix, strict=False):
                grouped[label].append(row)
            for label in range(k):
                if grouped[label]:
                    centroids[label] = self._mean_vector(grouped[label])
            if not changed:
                break
        return labels, centroids

    def _silhouette(self, matrix: list[list[float]], labels: list[int]) -> float:
        scores = []
        for index, row in enumerate(matrix):
            same = [
                self._distance(row, other)
                for j, other in enumerate(matrix)
                if labels[j] == labels[index] and j != index
            ]
            other_labels = sorted(set(labels) - {labels[index]})
            if not same or not other_labels:
                continue
            a = statistics.mean(same)
            b = min(
                statistics.mean(
                    self._distance(row, other)
                    for j, other in enumerate(matrix)
                    if labels[j] == label
                )
                for label in other_labels
            )
            scores.append((b - a) / max(a, b) if max(a, b) > 1e-12 else 0.0)
        return statistics.mean(scores) if scores else 0.0

    def _principal_component(self, matrix: list[list[float]]) -> list[float]:
        dimension = len(matrix[0])
        vector = [1.0 / math.sqrt(dimension)] * dimension
        for _ in range(80):
            multiplied = [0.0] * dimension
            for row in matrix:
                projection = self._dot(row, vector)
                for index, value in enumerate(row):
                    multiplied[index] += projection * value
            norm = math.sqrt(sum(value * value for value in multiplied))
            if norm <= 1e-12:
                break
            vector = [value / norm for value in multiplied]
        return vector

    def _remove_projection(self, matrix: list[list[float]], component: list[float]) -> list[list[float]]:
        residual = []
        for row in matrix:
            projection = self._dot(row, component)
            residual.append([value - projection * component[index] for index, value in enumerate(row)])
        return residual

    def _mean_vector(self, rows: list[list[float]]) -> list[float]:
        return [
            statistics.mean(row[index] for row in rows)
            for index in range(len(rows[0]))
        ]

    def _ks_distance(self, left: list[float], right: list[float]) -> float:
        if not left or not right:
            return 0.0
        values = sorted(set(left + right))
        best = 0.0
        left_sorted = sorted(left)
        right_sorted = sorted(right)
        for value in values:
            left_cdf = sum(1 for item in left_sorted if item <= value) / len(left_sorted)
            right_cdf = sum(1 for item in right_sorted if item <= value) / len(right_sorted)
            best = max(best, abs(left_cdf - right_cdf))
        return best

    def _write_reports(self, report: dict[str, Any]) -> dict[str, Path]:
        json_path = self.output_dir / f"{REPORT_STEM}.json"
        markdown_path = self.output_dir / f"{REPORT_STEM}.md"
        html_path = self.output_dir / f"{REPORT_STEM}.html"
        json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        markdown_path.write_text(self._markdown(report), encoding="utf-8")
        html_path.write_text(self._html(report), encoding="utf-8")
        return {"json": json_path, "markdown": markdown_path, "html": html_path}

    def _markdown(self, report: dict[str, Any]) -> str:
        next_step = report["scientific_next_step"]
        lines = [
            "# Domain Decomposition Research",
            "",
            "## Summary",
            f"- Experiments read: {report['scope']['experiment_count']}",
            f"- Trades read: {report['scope']['trade_count']}",
            f"- Pairs analyzed: {report['scope']['pair_count']}",
            f"- Best cluster silhouette: {report['clustering'].get('silhouette_score', 0.0):.4f}",
            f"- Scientific next step: **{next_step['choice']} - {next_step['label']}**",
            f"- Reason: {next_step['reason']}",
            "",
            "## Domain Answers",
        ]
        for question, payload in report["domain_answers"].items():
            lines.append(f"- **{question}**: {payload['answer']}")
        lines.extend(
            [
                "",
                "## Clusters",
                "| Cluster | Pairs |",
                "|---:|---|",
            ]
        )
        for cluster in report["clustering"].get("clusters", []):
            lines.append(f"| {cluster['cluster_id']} | {', '.join(cluster['pairs'])} |")
        lines.extend(
            [
                "",
                "## Pair Metrics",
                "| Pair | Trades | PF | Expectancy | Win rate | Profit | Drawdown |",
                "|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for pair, metrics in report["pair_metrics"].items():
            lines.append(
                "| {pair} | {trades} | {pf:.3f} | {exp:.4f} | {wr:.2%} | {profit:.3f} | {dd:.3f} |".format(
                    pair=pair,
                    trades=metrics["trades"],
                    pf=metrics["profit_factor"],
                    exp=metrics["expectancy"],
                    wr=metrics["win_rate"],
                    profit=metrics["profit_total_abs"],
                    dd=metrics["max_drawdown_abs"],
                )
            )
        lines.extend(
            [
                "",
                "## Top Strategy Specialization",
                "| Pair | Best strategy | PF | Expectancy | Trades | Gap |",
                "|---|---|---:|---:|---:|---:|",
            ]
        )
        for row in report["strategy_specialization"][:20]:
            lines.append(
                "| {pair} | {strategy} | {pf:.3f} | {exp:.4f} | {trades} | {gap:.4f} |".format(
                    pair=row["pair"],
                    strategy=row["best_strategy"],
                    pf=row["best_profit_factor"],
                    exp=row["best_expectancy"],
                    trades=row["best_trades"],
                    gap=row["expectancy_gap"],
                )
            )
        lines.extend(["", "## Final Recommendation", f"**{next_step['choice']}**"])
        return "\n".join(lines)

    def _html(self, report: dict[str, Any]) -> str:
        payload = json.dumps(report, ensure_ascii=False)
        answers = "".join(
            f"<li><strong>{html.escape(key)}</strong>: {value['answer']}</li>"
            for key, value in report["domain_answers"].items()
        )
        clusters = "".join(
            "<tr><td>{}</td><td>{}</td></tr>".format(
                cluster["cluster_id"],
                html.escape(", ".join(cluster["pairs"])),
            )
            for cluster in report["clustering"].get("clusters", [])
        )
        pair_rows = "".join(
            "<tr><td>{pair}</td><td>{trades}</td><td>{pf:.3f}</td><td>{exp:.4f}</td><td>{wr:.2%}</td><td>{profit:.3f}</td></tr>".format(
                pair=html.escape(pair),
                trades=metrics["trades"],
                pf=metrics["profit_factor"],
                exp=metrics["expectancy"],
                wr=metrics["win_rate"],
                profit=metrics["profit_total_abs"],
            )
            for pair, metrics in report["pair_metrics"].items()
        )
        next_step = report["scientific_next_step"]
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Domain Decomposition Research</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2933; }}
    table {{ border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 13px; }}
    th, td {{ border: 1px solid #d9e2ec; padding: 7px 9px; text-align: left; }}
    th {{ background: #f0f4f8; }}
    .metric {{ display: inline-block; border: 1px solid #d9e2ec; padding: 9px 11px; margin: 4px; }}
    canvas {{ width: 100%; height: 320px; border: 1px solid #d9e2ec; }}
  </style>
</head>
<body>
  <h1>Domain Decomposition Research</h1>
  <div>
    <span class="metric">Experiments<br><strong>{report['scope']['experiment_count']}</strong></span>
    <span class="metric">Trades<br><strong>{report['scope']['trade_count']}</strong></span>
    <span class="metric">Pairs<br><strong>{report['scope']['pair_count']}</strong></span>
    <span class="metric">Next step<br><strong>{next_step['choice']}</strong></span>
  </div>
  <h2>Recommendation</h2>
  <p><strong>{html.escape(next_step['label'])}</strong>: {html.escape(next_step['reason'])}</p>
  <h2>Domain Answers</h2>
  <ul>{answers}</ul>
  <h2>PCA Pair Map</h2>
  <canvas id="pca"></canvas>
  <h2>Clusters</h2>
  <table><tr><th>Cluster</th><th>Pairs</th></tr>{clusters}</table>
  <h2>Pair Metrics</h2>
  <table><tr><th>Pair</th><th>Trades</th><th>PF</th><th>Expectancy</th><th>Win rate</th><th>Profit</th></tr>{pair_rows}</table>
  <script>
    const data = {payload};
    const canvas = document.getElementById('pca');
    const ctx = canvas.getContext('2d');
    canvas.width = canvas.clientWidth * devicePixelRatio;
    canvas.height = canvas.clientHeight * devicePixelRatio;
    ctx.scale(devicePixelRatio, devicePixelRatio);
    const points = data.pca.points || {{}};
    const entries = Object.entries(points);
    const xs = entries.map(([, p]) => Number(p.pc1 || 0));
    const ys = entries.map(([, p]) => Number(p.pc2 || 0));
    const minX = Math.min(...xs, -1), maxX = Math.max(...xs, 1);
    const minY = Math.min(...ys, -1), maxY = Math.max(...ys, 1);
    function sx(x) {{ return 50 + (x - minX) / (maxX - minX || 1) * (canvas.clientWidth - 100); }}
    function sy(y) {{ return canvas.clientHeight - 40 - (y - minY) / (maxY - minY || 1) * (canvas.clientHeight - 80); }}
    entries.forEach(([pair, point], index) => {{
      const x = sx(Number(point.pc1 || 0));
      const y = sy(Number(point.pc2 || 0));
      ctx.fillStyle = ['#2f6f73', '#b15533', '#345995', '#7b6d8d', '#b88b4a'][index % 5];
      ctx.beginPath(); ctx.arc(x, y, 5, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = '#1f2933'; ctx.fillText(pair, x + 7, y + 4);
    }});
  </script>
</body>
</html>
"""

    def _strategy_plugin(self, strategy_name: str, parameters: dict[str, Any]) -> str:
        return (
            parameters.get("strategy_plugin")
            or parameters.get("plugin")
            or strategy_name
            or "UNKNOWN"
        )

    def _deep_find(self, payload: Any, keys: tuple[str, ...]) -> Any:
        if isinstance(payload, dict):
            for key in keys:
                if key in payload:
                    return payload[key]
            for value in payload.values():
                found = self._deep_find(value, keys)
                if found is not None:
                    return found
        elif isinstance(payload, list):
            for value in payload[:20]:
                found = self._deep_find(value, keys)
                if found is not None:
                    return found
        return None

    def _hour_session(self, value: datetime | None) -> str:
        if value is None:
            return "UNKNOWN"
        if 0 <= value.hour < 8:
            return "ASIA"
        if 8 <= value.hour < 13:
            return "LONDON"
        if 13 <= value.hour < 21:
            return "NY"
        return "AFTER_HOURS"

    def _weekday(self, value: datetime | None) -> str:
        if value is None:
            return "UNKNOWN"
        return ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"][value.weekday()]

    def _sharpe(self, values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        deviation = statistics.pstdev(values)
        return statistics.mean(values) / deviation * math.sqrt(len(values)) if deviation else 0.0

    def _max_drawdown(self, profits: list[float]) -> float:
        equity = 0.0
        peak = 0.0
        max_drawdown = 0.0
        for value in profits:
            equity += value
            peak = max(peak, equity)
            max_drawdown = max(max_drawdown, peak - equity)
        return max_drawdown

    def _dot(self, left: list[float], right: list[float]) -> float:
        return sum(a * b for a, b in zip(left, right, strict=False))

    def _distance(self, left: list[float], right: list[float]) -> float:
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right, strict=False)))

    def _cosine(self, left: list[float], right: list[float]) -> float:
        denominator = math.sqrt(self._dot(left, left)) * math.sqrt(self._dot(right, right))
        return self._dot(left, right) / denominator if denominator > 1e-12 else 0.0

    def _number(self, value: Any) -> float:
        try:
            if value is None or isinstance(value, bool):
                return 0.0
            parsed = float(value)
        except (TypeError, ValueError):
            return 0.0
        if math.isnan(parsed) or math.isinf(parsed):
            return 0.0
        return parsed

    def _loads(self, value: str | None, default: Any) -> Any:
        if not value:
            return default
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only domain decomposition research over existing lab results.",
    )
    subparsers = parser.add_subparsers(dest="command")
    analyze = subparsers.add_parser(
        "analyze",
        help="Generate domain decomposition HTML, Markdown and JSON reports.",
    )
    analyze.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    analyze.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    analyze.add_argument("--project-root", type=Path)
    analyze.add_argument("--timeframe", default=DEFAULT_TIMEFRAME)
    analyze.add_argument("--min-trades", type=int, default=20)
    analyze.add_argument(
        "--max-experiments",
        type=int,
        help="Optional cap for very large offline audits. Does not create new experiments.",
    )
    analyze.add_argument("--random-seed", type=int, default=42)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "analyze":
        research = DomainDecompositionResearch(
            db_path=args.db_path,
            output_dir=args.output_dir,
            project_root=args.project_root,
            timeframe=args.timeframe,
        )
        result = research.analyze(
            min_trades=args.min_trades,
            max_experiments=args.max_experiments,
            random_seed=args.random_seed,
        )
        print(json.dumps({key: str(path) for key, path in result.items()}, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
