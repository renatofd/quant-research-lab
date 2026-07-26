from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, median, pstdev
from typing import Any

try:
    from .experiment_database import ExperimentDatabase
    from .experiment_manager import ExperimentManager
except ImportError:
    from experiment_database import ExperimentDatabase
    from experiment_manager import ExperimentManager


DEFAULT_DB_PATH = Path(__file__).resolve().parent / "experiments.sqlite"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent
DEFAULT_METRICS = (
    "profit_factor",
    "max_drawdown_abs",
    "sharpe",
    "expectancy",
    "total_trades",
)
DEFAULT_IMPORTANCE_WEIGHTS = {
    "profit_factor": 0.35,
    "drawdown": 0.25,
    "sharpe": 0.20,
    "expectancy": 0.15,
    "trades": 0.05,
}


@dataclass(frozen=True)
class AblationComponent:
    name: str
    parameters: tuple[str, ...]
    remove_values: dict[str, Any] = field(default_factory=dict)
    description: str = ""


@dataclass(frozen=True)
class AblationConfig:
    low_quantile: float = 0.20
    high_quantile: float = 0.80
    include_remove_variant: bool = True
    include_parameter_variants: bool = True
    valuable_threshold: float = 0.05
    harmful_threshold: float = -0.05
    metric_weights: dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_IMPORTANCE_WEIGHTS)
    )

    @property
    def normalized_weights(self) -> dict[str, float]:
        weights = dict(DEFAULT_IMPORTANCE_WEIGHTS)
        weights.update(self.metric_weights)
        total = sum(abs(value) for value in weights.values())
        if total <= 0:
            return dict(DEFAULT_IMPORTANCE_WEIGHTS)
        return {key: value / total for key, value in weights.items()}


class AblationStudy:
    """Plan, run, and analyze component-level ablation experiments.

    This module is intentionally independent from the trading strategies. It creates
    regular lab experiments by changing plugin parameters only, then compares the
    resulting metrics with an already completed baseline experiment.
    """

    def __init__(
        self,
        *,
        database: ExperimentDatabase | None = None,
        output_dir: Path | str = DEFAULT_OUTPUT_DIR,
        config: AblationConfig | None = None,
    ) -> None:
        self.database = database or ExperimentDatabase()
        self.output_dir = Path(output_dir)
        self.config = config or AblationConfig()
        self.project_root = Path(__file__).resolve().parents[2]

    def plan(
        self,
        *,
        baseline_experiment_id: str,
        session_id: str | None = None,
        objective: str | None = None,
        strategy_plugin: str | None = None,
        components: list[str] | None = None,
    ) -> dict[str, Any]:
        baseline = self._require_experiment(baseline_experiment_id)
        baseline_parameters = self._plugin_parameters(baseline["parameters"])
        plugin_name = strategy_plugin or self._plugin_name(baseline)
        parameter_spec = self._parameter_spec(plugin_name)
        selected_components = self._selected_components(
            plugin_name,
            baseline_parameters,
            parameter_spec,
            components,
        )
        session_id = session_id or self._session_id(plugin_name)
        strategy_hash = ExperimentManager(database=self.database).strategy_hash()

        self.database.create_session(
            session_id=session_id,
            objective=objective
            or (
                "Ablation study for "
                f"{plugin_name} baseline {baseline_experiment_id}."
            ),
            strategy_name="LabPluginStrategy",
            search_method="ablation",
            goals={
                "baseline_experiment_id": baseline_experiment_id,
                "strategy_plugin": plugin_name,
                "components": [component.name for component in selected_components],
            },
            metadata={
                "study_type": "ablation",
                "baseline_experiment_id": baseline_experiment_id,
                "baseline_metrics": baseline.get("metrics", {}),
                "strategy_plugin": plugin_name,
                "component_count": len(selected_components),
            },
            status="paused",
        )

        created = []
        for component in selected_components:
            for variant in self._component_variants(
                component,
                baseline_parameters,
                parameter_spec,
            ):
                payload = {
                    "experiment_type": "strategy_plugin",
                    "strategy_plugin": plugin_name,
                    "plugin_parameters": variant["parameters"],
                    "ablation": {
                        "baseline_experiment_id": baseline_experiment_id,
                        "component": component.name,
                        "variant_type": variant["variant_type"],
                        "changed_parameters": variant["changed_parameters"],
                    },
                }
                experiment_id = self._experiment_id(component.name, payload)
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
                        "component": component.name,
                        "variant_type": variant["variant_type"],
                        "changed_parameters": variant["changed_parameters"],
                    }
                )

        return {
            "session_id": session_id,
            "baseline_experiment_id": baseline_experiment_id,
            "strategy_plugin": plugin_name,
            "created_experiments": len(created),
            "components": [component.name for component in selected_components],
            "experiments": created,
        }

    def run(
        self,
        session_id: str,
        *,
        limit: int | None = None,
        timeout_seconds: int = 900,
        retries: int = 0,
        execution_mode: str = "auto",
    ) -> dict[str, Any]:
        manager = ExperimentManager(
            database=self.database,
            execution_mode=execution_mode,
        )
        experiments = self.database.session_experiments(session_id)
        pending = [item for item in experiments if item["status"] == "pending"]
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
                    error=f"Ablation runner failure: {exc.__class__.__name__}: {exc!r}",
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

        after = self.database.session_experiments(session_id)
        counts = self._status_counts(after)
        if counts["pending"] == 0 and counts["running"] == 0:
            self.database.update_session_status(session_id, "finished")

        return {
            "session_id": session_id,
            "requested": len(pending),
            "counts": counts,
            "items": items,
        }

    def analyze(self, session_id: str) -> dict[str, Any]:
        session = self.database.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found.")

        metadata = session.get("metadata", {})
        baseline_id = metadata.get("baseline_experiment_id")
        if not baseline_id:
            raise ValueError("Ablation session metadata does not include a baseline.")
        baseline = self._require_experiment(baseline_id)
        baseline_metrics = baseline.get("metrics", {})

        experiments = self.database.session_experiments(session_id)
        completed = [item for item in experiments if item["status"] == "completed"]
        grouped = self._group_by_component(completed)
        component_rows = []
        for component_name, rows in grouped.items():
            component_rows.append(
                self._component_result(
                    component_name=component_name,
                    experiments=rows,
                    baseline_metrics=baseline_metrics,
                )
            )
        component_rows.sort(
            key=lambda item: item["component_importance_score"],
            reverse=True,
        )

        return {
            "session_id": session_id,
            "generated_at": datetime.now(UTC).isoformat(),
            "baseline_experiment_id": baseline_id,
            "strategy_plugin": metadata.get("strategy_plugin"),
            "status_counts": self._status_counts(experiments),
            "baseline_metrics": self._metric_subset(baseline_metrics),
            "component_results": component_rows,
            "summary": self._summary(component_rows),
        }

    def write_reports(self, session_id: str) -> dict[str, Path]:
        analysis = self.analyze(session_id)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        json_path = self.output_dir / f"ablation_report_{session_id}.json"
        html_path = self.output_dir / f"ablation_report_{session_id}.html"
        md_path = self.output_dir / f"ablation_report_{session_id}.md"
        json_path.write_text(
            json.dumps(analysis, indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        html_path.write_text(self._render_html(analysis), encoding="utf-8")
        md_path.write_text(self._render_markdown(analysis), encoding="utf-8")
        return {"json": json_path, "html": html_path, "markdown": md_path}

    def _selected_components(
        self,
        plugin_name: str,
        baseline_parameters: dict[str, Any],
        parameter_spec: dict[str, Any],
        component_names: list[str] | None,
    ) -> list[AblationComponent]:
        components = [
            component
            for component in self._default_components(plugin_name)
            if any(
                parameter in baseline_parameters or parameter in parameter_spec
                for parameter in (*component.parameters, *component.remove_values.keys())
            )
        ]
        if component_names:
            wanted = set(component_names)
            components = [component for component in components if component.name in wanted]
            missing = wanted - {component.name for component in components}
            if missing:
                raise ValueError(f"Unknown or unavailable components: {sorted(missing)}")
        return components

    def _default_components(self, plugin_name: str) -> list[AblationComponent]:
        if plugin_name == "TrendStrategy":
            return [
                AblationComponent(
                    "ema_fast_slow",
                    ("ema_fast_period", "ema_slow_period", "ema_fast_slow_weight"),
                    {"ema_fast_slow_weight": 0.0},
                    "Fast EMA above slow EMA confirmation.",
                ),
                AblationComponent(
                    "ema_trend",
                    ("ema_trend_period", "ema_slow_trend_weight"),
                    {"ema_slow_trend_weight": 0.0},
                    "Long-term trend confirmation.",
                ),
                AblationComponent(
                    "adx",
                    (
                        "adx_period",
                        "adx_entry_threshold",
                        "adx_exit_threshold",
                        "adx_weight",
                        "adx_loss_exit_weight",
                    ),
                    {"adx_weight": 0.0, "adx_loss_exit_weight": 0.0},
                    "Trend strength filter and ADX-based exit pressure.",
                ),
                AblationComponent(
                    "rsi",
                    ("rsi_period", "rsi_min", "rsi_max", "rsi_weight"),
                    {"rsi_weight": 0.0},
                    "Momentum health filter.",
                ),
                AblationComponent(
                    "volume",
                    ("volume_mean_period", "volume_multiplier", "volume_weight"),
                    {"volume_weight": 0.0},
                    "Volume expansion filter.",
                ),
                AblationComponent(
                    "atr",
                    ("atr_period", "atr_min_percent", "atr_weight"),
                    {"atr_weight": 0.0},
                    "Volatility activity filter.",
                ),
                AblationComponent(
                    "breakout",
                    ("breakout_weight",),
                    {"breakout_weight": 0.0},
                    "Close above previous high confirmation.",
                ),
                AblationComponent(
                    "score_threshold",
                    ("entry_score_threshold", "exit_score_threshold"),
                    {},
                    "Entry and exit score thresholds.",
                ),
                AblationComponent(
                    "risk",
                    ("roi", "stoploss"),
                    {},
                    "ROI and stoploss parameters.",
                ),
            ]

        if plugin_name == "PullbackStrategy":
            return [
                AblationComponent(
                    "trend",
                    (
                        "ema_fast_period",
                        "ema_slow_period",
                        "ema_trend_period",
                        "trend_buffer_percent",
                        "trend_weight",
                    ),
                    {"trend_weight": 0.0},
                    "Primary trend filter.",
                ),
                AblationComponent(
                    "pullback_touch",
                    ("pullback_lookback", "pullback_tolerance_percent", "pullback_touch_weight"),
                    {"pullback_touch_weight": 0.0},
                    "Controlled touch near fast EMA.",
                ),
                AblationComponent(
                    "pullback_control",
                    ("max_pullback_depth_percent", "pullback_control_weight"),
                    {"pullback_control_weight": 0.0},
                    "Maximum pullback depth control.",
                ),
                AblationComponent(
                    "reclaim_ema",
                    ("reclaim_ema_weight",),
                    {"reclaim_ema_weight": 0.0},
                    "Close reclaiming fast EMA.",
                ),
                AblationComponent(
                    "confirmation",
                    ("recovery_close_percent", "confirmation_weight"),
                    {"confirmation_weight": 0.0},
                    "Bullish candle and prior-high recovery.",
                ),
                AblationComponent(
                    "rsi",
                    ("rsi_period", "rsi_min", "rsi_max", "rsi_weight"),
                    {"rsi_weight": 0.0},
                    "RSI overbought protection.",
                ),
                AblationComponent(
                    "volume",
                    ("volume_mean_period", "volume_multiplier", "volume_weight"),
                    {"volume_weight": 0.0},
                    "Volume expansion filter.",
                ),
                AblationComponent(
                    "atr",
                    ("atr_period", "atr_min_percent", "atr_weight"),
                    {"atr_weight": 0.0},
                    "Volatility activity filter.",
                ),
                AblationComponent(
                    "score_threshold",
                    ("entry_score_threshold", "exit_score_threshold"),
                    {},
                    "Entry and exit score thresholds.",
                ),
                AblationComponent(
                    "exit_logic",
                    (
                        "ema_fast_loss_weight",
                        "ema_slow_loss_weight",
                        "trend_loss_weight",
                        "momentum_loss_weight",
                    ),
                    {
                        "ema_fast_loss_weight": 0.0,
                        "ema_slow_loss_weight": 0.0,
                        "trend_loss_weight": 0.0,
                        "momentum_loss_weight": 0.0,
                    },
                    "Plugin exit score components.",
                ),
                AblationComponent(
                    "risk",
                    ("roi", "stoploss"),
                    {},
                    "ROI and stoploss parameters.",
                ),
            ]

        return [
            AblationComponent(
                "all_numeric_parameters",
                tuple(),
                {},
                "Fallback component for plugins without known component mapping.",
            )
        ]

    def _component_variants(
        self,
        component: AblationComponent,
        baseline_parameters: dict[str, Any],
        parameter_spec: dict[str, Any],
    ) -> list[dict[str, Any]]:
        variants = []
        seen = set()
        if self.config.include_remove_variant and component.remove_values:
            params = dict(baseline_parameters)
            params.update(component.remove_values)
            self._append_variant(
                variants,
                seen,
                variant_type="remove_component",
                parameters=params,
                changed_parameters=component.remove_values,
                baseline_parameters=baseline_parameters,
            )

        if self.config.include_parameter_variants:
            for parameter in component.parameters:
                if parameter not in parameter_spec:
                    continue
                for label, value in self._parameter_variant_values(
                    parameter,
                    parameter_spec[parameter],
                    baseline_parameters.get(parameter),
                ):
                    params = dict(baseline_parameters)
                    params[parameter] = value
                    self._append_variant(
                        variants,
                        seen,
                        variant_type=f"vary_{label}",
                        parameters=params,
                        changed_parameters={parameter: value},
                        baseline_parameters=baseline_parameters,
                    )
        return variants

    def _append_variant(
        self,
        variants: list[dict[str, Any]],
        seen: set[str],
        *,
        variant_type: str,
        parameters: dict[str, Any],
        changed_parameters: dict[str, Any],
        baseline_parameters: dict[str, Any],
    ) -> None:
        if not changed_parameters:
            return
        if all(parameters.get(key) == baseline_parameters.get(key) for key in changed_parameters):
            return
        key = json.dumps(parameters, sort_keys=True, default=str)
        if key in seen:
            return
        seen.add(key)
        variants.append(
            {
                "variant_type": variant_type,
                "parameters": parameters,
                "changed_parameters": changed_parameters,
            }
        )

    def _parameter_variant_values(
        self,
        parameter: str,
        spec: dict[str, Any],
        baseline_value: Any,
    ) -> list[tuple[str, Any]]:
        low = self._number(spec.get("min"))
        high = self._number(spec.get("max"))
        default = spec.get("default")
        parameter_type = spec.get("type", "decimal")
        if low is None or high is None or high == low:
            values = [("default", default)]
        else:
            span = high - low
            values = [
                ("low", low + span * self.config.low_quantile),
                ("high", low + span * self.config.high_quantile),
            ]
            if default is not None:
                values.append(("default", default))

        normalized = []
        for label, value in values:
            cast_value = self._cast_parameter_value(value, parameter_type)
            if baseline_value is not None and cast_value == baseline_value:
                continue
            normalized.append((label, cast_value))
        return normalized

    def _cast_parameter_value(self, value: Any, parameter_type: str) -> Any:
        if parameter_type == "int":
            return int(round(float(value)))
        return round(float(value), 4)

    def _component_result(
        self,
        *,
        component_name: str,
        experiments: list[dict[str, Any]],
        baseline_metrics: dict[str, Any],
    ) -> dict[str, Any]:
        removal = [
            item
            for item in experiments
            if self._ablation_meta(item).get("variant_type") == "remove_component"
        ]
        comparison_group = removal or experiments
        aggregate = self._aggregate_metrics(comparison_group)
        all_aggregate = self._aggregate_metrics(experiments)
        importance = self._importance_score(baseline_metrics, aggregate)
        return {
            "component": component_name,
            "classification": self._classify(importance),
            "component_importance_score": importance,
            "completed_experiments": len(experiments),
            "removal_experiments": len(removal),
            "baseline_metrics": self._metric_subset(baseline_metrics),
            "comparison_metrics": aggregate,
            "all_variant_metrics": all_aggregate,
            "metric_delta_vs_baseline": self._metric_delta(baseline_metrics, aggregate),
            "variant_sensitivity": self._variant_sensitivity(experiments),
            "experiments": [
                {
                    "id": item["id"],
                    "variant_type": self._ablation_meta(item).get("variant_type"),
                    "changed_parameters": self._ablation_meta(item).get(
                        "changed_parameters",
                        {},
                    ),
                    "metrics": self._metric_subset(item.get("metrics", {})),
                }
                for item in experiments
            ],
        }

    def _importance_score(
        self,
        baseline_metrics: dict[str, Any],
        aggregate_metrics: dict[str, Any],
    ) -> float:
        weights = self.config.normalized_weights
        baseline_pf = self._metric(baseline_metrics, "profit_factor")
        observed_pf = self._metric(aggregate_metrics, "profit_factor")
        baseline_drawdown = self._drawdown(baseline_metrics)
        observed_drawdown = self._drawdown(aggregate_metrics)
        baseline_sharpe = self._metric(baseline_metrics, "sharpe")
        observed_sharpe = self._metric(aggregate_metrics, "sharpe")
        baseline_expectancy = self._metric(baseline_metrics, "expectancy")
        observed_expectancy = self._metric(aggregate_metrics, "expectancy")
        baseline_trades = self._metric(baseline_metrics, "total_trades")
        observed_trades = self._metric(aggregate_metrics, "total_trades")

        components = {
            "profit_factor": self._relative_delta(baseline_pf, observed_pf),
            "drawdown": self._relative_delta(observed_drawdown, baseline_drawdown),
            "sharpe": self._relative_delta(baseline_sharpe, observed_sharpe),
            "expectancy": self._relative_delta(baseline_expectancy, observed_expectancy),
            "trades": self._relative_delta(baseline_trades, observed_trades),
        }
        return sum(components[key] * weights.get(key, 0.0) for key in components)

    def _classify(self, importance: float) -> str:
        if importance >= self.config.valuable_threshold:
            return "adds_value"
        if importance <= self.config.harmful_threshold:
            return "degrades"
        return "neutral"

    def _aggregate_metrics(self, experiments: list[dict[str, Any]]) -> dict[str, Any]:
        if not experiments:
            return {metric: 0.0 for metric in DEFAULT_METRICS}
        metrics = [item.get("metrics", {}) for item in experiments]
        output = {}
        for metric in DEFAULT_METRICS:
            values = [self._metric(row, metric) for row in metrics]
            output[metric] = mean(values) if values else 0.0
            output[f"{metric}_median"] = median(values) if values else 0.0
            output[f"{metric}_std"] = pstdev(values) if len(values) > 1 else 0.0
        return output

    def _metric_delta(
        self,
        baseline_metrics: dict[str, Any],
        aggregate_metrics: dict[str, Any],
    ) -> dict[str, float]:
        return {
            metric: self._metric(aggregate_metrics, metric)
            - self._metric(baseline_metrics, metric)
            for metric in DEFAULT_METRICS
        }

    def _variant_sensitivity(self, experiments: list[dict[str, Any]]) -> dict[str, float]:
        output = {}
        for metric in DEFAULT_METRICS:
            values = [self._metric(item.get("metrics", {}), metric) for item in experiments]
            output[metric] = max(values) - min(values) if values else 0.0
        return output

    def _summary(self, component_rows: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "adds_value": [
                row["component"] for row in component_rows if row["classification"] == "adds_value"
            ],
            "neutral": [
                row["component"] for row in component_rows if row["classification"] == "neutral"
            ],
            "degrades": [
                row["component"] for row in component_rows if row["classification"] == "degrades"
            ],
            "top_components": [
                {
                    "component": row["component"],
                    "importance": row["component_importance_score"],
                    "classification": row["classification"],
                }
                for row in component_rows[:10]
            ],
        }

    def _group_by_component(
        self,
        experiments: list[dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for experiment in experiments:
            component = self._ablation_meta(experiment).get("component", "unknown")
            grouped.setdefault(component, []).append(experiment)
        return grouped

    def _ablation_meta(self, experiment: dict[str, Any]) -> dict[str, Any]:
        parameters = experiment.get("parameters", {})
        ablation = parameters.get("ablation")
        return ablation if isinstance(ablation, dict) else {}

    def _plugin_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        plugin_parameters = parameters.get("plugin_parameters")
        if isinstance(plugin_parameters, dict):
            return dict(plugin_parameters)
        nested = parameters.get("parameters")
        if isinstance(nested, dict):
            return dict(nested)
        return dict(parameters)

    def _plugin_name(self, experiment: dict[str, Any]) -> str:
        parameters = experiment.get("parameters", {})
        return (
            parameters.get("strategy_plugin")
            or experiment.get("strategy_plugin")
            or experiment.get("strategy_name")
            or "UNKNOWN"
        )

    def _parameter_spec(self, plugin_name: str) -> dict[str, Any]:
        try:
            from .strategy_plugins import create_plugin

            spec = create_plugin(plugin_name).get_parameters()
            if spec:
                return dict(spec)
        except Exception:
            pass

        try:
            from .strategy_plugins import placeholders

            plugin_class = getattr(placeholders, plugin_name)
            spec = plugin_class().get_parameters()
            return dict(spec)
        except Exception:
            return self._parameter_spec_from_ast(plugin_name)

    def _parameter_spec_from_ast(self, plugin_name: str) -> dict[str, Any]:
        path = Path(__file__).resolve().parent / "strategy_plugins" / "placeholders.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == plugin_name:
                for statement in node.body:
                    if (
                        isinstance(statement, ast.Assign)
                        and any(
                            isinstance(target, ast.Name)
                            and target.id == "PARAMETER_SPEC"
                            for target in statement.targets
                        )
                    ):
                        return ast.literal_eval(statement.value)
        raise ValueError(f"Could not load parameter spec for {plugin_name}.")

    def _require_experiment(self, experiment_id: str) -> dict[str, Any]:
        experiment = self.database.get_experiment(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found.")
        if not experiment.get("metrics"):
            raise ValueError(f"Experiment {experiment_id} has no metrics.")
        return experiment

    def _status_counts(self, experiments: list[dict[str, Any]]) -> dict[str, int]:
        return {
            status: sum(1 for item in experiments if item["status"] == status)
            for status in ("pending", "running", "completed", "error")
        }

    def _metric_subset(self, metrics: dict[str, Any]) -> dict[str, float]:
        return {metric: self._metric(metrics, metric) for metric in DEFAULT_METRICS}

    def _drawdown(self, metrics: dict[str, Any]) -> float:
        return self._metric(metrics, "max_drawdown_abs") or self._metric(
            metrics,
            "max_relative_drawdown",
        )

    def _metric(self, metrics: dict[str, Any], key: str) -> float:
        if key == "max_drawdown_abs":
            return self._number(metrics.get("max_drawdown_abs")) or self._number(
                metrics.get("max_relative_drawdown")
            ) or 0.0
        return self._number(metrics.get(key)) or 0.0

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

    def _relative_delta(self, baseline: float, observed: float) -> float:
        denominator = max(abs(baseline), 1.0)
        return (baseline - observed) / denominator

    def _experiment_id(self, component_name: str, payload: dict[str, Any]) -> str:
        digest = hashlib.sha1(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:12]
        safe_component = component_name.replace("_", "-")[:24]
        return f"ablation-{safe_component}-{digest}-{uuid.uuid4().hex[:8]}"

    def _session_id(self, plugin_name: str) -> str:
        stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        return f"ablation-{plugin_name.lower()}-{stamp}-{uuid.uuid4().hex[:8]}"

    def _render_markdown(self, analysis: dict[str, Any]) -> str:
        lines = [
            "# Ablation Study Report\n\n",
            f"Session: `{analysis['session_id']}`\n\n",
            f"Baseline: `{analysis['baseline_experiment_id']}`\n\n",
            "## Component Ranking\n\n",
            "| Component | Classification | Importance | PF delta | Drawdown delta | Sharpe delta | Expectancy delta | Trades delta |\n",
            "|---|---|---:|---:|---:|---:|---:|---:|\n",
        ]
        for row in analysis["component_results"]:
            delta = row["metric_delta_vs_baseline"]
            lines.append(
                "| {component} | {classification} | {score:.4f} | {pf:.4f} | "
                "{dd:.4f} | {sharpe:.4f} | {exp:.4f} | {trades:.2f} |\n".format(
                    component=row["component"],
                    classification=row["classification"],
                    score=row["component_importance_score"],
                    pf=delta["profit_factor"],
                    dd=delta["max_drawdown_abs"],
                    sharpe=delta["sharpe"],
                    exp=delta["expectancy"],
                    trades=delta["total_trades"],
                )
            )
        lines.extend(
            [
                "\n## Summary\n\n",
                f"- Adds value: {', '.join(analysis['summary']['adds_value']) or 'none'}\n",
                f"- Neutral: {', '.join(analysis['summary']['neutral']) or 'none'}\n",
                f"- Degrades: {', '.join(analysis['summary']['degrades']) or 'none'}\n",
            ]
        )
        return "".join(lines)

    def _render_html(self, analysis: dict[str, Any]) -> str:
        payload = json.dumps(analysis, ensure_ascii=False)
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Ablation Study Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2933; }}
    table {{ border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 13px; }}
    th, td {{ border: 1px solid #d9e2ec; padding: 7px 9px; text-align: left; }}
    th {{ background: #f0f4f8; }}
    .metric {{ display: inline-block; border: 1px solid #d9e2ec; padding: 8px 10px; margin: 4px 8px 4px 0; }}
    canvas {{ width: 100%; height: 260px; border: 1px solid #d9e2ec; }}
  </style>
</head>
<body>
  <h1>Ablation Study Report</h1>
  <p><strong>Session:</strong> <span id="session"></span></p>
  <p><strong>Baseline:</strong> <span id="baseline"></span></p>
  <div id="summary"></div>
  <canvas id="importance"></canvas>
  <h2>Component Ranking</h2>
  <table id="components"></table>
  <h2>Experiment Details</h2>
  <table id="details"></table>
  <script>
    const data = {payload};
    const rows = data.component_results || [];
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
    document.getElementById('summary').innerHTML =
      `<span class="metric"><strong>Adds value</strong><br>${{data.summary.adds_value.length}}</span>` +
      `<span class="metric"><strong>Neutral</strong><br>${{data.summary.neutral.length}}</span>` +
      `<span class="metric"><strong>Degrades</strong><br>${{data.summary.degrades.length}}</span>`;
    table('components',
      ['Component', 'Classification', 'Importance', 'PF delta', 'Drawdown delta', 'Sharpe delta', 'Expectancy delta', 'Trades delta', 'Completed'],
      rows.map(row => [
        row.component,
        row.classification,
        f(row.component_importance_score),
        f(row.metric_delta_vs_baseline.profit_factor),
        f(row.metric_delta_vs_baseline.max_drawdown_abs),
        f(row.metric_delta_vs_baseline.sharpe),
        f(row.metric_delta_vs_baseline.expectancy),
        f(row.metric_delta_vs_baseline.total_trades, 2),
        row.completed_experiments,
      ])
    );
    table('details',
      ['Component', 'Experiment', 'Variant', 'Changed parameters', 'PF', 'Drawdown', 'Sharpe', 'Expectancy', 'Trades'],
      rows.flatMap(row => row.experiments.map(exp => [
        row.component,
        exp.id,
        exp.variant_type,
        `<code>${{JSON.stringify(exp.changed_parameters)}}</code>`,
        f(exp.metrics.profit_factor),
        f(exp.metrics.max_drawdown_abs),
        f(exp.metrics.sharpe),
        f(exp.metrics.expectancy),
        f(exp.metrics.total_trades, 0),
      ]))
    );
    const canvas = document.getElementById('importance');
    const ctx = canvas.getContext('2d');
    canvas.width = canvas.clientWidth * devicePixelRatio;
    canvas.height = canvas.clientHeight * devicePixelRatio;
    ctx.scale(devicePixelRatio, devicePixelRatio);
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    ctx.fillText('Component Importance Score', 12, 18);
    const maxAbs = Math.max(...rows.map(row => Math.abs(n(row.component_importance_score))), 1);
    const barHeight = Math.max(14, (h - 48) / Math.max(rows.length, 1) - 4);
    rows.forEach((row, index) => {{
      const value = n(row.component_importance_score);
      const center = w / 2;
      const width = Math.abs(value) / maxAbs * (w / 2 - 90);
      const y = 38 + index * (barHeight + 4);
      ctx.fillStyle = value >= 0 ? '#2f6f73' : '#b15533';
      ctx.fillRect(value >= 0 ? center : center - width, y, width, barHeight);
      ctx.fillStyle = '#1f2933';
      ctx.fillText(row.component, 12, y + barHeight - 3);
      ctx.fillText(f(value), value >= 0 ? center + width + 6 : center - width - 58, y + barHeight - 3);
    }});
  </script>
</body>
</html>
"""


def _parse_components(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Component-level ablation study.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("--baseline-experiment-id", required=True)
    plan_parser.add_argument("--session-id")
    plan_parser.add_argument("--strategy-plugin")
    plan_parser.add_argument("--components")
    plan_parser.add_argument("--objective")

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("session_id")
    run_parser.add_argument("--limit", type=int)
    run_parser.add_argument("--timeout-seconds", type=int, default=900)
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
    study = AblationStudy(output_dir=getattr(args, "output_dir", DEFAULT_OUTPUT_DIR))

    if args.command == "plan":
        result = study.plan(
            baseline_experiment_id=args.baseline_experiment_id,
            session_id=args.session_id,
            objective=args.objective,
            strategy_plugin=args.strategy_plugin,
            components=_parse_components(args.components),
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.command == "run":
        result = study.run(
            args.session_id,
            limit=args.limit,
            timeout_seconds=args.timeout_seconds,
            retries=args.retries,
            execution_mode=args.execution_mode,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.command == "analyze":
        paths = study.write_reports(args.session_id)
        print(json.dumps({key: str(path) for key, path in paths.items()}, indent=2))


if __name__ == "__main__":
    main()
