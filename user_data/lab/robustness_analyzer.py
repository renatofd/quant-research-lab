from __future__ import annotations

import argparse
import json
import math
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, median, pstdev
from typing import Any


DEFAULT_DB_PATH = Path(__file__).resolve().parent / "experiments.sqlite"
DEFAULT_WEIGHTS = {
    "local_stability": 0.40,
    "profit_factor": 0.20,
    "drawdown": 0.15,
    "sharpe": 0.15,
    "trades": 0.10,
}
DEFAULT_HEATMAPS = (
    ("stoploss", "entry_score_threshold"),
    ("ema_fast_period", "ema_slow_period"),
    ("ema_fast_period", "adx_period"),
    ("breakout_weight", "ema_fast_slow_weight"),
)


@dataclass(frozen=True)
class RobustnessConfig:
    neighbor_count: int = 10
    cluster_count: int = 6
    heatmap_bins: int = 6
    important_parameter_count: int = 12
    pf_threshold: float = 1.0
    min_trades: int = 20
    max_drawdown: float | None = None
    cliff_pf_drop: float = 0.50
    stable_pf_std: float = 0.25
    weights: dict[str, float] | None = None

    @property
    def normalized_weights(self) -> dict[str, float]:
        weights = dict(DEFAULT_WEIGHTS)
        if self.weights:
            weights.update(self.weights)
        total = sum(max(0.0, value) for value in weights.values())
        if total <= 0:
            return dict(DEFAULT_WEIGHTS)
        return {key: max(0.0, value) / total for key, value in weights.items()}


class RobustnessAnalyzer:
    def __init__(
        self,
        *,
        db_path: Path | str = DEFAULT_DB_PATH,
        output_dir: Path | str | None = None,
        config: RobustnessConfig | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.output_dir = Path(output_dir or self.db_path.parent)
        self.config = config or RobustnessConfig()

    def analyze_session(self, session_id: str) -> dict[str, Any]:
        experiments = self._load_completed_session(session_id)
        if not experiments:
            raise ValueError(f"No completed experiments found for session {session_id}.")

        parameters = self._numeric_parameters(experiments)
        ranges = self._parameter_ranges(experiments, parameters)
        robust_rows = self._local_robustness(experiments, parameters, ranges)
        pareto_ids = self._pareto_frontier(experiments)
        important = self._important_parameters(experiments, parameters)
        sensitivity = self._local_sensitivity(experiments, important, ranges)
        heatmaps = self._heatmaps(experiments)
        clusters = self._clusters(experiments, parameters, ranges)
        optimal_regions = self._optimal_regions(experiments, clusters, important)
        scored = self._scientific_scores(experiments, robust_rows)

        by_id = {row["id"]: row for row in experiments}
        for row in scored:
            row["pareto_frontier"] = row["id"] in pareto_ids
            row["metrics"] = by_id[row["id"]]["metrics"]
            row["parameters"] = by_id[row["id"]]["parameters"]

        recommendations = self._recommendations(
            scored=scored,
            pareto_ids=pareto_ids,
            clusters=clusters,
            optimal_regions=optimal_regions,
            sensitivity=sensitivity,
        )

        return {
            "session_id": session_id,
            "generated_at": datetime.now(UTC).isoformat(),
            "experiment_count": len(experiments),
            "numeric_parameters": parameters,
            "config": {
                "neighbor_count": self.config.neighbor_count,
                "cluster_count": self.config.cluster_count,
                "heatmap_bins": self.config.heatmap_bins,
                "important_parameter_count": self.config.important_parameter_count,
                "pf_threshold": self.config.pf_threshold,
                "min_trades": self.config.min_trades,
                "max_drawdown": self._resolved_max_drawdown(experiments),
                "weights": self.config.normalized_weights,
            },
            "robustness_ranking": scored,
            "pareto_frontier": [row for row in scored if row["pareto_frontier"]],
            "important_parameters": important,
            "sensitivity": sensitivity,
            "heatmaps": heatmaps,
            "clusters": clusters,
            "optimal_regions": optimal_regions,
            "recommendations": recommendations,
        }

    def write_reports(self, session_id: str) -> dict[str, Path]:
        analysis = self.analyze_session(session_id)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        json_path = self.output_dir / f"robustness_report_{session_id}.json"
        html_path = self.output_dir / f"robustness_report_{session_id}.html"
        regions_path = self.output_dir / f"optimal_regions_{session_id}.json"

        json_path.write_text(json.dumps(analysis, indent=2, sort_keys=True), encoding="utf-8")
        regions_path.write_text(
            json.dumps(analysis["optimal_regions"], indent=2, sort_keys=True),
            encoding="utf-8",
        )
        html_path.write_text(self._render_html(analysis), encoding="utf-8")
        return {"json": json_path, "html": html_path, "optimal_regions": regions_path}

    def _load_completed_session(self, session_id: str) -> list[dict[str, Any]]:
        uri = f"file:{self.db_path.as_posix()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                select e.*
                from session_experiments se
                join experiments e on e.id = se.experiment_id
                where se.session_id = ?
                  and e.status = 'completed'
                  and e.metrics_json is not null
                order by se.position asc
                """,
                (session_id,),
            ).fetchall()

        experiments = []
        for row in rows:
            parameters = json.loads(row["parameters_json"])
            metrics = json.loads(row["metrics_json"])
            experiments.append(
                {
                    "id": row["id"],
                    "parameters": self._experiment_parameters(parameters),
                    "raw_parameters": parameters,
                    "metrics": metrics,
                }
            )
        return experiments

    def _experiment_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        plugin_parameters = parameters.get("plugin_parameters")
        if isinstance(plugin_parameters, dict):
            return plugin_parameters
        nested = parameters.get("parameters")
        if isinstance(nested, dict):
            return nested
        return parameters

    def _numeric_parameters(self, experiments: list[dict[str, Any]]) -> list[str]:
        parameters = set()
        for experiment in experiments:
            for key, value in experiment["parameters"].items():
                if self._number(value) is not None:
                    parameters.add(key)
        return sorted(parameters)

    def _parameter_ranges(
        self,
        experiments: list[dict[str, Any]],
        parameters: list[str],
    ) -> dict[str, tuple[float, float]]:
        ranges = {}
        for parameter in parameters:
            values = [
                self._number(experiment["parameters"].get(parameter))
                for experiment in experiments
            ]
            clean = [value for value in values if value is not None]
            ranges[parameter] = (min(clean), max(clean)) if clean else (0.0, 0.0)
        return ranges

    def _local_robustness(
        self,
        experiments: list[dict[str, Any]],
        parameters: list[str],
        ranges: dict[str, tuple[float, float]],
    ) -> list[dict[str, Any]]:
        rows = []
        for experiment in experiments:
            neighbors = self._neighbors(experiment, experiments, parameters, ranges)
            pfs = [self._metric(neighbor, "profit_factor") for neighbor in neighbors]
            pf_mean = mean(pfs) if pfs else 0.0
            pf_std = pstdev(pfs) if len(pfs) > 1 else 0.0
            cv = pf_std / abs(pf_mean) if abs(pf_mean) > 1e-12 else None
            own_pf = self._metric(experiment, "profit_factor")
            consistency = pf_mean / (pf_mean + pf_std + 1e-12) if pf_mean > 0 else 0.0
            alignment = 1.0 - min(1.0, abs(own_pf - pf_mean) / (abs(own_pf) + abs(pf_mean) + 1e-12))
            stability = max(0.0, min(1.0, 0.70 * consistency + 0.30 * alignment))
            rows.append(
                {
                    "id": experiment["id"],
                    "profit_factor": own_pf,
                    "neighbor_count": len(neighbors),
                    "neighbor_profit_factor_mean": pf_mean,
                    "neighbor_profit_factor_std": pf_std,
                    "neighbor_profit_factor_cv": cv,
                    "local_stability_score": stability,
                    "neighbors": [
                        {
                            "id": neighbor["id"],
                            "distance": self._distance(experiment, neighbor, parameters, ranges),
                            "profit_factor": self._metric(neighbor, "profit_factor"),
                            "drawdown": self._drawdown(neighbor),
                            "trades": self._metric(neighbor, "total_trades"),
                        }
                        for neighbor in neighbors
                    ],
                }
            )
        return rows

    def _neighbors(
        self,
        experiment: dict[str, Any],
        experiments: list[dict[str, Any]],
        parameters: list[str],
        ranges: dict[str, tuple[float, float]],
    ) -> list[dict[str, Any]]:
        candidates = [
            (
                self._distance(experiment, other, parameters, ranges),
                other["id"],
                other,
            )
            for other in experiments
            if other["id"] != experiment["id"]
        ]
        candidates.sort(key=lambda item: (item[0], item[1]))
        return [item[2] for item in candidates[: self.config.neighbor_count]]

    def _distance(
        self,
        left: dict[str, Any],
        right: dict[str, Any],
        parameters: list[str],
        ranges: dict[str, tuple[float, float]],
    ) -> float:
        total = 0.0
        count = 0
        for parameter in parameters:
            low, high = ranges[parameter]
            width = high - low
            if abs(width) <= 1e-12:
                continue
            left_value = self._number(left["parameters"].get(parameter))
            right_value = self._number(right["parameters"].get(parameter))
            if left_value is None or right_value is None:
                continue
            total += ((left_value - right_value) / width) ** 2
            count += 1
        return math.sqrt(total / count) if count else 0.0

    def _pareto_frontier(self, experiments: list[dict[str, Any]]) -> set[str]:
        frontier = set()
        for experiment in experiments:
            dominated = False
            for other in experiments:
                if other["id"] == experiment["id"]:
                    continue
                if self._dominates(other, experiment):
                    dominated = True
                    break
            if not dominated:
                frontier.add(experiment["id"])
        return frontier

    def _dominates(self, left: dict[str, Any], right: dict[str, Any]) -> bool:
        left_values = (
            self._metric(left, "profit_factor"),
            -self._drawdown(left),
            self._metric(left, "total_trades"),
            self._metric(left, "sharpe"),
        )
        right_values = (
            self._metric(right, "profit_factor"),
            -self._drawdown(right),
            self._metric(right, "total_trades"),
            self._metric(right, "sharpe"),
        )
        return all(x >= y for x, y in zip(left_values, right_values, strict=True)) and any(
            x > y for x, y in zip(left_values, right_values, strict=True)
        )

    def _important_parameters(
        self,
        experiments: list[dict[str, Any]],
        parameters: list[str],
    ) -> list[dict[str, Any]]:
        rows = []
        pf_values = [self._metric(experiment, "profit_factor") for experiment in experiments]
        drawdowns = [self._drawdown(experiment) for experiment in experiments]
        trades = [self._metric(experiment, "total_trades") for experiment in experiments]
        for parameter in parameters:
            values = [
                self._number(experiment["parameters"].get(parameter))
                for experiment in experiments
            ]
            pf_spearman = self._spearman(values, pf_values)
            pf_pearson = self._pearson(values, pf_values)
            drawdown_pearson = self._pearson(values, drawdowns)
            trades_pearson = self._pearson(values, trades)
            importance = (
                abs(pf_spearman or 0.0)
                + abs(pf_pearson or 0.0)
                + 0.50 * abs(drawdown_pearson or 0.0)
                + 0.25 * abs(trades_pearson or 0.0)
            )
            rows.append(
                {
                    "parameter": parameter,
                    "importance_score": importance,
                    "profit_factor_spearman": pf_spearman,
                    "profit_factor_pearson": pf_pearson,
                    "drawdown_pearson": drawdown_pearson,
                    "trades_pearson": trades_pearson,
                }
            )
        rows.sort(key=lambda item: item["importance_score"], reverse=True)
        return rows[: self.config.important_parameter_count]

    def _local_sensitivity(
        self,
        experiments: list[dict[str, Any]],
        important_parameters: list[dict[str, Any]],
        ranges: dict[str, tuple[float, float]],
    ) -> dict[str, Any]:
        output = {}
        for row in important_parameters:
            parameter = row["parameter"]
            values = []
            for experiment in experiments:
                value = self._number(experiment["parameters"].get(parameter))
                if value is not None:
                    values.append(
                        {
                            "id": experiment["id"],
                            "value": value,
                            "profit_factor": self._metric(experiment, "profit_factor"),
                            "drawdown": self._drawdown(experiment),
                            "trades": self._metric(experiment, "total_trades"),
                        }
                    )
            values.sort(key=lambda item: item["value"])
            low, high = ranges[parameter]
            width = high - low if high > low else 1.0
            adjacent = []
            cliffs = []
            for left, right in zip(values, values[1:], strict=False):
                value_delta = (right["value"] - left["value"]) / width
                pf_delta = right["profit_factor"] - left["profit_factor"]
                slope = pf_delta / value_delta if abs(value_delta) > 1e-12 else None
                item = {
                    "left_id": left["id"],
                    "right_id": right["id"],
                    "left_value": left["value"],
                    "right_value": right["value"],
                    "value_delta_normalized": value_delta,
                    "profit_factor_delta": pf_delta,
                    "slope": slope,
                }
                adjacent.append(item)
                if (
                    value_delta <= 0.10
                    and abs(pf_delta) >= self.config.cliff_pf_drop
                    and slope is not None
                ):
                    cliffs.append(item)

            bins = self._binned_parameter(values, "value", "profit_factor", self.config.heatmap_bins)
            stable_regions = [
                bin_row
                for bin_row in bins
                if bin_row["count"] >= 2
                and bin_row["profit_factor_mean"] >= self.config.pf_threshold
                and bin_row["profit_factor_std"] <= self.config.stable_pf_std
            ]
            output[parameter] = {
                "importance": row,
                "adjacent_changes": adjacent,
                "cliffs": sorted(
                    cliffs,
                    key=lambda item: abs(item["profit_factor_delta"]),
                    reverse=True,
                )[:10],
                "stable_regions": stable_regions,
                "binned_profit_factor": bins,
            }
        return output

    def _heatmaps(self, experiments: list[dict[str, Any]]) -> dict[str, Any]:
        output = {}
        for left, right in DEFAULT_HEATMAPS:
            if not all(
                self._number(experiment["parameters"].get(left)) is not None
                and self._number(experiment["parameters"].get(right)) is not None
                for experiment in experiments
            ):
                continue
            output[f"{left}__{right}"] = self._heatmap(experiments, left, right)
        return output

    def _heatmap(
        self,
        experiments: list[dict[str, Any]],
        left: str,
        right: str,
    ) -> dict[str, Any]:
        left_values = [self._number(experiment["parameters"].get(left)) for experiment in experiments]
        right_values = [self._number(experiment["parameters"].get(right)) for experiment in experiments]
        left_clean = [value for value in left_values if value is not None]
        right_clean = [value for value in right_values if value is not None]
        left_min, left_max = min(left_clean), max(left_clean)
        right_min, right_max = min(right_clean), max(right_clean)
        cells: dict[tuple[int, int], list[dict[str, Any]]] = {}
        for experiment in experiments:
            left_index = self._bin_index(
                self._number(experiment["parameters"].get(left)),
                left_min,
                left_max,
                self.config.heatmap_bins,
            )
            right_index = self._bin_index(
                self._number(experiment["parameters"].get(right)),
                right_min,
                right_max,
                self.config.heatmap_bins,
            )
            cells.setdefault((left_index, right_index), []).append(experiment)

        rows = []
        for (left_index, right_index), members in sorted(cells.items()):
            rows.append(
                {
                    "x_bin": left_index,
                    "y_bin": right_index,
                    "x_range": self._bin_range(left_min, left_max, left_index, self.config.heatmap_bins),
                    "y_range": self._bin_range(right_min, right_max, right_index, self.config.heatmap_bins),
                    "count": len(members),
                    "profit_factor_mean": mean(self._metric(item, "profit_factor") for item in members),
                    "drawdown_mean": mean(self._drawdown(item) for item in members),
                    "trades_mean": mean(self._metric(item, "total_trades") for item in members),
                }
            )
        return {
            "x_parameter": left,
            "y_parameter": right,
            "metric_layers": ["profit_factor_mean", "drawdown_mean", "trades_mean"],
            "cells": rows,
        }

    def _clusters(
        self,
        experiments: list[dict[str, Any]],
        parameters: list[str],
        ranges: dict[str, tuple[float, float]],
    ) -> list[dict[str, Any]]:
        k = min(max(1, self.config.cluster_count), len(experiments))
        vectors = [self._vector(experiment, parameters, ranges) for experiment in experiments]
        centers = self._initial_centers(experiments, vectors, k)
        assignments = [0] * len(experiments)
        for _ in range(50):
            changed = False
            for index, vector in enumerate(vectors):
                nearest = min(range(k), key=lambda center: self._vector_distance(vector, centers[center]))
                if nearest != assignments[index]:
                    assignments[index] = nearest
                    changed = True
            new_centers = []
            for cluster_id in range(k):
                members = [vectors[i] for i, assignment in enumerate(assignments) if assignment == cluster_id]
                if not members:
                    new_centers.append(centers[cluster_id])
                    continue
                new_centers.append(
                    [
                        mean(vector[position] for vector in members)
                        for position in range(len(parameters))
                    ]
                )
            centers = new_centers
            if not changed:
                break

        clusters = []
        max_drawdown = self._resolved_max_drawdown(experiments)
        for cluster_id in range(k):
            members = [
                experiment
                for experiment, assignment in zip(experiments, assignments, strict=True)
                if assignment == cluster_id
            ]
            if not members:
                continue
            pf_mean = mean(self._metric(item, "profit_factor") for item in members)
            drawdown_mean = mean(self._drawdown(item) for item in members)
            sharpe_mean = mean(self._metric(item, "sharpe") for item in members)
            trades_mean = mean(self._metric(item, "total_trades") for item in members)
            clusters.append(
                {
                    "cluster_id": cluster_id,
                    "count": len(members),
                    "experiment_ids": [item["id"] for item in members],
                    "profit_factor_mean": pf_mean,
                    "profit_factor_std": pstdev([self._metric(item, "profit_factor") for item in members])
                    if len(members) > 1
                    else 0.0,
                    "drawdown_mean": drawdown_mean,
                    "sharpe_mean": sharpe_mean,
                    "trades_mean": trades_mean,
                    "promising": (
                        pf_mean >= self.config.pf_threshold
                        and drawdown_mean <= max_drawdown
                        and trades_mean >= self.config.min_trades
                    ),
                    "parameter_ranges": self._parameter_box(members, parameters),
                }
            )
        clusters.sort(
            key=lambda item: (
                item["promising"],
                item["profit_factor_mean"],
                -item["drawdown_mean"],
                item["trades_mean"],
            ),
            reverse=True,
        )
        return clusters

    def _initial_centers(
        self,
        experiments: list[dict[str, Any]],
        vectors: list[list[float]],
        k: int,
    ) -> list[list[float]]:
        ordered = sorted(
            range(len(experiments)),
            key=lambda index: self._metric(experiments[index], "profit_factor"),
        )
        if k == 1:
            return [vectors[ordered[-1]]]
        centers = []
        for i in range(k):
            position = round(i * (len(ordered) - 1) / (k - 1))
            centers.append(list(vectors[ordered[position]]))
        return centers

    def _vector(
        self,
        experiment: dict[str, Any],
        parameters: list[str],
        ranges: dict[str, tuple[float, float]],
    ) -> list[float]:
        vector = []
        for parameter in parameters:
            low, high = ranges[parameter]
            value = self._number(experiment["parameters"].get(parameter))
            if value is None or high == low:
                vector.append(0.0)
            else:
                vector.append((value - low) / (high - low))
        return vector

    def _vector_distance(self, left: list[float], right: list[float]) -> float:
        return math.sqrt(
            sum((x - y) ** 2 for x, y in zip(left, right, strict=True)) / len(left)
        )

    def _optimal_regions(
        self,
        experiments: list[dict[str, Any]],
        clusters: list[dict[str, Any]],
        important_parameters: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        max_drawdown = self._resolved_max_drawdown(experiments)
        important_names = [row["parameter"] for row in important_parameters]
        by_id = {experiment["id"]: experiment for experiment in experiments}
        regions = []
        for cluster in clusters:
            members = [
                by_id[experiment_id]
                for experiment_id in cluster["experiment_ids"]
                if experiment_id in by_id
            ]
            qualifying = [
                experiment
                for experiment in members
                if self._metric(experiment, "profit_factor") >= self.config.pf_threshold
                and self._drawdown(experiment) <= max_drawdown
                and self._metric(experiment, "total_trades") >= self.config.min_trades
            ]
            if not qualifying:
                continue
            regions.append(
                {
                    "cluster_id": cluster["cluster_id"],
                    "qualifying_count": len(qualifying),
                    "experiment_ids": [experiment["id"] for experiment in qualifying],
                    "profit_factor_mean": mean(
                        self._metric(experiment, "profit_factor")
                        for experiment in qualifying
                    ),
                    "drawdown_mean": mean(self._drawdown(experiment) for experiment in qualifying),
                    "trades_mean": mean(
                        self._metric(experiment, "total_trades")
                        for experiment in qualifying
                    ),
                    "parameter_ranges": self._parameter_box(qualifying, important_names),
                }
            )
        regions.sort(
            key=lambda item: (
                item["qualifying_count"],
                item["profit_factor_mean"],
                -item["drawdown_mean"],
            ),
            reverse=True,
        )
        return regions

    def _scientific_scores(
        self,
        experiments: list[dict[str, Any]],
        robust_rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        robustness_by_id = {row["id"]: row for row in robust_rows}
        pf_values = [self._metric(item, "profit_factor") for item in experiments]
        drawdown_values = [self._drawdown(item) for item in experiments]
        sharpe_values = [self._metric(item, "sharpe") for item in experiments]
        trade_values = [self._metric(item, "total_trades") for item in experiments]
        weights = self.config.normalized_weights
        scored = []
        for experiment in experiments:
            robust = robustness_by_id[experiment["id"]]
            components = {
                "local_stability": robust["local_stability_score"],
                "profit_factor": self._normalize(
                    self._metric(experiment, "profit_factor"), pf_values
                ),
                "drawdown": 1.0 - self._normalize(self._drawdown(experiment), drawdown_values),
                "sharpe": self._normalize(self._metric(experiment, "sharpe"), sharpe_values),
                "trades": self._normalize(self._metric(experiment, "total_trades"), trade_values),
            }
            score = sum(components[key] * weights.get(key, 0.0) for key in components)
            scored.append(
                {
                    "id": experiment["id"],
                    "robustness_score": score,
                    "score_components": components,
                    "local_robustness": robust,
                    "profit_factor": self._metric(experiment, "profit_factor"),
                    "drawdown": self._drawdown(experiment),
                    "sharpe": self._metric(experiment, "sharpe"),
                    "total_trades": self._metric(experiment, "total_trades"),
                }
            )
        scored.sort(key=lambda item: item["robustness_score"], reverse=True)
        return scored

    def _recommendations(
        self,
        *,
        scored: list[dict[str, Any]],
        pareto_ids: set[str],
        clusters: list[dict[str, Any]],
        optimal_regions: list[dict[str, Any]],
        sensitivity: dict[str, Any],
    ) -> list[str]:
        recommendations = []
        top = scored[0] if scored else None
        if top:
            recommendations.append(
                "Use robustness_score for candidate selection; "
                f"current top robust experiment is {top['id']}."
            )
        if pareto_ids:
            recommendations.append(
                f"Pareto frontier contains {len(pareto_ids)} experiments; "
                "prefer candidates that are both robust and Pareto-efficient."
            )
        promising = [cluster for cluster in clusters if cluster["promising"]]
        if promising:
            recommendations.append(
                f"{len(promising)} parameter clusters satisfy the configured "
                "promising-region criteria."
            )
        else:
            recommendations.append(
                "No cluster satisfied all configured promising-region criteria; "
                "consider lowering PF threshold or raising sample size."
            )
        cliff_count = sum(len(row["cliffs"]) for row in sensitivity.values())
        if cliff_count:
            recommendations.append(
                f"Detected {cliff_count} local performance cliffs; avoid selecting "
                "single-point optima near those parameter changes."
            )
        if optimal_regions:
            recommendations.append(
                "Optimal-region JSON was exported with continuous parameter boxes "
                "that satisfy PF, drawdown and trade-count constraints."
            )
        else:
            recommendations.append(
                "No continuous optimal region matched the current thresholds."
            )
        return recommendations

    def _resolved_max_drawdown(self, experiments: list[dict[str, Any]]) -> float:
        if self.config.max_drawdown is not None:
            return self.config.max_drawdown
        values = sorted(self._drawdown(experiment) for experiment in experiments)
        if not values:
            return 0.0
        return median(values)

    def _parameter_box(
        self,
        experiments: list[dict[str, Any]],
        parameters: list[str],
    ) -> dict[str, dict[str, float]]:
        box = {}
        for parameter in parameters:
            values = [
                self._number(experiment["parameters"].get(parameter))
                for experiment in experiments
            ]
            clean = [value for value in values if value is not None]
            if clean:
                box[parameter] = {
                    "min": min(clean),
                    "max": max(clean),
                    "mean": mean(clean),
                }
        return box

    def _binned_parameter(
        self,
        values: list[dict[str, Any]],
        value_key: str,
        metric_key: str,
        bins: int,
    ) -> list[dict[str, Any]]:
        if not values:
            return []
        low = min(item[value_key] for item in values)
        high = max(item[value_key] for item in values)
        grouped: dict[int, list[dict[str, Any]]] = {}
        for item in values:
            index = self._bin_index(item[value_key], low, high, bins)
            grouped.setdefault(index, []).append(item)
        output = []
        for index, members in sorted(grouped.items()):
            metric_values = [member[metric_key] for member in members]
            output.append(
                {
                    "bin": index,
                    "range": self._bin_range(low, high, index, bins),
                    "count": len(members),
                    "profit_factor_mean": mean(metric_values),
                    "profit_factor_std": pstdev(metric_values)
                    if len(metric_values) > 1
                    else 0.0,
                }
            )
        return output

    def _bin_index(self, value: float | None, low: float, high: float, bins: int) -> int:
        if value is None or high == low:
            return 0
        return min(bins - 1, max(0, int((value - low) / (high - low) * bins)))

    def _bin_range(self, low: float, high: float, index: int, bins: int) -> dict[str, float]:
        width = (high - low) / bins if bins else 0.0
        return {"min": low + index * width, "max": low + (index + 1) * width}

    def _normalize(self, value: float, values: list[float]) -> float:
        low = min(values)
        high = max(values)
        if high == low:
            return 1.0
        return (value - low) / (high - low)

    def _metric(self, experiment: dict[str, Any], key: str) -> float:
        return self._number(experiment["metrics"].get(key)) or 0.0

    def _drawdown(self, experiment: dict[str, Any]) -> float:
        metrics = experiment["metrics"]
        return (
            self._number(metrics.get("max_drawdown_abs"))
            or self._number(metrics.get("max_relative_drawdown"))
            or 0.0
        )

    def _number(self, value: Any) -> float | None:
        try:
            if value is None or isinstance(value, bool):
                return None
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        if math.isnan(parsed) or math.isinf(parsed):
            return None
        return parsed

    def _pearson(
        self,
        left: list[float | None],
        right: list[float | None],
    ) -> float | None:
        pairs = [
            (x, y)
            for x, y in zip(left, right, strict=True)
            if x is not None and y is not None
        ]
        if len(pairs) < 3:
            return None
        left_values, right_values = zip(*pairs, strict=True)
        left_mean = mean(left_values)
        right_mean = mean(right_values)
        numerator = sum((x - left_mean) * (y - right_mean) for x, y in pairs)
        denominator = math.sqrt(
            sum((x - left_mean) ** 2 for x in left_values)
            * sum((y - right_mean) ** 2 for y in right_values)
        )
        return numerator / denominator if denominator else None

    def _spearman(
        self,
        left: list[float | None],
        right: list[float | None],
    ) -> float | None:
        pairs = [
            (x, y)
            for x, y in zip(left, right, strict=True)
            if x is not None and y is not None
        ]
        if len(pairs) < 3:
            return None
        left_values, right_values = zip(*pairs, strict=True)
        return self._pearson(self._ranks(list(left_values)), self._ranks(list(right_values)))

    def _ranks(self, values: list[float]) -> list[float]:
        ordered = sorted((value, index) for index, value in enumerate(values))
        ranks = [0.0] * len(values)
        index = 0
        while index < len(ordered):
            end = index
            while end + 1 < len(ordered) and ordered[end + 1][0] == ordered[index][0]:
                end += 1
            rank = (index + end + 2) / 2.0
            for _, original_index in ordered[index : end + 1]:
                ranks[original_index] = rank
            index = end + 1
        return ranks

    def _render_html(self, analysis: dict[str, Any]) -> str:
        payload = json.dumps(analysis, ensure_ascii=False)
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Robustness Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2933; }}
    table {{ border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 13px; }}
    th, td {{ border: 1px solid #d9e2ec; padding: 6px 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f0f4f8; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 18px; }}
    .metric {{ display: inline-block; border: 1px solid #d9e2ec; padding: 8px 10px; margin: 4px 8px 4px 0; }}
    canvas {{ width: 100%; height: 240px; border: 1px solid #d9e2ec; }}
    code {{ white-space: pre-wrap; }}
  </style>
</head>
<body>
  <h1>Robustness Report</h1>
  <p><strong>Session:</strong> <span id="session"></span></p>
  <div id="summary"></div>
  <div class="grid">
    <canvas id="scoreDistribution"></canvas>
    <canvas id="pfDrawdown"></canvas>
    <canvas id="clusterChart"></canvas>
    <canvas id="paretoChart"></canvas>
  </div>
  <h2>Top 50 by Robustness Score</h2>
  <table id="top"></table>
  <h2>Pareto Frontier</h2>
  <table id="pareto"></table>
  <h2>Clusters</h2>
  <table id="clusters"></table>
  <h2>Heatmaps</h2>
  <div id="heatmaps"></div>
  <h2>Optimal Regions</h2>
  <table id="regions"></table>
  <h2>Recommendations</h2>
  <ul id="recommendations"></ul>
  <script>
    const data = {payload};
    document.getElementById('session').textContent = data.session_id;
    document.getElementById('summary').innerHTML =
      `<span class="metric"><strong>Experiments</strong><br>${{data.experiment_count}}</span>` +
      `<span class="metric"><strong>Pareto</strong><br>${{data.pareto_frontier.length}}</span>` +
      `<span class="metric"><strong>Clusters</strong><br>${{data.clusters.length}}</span>` +
      `<span class="metric"><strong>Optimal regions</strong><br>${{data.optimal_regions.length}}</span>`;

    function number(value) {{
      const parsed = Number(value || 0);
      return Number.isFinite(parsed) ? parsed : 0;
    }}

    function fmt(value, digits = 4) {{
      return number(value).toFixed(digits);
    }}

    function table(id, headers, rows) {{
      document.getElementById(id).innerHTML =
        '<tr>' + headers.map(header => `<th>${{header}}</th>`).join('') + '</tr>' +
        rows.map(row => '<tr>' + row.map(cell => `<td>${{cell}}</td>`).join('') + '</tr>').join('');
    }}

    function renderTop() {{
      const rows = data.robustness_ranking.slice(0, 50).map(row => [
        row.id,
        fmt(row.robustness_score),
        fmt(row.profit_factor),
        fmt(row.drawdown),
        fmt(row.sharpe),
        fmt(row.total_trades, 0),
        fmt(row.local_robustness.neighbor_profit_factor_mean),
        fmt(row.local_robustness.neighbor_profit_factor_std),
        row.pareto_frontier ? 'yes' : 'no',
      ]);
      table('top', ['ID', 'Robustness', 'PF', 'Drawdown', 'Sharpe', 'Trades', 'Neighbor PF mean', 'Neighbor PF std', 'Pareto'], rows);
    }}

    function renderPareto() {{
      const rows = data.pareto_frontier.map(row => [
        row.id,
        fmt(row.robustness_score),
        fmt(row.profit_factor),
        fmt(row.drawdown),
        fmt(row.sharpe),
        fmt(row.total_trades, 0),
      ]);
      table('pareto', ['ID', 'Robustness', 'PF', 'Drawdown', 'Sharpe', 'Trades'], rows);
    }}

    function renderClusters() {{
      const rows = data.clusters.map(row => [
        row.cluster_id,
        row.count,
        fmt(row.profit_factor_mean),
        fmt(row.drawdown_mean),
        fmt(row.sharpe_mean),
        fmt(row.trades_mean),
        row.promising ? 'yes' : 'no',
      ]);
      table('clusters', ['Cluster', 'Count', 'PF mean', 'Drawdown mean', 'Sharpe mean', 'Trades mean', 'Promising'], rows);
    }}

    function renderRegions() {{
      const rows = data.optimal_regions.map(row => [
        row.cluster_id,
        row.qualifying_count,
        fmt(row.profit_factor_mean),
        fmt(row.drawdown_mean),
        fmt(row.trades_mean),
        `<code>${{JSON.stringify(row.parameter_ranges)}}</code>`,
      ]);
      table('regions', ['Cluster', 'Count', 'PF mean', 'Drawdown mean', 'Trades mean', 'Parameter ranges'], rows);
    }}

    function renderRecommendations() {{
      document.getElementById('recommendations').innerHTML =
        data.recommendations.map(item => `<li>${{item}}</li>`).join('');
    }}

    function drawHistogram(id, values, title) {{
      const canvas = document.getElementById(id);
      const ctx = canvas.getContext('2d');
      canvas.width = canvas.clientWidth * devicePixelRatio;
      canvas.height = canvas.clientHeight * devicePixelRatio;
      ctx.scale(devicePixelRatio, devicePixelRatio);
      const w = canvas.clientWidth, h = canvas.clientHeight;
      ctx.clearRect(0, 0, w, h);
      ctx.fillText(title, 12, 18);
      const clean = values.filter(Number.isFinite);
      const min = Math.min(...clean, 0), max = Math.max(...clean, 1);
      const bins = 14, counts = Array(bins).fill(0);
      clean.forEach(value => {{
        const index = Math.min(bins - 1, Math.max(0, Math.floor((value - min) / (max - min || 1) * bins)));
        counts[index]++;
      }});
      const maxCount = Math.max(...counts, 1);
      const barWidth = (w - 24) / bins;
      counts.forEach((count, index) => {{
        const barHeight = (h - 48) * count / maxCount;
        ctx.fillRect(12 + index * barWidth, h - 24 - barHeight, barWidth - 2, barHeight);
      }});
    }}

    function drawScatter(id, rows, xKey, yKey, title, paretoOnly = false) {{
      const canvas = document.getElementById(id);
      const ctx = canvas.getContext('2d');
      canvas.width = canvas.clientWidth * devicePixelRatio;
      canvas.height = canvas.clientHeight * devicePixelRatio;
      ctx.scale(devicePixelRatio, devicePixelRatio);
      const w = canvas.clientWidth, h = canvas.clientHeight;
      ctx.clearRect(0, 0, w, h);
      ctx.fillText(title, 12, 18);
      const xs = rows.map(row => number(row[xKey]));
      const ys = rows.map(row => number(row[yKey]));
      const maxX = Math.max(...xs, 1), maxY = Math.max(...ys, 1);
      rows.forEach(row => {{
        const x = 40 + number(row[xKey]) / maxX * (w - 60);
        const y = h - 30 - number(row[yKey]) / maxY * (h - 60);
        ctx.fillStyle = row.pareto_frontier || paretoOnly ? '#2f6f73' : '#9fb3c8';
        ctx.beginPath();
        ctx.arc(x, y, row.pareto_frontier ? 5 : 3, 0, Math.PI * 2);
        ctx.fill();
      }});
    }}

    function renderHeatmaps() {{
      const container = document.getElementById('heatmaps');
      container.innerHTML = '';
      Object.entries(data.heatmaps).forEach(([name, heatmap]) => {{
        const tableRows = heatmap.cells.map(cell => [
          `${{cell.x_range.min.toFixed(3)}}-${{cell.x_range.max.toFixed(3)}}`,
          `${{cell.y_range.min.toFixed(3)}}-${{cell.y_range.max.toFixed(3)}}`,
          cell.count,
          fmt(cell.profit_factor_mean),
          fmt(cell.drawdown_mean),
          fmt(cell.trades_mean),
        ]);
        const section = document.createElement('section');
        section.innerHTML = `<h3>${{heatmap.x_parameter}} x ${{heatmap.y_parameter}}</h3>`;
        const tableEl = document.createElement('table');
        tableEl.innerHTML =
          '<tr><th>X range</th><th>Y range</th><th>Count</th><th>PF</th><th>Drawdown</th><th>Trades</th></tr>' +
          tableRows.map(row => '<tr>' + row.map(cell => `<td>${{cell}}</td>`).join('') + '</tr>').join('');
        section.appendChild(tableEl);
        container.appendChild(section);
      }});
    }}

    renderTop();
    renderPareto();
    renderClusters();
    renderRegions();
    renderRecommendations();
    renderHeatmaps();
    drawHistogram('scoreDistribution', data.robustness_ranking.map(row => number(row.robustness_score)), 'Robustness Score Distribution');
    drawScatter('pfDrawdown', data.robustness_ranking, 'drawdown', 'profit_factor', 'PF vs Drawdown');
    drawScatter('paretoChart', data.robustness_ranking, 'total_trades', 'profit_factor', 'PF vs Trades');
    drawHistogram('clusterChart', data.clusters.map(row => number(row.profit_factor_mean)), 'Cluster PF Mean Distribution');
  </script>
</body>
</html>
"""


def _load_weights(value: str | None) -> dict[str, float] | None:
    if not value:
        return None
    path = Path(value)
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return json.loads(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze experiment robustness from SQLite only.")
    parser.add_argument("session_id")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--neighbors", type=int, default=10)
    parser.add_argument("--clusters", type=int, default=6)
    parser.add_argument("--heatmap-bins", type=int, default=6)
    parser.add_argument("--important-parameters", type=int, default=12)
    parser.add_argument("--pf-threshold", type=float, default=1.0)
    parser.add_argument("--min-trades", type=int, default=20)
    parser.add_argument("--max-drawdown", type=float)
    parser.add_argument("--cliff-pf-drop", type=float, default=0.50)
    parser.add_argument("--stable-pf-std", type=float, default=0.25)
    parser.add_argument("--weights-json")
    args = parser.parse_args()

    config = RobustnessConfig(
        neighbor_count=args.neighbors,
        cluster_count=args.clusters,
        heatmap_bins=args.heatmap_bins,
        important_parameter_count=args.important_parameters,
        pf_threshold=args.pf_threshold,
        min_trades=args.min_trades,
        max_drawdown=args.max_drawdown,
        cliff_pf_drop=args.cliff_pf_drop,
        stable_pf_std=args.stable_pf_std,
        weights=_load_weights(args.weights_json),
    )
    analyzer = RobustnessAnalyzer(
        db_path=args.db_path,
        output_dir=args.output_dir,
        config=config,
    )
    paths = analyzer.write_reports(args.session_id)
    print(json.dumps({key: str(value) for key, value in paths.items()}, indent=2))


if __name__ == "__main__":
    main()
