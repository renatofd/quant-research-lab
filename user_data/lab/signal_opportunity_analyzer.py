from __future__ import annotations

import argparse
import html
import json
import math
import sqlite3
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from .experiment_database import DEFAULT_DB_PATH
except ImportError:
    from experiment_database import DEFAULT_DB_PATH


DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "binance"
REPORT_STEM = "signal_opportunity_report"
TARGET_STRATEGIES = (
    "TrendStrategy",
    "PullbackStrategy",
    "MeanReversionStrategy",
    "NOfMTrendConfirmation",
    "NOfMTrendConfirmationStrategy",
)
STRATEGY_LABELS = {
    "NOfMTrendConfirmationStrategy": "NOfMTrendConfirmation",
}


@dataclass(frozen=True)
class ExperimentSpec:
    experiment_id: str
    strategy: str
    parameters: dict[str, Any]
    metrics: dict[str, Any]


class SignalOpportunityAnalyzer:
    """Offline candle-level signal funnel analysis for completed experiments."""

    def __init__(
        self,
        *,
        db_path: Path | str = DEFAULT_DB_PATH,
        data_dir: Path | str = DEFAULT_DATA_DIR,
        output_dir: Path | str = DEFAULT_OUTPUT_DIR,
        timeframe: str = "5m",
    ) -> None:
        self.db_path = Path(db_path)
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.timeframe = timeframe
        self._frames: dict[str, pd.DataFrame] = {}

    def analyze(
        self,
        *,
        max_experiments_per_strategy: int | None = None,
        min_completed_trades: int = 0,
    ) -> dict[str, Path]:
        experiments = self._load_experiments(
            max_per_strategy=max_experiments_per_strategy,
            min_completed_trades=min_completed_trades,
        )
        report = self._build_report(experiments)
        return self._write_reports(report)

    def _load_experiments(
        self,
        *,
        max_per_strategy: int | None,
        min_completed_trades: int,
    ) -> list[ExperimentSpec]:
        uri = f"file:{self.db_path.as_posix()}?mode=ro"
        grouped: dict[str, list[ExperimentSpec]] = defaultdict(list)
        with sqlite3.connect(uri, uri=True) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                select id, parameters_json, metrics_json
                from experiments
                where status = 'completed'
                  and metrics_json is not null
                order by created_at asc
                """
            ).fetchall()

        for row in rows:
            parameters = self._loads(row["parameters_json"], {})
            metrics = self._loads(row["metrics_json"], {})
            strategy = self._strategy_name(parameters)
            if strategy not in TARGET_STRATEGIES:
                continue
            if self._number(metrics.get("total_trades")) < min_completed_trades:
                continue
            spec = ExperimentSpec(
                experiment_id=row["id"],
                strategy=STRATEGY_LABELS.get(strategy, strategy),
                parameters=parameters.get("plugin_parameters", parameters),
                metrics=metrics,
            )
            grouped[spec.strategy].append(spec)

        experiments = []
        for strategy, rows in sorted(grouped.items()):
            selected = rows
            if max_per_strategy is not None:
                selected = sorted(
                    rows,
                    key=lambda item: self._number(item.metrics.get("profit_factor")),
                    reverse=True,
                )[:max_per_strategy]
            experiments.extend(selected)
        return experiments

    def _build_report(self, experiments: list[ExperimentSpec]) -> dict[str, Any]:
        frames = self._load_frames()
        analyzed = []
        redundancy_accumulator: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
        for experiment in experiments:
            for pair, frame in frames.items():
                result = self._analyze_experiment_pair(experiment, pair, frame)
                if result:
                    condition_series = result.pop("_condition_series")
                    self._update_redundancy(
                        redundancy_accumulator,
                        result["strategy"],
                        condition_series,
                    )
                    analyzed.append(result)

        strategy_summary = self._strategy_summary(analyzed)
        component_summary = self._component_summary(analyzed)
        redundancy = self._finalize_redundancy(redundancy_accumulator)
        weak_filters = self._weak_filters(component_summary)
        final_answer = self._trade_frequency_recommendations(component_summary)

        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "scope": {
                "db_path": str(self.db_path),
                "data_dir": str(self.data_dir),
                "timeframe": self.timeframe,
                "experiments": len(experiments),
                "experiment_pair_evaluations": len(analyzed),
                "strategies": sorted({item["strategy"] for item in analyzed}),
                "pairs": sorted(frames),
                "backtests_executed": False,
                "methodology": (
                    "Reconstructed enter_long opportunities offline from OHLCV candles "
                    "and completed experiment parameters. Final entries are signal "
                    "opportunities, not necessarily executed trades."
                ),
            },
            "strategy_summary": strategy_summary,
            "component_summary": component_summary,
            "redundancy_matrix": redundancy,
            "filters_that_reduce_frequency_without_pf_gain": weak_filters,
            "frequency_increase_recommendations": final_answer,
        }

    def _analyze_experiment_pair(
        self,
        experiment: ExperimentSpec,
        pair: str,
        frame: pd.DataFrame,
    ) -> dict[str, Any] | None:
        params = self._parameters_for(experiment.strategy, experiment.parameters)
        if not params:
            return None
        conditions, final_signal, ordered_steps = self._conditions_for(
            experiment.strategy,
            frame.copy(),
            pair,
            params,
        )
        if not conditions:
            return None

        valid = pd.Series(True, index=frame.index)
        for condition in conditions.values():
            valid &= condition.notna()
        valid &= frame["close"].notna() & frame["volume"].notna()

        sequential_counts = []
        current = valid.copy()
        sequential_counts.append({"step": "candles_total", "count": int(len(frame))})
        sequential_counts.append({"step": "valid_indicators", "count": int(valid.sum())})
        previous = int(valid.sum())
        for step in ordered_steps:
            current &= conditions[step].fillna(False)
            count = int(current.sum())
            sequential_counts.append(
                {
                    "step": step,
                    "count": count,
                    "eliminated": previous - count,
                    "eliminated_pct_of_previous": (previous - count) / previous if previous else 0.0,
                }
            )
            previous = count
        final_count = int((valid & final_signal.fillna(False)).sum())
        sequential_counts.append(
            {
                "step": "entrada_final",
                "count": final_count,
                "eliminated": previous - final_count,
                "eliminated_pct_of_previous": (previous - final_count) / previous if previous else 0.0,
            }
        )

        marginal = {}
        final_with_all = valid & final_signal.fillna(False)
        for name, condition in conditions.items():
            without = valid.copy()
            for other, other_condition in conditions.items():
                if other == name:
                    continue
                without &= other_condition.fillna(False)
            marginal[name] = {
                "passed": int((valid & condition.fillna(False)).sum()),
                "failed": int((valid & ~condition.fillna(False)).sum()),
                "marginal_eliminated": int((without & ~condition.fillna(False)).sum()),
                "conditional_pass_rate": (
                    int((without & condition.fillna(False)).sum()) / int(without.sum())
                    if int(without.sum())
                    else 0.0
                ),
                "final_opportunities": int(final_with_all.sum()),
            }

        metrics = experiment.metrics
        pair_metrics = metrics.get("profit_by_pair", {}).get(pair, {})
        return {
            "experiment_id": experiment.experiment_id,
            "strategy": experiment.strategy,
            "pair": pair,
            "profit_factor": self._number(pair_metrics.get("profit_factor", metrics.get("profit_factor"))),
            "expectancy": self._number(pair_metrics.get("expectancy", metrics.get("expectancy"))),
            "total_trades": self._number(pair_metrics.get("trades", metrics.get("total_trades"))),
            "sequential_counts": sequential_counts,
            "marginal": marginal,
            "_condition_series": {
                name: conditions[name].fillna(False).astype(bool)
                for name in conditions
            },
        }

    def _conditions_for(
        self,
        strategy: str,
        frame: pd.DataFrame,
        pair: str,
        params: dict[str, Any],
    ) -> tuple[dict[str, pd.Series], pd.Series, list[str]]:
        if strategy == "TrendStrategy":
            return self._trend_conditions(frame, params)
        if strategy == "PullbackStrategy":
            return self._pullback_conditions(frame, params)
        if strategy == "MeanReversionStrategy":
            return self._mean_reversion_conditions(frame, pair, params)
        if strategy == "NOfMTrendConfirmation":
            return self._nofm_conditions(frame, params)
        return {}, pd.Series(False, index=frame.index), []

    def _trend_conditions(
        self,
        frame: pd.DataFrame,
        params: dict[str, Any],
    ) -> tuple[dict[str, pd.Series], pd.Series, list[str]]:
        close = frame["close"].astype(float)
        high = frame["high"].astype(float)
        volume = frame["volume"].astype(float)
        ema_fast = close.ewm(span=params["ema_fast_period"], adjust=False).mean()
        ema_slow = close.ewm(span=params["ema_slow_period"], adjust=False).mean()
        ema_trend = close.ewm(span=params["ema_trend_period"], adjust=False).mean()
        rsi = self._rsi(close, params["rsi_period"])
        atr_pct = self._atr(frame, params["atr_period"]) / close * 100.0
        adx = self._adx(frame, params["adx_period"])
        volume_mean = volume.rolling(params["volume_mean_period"], min_periods=params["volume_mean_period"]).mean()
        conditions = {
            "ema_fast_slow": ema_fast > ema_slow,
            "ema_slow_trend": ema_slow > ema_trend,
            "adx": adx > params["adx_entry_threshold"],
            "rsi": rsi.between(params["rsi_min"], params["rsi_max"]),
            "volume": volume > volume_mean * params["volume_multiplier"],
            "atr": atr_pct > params["atr_min_percent"],
            "breakout": close > high.shift(1),
        }
        score = (
            conditions["ema_fast_slow"].astype(float) * params["ema_fast_slow_weight"]
            + conditions["ema_slow_trend"].astype(float) * params["ema_slow_trend_weight"]
            + conditions["adx"].astype(float) * params["adx_weight"]
            + conditions["rsi"].astype(float) * params["rsi_weight"]
            + conditions["volume"].astype(float) * params["volume_weight"]
            + conditions["atr"].astype(float) * params["atr_weight"]
            + conditions["breakout"].astype(float) * params["breakout_weight"]
        )
        final = score >= params["entry_score_threshold"]
        return conditions, final, ["ema_fast_slow", "ema_slow_trend", "adx", "atr", "rsi", "volume", "breakout"]

    def _pullback_conditions(
        self,
        frame: pd.DataFrame,
        params: dict[str, Any],
    ) -> tuple[dict[str, pd.Series], pd.Series, list[str]]:
        close = frame["close"].astype(float)
        open_ = frame["open"].astype(float)
        high = frame["high"].astype(float)
        low = frame["low"].astype(float)
        volume = frame["volume"].astype(float)
        ema_fast = close.ewm(span=params["ema_fast_period"], adjust=False).mean()
        ema_slow = close.ewm(span=params["ema_slow_period"], adjust=False).mean()
        ema_trend = close.ewm(span=params["ema_trend_period"], adjust=False).mean()
        rsi = self._rsi(close, params["rsi_period"])
        atr_pct = self._atr(frame, params["atr_period"]) / close * 100.0
        volume_mean = volume.rolling(params["volume_mean_period"], min_periods=params["volume_mean_period"]).mean()
        tolerance = params["pullback_tolerance_percent"] / 100.0
        max_depth = params["max_pullback_depth_percent"] / 100.0
        near_fast = (low <= ema_fast * (1.0 + tolerance)) & (low >= ema_fast * (1.0 - max_depth))
        recent_touch = near_fast.astype(int).rolling(params["pullback_lookback"], min_periods=1).max().astype(bool)
        controlled = low.rolling(params["pullback_lookback"], min_periods=1).min() >= ema_fast * (1.0 - max_depth)
        conditions = {
            "trend": (ema_fast > ema_slow) & (ema_slow > ema_trend) & (close > ema_trend * (1.0 + params["trend_buffer_percent"] / 100.0)),
            "pullback_touch": recent_touch,
            "pullback_control": controlled,
            "reclaim_ema": close > ema_fast,
            "confirmation": (close > open_) & (close > high.shift(1)) & (close > close.shift(1) * (1.0 + params["recovery_close_percent"] / 100.0)),
            "rsi": rsi.between(params["rsi_min"], params["rsi_max"]),
            "volume": volume > volume_mean * params["volume_multiplier"],
            "atr": atr_pct > params["atr_min_percent"],
        }
        score = (
            conditions["trend"].astype(float) * params["trend_weight"]
            + conditions["pullback_touch"].astype(float) * params["pullback_touch_weight"]
            + conditions["pullback_control"].astype(float) * params["pullback_control_weight"]
            + conditions["reclaim_ema"].astype(float) * params["reclaim_ema_weight"]
            + conditions["confirmation"].astype(float) * params["confirmation_weight"]
            + conditions["rsi"].astype(float) * params["rsi_weight"]
            + conditions["volume"].astype(float) * params["volume_weight"]
            + conditions["atr"].astype(float) * params["atr_weight"]
        )
        final = score >= params["entry_score_threshold"]
        return conditions, final, ["trend", "pullback_touch", "pullback_control", "reclaim_ema", "confirmation", "rsi", "volume", "atr"]

    def _mean_reversion_conditions(
        self,
        frame: pd.DataFrame,
        pair: str,
        params: dict[str, Any],
    ) -> tuple[dict[str, pd.Series], pd.Series, list[str]]:
        close = frame["close"].astype(float)
        high = frame["high"].astype(float)
        low = frame["low"].astype(float)
        open_ = frame["open"].astype(float)
        volume = frame["volume"].astype(float)
        typical = (high + low + close) / 3.0
        bb_mid = close.rolling(params["bollinger_period"], min_periods=params["bollinger_period"]).mean()
        bb_std = close.rolling(params["bollinger_period"], min_periods=params["bollinger_period"]).std(ddof=0)
        bb_low = bb_mid - bb_std * params["bollinger_std"]
        z_mean = close.rolling(params["zscore_period"], min_periods=params["zscore_period"]).mean()
        z_std = close.rolling(params["zscore_period"], min_periods=params["zscore_period"]).std(ddof=0)
        zscore = (close - z_mean) / z_std.replace(0.0, pd.NA)
        rolling_volume = volume.rolling(params["vwap_period"], min_periods=params["vwap_period"]).sum()
        vwap = (typical * volume).rolling(params["vwap_period"], min_periods=params["vwap_period"]).sum() / rolling_volume.replace(0.0, pd.NA)
        vwap_dev = (close - vwap) / vwap.replace(0.0, pd.NA) * 100.0
        rsi = self._rsi(close, params["rsi_period"])
        atr_pct = self._atr(frame, params["atr_period"]) / close * 100.0
        vol_mean = volume.rolling(params["volume_mean_period"], min_periods=params["volume_mean_period"]).mean()
        vol_ratio = volume / vol_mean.replace(0.0, pd.NA)
        reclaim_fraction = (close - low) / (high - low).replace(0.0, pd.NA)
        pair_allowed = pair.upper() not in self._csv_set(params["excluded_pairs"])
        dates = pd.to_datetime(frame["date"], utc=True, errors="coerce") if "date" in frame else pd.Series(pd.NaT, index=frame.index)
        weekday_set = self._csv_set(params["allowed_weekdays"])
        hour_set = self._int_set(params["allowed_hours"])
        session_set = self._csv_set(params["allowed_sessions"])
        time_allowed = pd.Series(True, index=frame.index)
        if weekday_set:
            time_allowed &= dates.dt.day_name().str.upper().isin(weekday_set)
        if hour_set:
            time_allowed &= dates.dt.hour.isin(hour_set)
        if session_set:
            time_allowed &= dates.dt.hour.map(self._session).isin(session_set)
        reclaim = (
            (close >= open_)
            & (reclaim_fraction >= params["reclaim_min_fraction"])
            & (close > close.shift(1))
            if params["require_bullish_reclaim"]
            else pd.Series(True, index=frame.index)
        )
        conditions = {
            "pair_allowed": pd.Series(pair_allowed, index=frame.index),
            "time_allowed": time_allowed,
            "bollinger_or_zscore": (close <= bb_low) | (zscore <= params["entry_zscore"]),
            "vwap": vwap_dev <= -params["vwap_deviation_min_pct"],
            "rsi": rsi <= params["rsi_oversold"],
            "atr": atr_pct.between(params["atr_min_percent"], params["atr_max_percent"]),
            "volume": vol_ratio.between(params["volume_min_ratio"], params["volume_max_ratio"]),
            "reclaim": reclaim,
        }
        final = pd.Series(True, index=frame.index)
        for condition in conditions.values():
            final &= condition.fillna(False)
        return conditions, final, ["pair_allowed", "time_allowed", "bollinger_or_zscore", "vwap", "rsi", "atr", "volume", "reclaim"]

    def _nofm_conditions(
        self,
        frame: pd.DataFrame,
        params: dict[str, Any],
    ) -> tuple[dict[str, pd.Series], pd.Series, list[str]]:
        close = frame["close"].astype(float)
        high = frame["high"].astype(float)
        volume = frame["volume"].astype(float)
        ema_fast = close.ewm(span=params["ema_fast_period"], adjust=False).mean()
        ema_slow = close.ewm(span=params["ema_slow_period"], adjust=False).mean()
        ema_trend = close.ewm(span=params["ema_trend_period"], adjust=False).mean()
        rsi = self._rsi(close, params["rsi_period"])
        atr_pct = self._atr(frame, params["atr_period"]) / close * 100.0
        adx = self._adx(frame, params["adx_period"])
        volume_mean = volume.rolling(params["volume_mean_period"], min_periods=params["volume_mean_period"]).mean()
        previous_high = high.shift(params["breakout_lookback"]).rolling(params["breakout_lookback"], min_periods=1).max()
        conditions = {
            "ema_fast_slow": ema_fast > ema_slow,
            "ema_slow_trend": ema_slow > ema_trend,
            "adx": adx > params["adx_entry_threshold"],
            "rsi": rsi.between(params["rsi_min"], params["rsi_max"]),
            "volume": volume > volume_mean * params["volume_multiplier"],
            "atr": atr_pct > params["atr_min_percent"],
            "breakout": close > previous_high,
        }
        count = sum(condition.astype(int) for condition in conditions.values())
        gate = pd.Series(True, index=frame.index)
        if params["require_ema_trend"]:
            gate &= conditions["ema_fast_slow"] & conditions["ema_slow_trend"]
        if params["require_price_above_trend"]:
            gate &= close > ema_trend
        final = (count >= params["n_required"]) & gate
        return conditions, final, ["ema_fast_slow", "ema_slow_trend", "adx", "atr", "rsi", "volume", "breakout"]

    def _strategy_summary(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[row["strategy"]].append(row)
        output = {}
        for strategy, items in grouped.items():
            sequential = self._aggregate_funnels(items)
            output[strategy] = {
                "experiment_pair_evaluations": len(items),
                "avg_profit_factor": statistics.mean([item["profit_factor"] for item in items]) if items else 0.0,
                "total_signal_opportunities": sum(item["sequential_counts"][-1]["count"] for item in items),
                "funnel": sequential,
            }
        return output

    def _aggregate_funnels(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, Counter] = defaultdict(Counter)
        order = []
        for item in items:
            for step in item["sequential_counts"]:
                name = step["step"]
                if name not in order:
                    order.append(name)
                grouped[name]["count"] += step.get("count", 0)
                grouped[name]["eliminated"] += step.get("eliminated", 0)
        rows = []
        previous = None
        for name in order:
            count = grouped[name]["count"]
            eliminated = grouped[name]["eliminated"] if previous is not None else 0
            rows.append(
                {
                    "step": name,
                    "count": count,
                    "retention_from_previous": count / previous if previous else 1.0,
                    "eliminated": eliminated,
                    "eliminated_pct": eliminated / previous if previous else 0.0,
                }
            )
            previous = count
        return rows

    def _component_summary(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        by_component: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            for component, stats in row["marginal"].items():
                by_component[f"{row['strategy']}:{component}"].append(
                    {
                        **stats,
                        "profit_factor": row["profit_factor"],
                        "total_trades": row["total_trades"],
                    }
                )
        output = {}
        for key, items in sorted(by_component.items()):
            passed = sum(item["passed"] for item in items)
            failed = sum(item["failed"] for item in items)
            marginal_eliminated = sum(item["marginal_eliminated"] for item in items)
            final_opportunities = sum(item["final_opportunities"] for item in items)
            pf = statistics.mean([item["profit_factor"] for item in items]) if items else 0.0
            conditional_pass = statistics.mean([item["conditional_pass_rate"] for item in items]) if items else 0.0
            opportunity_loss = failed / (passed + failed) if passed + failed else 0.0
            trade_frequency_gain = marginal_eliminated / final_opportunities if final_opportunities else 0.0
            precision_gain = pf * conditional_pass
            contribution = precision_gain - opportunity_loss + min(1.0, trade_frequency_gain) * 0.25
            output[key] = {
                "passed": passed,
                "failed": failed,
                "opportunity_gain": passed,
                "opportunity_loss": opportunity_loss,
                "marginal_eliminated": marginal_eliminated,
                "impact_conditional": conditional_pass,
                "avg_profit_factor": pf,
                "precision_gain": precision_gain,
                "trade_frequency_gain": trade_frequency_gain,
                "contribution_score": contribution,
                "classification": self._component_classification(opportunity_loss, precision_gain, contribution),
            }
        return output

    def _update_redundancy(
        self,
        accumulator: dict[str, list[float]],
        strategy: str,
        conditions: dict[str, pd.Series],
    ) -> None:
        names = list(conditions)
        total = len(next(iter(conditions.values()))) if names else 0
        for i, left in enumerate(names):
            left_values = conditions[left]
            for right in names[i + 1 :]:
                right_values = conditions[right]
                both = int((left_values & right_values).sum())
                either = int((left_values | right_values).sum())
                same = int((left_values == right_values).sum())
                jaccard = both / either if either else 0.0
                agreement = same / total if total else 0.0
                item = accumulator[f"{strategy}:{left}|{right}"]
                item[0] += (jaccard + agreement) / 2.0
                item[1] += 1.0

    def _finalize_redundancy(self, pairs: dict[str, list[float]]) -> dict[str, Any]:
        return {
            key: {
                "redundancy_score": values[0] / values[1] if values[1] else 0.0,
                "samples": int(values[1]),
                "classification": "redundant" if (values[0] / values[1] if values[1] else 0.0) >= 0.80 else "distinct",
            }
            for key, values in sorted(pairs.items())
        }

    def _weak_filters(self, components: dict[str, Any]) -> list[dict[str, Any]]:
        rows = []
        for key, stats in components.items():
            if stats["opportunity_loss"] >= 0.50 and stats["avg_profit_factor"] <= 1.0:
                rows.append({"component": key, **stats})
        return sorted(rows, key=lambda item: item["opportunity_loss"], reverse=True)

    def _trade_frequency_recommendations(self, components: dict[str, Any]) -> list[dict[str, Any]]:
        candidates = []
        for key, stats in components.items():
            if stats["opportunity_loss"] > 0.20:
                candidates.append(
                    {
                        "component": key,
                        "reason": (
                            "High opportunity loss with limited precision contribution"
                            if stats["precision_gain"] < 1.0
                            else "High opportunity loss; investigate gentler threshold before removal"
                        ),
                        "opportunity_loss": stats["opportunity_loss"],
                        "precision_gain": stats["precision_gain"],
                        "contribution_score": stats["contribution_score"],
                    }
                )
        return sorted(candidates, key=lambda item: (item["precision_gain"], -item["opportunity_loss"]))[:20]

    def _component_classification(self, opportunity_loss: float, precision_gain: float, contribution: float) -> str:
        if contribution > 0.5 and precision_gain > 1.0:
            return "aumenta_qualidade"
        if opportunity_loss > 0.6 and precision_gain < 1.0:
            return "gargalo"
        if opportunity_loss > 0.4:
            return "reduz_frequencia"
        return "neutro_ou_redundante"

    def _load_frames(self) -> dict[str, pd.DataFrame]:
        frames = {}
        for path in sorted(self.data_dir.glob(f"*-{self.timeframe}.feather")):
            pair = path.name[: -len(f"-{self.timeframe}.feather")].replace("_", "/")
            frame = pd.read_feather(path)
            frame["date"] = pd.to_datetime(frame["date"], utc=True, errors="coerce")
            frames[pair] = frame
        return frames

    def _parameters_for(self, strategy: str, raw: dict[str, Any]) -> dict[str, Any]:
        if strategy == "TrendStrategy":
            return self._resolve(raw, self._trend_defaults(), self._trend_aliases())
        if strategy == "PullbackStrategy":
            return self._resolve(raw, self._pullback_defaults(), self._trend_aliases())
        if strategy == "MeanReversionStrategy":
            return self._resolve(raw, self._mean_defaults(), {})
        if strategy == "NOfMTrendConfirmation":
            return self._resolve(raw, self._nofm_defaults(), {})
        return {}

    def _resolve(self, raw: dict[str, Any], defaults: dict[str, Any], aliases: dict[str, str]) -> dict[str, Any]:
        resolved = dict(defaults)
        for key in list(resolved):
            if key in raw:
                resolved[key] = raw[key]
            elif aliases.get(key) in raw:
                resolved[key] = raw[aliases[key]]
        for key, value in list(resolved.items()):
            if isinstance(defaults[key], bool):
                resolved[key] = self._bool(value)
            elif isinstance(defaults[key], int):
                resolved[key] = int(float(value))
            elif isinstance(defaults[key], float):
                resolved[key] = float(value)
            else:
                resolved[key] = str(value)
        if "atr_min_percent" in resolved and "atr_max_percent" in resolved and resolved["atr_min_percent"] > resolved["atr_max_percent"]:
            resolved["atr_min_percent"], resolved["atr_max_percent"] = resolved["atr_max_percent"], resolved["atr_min_percent"]
        if "volume_min_ratio" in resolved and "volume_max_ratio" in resolved and resolved["volume_min_ratio"] > resolved["volume_max_ratio"]:
            resolved["volume_min_ratio"], resolved["volume_max_ratio"] = resolved["volume_max_ratio"], resolved["volume_min_ratio"]
        if resolved.get("ema_fast_period", 0) >= resolved.get("ema_slow_period", 9999):
            resolved["ema_slow_period"] = resolved["ema_fast_period"] + 1
        if resolved.get("ema_slow_period", 0) >= resolved.get("ema_trend_period", 9999):
            resolved["ema_trend_period"] = resolved["ema_slow_period"] + 1
        return resolved

    def _trend_defaults(self) -> dict[str, Any]:
        return {
            "ema_fast_period": 12,
            "ema_slow_period": 34,
            "ema_trend_period": 200,
            "adx_period": 14,
            "atr_period": 14,
            "rsi_period": 14,
            "volume_mean_period": 20,
            "adx_entry_threshold": 22.0,
            "adx_exit_threshold": 18.0,
            "rsi_min": 42.0,
            "rsi_max": 70.0,
            "volume_multiplier": 1.1,
            "atr_min_percent": 0.20,
            "entry_score_threshold": 7.0,
            "ema_fast_slow_weight": 2.0,
            "ema_slow_trend_weight": 2.0,
            "adx_weight": 2.0,
            "rsi_weight": 1.0,
            "volume_weight": 1.0,
            "atr_weight": 1.0,
            "breakout_weight": 2.0,
        }

    def _pullback_defaults(self) -> dict[str, Any]:
        defaults = self._trend_defaults()
        defaults.update(
            {
                "ema_fast_period": 21,
                "ema_slow_period": 55,
                "pullback_lookback": 5,
                "trend_buffer_percent": 0.0,
                "pullback_tolerance_percent": 0.35,
                "max_pullback_depth_percent": 3.0,
                "recovery_close_percent": 0.05,
                "trend_weight": 2.0,
                "pullback_touch_weight": 2.0,
                "pullback_control_weight": 1.5,
                "reclaim_ema_weight": 2.0,
                "confirmation_weight": 2.0,
            }
        )
        return defaults

    def _mean_defaults(self) -> dict[str, Any]:
        return {
            "bollinger_period": 24,
            "bollinger_std": 2.2,
            "zscore_period": 48,
            "entry_zscore": -2.0,
            "exit_zscore": -0.15,
            "vwap_period": 48,
            "vwap_deviation_min_pct": 0.45,
            "rsi_period": 14,
            "rsi_oversold": 34.0,
            "rsi_exit": 52.0,
            "atr_period": 14,
            "atr_min_percent": 0.08,
            "atr_max_percent": 3.0,
            "volume_mean_period": 30,
            "volume_min_ratio": 0.75,
            "volume_max_ratio": 4.0,
            "require_bullish_reclaim": True,
            "reclaim_min_fraction": 0.55,
            "allowed_weekdays": "TUESDAY,FRIDAY",
            "allowed_hours": "14,15,16",
            "allowed_sessions": "NY",
            "excluded_pairs": "BTC/USDT,XRP/USDT",
        }

    def _nofm_defaults(self) -> dict[str, Any]:
        defaults = self._trend_defaults()
        defaults.update(
            {
                "n_required": 4,
                "require_ema_trend": True,
                "require_price_above_trend": False,
                "breakout_lookback": 1,
            }
        )
        return defaults

    def _trend_aliases(self) -> dict[str, str]:
        return {
            "ema_fast_period": "buy_ema_fast",
            "ema_slow_period": "buy_ema_slow",
            "ema_trend_period": "buy_ema_trend",
            "rsi_min": "buy_rsi_min",
            "rsi_max": "buy_rsi_max",
            "volume_multiplier": "buy_volume_mult",
        }

    def _write_reports(self, report: dict[str, Any]) -> dict[str, Path]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        json_path = self.output_dir / f"{REPORT_STEM}.json"
        markdown_path = self.output_dir / f"{REPORT_STEM}.md"
        html_path = self.output_dir / f"{REPORT_STEM}.html"
        json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        markdown_path.write_text(self._markdown(report), encoding="utf-8")
        html_path.write_text(self._html(report), encoding="utf-8")
        return {"json": json_path, "markdown": markdown_path, "html": html_path}

    def _markdown(self, report: dict[str, Any]) -> str:
        lines = [
            "# Signal Opportunity Report",
            "",
            "## Scope",
            f"- Experiments: {report['scope']['experiments']}",
            f"- Experiment-pair evaluations: {report['scope']['experiment_pair_evaluations']}",
            f"- Backtests executed: {report['scope']['backtests_executed']}",
            f"- Methodology: {report['scope']['methodology']}",
            "",
            "## Strategy Funnels",
        ]
        for strategy, summary in report["strategy_summary"].items():
            lines.extend(["", f"### {strategy}", "| Step | Count | Eliminated | Eliminated % |", "|---|---:|---:|---:|"])
            for row in summary["funnel"]:
                lines.append(
                    f"| {row['step']} | {row['count']} | {row['eliminated']} | {row['eliminated_pct']:.2%} |"
                )
        lines.extend(["", "## Main Bottlenecks", "| Component | Loss | Conditional pass | PF | Classification |", "|---|---:|---:|---:|---|"])
        for key, stats in sorted(
            report["component_summary"].items(),
            key=lambda item: item[1]["opportunity_loss"],
            reverse=True,
        )[:30]:
            lines.append(
                f"| {key} | {stats['opportunity_loss']:.2%} | {stats['impact_conditional']:.2%} | {stats['avg_profit_factor']:.3f} | {stats['classification']} |"
            )
        lines.extend(["", "## Recommendation"])
        for row in report["frequency_increase_recommendations"][:10]:
            lines.append(f"- {row['component']}: {row['reason']}")
        return "\n".join(lines) + "\n"

    def _html(self, report: dict[str, Any]) -> str:
        funnel_html = []
        for strategy, summary in report["strategy_summary"].items():
            rows = "".join(
                f"<tr><td>{html.escape(row['step'])}</td><td>{row['count']}</td><td>{row['eliminated']}</td><td>{row['eliminated_pct']:.2%}</td></tr>"
                for row in summary["funnel"]
            )
            funnel_html.append(
                f"<h2>{html.escape(strategy)}</h2><table><tr><th>Step</th><th>Count</th><th>Eliminated</th><th>Eliminated %</th></tr>{rows}</table>"
            )
        bottlenecks = "".join(
            f"<tr><td>{html.escape(key)}</td><td>{stats['opportunity_loss']:.2%}</td><td>{stats['impact_conditional']:.2%}</td><td>{stats['avg_profit_factor']:.3f}</td><td>{html.escape(stats['classification'])}</td></tr>"
            for key, stats in sorted(report["component_summary"].items(), key=lambda item: item[1]["opportunity_loss"], reverse=True)[:40]
        )
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Signal Opportunity Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #1f2933; }}
    table {{ border-collapse: collapse; width: 100%; margin: 16px 0 28px; }}
    th, td {{ border: 1px solid #d9e2ec; padding: 8px; text-align: left; }}
    th {{ background: #f0f4f8; }}
    pre {{ background: #f7f9fb; padding: 12px; overflow: auto; }}
  </style>
</head>
<body>
  <h1>Signal Opportunity Report</h1>
  <pre>{html.escape(json.dumps(report['scope'], indent=2, sort_keys=True))}</pre>
  {''.join(funnel_html)}
  <h2>Component Bottlenecks</h2>
  <table><tr><th>Component</th><th>Opportunity loss</th><th>Conditional pass</th><th>PF</th><th>Class</th></tr>{bottlenecks}</table>
  <h2>Frequency Recommendations</h2>
  <pre>{html.escape(json.dumps(report['frequency_increase_recommendations'][:20], indent=2, sort_keys=True))}</pre>
</body>
</html>
"""

    def _rsi(self, close: pd.Series, period: int) -> pd.Series:
        delta = close.diff()
        gain = delta.clip(lower=0.0)
        loss = -delta.clip(upper=0.0)
        avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        relative_strength = avg_gain / avg_loss.where(avg_loss != 0.0)
        return 100.0 - (100.0 / (1.0 + relative_strength))

    def _atr(self, frame: pd.DataFrame, period: int) -> pd.Series:
        previous_close = frame["close"].shift(1)
        true_range = pd.concat(
            [
                frame["high"] - frame["low"],
                (frame["high"] - previous_close).abs(),
                (frame["low"] - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        return true_range.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    def _adx(self, frame: pd.DataFrame, period: int) -> pd.Series:
        up_move = frame["high"].diff()
        down_move = -frame["low"].diff()
        plus_dm = up_move.where((up_move > down_move) & (up_move > 0.0), 0.0)
        minus_dm = down_move.where((down_move > up_move) & (down_move > 0.0), 0.0)
        atr = self._atr(frame, period)
        plus_di = 100.0 * plus_dm.ewm(alpha=1 / period, min_periods=period, adjust=False).mean() / atr
        minus_di = 100.0 * minus_dm.ewm(alpha=1 / period, min_periods=period, adjust=False).mean() / atr
        dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di)
        return dx.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    def _strategy_name(self, parameters: dict[str, Any]) -> str:
        return parameters.get("strategy_plugin") or parameters.get("strategy_name") or "UNKNOWN"

    def _session(self, hour: int) -> str:
        if 0 <= int(hour) < 7:
            return "ASIA"
        if 7 <= int(hour) < 13:
            return "LONDON"
        if 13 <= int(hour) < 21:
            return "NY"
        return "ASIA"

    def _csv_set(self, value: str) -> set[str]:
        return {item.strip().upper() for item in str(value).split(",") if item.strip()}

    def _int_set(self, value: str) -> set[int]:
        output = set()
        for item in str(value).split(","):
            item = item.strip()
            if item:
                try:
                    output.add(int(item))
                except ValueError:
                    pass
        return output

    def _bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _loads(self, value: str | None, default: Any) -> Any:
        if not value:
            return default
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default

    def _number(self, value: Any) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return 0.0
        return 0.0 if math.isnan(parsed) or math.isinf(parsed) else parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Offline signal opportunity funnel analyzer.")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--timeframe", default="5m")
    parser.add_argument("--max-experiments-per-strategy", type=int)
    parser.add_argument("--min-completed-trades", type=int, default=0)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    analyzer = SignalOpportunityAnalyzer(
        db_path=args.db_path,
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        timeframe=args.timeframe,
    )
    paths = analyzer.analyze(
        max_experiments_per_strategy=args.max_experiments_per_strategy,
        min_completed_trades=args.min_completed_trades,
    )
    print(json.dumps({key: str(path) for key, path in paths.items()}, indent=2))


if __name__ == "__main__":
    main()
