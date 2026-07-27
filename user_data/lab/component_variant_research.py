from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

try:
    from .backtest_runner import DEFAULT_BACKTEST_TIMEOUT_SECONDS, BacktestRunner
    from .experiment_database import ExperimentDatabase
    from .experiment_manager import ExperimentManager
    from .ranking_engine import RankingEngine
    from .robustness_analyzer import RobustnessAnalyzer
    from .walk_forward_analyzer import WalkForwardAnalyzer, WalkForwardBacktestRunner
except ImportError:
    from backtest_runner import DEFAULT_BACKTEST_TIMEOUT_SECONDS, BacktestRunner
    from experiment_database import ExperimentDatabase
    from experiment_manager import ExperimentManager
    from ranking_engine import RankingEngine
    from robustness_analyzer import RobustnessAnalyzer
    from walk_forward_analyzer import WalkForwardAnalyzer, WalkForwardBacktestRunner


DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent
BASELINE_VARIANT = "TrendAtrRequired"


@dataclass(frozen=True)
class AtrVariant:
    key: str
    strategy_plugin: str
    label: str
    description: str


ATR_VARIANTS: tuple[AtrVariant, ...] = (
    AtrVariant(
        key="atr_required",
        strategy_plugin="TrendAtrRequired",
        label="ATR obrigatorio baseline",
        description="TrendStrategy with ATR score contribution and a hard ATR condition.",
    ),
    AtrVariant(
        key="atr_disabled",
        strategy_plugin="TrendAtrDisabled",
        label="ATR desabilitado",
        description="TrendStrategy with ATR removed from score and threshold capacity.",
    ),
    AtrVariant(
        key="atr_score_only",
        strategy_plugin="TrendAtrScoreOnly",
        label="ATR apenas como peso do score",
        description="TrendStrategy with ATR as a score component but no hard ATR gate.",
    ),
    AtrVariant(
        key="atr_adaptive_percentile",
        strategy_plugin="TrendAtrAdaptivePercentile",
        label="ATR adaptativo por percentil",
        description="ATR condition compares current ATR percent with a rolling quantile.",
    ),
    AtrVariant(
        key="atr_moving_average",
        strategy_plugin="TrendAtrMovingAverage",
        label="ATR por media movel",
        description="ATR condition compares current ATR percent with its moving average.",
    ),
    AtrVariant(
        key="atr_regime_relative",
        strategy_plugin="TrendAtrRegimeRelative",
        label="ATR relativo ao regime",
        description="ATR threshold changes according to trend and volatility context.",
    ),
)


COMPONENT_VARIANT_PLUGIN_CODE = r'''
from __future__ import annotations

from typing import Any

import pandas as pd
from pandas import DataFrame

from .placeholders import TrendStrategy


class BaseTrendAtrVariant(TrendStrategy):
    name = "BaseTrendAtrVariant"
    hard_require_atr = False
    include_atr_score = True
    compensate_disabled_threshold = False

    EXTRA_PARAMETER_SPEC = {
        "atr_percentile_window": {"default": 96, "min": 24, "max": 576, "type": "int"},
        "atr_percentile": {"default": 0.65, "min": 0.10, "max": 0.95, "type": "decimal"},
        "atr_ma_window": {"default": 96, "min": 24, "max": 576, "type": "int"},
        "atr_ma_multiplier": {"default": 1.00, "min": 0.50, "max": 2.50, "type": "decimal"},
        "atr_regime_trend_multiplier": {"default": 0.75, "min": 0.25, "max": 2.00, "type": "decimal"},
        "atr_regime_range_multiplier": {"default": 1.25, "min": 0.50, "max": 3.00, "type": "decimal"},
        "atr_regime_high_vol_multiplier": {"default": 1.50, "min": 0.50, "max": 4.00, "type": "decimal"},
        "atr_regime_vol_window": {"default": 96, "min": 24, "max": 576, "type": "int"},
    }

    def get_name(self) -> str:
        return self.name

    def get_parameters(self) -> dict[str, Any]:
        return {**self.PARAMETER_SPEC, **self.EXTRA_PARAMETER_SPEC}

    def _parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        resolved = super()._parameters(parameters)
        for name, spec in self.EXTRA_PARAMETER_SPEC.items():
            value = parameters.get(name, spec["default"])
            resolved[name] = int(value) if spec["type"] == "int" else float(value)
        return resolved

    def populate_entry(
        self,
        dataframe: DataFrame,
        metadata: dict[str, Any],
        parameters: dict[str, Any],
    ) -> DataFrame:
        params = self._parameters(parameters)
        dataframe = self._ensure_indicators(dataframe, params)

        score = pd.Series(0.0, index=dataframe.index)
        ema_fast_slow = dataframe["trend_ema_fast"] > dataframe["trend_ema_slow"]
        ema_slow_trend = dataframe["trend_ema_slow"] > dataframe["trend_ema_trend"]
        adx_strong = dataframe["trend_adx"] > params["adx_entry_threshold"]
        rsi_healthy = dataframe["trend_rsi"].between(params["rsi_min"], params["rsi_max"])
        volume_expanded = (
            dataframe["volume"]
            > dataframe["trend_volume_mean"] * params["volume_multiplier"]
        )
        atr_active = self._atr_active(dataframe, params)
        candle_breakout = dataframe["close"] > dataframe["high"].shift(1)

        score += ema_fast_slow.astype(float) * params["ema_fast_slow_weight"]
        score += ema_slow_trend.astype(float) * params["ema_slow_trend_weight"]
        score += adx_strong.astype(float) * params["adx_weight"]
        score += rsi_healthy.astype(float) * params["rsi_weight"]
        score += volume_expanded.astype(float) * params["volume_weight"]
        if self.include_atr_score:
            score += atr_active.astype(float) * params["atr_weight"]
        score += candle_breakout.astype(float) * params["breakout_weight"]

        threshold = self._entry_threshold(params)
        entry = score >= threshold
        if self.hard_require_atr:
            entry = entry & atr_active

        dataframe["trend_atr_variant_active"] = atr_active.astype(int)
        dataframe["trend_entry_score"] = score
        dataframe["enter_long"] = entry.astype(int)
        dataframe["enter_tag"] = ""

        entry_mask = dataframe["enter_long"] == 1
        if entry_mask.any():
            dataframe.loc[entry_mask, "enter_tag"] = [
                self._variant_entry_reason(row, params, threshold)
                for _, row in dataframe.loc[entry_mask].iterrows()
            ]

        return dataframe

    def _entry_threshold(self, params: dict[str, Any]) -> float:
        threshold = float(params["entry_score_threshold"])
        if self.compensate_disabled_threshold:
            threshold -= float(params["atr_weight"])
        return max(0.0, threshold)

    def _atr_active(self, dataframe: DataFrame, params: dict[str, Any]) -> pd.Series:
        return dataframe["trend_atr_percent"] > params["atr_min_percent"]

    def _variant_entry_reason(
        self,
        row: pd.Series,
        params: dict[str, Any],
        threshold: float,
    ) -> str:
        base = self._entry_reason(row, params)
        status = "ATR active" if bool(row.get("trend_atr_variant_active")) else "ATR inactive"
        return f"{self.name}; threshold={threshold:.2f}; {status}; {base}"


class TrendAtrRequired(BaseTrendAtrVariant):
    name = "TrendAtrRequired"
    hard_require_atr = True
    include_atr_score = True


class TrendAtrDisabled(BaseTrendAtrVariant):
    name = "TrendAtrDisabled"
    hard_require_atr = False
    include_atr_score = False
    compensate_disabled_threshold = True

    def _atr_active(self, dataframe: DataFrame, params: dict[str, Any]) -> pd.Series:
        return pd.Series(True, index=dataframe.index)


class TrendAtrScoreOnly(BaseTrendAtrVariant):
    name = "TrendAtrScoreOnly"
    hard_require_atr = False
    include_atr_score = True


class TrendAtrAdaptivePercentile(BaseTrendAtrVariant):
    name = "TrendAtrAdaptivePercentile"
    hard_require_atr = True
    include_atr_score = True

    def _atr_active(self, dataframe: DataFrame, params: dict[str, Any]) -> pd.Series:
        window = int(params["atr_percentile_window"])
        percentile = float(params["atr_percentile"])
        threshold = dataframe["trend_atr_percent"].rolling(
            window,
            min_periods=max(2, window // 2),
        ).quantile(percentile)
        dataframe["trend_atr_variant_threshold"] = threshold
        return dataframe["trend_atr_percent"] > threshold


class TrendAtrMovingAverage(BaseTrendAtrVariant):
    name = "TrendAtrMovingAverage"
    hard_require_atr = True
    include_atr_score = True

    def _atr_active(self, dataframe: DataFrame, params: dict[str, Any]) -> pd.Series:
        window = int(params["atr_ma_window"])
        multiplier = float(params["atr_ma_multiplier"])
        threshold = dataframe["trend_atr_percent"].rolling(
            window,
            min_periods=max(2, window // 2),
        ).mean() * multiplier
        dataframe["trend_atr_variant_threshold"] = threshold
        return dataframe["trend_atr_percent"] > threshold


class TrendAtrRegimeRelative(BaseTrendAtrVariant):
    name = "TrendAtrRegimeRelative"
    hard_require_atr = True
    include_atr_score = True

    def _atr_active(self, dataframe: DataFrame, params: dict[str, Any]) -> pd.Series:
        window = int(params["atr_regime_vol_window"])
        trend_context = (
            (dataframe["trend_adx"] > params["adx_entry_threshold"])
            & (dataframe["trend_ema_slow"] > dataframe["trend_ema_trend"])
        )
        high_volatility = dataframe["trend_atr_percent"] > (
            dataframe["trend_atr_percent"].rolling(
                window,
                min_periods=max(2, window // 2),
            ).median() * params["atr_regime_high_vol_multiplier"]
        )
        threshold = pd.Series(params["atr_min_percent"], index=dataframe.index)
        threshold = threshold.where(
            ~trend_context,
            params["atr_min_percent"] * params["atr_regime_trend_multiplier"],
        )
        threshold = threshold.where(
            trend_context,
            params["atr_min_percent"] * params["atr_regime_range_multiplier"],
        )
        threshold = threshold.where(
            ~high_volatility,
            params["atr_min_percent"] * params["atr_regime_high_vol_multiplier"],
        )
        dataframe["trend_atr_variant_threshold"] = threshold
        return dataframe["trend_atr_percent"] > threshold
'''


class ComponentVariantBacktestRunner(BacktestRunner):
    """BacktestRunner that injects component variants only into the sandbox."""

    def _copy_plugin_infrastructure(self, sandbox_user_data: Path) -> None:
        super()._copy_plugin_infrastructure(sandbox_user_data)
        plugin_dir = sandbox_user_data / "strategy_plugins"
        plugin_dir.mkdir(parents=True, exist_ok=True)
        (plugin_dir / "component_atr_variants.py").write_text(
            COMPONENT_VARIANT_PLUGIN_CODE,
            encoding="utf-8",
        )
        self._patch_registry(plugin_dir / "registry.py")

    def _patch_registry(self, registry_path: Path) -> None:
        text = registry_path.read_text(encoding="utf-8")
        if "component_atr_variants" in text:
            return

        import_block = (
            "from .component_atr_variants import (\n"
            "    TrendAtrAdaptivePercentile,\n"
            "    TrendAtrDisabled,\n"
            "    TrendAtrMovingAverage,\n"
            "    TrendAtrRegimeRelative,\n"
            "    TrendAtrRequired,\n"
            "    TrendAtrScoreOnly,\n"
            ")\n"
        )
        text = text.replace("\n\nPLUGIN_CLASSES", f"\n{import_block}\nPLUGIN_CLASSES", 1)
        insert = (
            '    "TrendAtrRequired": TrendAtrRequired,\n'
            '    "TrendAtrDisabled": TrendAtrDisabled,\n'
            '    "TrendAtrScoreOnly": TrendAtrScoreOnly,\n'
            '    "TrendAtrAdaptivePercentile": TrendAtrAdaptivePercentile,\n'
            '    "TrendAtrMovingAverage": TrendAtrMovingAverage,\n'
            '    "TrendAtrRegimeRelative": TrendAtrRegimeRelative,\n'
        )
        text = text.replace("PLUGIN_CLASSES: dict[str, type[StrategyPlugin]] = {\n", f"PLUGIN_CLASSES: dict[str, type[StrategyPlugin]] = {{\n{insert}", 1)
        registry_path.write_text(text, encoding="utf-8")


class ComponentVariantWalkForwardRunner(
    ComponentVariantBacktestRunner,
    WalkForwardBacktestRunner,
):
    """Walk-forward runner with sandbox-only component variant registration."""


class ComponentVariantResearch:
    def __init__(
        self,
        *,
        database: ExperimentDatabase | None = None,
        ranking: RankingEngine | None = None,
        output_dir: Path | str = DEFAULT_OUTPUT_DIR,
    ) -> None:
        self.database = database or ExperimentDatabase()
        self.ranking = ranking or RankingEngine(self.database)
        self.output_dir = Path(output_dir)

    def variants(self) -> list[dict[str, Any]]:
        return [variant.__dict__.copy() for variant in ATR_VARIANTS]

    def plan(
        self,
        *,
        session_id: str | None = None,
        base_experiment_id: str | None = None,
        base_parameters: dict[str, Any] | None = None,
        variant_keys: list[str] | None = None,
    ) -> dict[str, Any]:
        session_id = session_id or self._session_id()
        base_params = self._base_plugin_parameters(
            base_experiment_id=base_experiment_id,
            base_parameters=base_parameters,
        )
        variants = self._selected_variants(variant_keys)
        strategy_hash = self._strategy_hash()

        self.database.create_session(
            session_id=session_id,
            objective="Component variant research for TrendStrategy ATR behavior.",
            strategy_name="LabPluginStrategy",
            search_method="component_variant",
            goals={
                "component": "ATR",
                "base_experiment_id": base_experiment_id,
                "variant_count": len(variants),
            },
            metadata={
                "study_type": "component_variant",
                "component": "ATR",
                "base_experiment_id": base_experiment_id,
                "variants": [variant.__dict__ for variant in variants],
            },
            status="paused",
        )

        created = []
        for variant in variants:
            payload = self._variant_payload(variant, base_params, session_id)
            experiment_id = self._experiment_id(payload)
            self.database.create_experiment(
                experiment_id=experiment_id,
                strategy_name="LabPluginStrategy",
                strategy_hash=strategy_hash,
                parameters=payload,
            )
            self.database.add_experiment_to_session(session_id, experiment_id)
            created.append(experiment_id)

        return {
            "session_id": session_id,
            "experiments_created": len(created),
            "experiments": created,
            "variants": [variant.__dict__ for variant in variants],
        }

    def run_pending(
        self,
        session_id: str,
        *,
        limit: int | None = None,
        retries: int = 0,
        timeout_seconds: int = DEFAULT_BACKTEST_TIMEOUT_SECONDS,
        execution_mode: str = "auto",
    ) -> dict[str, Any]:
        runner = ComponentVariantBacktestRunner(execution_mode=execution_mode)
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
            manager.run_experiment(
                experiment["id"],
                retries=retries,
                timeout_seconds=timeout_seconds,
            )
            current = self.database.get_experiment(experiment["id"])
            items.append(
                {
                    "id": experiment["id"],
                    "status": current.get("status") if current else "missing",
                    "variant": self._variant_key(experiment),
                    "error": current.get("error") if current else "missing experiment",
                }
            )

        experiments = self.database.session_experiments(session_id)
        if experiments and not any(row["status"] in {"pending", "running"} for row in experiments):
            self.database.update_session_status(session_id, "finished")
        return {"session_id": session_id, "items": items, "counts": self._status_counts(experiments)}

    def plan_walk_forward(
        self,
        *,
        candidate_session_id: str,
        session_id: str | None = None,
        start_date: str,
        train_days: int,
        test_days: int,
        shift_days: int,
        folds: int,
        candidate_limit: int = 20,
        strategy_plugin: str | None = None,
    ) -> dict[str, Any]:
        analyzer = WalkForwardAnalyzer(database=self.database, ranking=self.ranking)
        result = analyzer.plan(
            session_id=session_id,
            start_date=start_date,
            train_days=train_days,
            test_days=test_days,
            shift_days=shift_days,
            folds=folds,
            candidate_session_id=candidate_session_id,
            candidate_limit=candidate_limit,
            strategy_plugin=strategy_plugin,
        )
        self.database.update_session_status(
            result["session_id"],
            "paused",
            metadata={
                "component_variant_candidate_session_id": candidate_session_id,
                "component_variant_runner": True,
            },
        )
        return result

    def run_walk_forward_phase(
        self,
        session_id: str,
        *,
        phase: str,
        limit: int | None = None,
        retries: int = 0,
        timeout_seconds: int = DEFAULT_BACKTEST_TIMEOUT_SECONDS,
        execution_mode: str = "auto",
    ) -> dict[str, Any]:
        if phase not in {"train", "test"}:
            raise ValueError("phase must be train or test.")

        runner = ComponentVariantWalkForwardRunner(execution_mode=execution_mode)
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
            and experiment.get("parameters", {}).get("walk_forward", {}).get("phase") == phase
        ]
        if limit is not None:
            pending = pending[:limit]
        if pending:
            self.database.update_session_status(session_id, "running")

        items = []
        for experiment in pending:
            manager.run_experiment(
                experiment["id"],
                retries=retries,
                timeout_seconds=timeout_seconds,
            )
            current = self.database.get_experiment(experiment["id"])
            items.append(
                {
                    "id": experiment["id"],
                    "status": current.get("status") if current else "missing",
                    "phase": phase,
                    "variant": self._variant_key(experiment),
                    "error": current.get("error") if current else "missing experiment",
                }
            )
        return {"session_id": session_id, "phase": phase, "items": items}

    def select_walk_forward(self, session_id: str, *, order_by: str = "score") -> dict[str, Any]:
        return WalkForwardAnalyzer(database=self.database, ranking=self.ranking).select(
            session_id,
            order_by=order_by,
        )

    def write_reports(
        self,
        session_id: str,
        *,
        walk_forward_session_id: str | None = None,
    ) -> dict[str, Path]:
        analysis = self.analyze(
            session_id,
            walk_forward_session_id=walk_forward_session_id,
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)
        json_path = self.output_dir / f"component_variant_report_{session_id}.json"
        html_path = self.output_dir / f"component_variant_report_{session_id}.html"
        md_path = self.output_dir / f"component_variant_report_{session_id}.md"
        json_path.write_text(
            json.dumps(analysis, indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        html_path.write_text(self._render_html(analysis), encoding="utf-8")
        md_path.write_text(self._render_markdown(analysis), encoding="utf-8")
        return {"json": json_path, "html": html_path, "markdown": md_path}

    def analyze(
        self,
        session_id: str,
        *,
        walk_forward_session_id: str | None = None,
    ) -> dict[str, Any]:
        session = self._require_session(session_id)
        experiments = self.database.session_experiments(session_id)
        completed = [
            experiment
            for experiment in experiments
            if experiment["status"] == "completed" and experiment.get("metrics")
        ]
        variant_rows = self._variant_metric_rows(completed)
        robustness = self._robustness_by_variant(session_id)
        walk_forward = self._walk_forward_by_variant(walk_forward_session_id)

        for row in variant_rows:
            variant = row["strategy_plugin"]
            row["walk_forward_survival_rate"] = walk_forward.get(variant, {}).get("survival_rate")
            row["stability_index"] = walk_forward.get(variant, {}).get("stability_index")
            row["robustness_score"] = robustness.get(variant)

        baseline = next(
            (row for row in variant_rows if row["strategy_plugin"] == BASELINE_VARIANT),
            None,
        )
        for row in variant_rows:
            row["classification"] = self._classify(row, baseline)

        return {
            "session_id": session_id,
            "generated_at": datetime.now(UTC).isoformat(),
            "session": session,
            "status_counts": self._status_counts(experiments),
            "variants": [variant.__dict__ for variant in ATR_VARIANTS],
            "rows": variant_rows,
            "walk_forward_session_id": walk_forward_session_id,
            "walk_forward": walk_forward,
            "robustness": robustness,
        }

    def _variant_metric_rows(self, experiments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for experiment in experiments:
            grouped.setdefault(experiment["strategy_plugin"], []).append(experiment)

        rows = []
        for variant in ATR_VARIANTS:
            items = grouped.get(variant.strategy_plugin, [])
            best = self._best_experiment(items)
            metrics = best.get("metrics", {}) if best else {}
            rows.append(
                {
                    "variant_key": variant.key,
                    "strategy_plugin": variant.strategy_plugin,
                    "label": variant.label,
                    "description": variant.description,
                    "experiment_count": len(items),
                    "best_experiment_id": best.get("id") if best else None,
                    "profit_factor": self._number(metrics.get("profit_factor")),
                    "sharpe": self._number(metrics.get("sharpe")),
                    "drawdown": self._number(
                        metrics.get("max_drawdown_abs")
                        if metrics.get("max_drawdown_abs") is not None
                        else metrics.get("max_relative_drawdown")
                    ),
                    "trades": self._number(metrics.get("total_trades")),
                    "score": self.ranking.composite_score(metrics) if metrics else 0.0,
                }
            )
        return rows

    def _robustness_by_variant(self, session_id: str) -> dict[str, float]:
        try:
            analysis = RobustnessAnalyzer().analyze_session(session_id)
        except Exception:
            return {}

        experiment_variants = {
            experiment["id"]: experiment.get("strategy_plugin")
            for experiment in self.database.session_experiments(session_id)
        }
        output: dict[str, list[float]] = {}
        for row in analysis.get("robustness_ranking", []):
            strategy_plugin = experiment_variants.get(row.get("id"))
            score = self._number(row.get("robustness_score"))
            if strategy_plugin and score is not None:
                output.setdefault(strategy_plugin, []).append(score)
        return {key: max(values) for key, values in output.items() if values}

    def _walk_forward_by_variant(self, session_id: str | None) -> dict[str, dict[str, float]]:
        if not session_id:
            return {}
        try:
            analysis = WalkForwardAnalyzer(database=self.database, ranking=self.ranking).analyze(session_id)
        except Exception:
            return {}

        grouped: dict[str, list[dict[str, Any]]] = {}
        for fold in analysis.get("folds", []):
            test_id = fold.get("test_experiment_id")
            if not test_id:
                continue
            experiment = self.database.get_experiment(test_id)
            if not experiment:
                continue
            variant = experiment.get("strategy_plugin")
            if variant:
                grouped.setdefault(variant, []).append(fold)

        output = {}
        for variant, folds in grouped.items():
            survived = sum(1 for fold in folds if fold.get("survived"))
            pfs = [
                self._number(fold.get("test_metrics", {}).get("profit_factor")) or 0.0
                for fold in folds
            ]
            pf_mean = mean(pfs) if pfs else 0.0
            pf_spread = max(pfs) - min(pfs) if len(pfs) > 1 else 0.0
            output[variant] = {
                "survival_rate": survived / len(folds) if folds else 0.0,
                "stability_index": pf_mean / (pf_mean + pf_spread + 1e-12) if pf_mean > 0 else 0.0,
                "folds": len(folds),
            }
        return output

    def _classify(
        self,
        row: dict[str, Any],
        baseline: dict[str, Any] | None,
    ) -> str:
        if not row.get("best_experiment_id"):
            return "neutral"
        if baseline is None or row["strategy_plugin"] == BASELINE_VARIANT:
            return "neutral"

        pf = row.get("profit_factor") or 0.0
        base_pf = baseline.get("profit_factor") or 0.0
        drawdown = row.get("drawdown") or 0.0
        base_drawdown = baseline.get("drawdown") or 0.0
        survival = row.get("walk_forward_survival_rate")
        base_survival = baseline.get("walk_forward_survival_rate")
        stability = row.get("stability_index")
        base_stability = baseline.get("stability_index")
        robustness = row.get("robustness_score")
        base_robustness = baseline.get("robustness_score")

        generalization_better = self._greater_or_missing(survival, base_survival) and self._greater_or_missing(stability, base_stability)
        robustness_better = self._greater_or_missing(robustness, base_robustness)
        drawdown_ok = base_drawdown <= 0 or drawdown <= base_drawdown * 1.10

        if pf >= base_pf * 0.95 and drawdown_ok and generalization_better and robustness_better:
            return "improves_generalization"
        if pf > base_pf * 1.10 and not generalization_better:
            return "overfits"
        if pf < base_pf * 0.80 or (base_drawdown > 0 and drawdown > base_drawdown * 1.25):
            return "degrades"
        return "neutral"

    def _base_plugin_parameters(
        self,
        *,
        base_experiment_id: str | None,
        base_parameters: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if base_parameters:
            return dict(base_parameters)
        if base_experiment_id:
            experiment = self.database.get_experiment(base_experiment_id)
            if not experiment:
                raise ValueError(f"Base experiment {base_experiment_id} not found.")
            parameters = experiment.get("parameters", {})
            plugin_parameters = parameters.get("plugin_parameters")
            if isinstance(plugin_parameters, dict):
                return dict(plugin_parameters)
            nested = parameters.get("parameters")
            if isinstance(nested, dict):
                return dict(nested)
            return dict(parameters)
        return {}

    def _variant_payload(
        self,
        variant: AtrVariant,
        base_params: dict[str, Any],
        session_id: str,
    ) -> dict[str, Any]:
        plugin_parameters = dict(base_params)
        plugin_parameters["component_variant"] = variant.key
        plugin_parameters["component_variant_label"] = variant.label
        return {
            "experiment_type": "strategy_plugin",
            "strategy_plugin": variant.strategy_plugin,
            "plugin_parameters": plugin_parameters,
            "component_variant": {
                "session_id": session_id,
                "component": "ATR",
                "variant_key": variant.key,
                "label": variant.label,
                "baseline": variant.strategy_plugin == BASELINE_VARIANT,
            },
        }

    def _selected_variants(self, variant_keys: list[str] | None) -> list[AtrVariant]:
        if not variant_keys:
            return list(ATR_VARIANTS)
        allowed = set(variant_keys)
        variants = [variant for variant in ATR_VARIANTS if variant.key in allowed]
        missing = allowed.difference(variant.key for variant in variants)
        if missing:
            raise ValueError(f"Unknown variant keys: {', '.join(sorted(missing))}")
        return variants

    def _best_experiment(self, experiments: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not experiments:
            return None
        return sorted(
            experiments,
            key=lambda experiment: self.ranking.composite_score(experiment.get("metrics", {})),
            reverse=True,
        )[0]

    def _strategy_hash(self) -> str:
        digest = hashlib.sha256()
        digest.update(ExperimentManager(database=self.database).strategy_hash().encode("utf-8"))
        digest.update(Path(__file__).read_bytes())
        digest.update(COMPONENT_VARIANT_PLUGIN_CODE.encode("utf-8"))
        return digest.hexdigest()

    def _experiment_id(self, payload: dict[str, Any]) -> str:
        digest = hashlib.sha1(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:12]
        variant = payload.get("component_variant", {}).get("variant_key", "variant")
        return f"component-{variant}-{digest}-{uuid.uuid4().hex[:8]}"

    def _session_id(self) -> str:
        stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        return f"component-variant-{stamp}-{uuid.uuid4().hex[:8]}"

    def _variant_key(self, experiment: dict[str, Any]) -> str | None:
        component = experiment.get("parameters", {}).get("component_variant")
        if isinstance(component, dict):
            return component.get("variant_key")
        return None

    def _status_counts(self, experiments: list[dict[str, Any]]) -> dict[str, int]:
        return {
            status: sum(1 for experiment in experiments if experiment["status"] == status)
            for status in ("pending", "running", "completed", "error")
        }

    def _require_session(self, session_id: str) -> dict[str, Any]:
        session = self.database.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found.")
        return session

    def _greater_or_missing(self, value: Any, baseline: Any) -> bool:
        if value is None or baseline is None:
            return True
        return float(value) >= float(baseline)

    def _number(self, value: Any) -> float | None:
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def _render_markdown(self, analysis: dict[str, Any]) -> str:
        lines = [
            "# Component Variant Research\n\n",
            f"Session: `{analysis['session_id']}`\n\n",
            "## ATR Variants\n\n",
            "| Variant | PF | Sharpe | Drawdown | Trades | WF Survival | Stability | Robustness | Classification |\n",
            "|---|---:|---:|---:|---:|---:|---:|---:|---|\n",
        ]
        for row in analysis["rows"]:
            lines.append(
                "| {label} | {pf:.4f} | {sharpe:.4f} | {drawdown:.4f} | {trades:.0f} | "
                "{survival} | {stability} | {robustness} | {classification} |\n".format(
                    label=row["label"],
                    pf=row.get("profit_factor") or 0.0,
                    sharpe=row.get("sharpe") or 0.0,
                    drawdown=row.get("drawdown") or 0.0,
                    trades=row.get("trades") or 0.0,
                    survival=self._format_optional(row.get("walk_forward_survival_rate")),
                    stability=self._format_optional(row.get("stability_index")),
                    robustness=self._format_optional(row.get("robustness_score")),
                    classification=row["classification"],
                )
            )
        return "".join(lines)

    def _render_html(self, analysis: dict[str, Any]) -> str:
        payload = json.dumps(analysis, ensure_ascii=False)
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Component Variant Research</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2933; }}
    table {{ border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 13px; }}
    th, td {{ border: 1px solid #d9e2ec; padding: 7px 9px; text-align: left; }}
    th {{ background: #f0f4f8; }}
    .metric {{ display: inline-block; border: 1px solid #d9e2ec; padding: 8px 10px; margin: 4px 8px 4px 0; }}
  </style>
</head>
<body>
  <h1>Component Variant Research</h1>
  <p><strong>Session:</strong> <span id="session"></span></p>
  <table id="rows"></table>
  <script>
    const data = {payload};
    function n(value) {{
      const parsed = Number(value || 0);
      return Number.isFinite(parsed) ? parsed : 0;
    }}
    function f(value, digits = 4) {{
      if (value === null || value === undefined) return 'n/a';
      return n(value).toFixed(digits);
    }}
    document.getElementById('session').textContent = data.session_id;
    const headers = ['Variant', 'Profit Factor', 'Sharpe', 'Drawdown', 'Trades', 'WF Survival', 'Stability', 'Robustness', 'Classification'];
    const rows = data.rows || [];
    document.getElementById('rows').innerHTML =
      '<tr>' + headers.map(header => `<th>${{header}}</th>`).join('') + '</tr>' +
      rows.map(row => '<tr>' + [
        row.label,
        f(row.profit_factor),
        f(row.sharpe),
        f(row.drawdown),
        f(row.trades, 0),
        f(row.walk_forward_survival_rate),
        f(row.stability_index),
        f(row.robustness_score),
        row.classification,
      ].map(cell => `<td>${{cell}}</td>`).join('') + '</tr>').join('');
  </script>
</body>
</html>
"""

    def _format_optional(self, value: Any) -> str:
        number = self._number(value)
        return "n/a" if number is None else f"{number:.4f}"


def _parse_variant_keys(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_json_object(value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    return json.loads(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Research structural ATR variants for TrendStrategy.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("variants")

    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("--session-id")
    plan_parser.add_argument("--base-experiment-id")
    plan_parser.add_argument("--base-parameters-json")
    plan_parser.add_argument("--variants", help="Comma-separated variant keys.")

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("session_id")
    run_parser.add_argument("--limit", type=int)
    run_parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_BACKTEST_TIMEOUT_SECONDS)
    run_parser.add_argument("--retries", type=int, default=0)
    run_parser.add_argument("--execution-mode", choices=("auto", "docker", "freqtrade"), default="auto")

    wf_plan = subparsers.add_parser("walk-forward-plan")
    wf_plan.add_argument("--candidate-session-id", required=True)
    wf_plan.add_argument("--session-id")
    wf_plan.add_argument("--start-date", required=True)
    wf_plan.add_argument("--train-days", type=int, required=True)
    wf_plan.add_argument("--test-days", type=int, required=True)
    wf_plan.add_argument("--shift-days", type=int, required=True)
    wf_plan.add_argument("--folds", type=int, required=True)
    wf_plan.add_argument("--candidate-limit", type=int, default=20)
    wf_plan.add_argument("--strategy-plugin")

    wf_run = subparsers.add_parser("walk-forward-run")
    wf_run.add_argument("session_id")
    wf_run.add_argument("--phase", choices=("train", "test"), required=True)
    wf_run.add_argument("--limit", type=int)
    wf_run.add_argument("--timeout-seconds", type=int, default=DEFAULT_BACKTEST_TIMEOUT_SECONDS)
    wf_run.add_argument("--retries", type=int, default=0)
    wf_run.add_argument("--execution-mode", choices=("auto", "docker", "freqtrade"), default="auto")

    wf_select = subparsers.add_parser("walk-forward-select")
    wf_select.add_argument("session_id")
    wf_select.add_argument("--order-by", default="score")

    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("session_id")
    report_parser.add_argument("--walk-forward-session-id")
    report_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)

    args = parser.parse_args()
    research = ComponentVariantResearch(output_dir=getattr(args, "output_dir", DEFAULT_OUTPUT_DIR))

    if args.command == "variants":
        result = {"variants": research.variants()}
    elif args.command == "plan":
        result = research.plan(
            session_id=args.session_id,
            base_experiment_id=args.base_experiment_id,
            base_parameters=_parse_json_object(args.base_parameters_json),
            variant_keys=_parse_variant_keys(args.variants),
        )
    elif args.command == "run":
        result = research.run_pending(
            args.session_id,
            limit=args.limit,
            retries=args.retries,
            timeout_seconds=args.timeout_seconds,
            execution_mode=args.execution_mode,
        )
    elif args.command == "walk-forward-plan":
        result = research.plan_walk_forward(
            candidate_session_id=args.candidate_session_id,
            session_id=args.session_id,
            start_date=args.start_date,
            train_days=args.train_days,
            test_days=args.test_days,
            shift_days=args.shift_days,
            folds=args.folds,
            candidate_limit=args.candidate_limit,
            strategy_plugin=args.strategy_plugin,
        )
    elif args.command == "walk-forward-run":
        result = research.run_walk_forward_phase(
            args.session_id,
            phase=args.phase,
            limit=args.limit,
            retries=args.retries,
            timeout_seconds=args.timeout_seconds,
            execution_mode=args.execution_mode,
        )
    elif args.command == "walk-forward-select":
        result = research.select_walk_forward(args.session_id, order_by=args.order_by)
    elif args.command == "report":
        result = {
            key: str(path)
            for key, path in research.write_reports(
                args.session_id,
                walk_forward_session_id=args.walk_forward_session_id,
            ).items()
        }
    else:
        raise ValueError(f"Unknown command: {args.command}")

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
