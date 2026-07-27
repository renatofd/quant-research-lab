from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, median
from typing import Any

try:
    from .backtest_runner import DEFAULT_BACKTEST_TIMEOUT_SECONDS, BacktestRunner
    from .experiment_database import ExperimentDatabase
    from .experiment_manager import ExperimentManager
    from .ranking_engine import RankingEngine
    from .robustness_analyzer import RobustnessAnalyzer
    from .trend_research_engine import TrendParameterSpace
    from .walk_forward_analyzer import WalkForwardAnalyzer, WalkForwardBacktestRunner
except ImportError:
    from backtest_runner import DEFAULT_BACKTEST_TIMEOUT_SECONDS, BacktestRunner
    from experiment_database import ExperimentDatabase
    from experiment_manager import ExperimentManager
    from ranking_engine import RankingEngine
    from robustness_analyzer import RobustnessAnalyzer
    from trend_research_engine import TrendParameterSpace
    from walk_forward_analyzer import WalkForwardAnalyzer, WalkForwardBacktestRunner


DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent
BASELINE_VARIANT = "TrendEntryScoreSumBaseline"


@dataclass(frozen=True)
class EntryLogicVariant:
    key: str
    strategy_plugin: str
    label: str
    description: str


ENTRY_LOGIC_VARIANTS: tuple[EntryLogicVariant, ...] = (
    EntryLogicVariant(
        key="score_sum_baseline",
        strategy_plugin="TrendEntryScoreSumBaseline",
        label="Score sum baseline",
        description="Original TrendStrategy score summation decision.",
    ),
    EntryLogicVariant(
        key="required_core",
        strategy_plugin="TrendEntryRequiredCore",
        label="Required core components",
        description="Requires core trend, ADX and ATR components in addition to score.",
    ),
    EntryLogicVariant(
        key="n_of_m",
        strategy_plugin="TrendEntryNOfM",
        label="N of M components",
        description="Entry requires a configurable number of active components.",
    ),
    EntryLogicVariant(
        key="voting",
        strategy_plugin="TrendEntryVoting",
        label="Component voting",
        description="Entry uses one vote per enabled component instead of weighted sum.",
    ),
    EntryLogicVariant(
        key="dynamic_regime_weights",
        strategy_plugin="TrendEntryDynamicRegimeWeights",
        label="Dynamic regime weights",
        description="Existing component weights are adjusted using trend/volatility context.",
    ),
    EntryLogicVariant(
        key="adaptive_threshold",
        strategy_plugin="TrendEntryAdaptiveThreshold",
        label="Adaptive threshold",
        description="Score threshold adapts from existing ADX, EMA trend and ATR context.",
    ),
    EntryLogicVariant(
        key="normalized_score",
        strategy_plugin="TrendEntryNormalizedScore",
        label="Normalized score",
        description="Score is normalized by active maximum weight before applying threshold.",
    ),
    EntryLogicVariant(
        key="selective_disable",
        strategy_plugin="TrendEntrySelectiveDisable",
        label="Selective component disable",
        description="Selected existing components are removed only from entry decision logic.",
    ),
)


ENTRY_LOGIC_PLUGIN_CODE = r'''
from __future__ import annotations

from typing import Any

import pandas as pd
from pandas import DataFrame

from .placeholders import TrendStrategy


COMPONENT_ORDER = (
    "ema_fast_slow",
    "ema_slow_trend",
    "adx",
    "rsi",
    "volume",
    "atr",
    "breakout",
)


class BaseTrendEntryLogicVariant(TrendStrategy):
    name = "BaseTrendEntryLogicVariant"

    EXTRA_PARAMETER_SPEC = {
        "n_of_m_required": {"default": 4, "min": 1, "max": 7, "type": "int"},
        "vote_threshold": {"default": 4, "min": 1, "max": 7, "type": "int"},
        "normalized_score_threshold": {"default": 0.55, "min": 0.05, "max": 1.00, "type": "decimal"},
        "adaptive_threshold_trend_delta": {"default": -1.0, "min": -5.0, "max": 5.0, "type": "decimal"},
        "adaptive_threshold_range_delta": {"default": 1.0, "min": -5.0, "max": 5.0, "type": "decimal"},
        "adaptive_threshold_high_vol_delta": {"default": 1.5, "min": -5.0, "max": 5.0, "type": "decimal"},
        "dynamic_trend_multiplier": {"default": 1.25, "min": 0.25, "max": 3.0, "type": "decimal"},
        "dynamic_range_multiplier": {"default": 0.75, "min": 0.25, "max": 3.0, "type": "decimal"},
        "dynamic_high_vol_multiplier": {"default": 0.50, "min": 0.0, "max": 3.0, "type": "decimal"},
        "selective_disable_mask": {"default": 0, "min": 0, "max": 127, "type": "int"},
        "regime_window": {"default": 96, "min": 24, "max": 576, "type": "int"},
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
        components = self._components(dataframe, params)
        enabled = self._enabled_components(params)
        score = self._score(dataframe, components, params, enabled)
        entry = self._entry_mask(dataframe, components, score, params, enabled)

        dataframe["trend_entry_score"] = score
        dataframe["trend_entry_votes"] = self._vote_count(components, enabled)
        dataframe["trend_entry_logic"] = self.name
        dataframe["enter_long"] = entry.astype(int)
        dataframe["enter_tag"] = ""

        entry_mask = dataframe["enter_long"] == 1
        if entry_mask.any():
            dataframe.loc[entry_mask, "enter_tag"] = [
                self._entry_logic_reason(row, params, enabled)
                for _, row in dataframe.loc[entry_mask].iterrows()
            ]
        return dataframe

    def _components(
        self,
        dataframe: DataFrame,
        params: dict[str, Any],
    ) -> dict[str, pd.Series]:
        return {
            "ema_fast_slow": dataframe["trend_ema_fast"] > dataframe["trend_ema_slow"],
            "ema_slow_trend": dataframe["trend_ema_slow"] > dataframe["trend_ema_trend"],
            "adx": dataframe["trend_adx"] > params["adx_entry_threshold"],
            "rsi": dataframe["trend_rsi"].between(params["rsi_min"], params["rsi_max"]),
            "volume": dataframe["volume"] > dataframe["trend_volume_mean"] * params["volume_multiplier"],
            "atr": dataframe["trend_atr_percent"] > params["atr_min_percent"],
            "breakout": dataframe["close"] > dataframe["high"].shift(1),
        }

    def _weights(self, params: dict[str, Any]) -> dict[str, float]:
        return {
            "ema_fast_slow": params["ema_fast_slow_weight"],
            "ema_slow_trend": params["ema_slow_trend_weight"],
            "adx": params["adx_weight"],
            "rsi": params["rsi_weight"],
            "volume": params["volume_weight"],
            "atr": params["atr_weight"],
            "breakout": params["breakout_weight"],
        }

    def _enabled_components(self, params: dict[str, Any]) -> tuple[str, ...]:
        return COMPONENT_ORDER

    def _score(
        self,
        dataframe: DataFrame,
        components: dict[str, pd.Series],
        params: dict[str, Any],
        enabled: tuple[str, ...],
    ) -> pd.Series:
        weights = self._weights(params)
        score = pd.Series(0.0, index=dataframe.index)
        for name in enabled:
            score += components[name].fillna(False).astype(float) * weights[name]
        return score

    def _entry_mask(
        self,
        dataframe: DataFrame,
        components: dict[str, pd.Series],
        score: pd.Series,
        params: dict[str, Any],
        enabled: tuple[str, ...],
    ) -> pd.Series:
        return score >= params["entry_score_threshold"]

    def _vote_count(
        self,
        components: dict[str, pd.Series],
        enabled: tuple[str, ...],
    ) -> pd.Series:
        if not enabled:
            first = next(iter(components.values()))
            return pd.Series(0, index=first.index)
        votes = None
        for name in enabled:
            value = components[name].fillna(False).astype(int)
            votes = value if votes is None else votes + value
        return votes

    def _regime(self, dataframe: DataFrame, params: dict[str, Any]) -> dict[str, pd.Series]:
        window = int(params["regime_window"])
        atr_median = dataframe["trend_atr_percent"].rolling(
            window,
            min_periods=max(2, window // 2),
        ).median()
        trend = (
            (dataframe["trend_adx"] > params["adx_entry_threshold"])
            & (dataframe["trend_ema_slow"] > dataframe["trend_ema_trend"])
        )
        high_vol = dataframe["trend_atr_percent"] > (atr_median * 1.5)
        return {
            "trend": trend.fillna(False),
            "high_vol": high_vol.fillna(False),
            "range": (~trend & ~high_vol).fillna(False),
        }

    def _entry_logic_reason(
        self,
        row: pd.Series,
        params: dict[str, Any],
        enabled: tuple[str, ...],
    ) -> str:
        return (
            f"{self.name}; score={row['trend_entry_score']:.2f}; "
            f"votes={int(row.get('trend_entry_votes', 0))}; "
            f"enabled={','.join(enabled)}"
        )


class TrendEntryScoreSumBaseline(BaseTrendEntryLogicVariant):
    name = "TrendEntryScoreSumBaseline"


class TrendEntryRequiredCore(BaseTrendEntryLogicVariant):
    name = "TrendEntryRequiredCore"

    def _entry_mask(self, dataframe, components, score, params, enabled):
        required = (
            components["ema_slow_trend"].fillna(False)
            & components["adx"].fillna(False)
            & components["atr"].fillna(False)
        )
        return (score >= params["entry_score_threshold"]) & required


class TrendEntryNOfM(BaseTrendEntryLogicVariant):
    name = "TrendEntryNOfM"

    def _entry_mask(self, dataframe, components, score, params, enabled):
        votes = self._vote_count(components, enabled)
        return votes >= min(int(params["n_of_m_required"]), len(enabled))


class TrendEntryVoting(BaseTrendEntryLogicVariant):
    name = "TrendEntryVoting"

    def _entry_mask(self, dataframe, components, score, params, enabled):
        votes = self._vote_count(components, enabled)
        return votes >= min(int(params["vote_threshold"]), len(enabled))


class TrendEntryDynamicRegimeWeights(BaseTrendEntryLogicVariant):
    name = "TrendEntryDynamicRegimeWeights"

    def _score(self, dataframe, components, params, enabled):
        weights = self._weights(params)
        regime = self._regime(dataframe, params)
        score = pd.Series(0.0, index=dataframe.index)
        trend_multiplier = pd.Series(1.0, index=dataframe.index).where(
            ~regime["trend"],
            params["dynamic_trend_multiplier"],
        )
        range_multiplier = pd.Series(1.0, index=dataframe.index).where(
            ~regime["range"],
            params["dynamic_range_multiplier"],
        )
        high_vol_multiplier = pd.Series(1.0, index=dataframe.index).where(
            ~regime["high_vol"],
            params["dynamic_high_vol_multiplier"],
        )
        for name in enabled:
            multiplier = pd.Series(1.0, index=dataframe.index)
            if name in {"ema_fast_slow", "ema_slow_trend", "adx", "breakout"}:
                multiplier *= trend_multiplier
            if name in {"rsi", "volume"}:
                multiplier *= range_multiplier
            if name == "atr":
                multiplier *= high_vol_multiplier
            score += components[name].fillna(False).astype(float) * weights[name] * multiplier
        return score


class TrendEntryAdaptiveThreshold(BaseTrendEntryLogicVariant):
    name = "TrendEntryAdaptiveThreshold"

    def _entry_mask(self, dataframe, components, score, params, enabled):
        regime = self._regime(dataframe, params)
        threshold = pd.Series(params["entry_score_threshold"], index=dataframe.index)
        threshold = threshold.where(
            ~regime["trend"],
            threshold + params["adaptive_threshold_trend_delta"],
        )
        threshold = threshold.where(
            ~regime["range"],
            threshold + params["adaptive_threshold_range_delta"],
        )
        threshold = threshold.where(
            ~regime["high_vol"],
            threshold + params["adaptive_threshold_high_vol_delta"],
        )
        threshold = threshold.clip(lower=0.0)
        dataframe["trend_entry_threshold"] = threshold
        return score >= threshold


class TrendEntryNormalizedScore(BaseTrendEntryLogicVariant):
    name = "TrendEntryNormalizedScore"

    def _entry_mask(self, dataframe, components, score, params, enabled):
        weights = self._weights(params)
        max_score = sum(max(0.0, float(weights[name])) for name in enabled)
        normalized = score / max(max_score, 1e-12)
        dataframe["trend_entry_score_normalized"] = normalized
        return normalized >= params["normalized_score_threshold"]


class TrendEntrySelectiveDisable(BaseTrendEntryLogicVariant):
    name = "TrendEntrySelectiveDisable"

    def _enabled_components(self, params: dict[str, Any]) -> tuple[str, ...]:
        mask = int(params["selective_disable_mask"])
        enabled = [
            name
            for index, name in enumerate(COMPONENT_ORDER)
            if not (mask & (1 << index))
        ]
        return tuple(enabled) or COMPONENT_ORDER
'''


class EntryLogicBacktestRunner(BacktestRunner):
    """BacktestRunner that registers entry-logic variants only in the sandbox."""

    def _copy_plugin_infrastructure(self, sandbox_user_data: Path) -> None:
        super()._copy_plugin_infrastructure(sandbox_user_data)
        plugin_dir = sandbox_user_data / "strategy_plugins"
        plugin_dir.mkdir(parents=True, exist_ok=True)
        (plugin_dir / "entry_logic_variants.py").write_text(
            ENTRY_LOGIC_PLUGIN_CODE,
            encoding="utf-8",
        )
        self._patch_registry(plugin_dir / "registry.py")

    def _patch_registry(self, registry_path: Path) -> None:
        text = registry_path.read_text(encoding="utf-8")
        if "entry_logic_variants" in text:
            return

        import_block = (
            "from .entry_logic_variants import (\n"
            "    TrendEntryAdaptiveThreshold,\n"
            "    TrendEntryDynamicRegimeWeights,\n"
            "    TrendEntryNOfM,\n"
            "    TrendEntryNormalizedScore,\n"
            "    TrendEntryRequiredCore,\n"
            "    TrendEntryScoreSumBaseline,\n"
            "    TrendEntrySelectiveDisable,\n"
            "    TrendEntryVoting,\n"
            ")\n"
        )
        text = text.replace("\n\nPLUGIN_CLASSES", f"\n{import_block}\nPLUGIN_CLASSES", 1)
        insert = (
            '    "TrendEntryScoreSumBaseline": TrendEntryScoreSumBaseline,\n'
            '    "TrendEntryRequiredCore": TrendEntryRequiredCore,\n'
            '    "TrendEntryNOfM": TrendEntryNOfM,\n'
            '    "TrendEntryVoting": TrendEntryVoting,\n'
            '    "TrendEntryDynamicRegimeWeights": TrendEntryDynamicRegimeWeights,\n'
            '    "TrendEntryAdaptiveThreshold": TrendEntryAdaptiveThreshold,\n'
            '    "TrendEntryNormalizedScore": TrendEntryNormalizedScore,\n'
            '    "TrendEntrySelectiveDisable": TrendEntrySelectiveDisable,\n'
        )
        text = text.replace(
            "PLUGIN_CLASSES: dict[str, type[StrategyPlugin]] = {\n",
            f"PLUGIN_CLASSES: dict[str, type[StrategyPlugin]] = {{\n{insert}",
            1,
        )
        registry_path.write_text(text, encoding="utf-8")


class EntryLogicWalkForwardRunner(EntryLogicBacktestRunner, WalkForwardBacktestRunner):
    """Walk-forward runner with sandbox-only entry-logic variant registration."""


class EntryLogicResearch:
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
        return [variant.__dict__.copy() for variant in ENTRY_LOGIC_VARIANTS]

    def plan(
        self,
        *,
        session_id: str | None = None,
        count_per_variant: int = 25,
        seed: int | None = None,
        variant_keys: list[str] | None = None,
        base_parameters: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if count_per_variant <= 0:
            raise ValueError("count_per_variant must be positive.")

        session_id = session_id or self._session_id()
        variants = self._selected_variants(variant_keys)
        samples = base_parameters or [
            payload["plugin_parameters"]
            for payload in TrendParameterSpace(seed=seed).sample_wide(count_per_variant)
        ]
        strategy_hash = self._strategy_hash()

        self.database.create_session(
            session_id=session_id,
            objective="Entry logic architecture research for TrendStrategy components.",
            strategy_name="LabPluginStrategy",
            search_method="entry_logic_research",
            goals={
                "count_per_variant": len(samples),
                "variant_count": len(variants),
                "total_experiments": len(samples) * len(variants),
                "seed": seed,
            },
            metadata={
                "study_type": "entry_logic_research",
                "parameter_distribution": "TrendParameterSpace.sample_wide",
                "variants": [variant.__dict__ for variant in variants],
            },
            status="paused",
        )

        created = []
        for sample_index, parameters in enumerate(samples):
            for variant in variants:
                payload = self._variant_payload(
                    variant=variant,
                    plugin_parameters=parameters,
                    session_id=session_id,
                    sample_index=sample_index,
                )
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
        runner = EntryLogicBacktestRunner(execution_mode=execution_mode)
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
                "entry_logic_candidate_session_id": candidate_session_id,
                "entry_logic_runner": True,
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

        runner = EntryLogicWalkForwardRunner(execution_mode=execution_mode)
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
        json_path = self.output_dir / f"entry_logic_report_{session_id}.json"
        html_path = self.output_dir / f"entry_logic_report_{session_id}.html"
        md_path = self.output_dir / f"entry_logic_report_{session_id}.md"
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
        rows = self._variant_metric_rows(completed)
        robustness = self._robustness_by_variant(session_id)
        walk_forward = self._walk_forward_by_variant(walk_forward_session_id)
        for row in rows:
            plugin = row["strategy_plugin"]
            row["robustness_score"] = robustness.get(plugin)
            row["walk_forward_survival_rate"] = walk_forward.get(plugin, {}).get("survival_rate")
            row["stability_index"] = walk_forward.get(plugin, {}).get("stability_index")
        return {
            "session_id": session_id,
            "generated_at": datetime.now(UTC).isoformat(),
            "session": session,
            "status_counts": self._status_counts(experiments),
            "variants": [variant.__dict__ for variant in ENTRY_LOGIC_VARIANTS],
            "rows": rows,
            "walk_forward_session_id": walk_forward_session_id,
            "walk_forward": walk_forward,
            "robustness": robustness,
        }

    def _variant_metric_rows(self, experiments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for experiment in experiments:
            grouped.setdefault(experiment["strategy_plugin"], []).append(experiment)

        rows = []
        for variant in ENTRY_LOGIC_VARIANTS:
            items = grouped.get(variant.strategy_plugin, [])
            metrics_rows = [item.get("metrics", {}) for item in items]
            pfs = [self._number(row.get("profit_factor")) for row in metrics_rows]
            pfs = [value for value in pfs if value is not None]
            drawdowns = [
                self._drawdown(row)
                for row in metrics_rows
            ]
            drawdowns = [value for value in drawdowns if value is not None]
            rows.append(
                {
                    "variant_key": variant.key,
                    "strategy_plugin": variant.strategy_plugin,
                    "label": variant.label,
                    "description": variant.description,
                    "experiment_count": len(items),
                    "profit_factor_mean": mean(pfs) if pfs else 0.0,
                    "profit_factor_median": median(pfs) if pfs else 0.0,
                    "profit_factor_best": max(pfs) if pfs else 0.0,
                    "sharpe_mean": self._metric_mean(metrics_rows, "sharpe"),
                    "drawdown_mean": mean(drawdowns) if drawdowns else 0.0,
                    "expectancy_mean": self._metric_mean(metrics_rows, "expectancy"),
                    "trades_mean": self._metric_mean(metrics_rows, "total_trades"),
                    "pf_gt_1_percent": (
                        sum(1 for value in pfs if value > 1.0) / len(pfs) * 100.0
                        if pfs
                        else 0.0
                    ),
                    "average_backtest_seconds": self._runtime_mean(items),
                    "best_experiment_id": self._best_experiment_id(items),
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
        grouped: dict[str, list[float]] = {}
        for row in analysis.get("robustness_ranking", []):
            plugin = experiment_variants.get(row.get("id"))
            score = self._number(row.get("robustness_score"))
            if plugin and score is not None:
                grouped.setdefault(plugin, []).append(score)
        return {plugin: mean(scores) for plugin, scores in grouped.items() if scores}

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
            if experiment and experiment.get("strategy_plugin"):
                grouped.setdefault(experiment["strategy_plugin"], []).append(fold)

        output = {}
        for plugin, folds in grouped.items():
            survived = sum(1 for fold in folds if fold.get("survived"))
            test_pfs = [
                self._number(fold.get("test_metrics", {}).get("profit_factor")) or 0.0
                for fold in folds
            ]
            pf_mean = mean(test_pfs) if test_pfs else 0.0
            pf_spread = max(test_pfs) - min(test_pfs) if len(test_pfs) > 1 else 0.0
            output[plugin] = {
                "survival_rate": survived / len(folds) if folds else 0.0,
                "stability_index": pf_mean / (pf_mean + pf_spread + 1e-12) if pf_mean > 0 else 0.0,
                "folds": len(folds),
            }
        return output

    def _variant_payload(
        self,
        *,
        variant: EntryLogicVariant,
        plugin_parameters: dict[str, Any],
        session_id: str,
        sample_index: int,
    ) -> dict[str, Any]:
        parameters = dict(plugin_parameters)
        parameters["entry_logic_variant"] = variant.key
        return {
            "experiment_type": "strategy_plugin",
            "strategy_plugin": variant.strategy_plugin,
            "plugin_parameters": parameters,
            "entry_logic": {
                "session_id": session_id,
                "variant_key": variant.key,
                "label": variant.label,
                "sample_index": sample_index,
                "baseline": variant.strategy_plugin == BASELINE_VARIANT,
            },
        }

    def _selected_variants(self, variant_keys: list[str] | None) -> list[EntryLogicVariant]:
        if not variant_keys:
            return list(ENTRY_LOGIC_VARIANTS)
        wanted = set(variant_keys)
        variants = [variant for variant in ENTRY_LOGIC_VARIANTS if variant.key in wanted]
        missing = wanted.difference(variant.key for variant in variants)
        if missing:
            raise ValueError(f"Unknown variant keys: {', '.join(sorted(missing))}")
        return variants

    def _strategy_hash(self) -> str:
        digest = hashlib.sha256()
        digest.update(ExperimentManager(database=self.database).strategy_hash().encode("utf-8"))
        digest.update(Path(__file__).read_bytes())
        digest.update(ENTRY_LOGIC_PLUGIN_CODE.encode("utf-8"))
        return digest.hexdigest()

    def _experiment_id(self, payload: dict[str, Any]) -> str:
        digest = hashlib.sha1(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:12]
        variant = payload.get("entry_logic", {}).get("variant_key", "entry")
        return f"entry-{variant}-{digest}-{uuid.uuid4().hex[:8]}"

    def _session_id(self) -> str:
        stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        return f"entry-logic-{stamp}-{uuid.uuid4().hex[:8]}"

    def _variant_key(self, experiment: dict[str, Any]) -> str | None:
        entry_logic = experiment.get("parameters", {}).get("entry_logic")
        if isinstance(entry_logic, dict):
            return entry_logic.get("variant_key")
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

    def _metric_mean(self, metrics_rows: list[dict[str, Any]], metric: str) -> float:
        values = [self._number(row.get(metric)) for row in metrics_rows]
        clean = [value for value in values if value is not None]
        return mean(clean) if clean else 0.0

    def _drawdown(self, metrics: dict[str, Any]) -> float | None:
        return self._number(metrics.get("max_drawdown_abs")) or self._number(
            metrics.get("max_relative_drawdown")
        )

    def _runtime_mean(self, experiments: list[dict[str, Any]]) -> float:
        values = [self._number(experiment.get("runtime_seconds")) for experiment in experiments]
        clean = [value for value in values if value is not None]
        return mean(clean) if clean else 0.0

    def _best_experiment_id(self, experiments: list[dict[str, Any]]) -> str | None:
        if not experiments:
            return None
        best = sorted(
            experiments,
            key=lambda experiment: self.ranking.composite_score(experiment.get("metrics", {})),
            reverse=True,
        )[0]
        return best.get("id")

    def _number(self, value: Any) -> float | None:
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def _render_markdown(self, analysis: dict[str, Any]) -> str:
        lines = [
            "# Entry Logic Research\n\n",
            f"Session: `{analysis['session_id']}`\n\n",
            "| Variant | Experiments | PF mean | PF best | Sharpe | Drawdown | Trades | Robustness | WF survival | Stability |\n",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n",
        ]
        for row in analysis["rows"]:
            lines.append(
                "| {label} | {count} | {pf_mean:.4f} | {pf_best:.4f} | {sharpe:.4f} | "
                "{drawdown:.4f} | {trades:.1f} | {robustness} | {survival} | {stability} |\n".format(
                    label=row["label"],
                    count=row["experiment_count"],
                    pf_mean=row["profit_factor_mean"],
                    pf_best=row["profit_factor_best"],
                    sharpe=row["sharpe_mean"],
                    drawdown=row["drawdown_mean"],
                    trades=row["trades_mean"],
                    robustness=self._format_optional(row.get("robustness_score")),
                    survival=self._format_optional(row.get("walk_forward_survival_rate")),
                    stability=self._format_optional(row.get("stability_index")),
                )
            )
        return "".join(lines)

    def _render_html(self, analysis: dict[str, Any]) -> str:
        payload = json.dumps(analysis, ensure_ascii=False)
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Entry Logic Research</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2933; }}
    table {{ border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 13px; }}
    th, td {{ border: 1px solid #d9e2ec; padding: 7px 9px; text-align: left; }}
    th {{ background: #f0f4f8; }}
  </style>
</head>
<body>
  <h1>Entry Logic Research</h1>
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
    const headers = ['Variant', 'Experiments', 'PF mean', 'PF best', 'Sharpe', 'Drawdown', 'Trades', 'Robustness', 'WF survival', 'Stability'];
    document.getElementById('rows').innerHTML =
      '<tr>' + headers.map(header => `<th>${{header}}</th>`).join('') + '</tr>' +
      (data.rows || []).map(row => '<tr>' + [
        row.label,
        row.experiment_count,
        f(row.profit_factor_mean),
        f(row.profit_factor_best),
        f(row.sharpe_mean),
        f(row.drawdown_mean),
        f(row.trades_mean, 1),
        f(row.robustness_score),
        f(row.walk_forward_survival_rate),
        f(row.stability_index),
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


def _parse_parameters_file(value: str | None) -> list[dict[str, Any]] | None:
    if not value:
        return None
    payload = json.loads(Path(value).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("base parameters file must contain a JSON list.")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Research TrendStrategy entry decision architectures.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("variants")

    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("--session-id")
    plan_parser.add_argument("--count-per-variant", type=int, default=25)
    plan_parser.add_argument("--seed", type=int)
    plan_parser.add_argument("--variants", help="Comma-separated variant keys.")
    plan_parser.add_argument("--base-parameters-file")

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
    research = EntryLogicResearch(output_dir=getattr(args, "output_dir", DEFAULT_OUTPUT_DIR))

    if args.command == "variants":
        result = {"variants": research.variants()}
    elif args.command == "plan":
        result = research.plan(
            session_id=args.session_id,
            count_per_variant=args.count_per_variant,
            seed=args.seed,
            variant_keys=_parse_variant_keys(args.variants),
            base_parameters=_parse_parameters_file(args.base_parameters_file),
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
