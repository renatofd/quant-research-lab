from __future__ import annotations

import argparse
import hashlib
import json
import math
import uuid
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, median, pstdev
from typing import Any

try:
    from .backtest_runner import DEFAULT_BACKTEST_TIMEOUT_SECONDS, BacktestRunner
    from .experiment_database import ExperimentDatabase
    from .experiment_manager import ExperimentManager
    from .ranking_engine import RankingEngine
    from .robustness_analyzer import RobustnessAnalyzer
    from .strategy_plugins import create_plugin
    from .trend_research_engine import DEFAULT_METRICS, TrendParameterSpace
except ImportError:
    from backtest_runner import DEFAULT_BACKTEST_TIMEOUT_SECONDS, BacktestRunner
    from experiment_database import ExperimentDatabase
    from experiment_manager import ExperimentManager
    from ranking_engine import RankingEngine
    from robustness_analyzer import RobustnessAnalyzer
    from strategy_plugins import create_plugin
    from trend_research_engine import DEFAULT_METRICS, TrendParameterSpace


DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent
LOCAL_INT_DELTAS = (-2, -1, 1, 2)
LOCAL_DECIMAL_PERCENT_DELTAS = (-0.05, -0.02, 0.02, 0.05)
REPORT_METRICS = tuple(metric for metric in DEFAULT_METRICS if metric != "winrate")


class NeighborhoodExplorer:
    """Local one-parameter-at-a-time exploration around a completed experiment."""

    def __init__(
        self,
        *,
        database: ExperimentDatabase | None = None,
        output_dir: Path | str = DEFAULT_OUTPUT_DIR,
    ) -> None:
        self.database = database or ExperimentDatabase()
        self.output_dir = Path(output_dir)
        self.ranking = RankingEngine(self.database)
        self.trend_space = TrendParameterSpace()

    def plan(
        self,
        *,
        baseline_experiment_id: str,
        session_id: str | None = None,
        parameters: list[str] | None = None,
        max_experiments: int | None = None,
    ) -> dict[str, Any]:
        baseline = self._require_completed_experiment(baseline_experiment_id)
        plugin_name = self._plugin_name(baseline)
        baseline_parameters = self._plugin_parameters(baseline)
        parameter_spec = self._parameter_spec(plugin_name)
        baseline_parameters = self._with_default_parameters(
            baseline_parameters,
            parameter_spec,
        )
        parameter_names = parameters or list(parameter_spec)
        unknown = [name for name in parameter_names if name not in parameter_spec]
        if unknown:
            raise ValueError(f"Unknown {plugin_name} parameters: {unknown}")

        session_id = session_id or self._session_id(plugin_name)
        self.database.create_session(
            session_id=session_id,
            objective=(
                "Local neighborhood exploration around "
                f"{baseline_experiment_id}."
            ),
            strategy_name="LabPluginStrategy",
            search_method="local_neighborhood",
            goals={
                "baseline_experiment_id": baseline_experiment_id,
                "strategy_plugin": plugin_name,
                "parameters": parameter_names,
                "max_experiments": max_experiments,
            },
            metadata={
                "study_type": "neighborhood_exploration",
                "baseline_experiment_id": baseline_experiment_id,
                "baseline_metrics": baseline.get("metrics", {}),
                "baseline_parameters": baseline_parameters,
                "strategy_plugin": plugin_name,
                "center_point_reuses_baseline": True,
            },
            status="paused",
        )

        created = []
        strategy_hash = ExperimentManager(database=self.database).strategy_hash()
        for parameter in parameter_names:
            for variant in self._variants_for_parameter(
                parameter,
                baseline_parameters,
                parameter_spec,
                plugin_name,
            ):
                if max_experiments is not None and len(created) >= max_experiments:
                    break
                payload = {
                    "experiment_type": "strategy_plugin",
                    "strategy_plugin": plugin_name,
                    "research_phase": "local_neighborhood",
                    "plugin_parameters": variant["parameters"],
                    "neighborhood": {
                        "baseline_experiment_id": baseline_experiment_id,
                        "parameter": parameter,
                        "offset": variant["offset"],
                        "relative_offset": variant["relative_offset"],
                        "baseline_value": baseline_parameters[parameter],
                        "candidate_value": variant["parameters"][parameter],
                    },
                }
                experiment_id = self._experiment_id(payload)
                self.database.create_experiment(
                    experiment_id=experiment_id,
                    strategy_name="LabPluginStrategy",
                    strategy_hash=strategy_hash,
                    parameters=payload,
                )
                self.database.add_experiment_to_session(session_id, experiment_id)
                created.append(
                    {
                        "id": experiment_id,
                        "parameter": parameter,
                        "offset": variant["offset"],
                        "relative_offset": variant["relative_offset"],
                        "value": variant["parameters"][parameter],
                    }
                )

        return {
            "session_id": session_id,
            "baseline_experiment_id": baseline_experiment_id,
            "strategy_plugin": plugin_name,
            "created_experiments": len(created),
            "parameters": parameter_names,
            "experiments": created,
        }

    def run(
        self,
        session_id: str,
        *,
        limit: int | None = None,
        timeout_seconds: int = DEFAULT_BACKTEST_TIMEOUT_SECONDS,
        retries: int = 0,
        execution_mode: str = "auto",
    ) -> dict[str, Any]:
        runner = BacktestRunner(execution_mode=execution_mode)
        manager = ExperimentManager(
            database=self.database,
            runner=runner,
            ranking=self.ranking,
            execution_mode=execution_mode,
        )
        pending = [
            experiment
            for experiment in self.database.session_experiments(session_id)
            if experiment["status"] == "pending"
        ]
        if limit is not None:
            pending = pending[:limit]
        if pending:
            self.database.update_session_status(session_id, "running")

        items = []
        for experiment in pending:
            try:
                manager.run_experiment(
                    experiment["id"],
                    retries=retries,
                    timeout_seconds=timeout_seconds,
                )
            except Exception as exc:
                self.database.update_status(
                    experiment["id"],
                    "error",
                    error=(
                        "Neighborhood runner failure: "
                        f"{exc.__class__.__name__}: {exc!r}"
                    ),
                )
            current = self.database.get_experiment(experiment["id"])
            items.append(
                {
                    "id": experiment["id"],
                    "status": current.get("status") if current else "missing",
                    "runtime_seconds": current.get("runtime_seconds") if current else None,
                    "error": current.get("error") if current else "missing experiment",
                }
            )

        experiments = self.database.session_experiments(session_id)
        counts = self._status_counts(experiments)
        if counts["pending"] == 0 and counts["running"] == 0:
            self.database.update_session_status(session_id, "finished")

        return {"session_id": session_id, "counts": counts, "items": items}

    def analyze(self, session_id: str) -> dict[str, Any]:
        session = self.database.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found.")

        metadata = session.get("metadata", {})
        baseline_id = metadata.get("baseline_experiment_id")
        baseline = self._require_completed_experiment(baseline_id)
        baseline_parameters = metadata.get("baseline_parameters") or self._plugin_parameters(
            baseline
        )
        baseline_metrics = baseline.get("metrics", {})
        experiments = self.database.session_experiments(session_id)
        completed = [item for item in experiments if item["status"] == "completed"]

        curves = []
        for parameter in sorted(self._parameters_from_session(experiments)):
            rows = self._curve_rows(
                parameter=parameter,
                baseline_id=baseline_id,
                baseline_parameters=baseline_parameters,
                baseline_metrics=baseline_metrics,
                completed=completed,
            )
            curves.append(self._parameter_analysis(parameter, rows, baseline_metrics))

        curves.sort(key=lambda row: row["sensitivity_score"], reverse=True)
        robustness = self._robustness_summary(session_id)
        return {
            "session_id": session_id,
            "generated_at": datetime.now(UTC).isoformat(),
            "baseline_experiment_id": baseline_id,
            "strategy_plugin": metadata.get("strategy_plugin"),
            "status_counts": self._status_counts(experiments),
            "baseline_parameters": baseline_parameters,
            "baseline_metrics": self._metric_subset(baseline_metrics),
            "parameter_curves": curves,
            "robustness_analyzer": robustness,
            "recommendations": self._recommendations(curves),
        }

    def write_reports(self, session_id: str) -> dict[str, Path]:
        analysis = self.analyze(session_id)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        json_path = self.output_dir / f"neighborhood_report_{session_id}.json"
        html_path = self.output_dir / f"neighborhood_report_{session_id}.html"
        md_path = self.output_dir / f"neighborhood_report_{session_id}.md"
        json_path.write_text(
            json.dumps(analysis, indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        html_path.write_text(self._render_html(analysis), encoding="utf-8")
        md_path.write_text(self._render_markdown(analysis), encoding="utf-8")
        return {"json": json_path, "html": html_path, "markdown": md_path}

    def _variants_for_parameter(
        self,
        parameter: str,
        baseline_parameters: dict[str, Any],
        parameter_spec: dict[str, Any],
        plugin_name: str,
    ) -> list[dict[str, Any]]:
        spec = parameter_spec[parameter]
        baseline_value = baseline_parameters[parameter]
        values = []
        if spec["type"] == "int":
            for offset in LOCAL_INT_DELTAS:
                values.append((offset, None, int(baseline_value) + offset))
        elif spec["type"] == "decimal":
            for relative_offset in LOCAL_DECIMAL_PERCENT_DELTAS:
                values.append(
                    (
                        baseline_value * relative_offset,
                        relative_offset,
                        baseline_value * (1.0 + relative_offset),
                    )
                )
        elif spec["type"] == "bool":
            values.append((1, None, not bool(baseline_value)))
        else:
            return []

        variants = []
        seen = set()
        for offset, relative_offset, raw_value in values:
            candidate_value = (
                bool(raw_value)
                if spec["type"] == "bool"
                else self._clamp_and_cast(raw_value, spec)
            )
            if candidate_value == baseline_value or candidate_value in seen:
                continue
            candidate = dict(baseline_parameters)
            candidate[parameter] = candidate_value
            if not self._is_valid_parameters(plugin_name, candidate):
                continue
            seen.add(candidate_value)
            variants.append(
                {
                    "offset": offset,
                    "relative_offset": relative_offset,
                    "parameters": candidate,
                }
            )
        return variants

    def _parameter_spec(self, plugin_name: str) -> dict[str, Any]:
        spec = create_plugin(plugin_name).get_parameters()
        if spec:
            return dict(spec)
        if plugin_name == "TrendStrategy":
            return dict(self.trend_space.spec)
        raise ValueError(f"Could not load parameter spec for {plugin_name}.")

    def _with_default_parameters(
        self,
        parameters: dict[str, Any],
        parameter_spec: dict[str, Any],
    ) -> dict[str, Any]:
        resolved = dict(parameters)
        for name, spec in parameter_spec.items():
            if name not in resolved and "default" in spec:
                resolved[name] = spec["default"]
        return resolved

    def _is_valid_parameters(self, plugin_name: str, parameters: dict[str, Any]) -> bool:
        if plugin_name == "TrendStrategy":
            return self.trend_space._is_valid(parameters)
        return True

    def _clamp_and_cast(self, value: Any, spec: dict[str, Any]) -> int | float:
        low = float(spec["min"])
        high = float(spec["max"])
        clamped = min(high, max(low, float(value)))
        if spec["type"] == "int":
            return int(round(clamped))
        return round(clamped, 4)

    def _curve_rows(
        self,
        *,
        parameter: str,
        baseline_id: str,
        baseline_parameters: dict[str, Any],
        baseline_metrics: dict[str, Any],
        completed: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        rows = [
            {
                "experiment_id": baseline_id,
                "parameter": parameter,
                "value": self._number(baseline_parameters[parameter]),
                "offset": 0.0,
                "relative_offset": 0.0,
                "is_baseline": True,
                "metrics": self._metric_subset(baseline_metrics),
            }
        ]
        for experiment in completed:
            meta = self._neighborhood_meta(experiment)
            if meta.get("parameter") != parameter:
                continue
            rows.append(
                {
                    "experiment_id": experiment["id"],
                    "parameter": parameter,
                    "value": self._number(meta.get("candidate_value")),
                    "offset": self._number(meta.get("offset")) or 0.0,
                    "relative_offset": self._number(meta.get("relative_offset")),
                    "is_baseline": False,
                    "metrics": self._metric_subset(experiment.get("metrics", {})),
                }
            )
        return sorted(rows, key=lambda row: row["value"])

    def _parameter_analysis(
        self,
        parameter: str,
        rows: list[dict[str, Any]],
        baseline_metrics: dict[str, Any],
    ) -> dict[str, Any]:
        baseline_pf = self._metric(baseline_metrics, "profit_factor")
        baseline_drawdown = self._drawdown(baseline_metrics)
        sensitivity = self._sensitivity_score(rows)
        radius = self._robustness_radius(rows, baseline_drawdown)
        plateaus = self._plateaus(rows)
        cliffs = self._cliffs(rows, baseline_pf)
        return {
            "parameter": parameter,
            "baseline_value": next(row["value"] for row in rows if row["is_baseline"]),
            "sensitivity_score": sensitivity,
            "robustness_radius": radius,
            "classification": self._classify_parameter(sensitivity, radius, plateaus, cliffs),
            "plateaus": plateaus,
            "cliffs": cliffs,
            "curve": rows,
        }

    def _robustness_radius(
        self,
        rows: list[dict[str, Any]],
        baseline_drawdown: float,
    ) -> dict[str, Any]:
        baseline = next(row for row in rows if row["is_baseline"])
        allowed_drawdown = baseline_drawdown * 1.20
        safe_rows = [
            row
            for row in rows
            if row["metrics"]["profit_factor"] > 1.0
            and row["metrics"]["max_drawdown_abs"] <= allowed_drawdown
        ]
        contiguous = self._contiguous_safe_rows(rows, baseline, safe_rows)
        if not contiguous:
            return {"min": baseline["value"], "max": baseline["value"], "width": 0.0}
        low = min(row["value"] for row in contiguous)
        high = max(row["value"] for row in contiguous)
        return {"min": low, "max": high, "width": high - low}

    def _contiguous_safe_rows(
        self,
        rows: list[dict[str, Any]],
        baseline: dict[str, Any],
        safe_rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        safe_ids = {row["experiment_id"] for row in safe_rows}
        baseline_index = rows.index(baseline)
        selected = [baseline] if baseline["experiment_id"] in safe_ids else []
        for index in range(baseline_index - 1, -1, -1):
            if rows[index]["experiment_id"] not in safe_ids:
                break
            selected.append(rows[index])
        for index in range(baseline_index + 1, len(rows)):
            if rows[index]["experiment_id"] not in safe_ids:
                break
            selected.append(rows[index])
        return selected

    def _sensitivity_score(self, rows: list[dict[str, Any]]) -> float:
        baseline = next(row for row in rows if row["is_baseline"])
        slopes = []
        for row in rows:
            if row["is_baseline"]:
                continue
            delta_parameter = row["value"] - baseline["value"]
            if abs(delta_parameter) <= 1e-12:
                continue
            delta_pf = row["metrics"]["profit_factor"] - baseline["metrics"]["profit_factor"]
            slopes.append(abs(delta_pf / delta_parameter))
        return mean(slopes) if slopes else 0.0

    def _plateaus(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        plateaus = []
        for left, right in zip(rows, rows[1:], strict=False):
            pf_delta = abs(right["metrics"]["profit_factor"] - left["metrics"]["profit_factor"])
            drawdown_delta = abs(
                right["metrics"]["max_drawdown_abs"]
                - left["metrics"]["max_drawdown_abs"]
            )
            if pf_delta <= 0.10 and drawdown_delta <= max(1.0, left["metrics"]["max_drawdown_abs"] * 0.10):
                plateaus.append(
                    {
                        "min": left["value"],
                        "max": right["value"],
                        "profit_factor_delta": pf_delta,
                        "drawdown_delta": drawdown_delta,
                    }
                )
        return plateaus

    def _cliffs(
        self,
        rows: list[dict[str, Any]],
        baseline_pf: float,
    ) -> list[dict[str, Any]]:
        cliffs = []
        threshold = max(0.25, abs(baseline_pf) * 0.25)
        for left, right in zip(rows, rows[1:], strict=False):
            pf_delta = right["metrics"]["profit_factor"] - left["metrics"]["profit_factor"]
            if abs(pf_delta) >= threshold:
                cliffs.append(
                    {
                        "from": left["value"],
                        "to": right["value"],
                        "profit_factor_delta": pf_delta,
                    }
                )
        return cliffs

    def _classify_parameter(
        self,
        sensitivity: float,
        radius: dict[str, Any],
        plateaus: list[dict[str, Any]],
        cliffs: list[dict[str, Any]],
    ) -> str:
        if cliffs and sensitivity > 0.25:
            return "extremely_sensitive"
        if radius["width"] > 0 and plateaus:
            return "robust"
        if sensitivity <= 0.05:
            return "indifferent"
        return "sensitive"

    def _recommendations(self, curves: list[dict[str, Any]]) -> dict[str, Any]:
        free = [
            row["parameter"]
            for row in curves
            if row["classification"] in {"extremely_sensitive", "sensitive"}
        ]
        freeze = [
            row["parameter"]
            for row in curves
            if row["classification"] in {"indifferent", "robust"}
        ]
        return {
            "free_next_optimization": free,
            "freeze_next_optimization": freeze,
            "extremely_sensitive": [
                row["parameter"]
                for row in curves
                if row["classification"] == "extremely_sensitive"
            ],
            "robust": [
                row["parameter"] for row in curves if row["classification"] == "robust"
            ],
            "indifferent": [
                row["parameter"]
                for row in curves
                if row["classification"] == "indifferent"
            ],
            "safe_regions": {
                row["parameter"]: row["robustness_radius"]
                for row in curves
                if row["robustness_radius"]["width"] > 0
            },
            "dangerous_regions": {
                row["parameter"]: row["cliffs"] for row in curves if row["cliffs"]
            },
        }

    def _robustness_summary(self, session_id: str) -> dict[str, Any]:
        try:
            analysis = RobustnessAnalyzer().analyze_session(session_id)
        except Exception as exc:
            return {"available": False, "error": repr(exc)}
        return {
            "available": True,
            "pareto_count": len(analysis.get("pareto_frontier", [])),
            "optimal_regions_count": len(analysis.get("optimal_regions", [])),
            "top_robust": (
                analysis.get("robustness_ranking", [{}])[0]
                if analysis.get("robustness_ranking")
                else {}
            ),
        }

    def _parameters_from_session(self, experiments: list[dict[str, Any]]) -> set[str]:
        parameters = set()
        for experiment in experiments:
            parameter = self._neighborhood_meta(experiment).get("parameter")
            if parameter:
                parameters.add(parameter)
        return parameters

    def _neighborhood_meta(self, experiment: dict[str, Any]) -> dict[str, Any]:
        meta = experiment.get("parameters", {}).get("neighborhood")
        return meta if isinstance(meta, dict) else {}

    def _require_completed_experiment(self, experiment_id: str | None) -> dict[str, Any]:
        if not experiment_id:
            raise ValueError("Experiment id is required.")
        experiment = self.database.get_experiment(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found.")
        if experiment["status"] != "completed" or not experiment.get("metrics"):
            raise ValueError(f"Experiment {experiment_id} is not completed.")
        return experiment

    def _plugin_name(self, experiment: dict[str, Any]) -> str:
        parameters = experiment.get("parameters", {})
        return (
            parameters.get("strategy_plugin")
            or experiment.get("strategy_plugin")
            or experiment.get("strategy_name")
            or "UNKNOWN"
        )

    def _plugin_parameters(self, experiment: dict[str, Any]) -> dict[str, Any]:
        parameters = experiment.get("parameters", {})
        plugin_parameters = parameters.get("plugin_parameters")
        return dict(plugin_parameters) if isinstance(plugin_parameters, dict) else {}

    def _metric_subset(self, metrics: dict[str, Any]) -> dict[str, float]:
        return {metric: self._metric(metrics, metric) for metric in REPORT_METRICS}

    def _metric(self, metrics: dict[str, Any], key: str) -> float:
        if key == "max_drawdown_abs":
            return self._drawdown(metrics)
        return self._number(metrics.get(key)) or 0.0

    def _drawdown(self, metrics: dict[str, Any]) -> float:
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

    def _status_counts(self, experiments: list[dict[str, Any]]) -> dict[str, int]:
        return {
            status: sum(1 for experiment in experiments if experiment["status"] == status)
            for status in ("pending", "running", "completed", "error")
        }

    def _experiment_id(self, payload: dict[str, Any]) -> str:
        digest = hashlib.sha1(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:12]
        parameter = payload["neighborhood"]["parameter"].replace("_", "-")[:24]
        return f"neighbor-{parameter}-{digest}-{uuid.uuid4().hex[:8]}"

    def _session_id(self, plugin_name: str) -> str:
        stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        return f"neighborhood-{plugin_name.lower()}-{stamp}-{uuid.uuid4().hex[:8]}"

    def _render_markdown(self, analysis: dict[str, Any]) -> str:
        lines = [
            "# Neighborhood Explorer Report\n\n",
            f"Session: `{analysis['session_id']}`\n\n",
            f"Baseline: `{analysis['baseline_experiment_id']}`\n\n",
            "## Sensitivity Ranking\n\n",
            "| Parameter | Class | Sensitivity | Robustness Radius | Plateaus | Cliffs |\n",
            "|---|---|---:|---:|---:|---:|\n",
        ]
        for row in analysis["parameter_curves"]:
            lines.append(
                "| {parameter} | {classification} | {sensitivity:.6f} | "
                "{radius:.6f} | {plateaus} | {cliffs} |\n".format(
                    parameter=row["parameter"],
                    classification=row["classification"],
                    sensitivity=row["sensitivity_score"],
                    radius=row["robustness_radius"]["width"],
                    plateaus=len(row["plateaus"]),
                    cliffs=len(row["cliffs"]),
                )
            )
        recommendations = analysis["recommendations"]
        lines.extend(
            [
                "\n## Recommendations\n\n",
                "- Keep free: "
                + (", ".join(recommendations["free_next_optimization"]) or "none")
                + "\n",
                "- Freeze: "
                + (", ".join(recommendations["freeze_next_optimization"]) or "none")
                + "\n",
                "- Extremely sensitive: "
                + (", ".join(recommendations["extremely_sensitive"]) or "none")
                + "\n",
                "- Robust: "
                + (", ".join(recommendations["robust"]) or "none")
                + "\n",
                "- Indifferent: "
                + (", ".join(recommendations["indifferent"]) or "none")
                + "\n",
            ]
        )
        return "".join(lines)

    def _render_html(self, analysis: dict[str, Any]) -> str:
        payload = json.dumps(analysis, ensure_ascii=False)
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Neighborhood Explorer</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2933; }}
    table {{ border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 13px; }}
    th, td {{ border: 1px solid #d9e2ec; padding: 7px 9px; text-align: left; }}
    th {{ background: #f0f4f8; }}
    canvas {{ width: 100%; height: 260px; border: 1px solid #d9e2ec; margin: 12px 0; }}
    code {{ white-space: pre-wrap; }}
  </style>
</head>
<body>
  <h1>Neighborhood Explorer</h1>
  <p><strong>Session:</strong> <span id="session"></span></p>
  <p><strong>Baseline:</strong> <span id="baseline"></span></p>
  <h2>Sensitivity Ranking</h2>
  <table id="ranking"></table>
  <h2>Curves</h2>
  <div id="curves"></div>
  <h2>Recommendations</h2>
  <pre id="recommendations"></pre>
  <script>
    const data = {payload};
    const metrics = ['profit_factor', 'max_drawdown_abs', 'sharpe', 'expectancy', 'total_trades'];
    function n(value) {{
      const parsed = Number(value || 0);
      return Number.isFinite(parsed) ? parsed : 0;
    }}
    function f(value, digits = 4) {{ return n(value).toFixed(digits); }}
    function table(id, headers, rows) {{
      document.getElementById(id).innerHTML =
        '<tr>' + headers.map(header => `<th>${{header}}</th>`).join('') + '</tr>' +
        rows.map(row => '<tr>' + row.map(cell => `<td>${{cell}}</td>`).join('') + '</tr>').join('');
    }}
    document.getElementById('session').textContent = data.session_id;
    document.getElementById('baseline').textContent = data.baseline_experiment_id;
    table('ranking',
      ['Parameter', 'Class', 'Sensitivity', 'Radius', 'Plateaus', 'Cliffs'],
      data.parameter_curves.map(row => [
        row.parameter,
        row.classification,
        f(row.sensitivity_score, 6),
        f(row.robustness_radius.width, 6),
        row.plateaus.length,
        row.cliffs.length,
      ])
    );
    document.getElementById('recommendations').textContent = JSON.stringify(data.recommendations, null, 2);
    const container = document.getElementById('curves');
    function draw(canvas, rows, metric, title) {{
      const ctx = canvas.getContext('2d');
      canvas.width = canvas.clientWidth * devicePixelRatio;
      canvas.height = canvas.clientHeight * devicePixelRatio;
      ctx.scale(devicePixelRatio, devicePixelRatio);
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      ctx.clearRect(0, 0, w, h);
      ctx.fillText(title, 12, 18);
      if (rows.length < 2) return;
      const xs = rows.map(row => n(row.value));
      const ys = rows.map(row => n(row.metrics[metric]));
      const minX = Math.min(...xs);
      const maxX = Math.max(...xs);
      const minY = Math.min(...ys);
      const maxY = Math.max(...ys);
      ctx.beginPath();
      rows.forEach((row, index) => {{
        const x = 38 + ((n(row.value) - minX) / (maxX - minX || 1)) * (w - 60);
        const y = h - 30 - ((n(row.metrics[metric]) - minY) / (maxY - minY || 1)) * (h - 60);
        if (index === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }});
      ctx.stroke();
      rows.forEach(row => {{
        const x = 38 + ((n(row.value) - minX) / (maxX - minX || 1)) * (w - 60);
        const y = h - 30 - ((n(row.metrics[metric]) - minY) / (maxY - minY || 1)) * (h - 60);
        ctx.fillStyle = row.is_baseline ? '#b15533' : '#2f6f73';
        ctx.beginPath();
        ctx.arc(x, y, row.is_baseline ? 5 : 3, 0, Math.PI * 2);
        ctx.fill();
      }});
    }}
    data.parameter_curves.forEach(row => {{
      const section = document.createElement('section');
      section.innerHTML = `<h3>${{row.parameter}}</h3>`;
      metrics.forEach(metric => {{
        const canvas = document.createElement('canvas');
        section.appendChild(canvas);
        draw(canvas, row.curve, metric, `${{row.parameter}}: ${{metric}}`);
      }});
      container.appendChild(section);
    }});
  </script>
</body>
</html>
"""


def _parse_parameters(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Explore a local parameter neighborhood.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("baseline_experiment_id")
    plan_parser.add_argument("--session-id")
    plan_parser.add_argument("--parameters")
    plan_parser.add_argument("--max-experiments", type=int)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("session_id")
    run_parser.add_argument("--limit", type=int)
    run_parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_BACKTEST_TIMEOUT_SECONDS)
    run_parser.add_argument("--retries", type=int, default=0)
    run_parser.add_argument(
        "--execution-mode",
        choices=("auto", "docker", "freqtrade"),
        default="auto",
    )

    analyze_parser = subparsers.add_parser("analyze")
    analyze_parser.add_argument("session_id")
    analyze_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)

    args = parser.parse_args()
    explorer = NeighborhoodExplorer(output_dir=getattr(args, "output_dir", DEFAULT_OUTPUT_DIR))

    if args.command == "plan":
        result = explorer.plan(
            baseline_experiment_id=args.baseline_experiment_id,
            session_id=args.session_id,
            parameters=_parse_parameters(args.parameters),
            max_experiments=args.max_experiments,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.command == "run":
        result = explorer.run(
            args.session_id,
            limit=args.limit,
            timeout_seconds=args.timeout_seconds,
            retries=args.retries,
            execution_mode=args.execution_mode,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.command == "analyze":
        paths = explorer.write_reports(args.session_id)
        print(json.dumps({key: str(path) for key, path in paths.items()}, indent=2))


if __name__ == "__main__":
    main()
