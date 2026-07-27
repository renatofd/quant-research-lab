from __future__ import annotations

import argparse
import hashlib
import json
import math
import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from random import Random
from statistics import mean
from typing import Any

try:
    from .experiment_database import ExperimentDatabase
    from .experiment_manager import ExperimentManager
    from .strategy_plugins.registry import create_plugin
except ImportError:
    from experiment_database import ExperimentDatabase
    from experiment_manager import ExperimentManager
    from strategy_plugins.registry import create_plugin


DEFAULT_METRICS = (
    "profit_factor",
    "max_drawdown_abs",
    "sharpe",
    "expectancy",
    "winrate",
    "total_trades",
)


class TrendParameterSpace:
    def __init__(self, *, seed: int | None = None) -> None:
        self.plugin = create_plugin("TrendStrategy")
        self.spec = self.plugin.get_parameters()
        self.random = Random(seed)

    def sample_wide(self, count: int) -> list[dict[str, Any]]:
        samples = []
        attempts = 0
        while len(samples) < count and attempts < count * 200:
            attempts += 1
            parameters = {
                name: self._sample_from_spec(spec)
                for name, spec in self.spec.items()
            }
            if self._is_valid(parameters):
                samples.append(self._experiment(parameters))
        return samples

    def sample_refined(
        self,
        completed_experiments: list[dict[str, Any]],
        *,
        count: int,
        top_fraction: float = 0.10,
        expansion: float = 0.25,
    ) -> list[dict[str, Any]]:
        top = self._top_experiments(completed_experiments, top_fraction=top_fraction)
        if not top:
            return self.sample_wide(count)

        refined_ranges = self.refined_ranges(top, expansion=expansion)
        samples = []
        attempts = 0
        while len(samples) < count and attempts < count * 200:
            attempts += 1
            parameters = {
                name: self._sample_from_range(name, bounds)
                for name, bounds in refined_ranges.items()
            }
            if self._is_valid(parameters):
                samples.append(self._experiment(parameters))
        return samples

    def refined_ranges(
        self,
        top_experiments: list[dict[str, Any]],
        *,
        expansion: float = 0.25,
    ) -> dict[str, dict[str, Any]]:
        ranges = {}
        for name, spec in self.spec.items():
            values = [
                self._number(self._plugin_parameters(experiment).get(name))
                for experiment in top_experiments
            ]
            values = [value for value in values if value is not None]
            if not values:
                ranges[name] = dict(spec)
                continue

            low = min(values)
            high = max(values)
            span = high - low
            fallback_span = float(spec["max"]) - float(spec["min"])
            padding = max(span * expansion, fallback_span * 0.05)
            ranges[name] = {
                **spec,
                "min": max(float(spec["min"]), low - padding),
                "max": min(float(spec["max"]), high + padding),
            }
        return ranges

    def _top_experiments(
        self,
        experiments: list[dict[str, Any]],
        *,
        top_fraction: float,
    ) -> list[dict[str, Any]]:
        completed = [
            experiment
            for experiment in experiments
            if experiment.get("metrics") and self._plugin_name(experiment) == "TrendStrategy"
        ]
        ranked = sorted(
            completed,
            key=lambda experiment: self._number(
                experiment.get("metrics", {}).get("profit_factor")
            )
            or 0.0,
            reverse=True,
        )
        return ranked[: max(1, int(len(ranked) * top_fraction))]

    def _sample_from_spec(self, spec: dict[str, Any]) -> int | float:
        return self._sample_from_range("", spec)

    def _sample_from_range(self, name: str, spec: dict[str, Any]) -> int | float:
        if spec["type"] == "int":
            return self.random.randint(math.ceil(spec["min"]), math.floor(spec["max"]))
        value = self.random.uniform(float(spec["min"]), float(spec["max"]))
        decimals = 4 if name in {"roi", "stoploss"} else 3
        return round(value, decimals)

    def _is_valid(self, parameters: dict[str, Any]) -> bool:
        if parameters["ema_fast_period"] >= parameters["ema_slow_period"]:
            return False
        if parameters["ema_slow_period"] >= parameters["ema_trend_period"]:
            return False
        if parameters["rsi_min"] >= parameters["rsi_max"]:
            return False
        if parameters["adx_exit_threshold"] >= parameters["adx_entry_threshold"]:
            return False
        if parameters["stoploss"] >= 0:
            return False
        return True

    def _experiment(self, plugin_parameters: dict[str, Any]) -> dict[str, Any]:
        return {
            "experiment_type": "strategy_plugin",
            "strategy_plugin": "TrendStrategy",
            "research_phase": "unassigned",
            "plugin_parameters": plugin_parameters,
        }

    def _plugin_name(self, experiment: dict[str, Any]) -> str:
        return experiment.get("parameters", {}).get("strategy_plugin", "")

    def _plugin_parameters(self, experiment: dict[str, Any]) -> dict[str, Any]:
        return experiment.get("parameters", {}).get("plugin_parameters", {})

    def _number(self, value: Any) -> float | None:
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None


class TrendResearchAnalyzer:
    def __init__(self) -> None:
        self.parameter_space = TrendParameterSpace()
        self.parameter_names = tuple(self.parameter_space.spec)

    def analyze(self, experiments: list[dict[str, Any]]) -> dict[str, Any]:
        completed = [
            experiment
            for experiment in experiments
            if experiment.get("metrics")
            and experiment.get("parameters", {}).get("strategy_plugin") == "TrendStrategy"
        ]
        ranked = sorted(
            completed,
            key=lambda experiment: self._metric(experiment, "profit_factor"),
            reverse=True,
        )
        top_10_percent = ranked[: max(1, int(len(ranked) * 0.10))] if ranked else []

        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "experiment_count": len(experiments),
            "completed_count": len(completed),
            "top_100": self._top_rows(ranked[:100]),
            "importance": self._importance(completed),
            "correlation_matrix": self._correlation_matrix(completed),
            "best_value_distribution": self._best_value_distribution(top_10_percent),
            "interactions": self._interactions(completed),
            "heatmaps": self._heatmaps(completed),
            "evolution": self._evolution(completed),
            "diversity": self._diversity(completed),
            "recommendations": self._recommendations(completed),
        }

    def _importance(self, experiments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows = []
        for parameter in self.parameter_names:
            values = [self._parameter(experiment, parameter) for experiment in experiments]
            profit_factor = [self._metric(experiment, "profit_factor") for experiment in experiments]
            drawdown = [self._metric(experiment, "max_drawdown_abs") for experiment in experiments]
            sensitivity = self._bin_sensitivity(experiments, parameter, "profit_factor")
            rows.append(
                {
                    "parameter": parameter,
                    "profit_factor_pearson": self._pearson(values, profit_factor),
                    "profit_factor_spearman": self._spearman(values, profit_factor),
                    "drawdown_pearson": self._pearson(values, drawdown),
                    "sensitivity": sensitivity,
                    "importance_score": self._importance_score(values, profit_factor, sensitivity),
                }
            )
        return sorted(rows, key=lambda row: row["importance_score"], reverse=True)

    def _correlation_matrix(self, experiments: list[dict[str, Any]]) -> dict[str, dict[str, float | None]]:
        names = [*self.parameter_names, *DEFAULT_METRICS]
        columns = {
            name: [
                self._parameter(experiment, name)
                if name in self.parameter_names
                else self._metric(experiment, name)
                for experiment in experiments
            ]
            for name in names
        }
        return {
            left: {
                right: self._pearson(columns[left], columns[right])
                for right in names
            }
            for left in names
        }

    def _best_value_distribution(
        self,
        top_experiments: list[dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        output = {}
        for parameter in self.parameter_names:
            counter = Counter(
                self._parameter(experiment, parameter)
                for experiment in top_experiments
            )
            output[parameter] = [
                {"value": value, "count": count}
                for value, count in counter.most_common()
            ]
        return output

    def _interactions(self, experiments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        global_mean = self._mean(
            [self._metric(experiment, "profit_factor") for experiment in experiments]
        )
        rows = []
        for index, left in enumerate(self.parameter_names):
            for right in self.parameter_names[index + 1 :]:
                strength = self._interaction_strength(experiments, left, right, global_mean)
                rows.append(
                    {
                        "left": left,
                        "right": right,
                        "metric": "profit_factor",
                        "interaction_strength": strength,
                    }
                )
        return sorted(rows, key=lambda row: row["interaction_strength"], reverse=True)[:50]

    def _heatmaps(self, experiments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        heatmaps = []
        for interaction in self._interactions(experiments)[:10]:
            left = interaction["left"]
            right = interaction["right"]
            cells: dict[str, list[float]] = defaultdict(list)
            for experiment in experiments:
                left_bin = self._bin_label(self._parameter(experiment, left), left)
                right_bin = self._bin_label(self._parameter(experiment, right), right)
                cells[f"{left_bin}|{right_bin}"].append(
                    self._metric(experiment, "profit_factor")
                )
            heatmaps.append(
                {
                    "left": left,
                    "right": right,
                    "cells": [
                        {
                            "left_bin": key.split("|", 1)[0],
                            "right_bin": key.split("|", 1)[1],
                            "count": len(values),
                            "profit_factor_mean": self._mean(values),
                        }
                        for key, values in sorted(cells.items())
                    ],
                }
            )
        return heatmaps

    def _evolution(self, experiments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ordered = sorted(experiments, key=lambda experiment: experiment.get("updated_at") or "")
        best_profit_factor = -math.inf
        rows = []
        for index, experiment in enumerate(ordered, start=1):
            best_profit_factor = max(best_profit_factor, self._metric(experiment, "profit_factor"))
            rows.append(
                {
                    "index": index,
                    "experiment_id": experiment["id"],
                    "profit_factor": self._metric(experiment, "profit_factor"),
                    "best_profit_factor": best_profit_factor,
                    "drawdown": self._metric(experiment, "max_drawdown_abs"),
                    "sharpe": self._metric(experiment, "sharpe"),
                    "expectancy": self._metric(experiment, "expectancy"),
                }
            )
        return rows

    def _diversity(self, experiments: list[dict[str, Any]]) -> dict[str, Any]:
        rows = {}
        for parameter in self.parameter_names:
            values = [self._parameter(experiment, parameter) for experiment in experiments]
            clean = [value for value in values if value is not None]
            rows[parameter] = {
                "unique_values": len(set(clean)),
                "min": min(clean) if clean else None,
                "max": max(clean) if clean else None,
                "diversity_ratio": len(set(clean)) / len(clean) if clean else 0.0,
            }
        return rows

    def _recommendations(self, experiments: list[dict[str, Any]]) -> dict[str, Any]:
        importance = self._importance(experiments)
        important = [row for row in importance if row["importance_score"] >= 0.10]
        fixable = [row for row in importance if row["importance_score"] < 0.05]
        return {
            "important_parameters": important,
            "fixable_parameters": fixable,
            "high_interactions": self._interactions(experiments)[:10],
            "best_intervals": self._best_intervals(experiments),
        }

    def _best_intervals(self, experiments: list[dict[str, Any]]) -> dict[str, Any]:
        output = {}
        for parameter in self.parameter_names:
            grouped: dict[str, list[float]] = defaultdict(list)
            for experiment in experiments:
                grouped[self._bin_label(self._parameter(experiment, parameter), parameter)].append(
                    self._metric(experiment, "profit_factor")
                )
            intervals = [
                {
                    "interval": interval,
                    "count": len(values),
                    "profit_factor_mean": self._mean(values),
                }
                for interval, values in grouped.items()
            ]
            output[parameter] = sorted(
                intervals,
                key=lambda row: row["profit_factor_mean"],
                reverse=True,
            )[:5]
        return output

    def _top_rows(self, experiments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "id": experiment["id"],
                "profit_factor": self._metric(experiment, "profit_factor"),
                "drawdown": self._metric(experiment, "max_drawdown_abs"),
                "sharpe": self._metric(experiment, "sharpe"),
                "expectancy": self._metric(experiment, "expectancy"),
                "winrate": self._metric(experiment, "winrate"),
                "total_trades": self._metric(experiment, "total_trades"),
                "parameters": experiment.get("parameters", {}).get("plugin_parameters", {}),
            }
            for experiment in experiments
        ]

    def _interaction_strength(
        self,
        experiments: list[dict[str, Any]],
        left: str,
        right: str,
        global_mean: float,
    ) -> float:
        left_means: dict[str, list[float]] = defaultdict(list)
        right_means: dict[str, list[float]] = defaultdict(list)
        pair_means: dict[tuple[str, str], list[float]] = defaultdict(list)
        for experiment in experiments:
            value = self._metric(experiment, "profit_factor")
            left_bin = self._bin_label(self._parameter(experiment, left), left)
            right_bin = self._bin_label(self._parameter(experiment, right), right)
            left_means[left_bin].append(value)
            right_means[right_bin].append(value)
            pair_means[(left_bin, right_bin)].append(value)

        residuals = []
        for (left_bin, right_bin), values in pair_means.items():
            expected = (
                self._mean(left_means[left_bin])
                + self._mean(right_means[right_bin])
                - global_mean
            )
            residuals.append(abs(self._mean(values) - expected))
        return max(residuals) if residuals else 0.0

    def _bin_sensitivity(
        self,
        experiments: list[dict[str, Any]],
        parameter: str,
        metric: str,
    ) -> float:
        grouped: dict[str, list[float]] = defaultdict(list)
        for experiment in experiments:
            grouped[self._bin_label(self._parameter(experiment, parameter), parameter)].append(
                self._metric(experiment, metric)
            )
        means = [self._mean(values) for values in grouped.values() if values]
        return max(means) - min(means) if len(means) >= 2 else 0.0

    def _importance_score(
        self,
        values: list[Any],
        target: list[float],
        sensitivity: float,
    ) -> float:
        spearman = self._spearman(values, target)
        target_mean = abs(self._mean(target)) or 1.0
        normalized_sensitivity = abs(sensitivity) / target_mean
        return abs(spearman or 0.0) * 0.60 + normalized_sensitivity * 0.40

    def _bin_label(self, value: Any, parameter: str, bins: int = 5) -> str:
        numeric = self._number(value)
        if numeric is None:
            return "n/a"
        spec = self.parameter_space.spec[parameter]
        if spec["type"] == "int" and (float(spec["max"]) - float(spec["min"])) <= bins:
            return str(int(numeric))
        width = (float(spec["max"]) - float(spec["min"])) / bins
        if width <= 0:
            return str(numeric)
        index = min(bins - 1, max(0, int((numeric - float(spec["min"])) / width)))
        low = float(spec["min"]) + index * width
        high = low + width
        return f"{low:.4g}-{high:.4g}"

    def _parameter(self, experiment: dict[str, Any], parameter: str) -> Any:
        return experiment.get("parameters", {}).get("plugin_parameters", {}).get(parameter)

    def _metric(self, experiment: dict[str, Any], metric: str) -> float:
        value = experiment.get("metrics", {}).get(metric)
        return self._number(value) or 0.0

    def _pearson(self, left: list[Any], right: list[Any]) -> float | None:
        pairs = [
            (self._number(x), self._number(y))
            for x, y in zip(left, right, strict=True)
        ]
        pairs = [(x, y) for x, y in pairs if x is not None and y is not None]
        if len(pairs) < 3:
            return None
        xs, ys = zip(*pairs, strict=True)
        mean_x = mean(xs)
        mean_y = mean(ys)
        denominator = math.sqrt(
            sum((x - mean_x) ** 2 for x in xs)
            * sum((y - mean_y) ** 2 for y in ys)
        )
        if not denominator:
            return None
        return sum((x - mean_x) * (y - mean_y) for x, y in pairs) / denominator

    def _spearman(self, left: list[Any], right: list[Any]) -> float | None:
        pairs = [
            (self._number(x), self._number(y))
            for x, y in zip(left, right, strict=True)
        ]
        pairs = [(x, y) for x, y in pairs if x is not None and y is not None]
        if len(pairs) < 3:
            return None
        xs, ys = zip(*pairs, strict=True)
        return self._pearson(self._ranks(list(xs)), self._ranks(list(ys)))

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

    def _mean(self, values: list[float]) -> float:
        clean = [value for value in values if value is not None]
        return sum(clean) / len(clean) if clean else 0.0

    def _number(self, value: Any) -> float | None:
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None


class TrendResearchEngine:
    def __init__(
        self,
        *,
        database: ExperimentDatabase | None = None,
        manager: ExperimentManager | None = None,
        seed: int | None = None,
    ) -> None:
        self.database = database or ExperimentDatabase()
        self.manager = manager or ExperimentManager(database=self.database)
        self.parameter_space = TrendParameterSpace(seed=seed)
        self.analyzer = TrendResearchAnalyzer()

    def create_session(
        self,
        *,
        objective: str = "TrendStrategy two-phase research",
        max_experiments: int,
        phase1_experiments: int,
        refinement_batch_size: int,
        convergence_patience: int = 3,
        convergence_min_delta: float = 0.02,
    ) -> str:
        session_id = self._session_id(objective)
        self.database.create_session(
            session_id=session_id,
            objective=objective,
            strategy_name="LabPluginStrategy",
            search_method="trend_two_phase",
            goals={
                "max_experiments": max_experiments,
                "phase1_experiments": phase1_experiments,
                "refinement_batch_size": refinement_batch_size,
                "convergence_patience": convergence_patience,
                "convergence_min_delta": convergence_min_delta,
            },
            metadata={
                "strategy_plugin": "TrendStrategy",
                "research_phase": "created",
            },
            status="paused",
        )
        return session_id

    def plan_exploration(self, session_id: str, *, count: int) -> list[str]:
        experiments = self.parameter_space.sample_wide(count)
        for experiment in experiments:
            experiment["research_phase"] = "exploration"
        return self._store_experiments(session_id, experiments)

    def plan_refinement(
        self,
        session_id: str,
        *,
        count: int,
        top_fraction: float = 0.10,
        expansion: float = 0.25,
    ) -> list[str]:
        completed = [
            experiment
            for experiment in self.database.session_experiments(session_id)
            if experiment["status"] == "completed"
        ]
        experiments = self.parameter_space.sample_refined(
            completed,
            count=count,
            top_fraction=top_fraction,
            expansion=expansion,
        )
        for experiment in experiments:
            experiment["research_phase"] = "refinement"
        return self._store_experiments(session_id, experiments)

    def next_refinement_plan(self, session_id: str) -> dict[str, Any]:
        session = self.database.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found.")
        experiments = self.database.session_experiments(session_id)
        completed = [experiment for experiment in experiments if experiment["status"] == "completed"]
        goals = session["goals"]
        current_total = len(experiments)
        max_experiments = int(goals.get("max_experiments", current_total))
        batch_size = int(goals.get("refinement_batch_size", 0))

        should_stop, reason = self._should_stop(session, completed)
        remaining = max(0, max_experiments - current_total)
        next_count = 0 if should_stop else min(batch_size, remaining)
        return {
            "session_id": session_id,
            "current_total": current_total,
            "completed": len(completed),
            "remaining": remaining,
            "next_refinement_count": next_count,
            "should_stop": should_stop or next_count == 0,
            "stop_reason": reason if should_stop else ("limit_reached" if next_count == 0 else None),
        }

    def analysis(self, session_id: str) -> dict[str, Any]:
        return self.analyzer.analyze(self.database.session_experiments(session_id))

    def write_report(
        self,
        session_id: str,
        *,
        output_dir: Path | str | None = None,
    ) -> dict[str, Path]:
        output_dir = Path(output_dir or Path(__file__).resolve().parent)
        output_dir.mkdir(parents=True, exist_ok=True)
        analysis = self.analysis(session_id)
        json_path = output_dir / f"trend_research_{session_id}.json"
        html_path = output_dir / f"trend_research_{session_id}.html"
        json_path.write_text(json.dumps(analysis, indent=2, sort_keys=True), encoding="utf-8")
        html_path.write_text(self._render_html(session_id, analysis), encoding="utf-8")
        return {"json": json_path, "html": html_path}

    def _store_experiments(
        self,
        session_id: str,
        experiments: list[dict[str, Any]],
    ) -> list[str]:
        strategy_hash = self.manager.strategy_hash()
        ids = []
        for parameters in experiments:
            experiment_id = self._experiment_id(parameters)
            self.database.create_experiment(
                experiment_id=experiment_id,
                strategy_name="LabPluginStrategy",
                strategy_hash=strategy_hash,
                parameters=parameters,
            )
            self.database.add_experiment_to_session(session_id, experiment_id)
            ids.append(experiment_id)

        self.database.update_session_status(
            session_id,
            "paused",
            metadata={
                "strategy_plugin": "TrendStrategy",
                "last_planned_at": datetime.now(UTC).isoformat(),
            },
        )
        return ids

    def _should_stop(
        self,
        session: dict[str, Any],
        completed: list[dict[str, Any]],
    ) -> tuple[bool, str | None]:
        goals = session["goals"]
        patience = int(goals.get("convergence_patience", 3))
        min_delta = float(goals.get("convergence_min_delta", 0.02))
        if len(completed) < patience + 1:
            return False, None

        evolution = self.analyzer._evolution(completed)
        best_values = [row["best_profit_factor"] for row in evolution]
        recent = best_values[-patience - 1 :]
        improvement = recent[-1] - recent[0]
        if improvement < min_delta:
            return True, "converged_profit_factor"
        return False, None

    def _render_html(self, session_id: str, analysis: dict[str, Any]) -> str:
        payload = json.dumps(analysis, ensure_ascii=False)
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>TrendStrategy Research Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2933; }}
    table {{ border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 13px; }}
    th, td {{ border: 1px solid #d9e2ec; padding: 6px 8px; text-align: left; }}
    th {{ background: #f0f4f8; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(320px, 1fr)); gap: 18px; }}
    canvas {{ width: 100%; height: 220px; border: 1px solid #d9e2ec; }}
    code {{ white-space: pre-wrap; }}
  </style>
</head>
<body>
  <h1>TrendStrategy Research Report</h1>
  <p id="summary"></p>
  <div class="grid">
    <canvas id="profitFactor"></canvas>
    <canvas id="drawdown"></canvas>
    <canvas id="sharpe"></canvas>
    <canvas id="expectancy"></canvas>
  </div>
  <h2>Top 100 Experiments</h2>
  <table id="top"></table>
  <h2>Parameter Importance</h2>
  <table id="importance"></table>
  <h2>High Interactions</h2>
  <table id="interactions"></table>
  <h2>Best Intervals</h2>
  <table id="intervals"></table>
  <script>
    const data = {payload};
    document.getElementById('summary').textContent =
      `${{data.completed_count}} completed TrendStrategy experiments analyzed.`;

    function line(id, values, title) {{
      const canvas = document.getElementById(id);
      const ctx = canvas.getContext('2d');
      canvas.width = canvas.clientWidth * devicePixelRatio;
      canvas.height = canvas.clientHeight * devicePixelRatio;
      ctx.scale(devicePixelRatio, devicePixelRatio);
      const w = canvas.clientWidth, h = canvas.clientHeight;
      ctx.clearRect(0, 0, w, h);
      ctx.fillText(title, 12, 18);
      if (values.length < 2) return;
      const min = Math.min(...values), max = Math.max(...values);
      ctx.beginPath();
      values.forEach((value, index) => {{
        const x = 12 + index * (w - 24) / (values.length - 1);
        const y = h - 24 - ((value - min) / (max - min || 1)) * (h - 48);
        if (index === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }});
      ctx.stroke();
    }}

    function renderTop() {{
      document.getElementById('top').innerHTML =
        '<tr><th>#</th><th>ID</th><th>Profit Factor</th><th>Drawdown</th><th>Sharpe</th><th>Expectancy</th><th>Trades</th><th>Parameters</th></tr>' +
        (data.top_100 || []).map((row, index) => `
        <tr><td>${{index + 1}}</td><td>${{row.id}}</td><td>${{row.profit_factor.toFixed(4)}}</td>
        <td>${{row.drawdown.toFixed(4)}}</td><td>${{row.sharpe.toFixed(4)}}</td>
        <td>${{row.expectancy.toFixed(4)}}</td><td>${{row.total_trades}}</td>
        <td><code>${{JSON.stringify(row.parameters)}}</code></td></tr>`).join('');
    }}

    function renderImportance() {{
      document.getElementById('importance').innerHTML =
        '<tr><th>Parameter</th><th>Importance</th><th>PF Spearman</th><th>PF Pearson</th><th>Drawdown Pearson</th><th>Sensitivity</th></tr>' +
        (data.importance || []).map(row => `
        <tr><td>${{row.parameter}}</td><td>${{row.importance_score.toFixed(4)}}</td>
        <td>${{Number(row.profit_factor_spearman || 0).toFixed(4)}}</td>
        <td>${{Number(row.profit_factor_pearson || 0).toFixed(4)}}</td>
        <td>${{Number(row.drawdown_pearson || 0).toFixed(4)}}</td>
        <td>${{row.sensitivity.toFixed(4)}}</td></tr>`).join('');
    }}

    function renderInteractions() {{
      document.getElementById('interactions').innerHTML =
        '<tr><th>Left</th><th>Right</th><th>Strength</th></tr>' +
        (data.interactions || []).slice(0, 20).map(row => `
        <tr><td>${{row.left}}</td><td>${{row.right}}</td>
        <td>${{row.interaction_strength.toFixed(4)}}</td></tr>`).join('');
    }}

    function renderIntervals() {{
      const rows = [];
      Object.entries((data.recommendations || {{}}).best_intervals || {{}}).forEach(([parameter, intervals]) => {{
        intervals.slice(0, 3).forEach(item => rows.push(`<tr><td>${{parameter}}</td><td>${{item.interval}}</td><td>${{item.count}}</td><td>${{item.profit_factor_mean.toFixed(4)}}</td></tr>`));
      }});
      document.getElementById('intervals').innerHTML =
        '<tr><th>Parameter</th><th>Interval</th><th>Count</th><th>Mean PF</th></tr>' + rows.join('');
    }}

    line('profitFactor', (data.evolution || []).map(row => row.best_profit_factor), 'Best Profit Factor');
    line('drawdown', (data.evolution || []).map(row => row.drawdown), 'Drawdown');
    line('sharpe', (data.evolution || []).map(row => row.sharpe), 'Sharpe');
    line('expectancy', (data.evolution || []).map(row => row.expectancy), 'Expectancy');
    renderTop();
    renderImportance();
    renderInteractions();
    renderIntervals();
  </script>
</body>
</html>
"""

    def _session_id(self, objective: str) -> str:
        payload = f"{datetime.now(UTC).isoformat()}:TrendStrategy:{objective}"
        digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:10]
        return f"trend-session-{digest}-{uuid.uuid4().hex[:6]}"

    def _experiment_id(self, parameters: dict[str, Any]) -> str:
        payload = json.dumps(parameters, sort_keys=True)
        prefix = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]
        return f"trend-exp-{prefix}-{uuid.uuid4().hex[:8]}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Two-phase TrendStrategy research engine.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create-session")
    create.add_argument("--max-experiments", type=int, required=True)
    create.add_argument("--phase1-experiments", type=int, required=True)
    create.add_argument("--refinement-batch-size", type=int, required=True)
    create.add_argument("--objective", default="TrendStrategy two-phase research")
    create.add_argument("--seed", type=int)

    phase1 = subparsers.add_parser("plan-exploration")
    phase1.add_argument("session_id")
    phase1.add_argument("--count", type=int, required=True)
    phase1.add_argument("--seed", type=int)

    refine = subparsers.add_parser("plan-refinement")
    refine.add_argument("session_id")
    refine.add_argument("--count", type=int, required=True)
    refine.add_argument("--top-fraction", type=float, default=0.10)
    refine.add_argument("--expansion", type=float, default=0.25)
    refine.add_argument("--seed", type=int)

    next_plan = subparsers.add_parser("next-refinement")
    next_plan.add_argument("session_id")

    report = subparsers.add_parser("report")
    report.add_argument("session_id")
    report.add_argument("--output-dir", type=Path)

    args = parser.parse_args()
    engine = TrendResearchEngine(seed=getattr(args, "seed", None))

    if args.command == "create-session":
        session_id = engine.create_session(
            objective=args.objective,
            max_experiments=args.max_experiments,
            phase1_experiments=args.phase1_experiments,
            refinement_batch_size=args.refinement_batch_size,
        )
        print(session_id)
    elif args.command == "plan-exploration":
        print("\n".join(engine.plan_exploration(args.session_id, count=args.count)))
    elif args.command == "plan-refinement":
        print(
            "\n".join(
                engine.plan_refinement(
                    args.session_id,
                    count=args.count,
                    top_fraction=args.top_fraction,
                    expansion=args.expansion,
                )
            )
        )
    elif args.command == "next-refinement":
        print(json.dumps(engine.next_refinement_plan(args.session_id), indent=2))
    elif args.command == "report":
        paths = engine.write_report(args.session_id, output_dir=args.output_dir)
        print(json.dumps({key: str(value) for key, value in paths.items()}, indent=2))


if __name__ == "__main__":
    main()
