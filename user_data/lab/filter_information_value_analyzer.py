from __future__ import annotations

import argparse
import csv
import html
import json
import math
import sqlite3
import statistics
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from .experiment_database import DEFAULT_DB_PATH
    from .signal_opportunity_analyzer import SignalOpportunityAnalyzer
except ImportError:
    from experiment_database import DEFAULT_DB_PATH
    from signal_opportunity_analyzer import SignalOpportunityAnalyzer


REPORT_STEM = "filter_information_value_report"
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
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "binance"


@dataclass(frozen=True)
class ExperimentSpec:
    experiment_id: str
    strategy: str
    parameters: dict[str, Any]
    metrics: dict[str, Any]
    result_path: str | None


@dataclass
class FilterStats:
    strategy: str
    filter_name: str
    opportunities: int = 0
    approved: int = 0
    rejected: int = 0
    observed_trades: int = 0
    approved_winners: int = 0
    approved_losers: int = 0
    blocked_winners: int = 0
    blocked_losers: int = 0
    approved_profit: float = 0.0
    blocked_profit: float = 0.0
    eliminated_profit: float = 0.0
    avoided_loss_abs: float = 0.0
    marginal_candidates: int = 0
    marginal_observed_trades: int = 0
    marginal_winners: int = 0
    marginal_losers: int = 0
    marginal_profit: float = 0.0
    experiment_profit_factors: list[float] = field(default_factory=list)
    experiment_drawdowns: list[float] = field(default_factory=list)
    experiment_sharpes: list[float] = field(default_factory=list)
    experiment_expectancies: list[float] = field(default_factory=list)


@dataclass
class RedundancyStats:
    strategy: str
    left: str
    right: str
    n00: int = 0
    n01: int = 0
    n10: int = 0
    n11: int = 0


class FilterInformationValueAnalyzer:
    """Offline information-value analysis for filters using existing lab artifacts only."""

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
        self.signal = SignalOpportunityAnalyzer(
            db_path=self.db_path,
            data_dir=self.data_dir,
            output_dir=self.output_dir,
            timeframe=self.timeframe,
        )
        self._date_positions: dict[str, dict[int, int]] = {}

    def analyze(
        self,
        *,
        max_experiments_per_strategy: int | None = None,
        min_completed_trades: int = 0,
        full_candle_reconstruction: bool = False,
    ) -> dict[str, Path]:
        if not full_candle_reconstruction:
            return self._analyze_from_existing_artifacts(
                max_experiments_per_strategy=max_experiments_per_strategy,
                min_completed_trades=min_completed_trades,
            )

        experiments = self._load_experiments(
            max_per_strategy=max_experiments_per_strategy,
            min_completed_trades=min_completed_trades,
        )
        frames = self.signal._load_frames()
        self._date_positions = {
            pair: self._build_date_positions(frame)
            for pair, frame in frames.items()
        }

        filters: dict[tuple[str, str], FilterStats] = {}
        redundancy: dict[tuple[str, str, str], RedundancyStats] = {}
        missing_trade_artifacts = 0
        experiment_pair_evaluations = 0
        parsed_trade_experiments = 0
        observed_trade_entries = 0

        for experiment in experiments:
            trades_by_pair = self._load_trades(experiment)
            if trades_by_pair is None:
                missing_trade_artifacts += 1
                trades_by_pair = {}
            else:
                parsed_trade_experiments += 1

            for pair, frame in frames.items():
                result = self._analyze_experiment_pair(
                    experiment=experiment,
                    pair=pair,
                    frame=frame,
                    trades=trades_by_pair.get(pair, []),
                    filters=filters,
                    redundancy=redundancy,
                )
                if result:
                    experiment_pair_evaluations += 1
                    observed_trade_entries += result

        matrix_rows = [self._filter_row(stats) for stats in filters.values()]
        confusion_rows = [self._confusion_row(stats) for stats in filters.values()]
        ranking_rows = self._ranking_rows(matrix_rows, confusion_rows)
        redundancy_rows = [self._redundancy_row(stats) for stats in redundancy.values()]
        objective_answers = self._objective_answers(matrix_rows, ranking_rows, confusion_rows, redundancy_rows)

        report = {
            "generated_at": datetime.now(UTC).isoformat(),
            "scope": {
                "db_path": str(self.db_path),
                "data_dir": str(self.data_dir),
                "timeframe": self.timeframe,
                "experiments_analyzed": len(experiments),
                "experiment_pair_evaluations": experiment_pair_evaluations,
                "parsed_trade_experiments": parsed_trade_experiments,
                "missing_trade_artifacts": missing_trade_artifacts,
                "observed_trade_entries_matched_to_candles": observed_trade_entries,
                "backtests_executed": False,
                "methodology": (
                    "Filters were reconstructed offline from OHLCV candles and completed "
                    "experiment parameters. Confusion metrics use only official observed "
                    "trade entries found in existing result artifacts. Rejected candles "
                    "without a realized trade outcome are not treated as winners or losers."
                ),
                "limitations": [
                    (
                        "True outcomes for never-executed blocked candles are unobservable "
                        "without running counterfactual backtests."
                    ),
                    (
                        "Blocked winner/loss metrics mean: an observed trade where this "
                        "individual filter was false and would have blocked the trade if "
                        "made mandatory."
                    ),
                    (
                        "Marginal PF/Sharpe/drawdown gains are reported as observational "
                        "proxies when no official ablation result exists for the exact "
                        "counterfactual."
                    ),
                ],
            },
            "filter_information_matrix": matrix_rows,
            "filter_confusion_matrix": confusion_rows,
            "filter_ranking": ranking_rows,
            "redundancy_matrix": redundancy_rows,
            "objective_answers": objective_answers,
        }
        return self._write_outputs(report)

    def _analyze_from_existing_artifacts(
        self,
        *,
        max_experiments_per_strategy: int | None,
        min_completed_trades: int,
    ) -> dict[str, Path]:
        signal_report_path = self.output_dir / "signal_opportunity_report.json"
        if not signal_report_path.exists():
            return self.analyze(
                max_experiments_per_strategy=max_experiments_per_strategy,
                min_completed_trades=min_completed_trades,
                full_candle_reconstruction=True,
            )

        signal_report = self._loads(signal_report_path.read_text(encoding="utf-8"), {})
        experiments = self._load_experiments(
            max_per_strategy=max_experiments_per_strategy,
            min_completed_trades=min_completed_trades,
        )
        filters = self._filters_from_signal_report(signal_report)
        missing_trade_artifacts = 0
        parsed_trade_experiments = 0
        observed_trades = 0

        filters_by_strategy: dict[str, list[str]] = defaultdict(list)
        for strategy, filter_name in filters:
            filters_by_strategy[strategy].append(filter_name)

        for experiment in experiments:
            trades_by_pair = self._load_trades(experiment)
            if trades_by_pair is None:
                missing_trade_artifacts += 1
                continue
            parsed_trade_experiments += 1
            strategy_filters = filters_by_strategy.get(experiment.strategy, [])
            if not strategy_filters:
                continue
            for trades in trades_by_pair.values():
                for trade in trades:
                    observed_trades += 1
                    passed = self._filters_from_enter_tag(experiment.strategy, trade.get("enter_tag"), strategy_filters)
                    profit = self._number(trade.get("profit_abs", trade.get("profit_ratio")))
                    winner = self._number(trade.get("profit_ratio")) > 0
                    for filter_name in strategy_filters:
                        stats = filters[(experiment.strategy, filter_name)]
                        stats.observed_trades += 1
                        if filter_name in passed:
                            stats.approved_profit += profit
                            if winner:
                                stats.approved_winners += 1
                            else:
                                stats.approved_losers += 1
                        else:
                            stats.blocked_profit += profit
                            if winner:
                                stats.blocked_winners += 1
                                stats.eliminated_profit += max(0.0, profit)
                            else:
                                stats.blocked_losers += 1
                                stats.avoided_loss_abs += abs(min(0.0, profit))

        matrix_rows = [self._filter_row(stats) for stats in filters.values()]
        confusion_rows = [self._confusion_row(stats) for stats in filters.values()]
        ranking_rows = self._ranking_rows(matrix_rows, confusion_rows)
        redundancy_rows = self._redundancy_from_signal_report(signal_report)
        self._apply_redundancy_hints(ranking_rows, redundancy_rows)
        objective_answers = self._objective_answers(matrix_rows, ranking_rows, confusion_rows, redundancy_rows)
        report = {
            "generated_at": datetime.now(UTC).isoformat(),
            "scope": {
                "db_path": str(self.db_path),
                "data_dir": str(self.data_dir),
                "timeframe": self.timeframe,
                "experiments_analyzed": len(experiments),
                "experiment_pair_evaluations": signal_report.get("scope", {}).get("experiment_pair_evaluations", 0),
                "parsed_trade_experiments": parsed_trade_experiments,
                "missing_trade_artifacts": missing_trade_artifacts,
                "observed_trade_entries_matched_to_candles": observed_trades,
                "backtests_executed": False,
                "artifact_mode": True,
                "source_signal_report": str(signal_report_path),
                "methodology": (
                    "Opportunity counts and redundancy were read from the existing "
                    "signal_opportunity_report. Confusion and cost metrics were computed "
                    "from official closed trades in existing result artifacts using enter_tag "
                    "evidence for which filters contributed to each entry."
                ),
                "limitations": [
                    (
                        "This is observational. It does not assign a realized outcome to "
                        "candles where no official trade was executed."
                    ),
                    (
                        "For score-based strategies, a missing filter in enter_tag is treated "
                        "as a filter that did not contribute to that entry, not proof that the "
                        "current strategy blocked the trade."
                    ),
                    (
                        "For MeanReversionStrategy, which is implemented as conjunctive filters, "
                        "all entry filters are treated as passed for observed entries."
                    ),
                    (
                        "Causal removal decisions require counterfactual ablation backtests; "
                        "this report identifies candidates for investigation, not production changes."
                    ),
                ],
            },
            "filter_information_matrix": matrix_rows,
            "filter_confusion_matrix": confusion_rows,
            "filter_ranking": ranking_rows,
            "redundancy_matrix": redundancy_rows,
            "objective_answers": objective_answers,
        }
        return self._write_outputs(report)

    def _filters_from_signal_report(self, report: dict[str, Any]) -> dict[tuple[str, str], FilterStats]:
        output: dict[tuple[str, str], FilterStats] = {}
        for key, stats in report.get("component_summary", {}).items():
            if ":" not in key:
                continue
            strategy, filter_name = key.split(":", 1)
            item = FilterStats(strategy=strategy, filter_name=filter_name)
            item.approved = int(stats.get("passed", 0) or 0)
            item.rejected = int(stats.get("failed", 0) or 0)
            item.opportunities = item.approved + item.rejected
            item.marginal_candidates = int(stats.get("marginal_eliminated", 0) or 0)
            item.experiment_profit_factors.append(self._number(stats.get("avg_profit_factor")))
            output[(strategy, filter_name)] = item
        return output

    def _filters_from_enter_tag(self, strategy: str, enter_tag: Any, strategy_filters: list[str]) -> set[str]:
        text = str(enter_tag or "")
        lower = text.lower()
        if strategy == "MeanReversionStrategy":
            return set(strategy_filters)
        if strategy == "NOfMTrendConfirmation":
            return {
                name
                for name in strategy_filters
                if name.lower() in lower
            }
        mapping = {
            "ema_fast_slow": ("ema fast above slow", "fast above slow"),
            "ema_slow_trend": ("ema slow above trend", "slow above trend"),
            "adx": ("adx=", "adx "),
            "rsi": ("rsi=", "not overbought", "healthy range"),
            "volume": ("volume=", "x mean", "vol="),
            "atr": ("atr=", "atr active", "active"),
            "breakout": ("close=", "close>", "breakout"),
            "trend": ("trend", "ema trend", "above trend"),
            "pullback_touch": ("pullback touched", "touched ema"),
            "pullback_control": ("pullback depth", "depth within"),
            "reclaim_ema": ("reclaimed ema", "close reclaimed"),
            "confirmation": ("retake candle", "confirmation"),
            "pair_allowed": ("meanreversionentry",),
            "time_allowed": ("meanreversionentry",),
            "bollinger_or_zscore": ("bb_low", "z="),
            "vwap": ("vwap",),
            "reclaim": ("reclaim",),
        }
        passed = set()
        for name in strategy_filters:
            tokens = mapping.get(name, (name.replace("_", " "), name))
            if any(token.lower() in lower for token in tokens):
                passed.add(name)
        return passed

    def _redundancy_from_signal_report(self, report: dict[str, Any]) -> list[dict[str, Any]]:
        rows = []
        for key, stats in report.get("redundancy_matrix", {}).items():
            if ":" not in key or "|" not in key:
                continue
            strategy, pair = key.split(":", 1)
            left, right = pair.split("|", 1)
            score = self._number(stats.get("redundancy_score"))
            rows.append(
                {
                    "strategy": strategy,
                    "filter_left": left,
                    "filter_right": right,
                    "correlation": None,
                    "mutual_information": None,
                    "jaccard": None,
                    "overlap": None,
                    "agreement": None,
                    "functional_redundancy": score,
                    "classification": (
                        "praticamente_equivalente"
                        if score >= 0.80
                        else "complementar_ou_parcialmente_redundante"
                        if score >= 0.55
                        else "independente"
                    ),
                }
            )
        return sorted(rows, key=lambda row: row["functional_redundancy"], reverse=True)

    def _apply_redundancy_hints(
        self,
        ranking_rows: list[dict[str, Any]],
        redundancy_rows: list[dict[str, Any]],
    ) -> None:
        redundant_filters = set()
        for row in redundancy_rows:
            if row["classification"] == "praticamente_equivalente":
                redundant_filters.add((row["strategy"], row["filter_left"]))
                redundant_filters.add((row["strategy"], row["filter_right"]))
        for row in ranking_rows:
            if (row["strategy"], row["filter"]) in redundant_filters and row["classification"] not in {"ESSENCIAL", "PREJUDICIAL"}:
                row["classification"] = "REDUNDANTE"
                row["justification"] += "; strong functional redundancy in opportunity matrix"

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
                select id, parameters_json, metrics_json, result_path
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
            grouped[STRATEGY_LABELS.get(strategy, strategy)].append(
                ExperimentSpec(
                    experiment_id=row["id"],
                    strategy=STRATEGY_LABELS.get(strategy, strategy),
                    parameters=parameters.get("plugin_parameters", parameters),
                    metrics=metrics,
                    result_path=row["result_path"],
                )
            )

        experiments: list[ExperimentSpec] = []
        for strategy, items in sorted(grouped.items()):
            selected = items
            if max_per_strategy is not None:
                selected = sorted(
                    items,
                    key=lambda item: self._number(item.metrics.get("profit_factor")),
                    reverse=True,
                )[:max_per_strategy]
            experiments.extend(selected)
        return experiments

    def _analyze_experiment_pair(
        self,
        *,
        experiment: ExperimentSpec,
        pair: str,
        frame: pd.DataFrame,
        trades: list[dict[str, Any]],
        filters: dict[tuple[str, str], FilterStats],
        redundancy: dict[tuple[str, str, str], RedundancyStats],
    ) -> int:
        params = self.signal._parameters_for(experiment.strategy, experiment.parameters)
        if not params:
            return 0
        conditions, _final_signal, _ordered_steps = self.signal._conditions_for(
            experiment.strategy,
            frame.copy(),
            pair,
            params,
        )
        if not conditions:
            return 0

        valid = pd.Series(True, index=frame.index)
        for condition in conditions.values():
            valid &= condition.notna()
        valid &= frame["close"].notna() & frame["volume"].notna()
        if int(valid.sum()) == 0:
            return 0

        winners, losers, profits = self._trade_labels(pair, frame, trades)
        observed = winners | losers
        observed_count = int(observed.sum())

        clean_conditions = {
            name: (condition.fillna(False).astype(bool) & valid)
            for name, condition in conditions.items()
        }
        self._update_redundancy(experiment.strategy, clean_conditions, valid, redundancy)

        all_filters = list(clean_conditions)
        pair_metrics = experiment.metrics.get("profit_by_pair", {}).get(pair, {})
        pf = self._number(pair_metrics.get("profit_factor", experiment.metrics.get("profit_factor")))
        drawdown = self._number(pair_metrics.get("max_drawdown_abs", experiment.metrics.get("max_drawdown_abs")))
        sharpe = self._number(pair_metrics.get("sharpe", experiment.metrics.get("sharpe")))
        expectancy = self._number(pair_metrics.get("expectancy", experiment.metrics.get("expectancy")))

        for name, passed in clean_conditions.items():
            key = (experiment.strategy, name)
            stats = filters.setdefault(key, FilterStats(strategy=experiment.strategy, filter_name=name))
            rejected = valid & ~passed
            stats.opportunities += int(valid.sum())
            stats.approved += int(passed.sum())
            stats.rejected += int(rejected.sum())
            stats.observed_trades += observed_count

            approved_winners = passed & winners
            approved_losers = passed & losers
            blocked_winners = rejected & winners
            blocked_losers = rejected & losers

            stats.approved_winners += int(approved_winners.sum())
            stats.approved_losers += int(approved_losers.sum())
            stats.blocked_winners += int(blocked_winners.sum())
            stats.blocked_losers += int(blocked_losers.sum())
            stats.approved_profit += float(profits[passed & observed].sum())
            blocked_profit = float(profits[rejected & observed].sum())
            stats.blocked_profit += blocked_profit
            stats.eliminated_profit += float(profits[blocked_winners].sum())
            stats.avoided_loss_abs += abs(float(profits[blocked_losers].sum()))

            without_filter = valid.copy()
            for other in all_filters:
                if other != name:
                    without_filter &= clean_conditions[other]
            marginal = without_filter & ~passed
            marginal_observed = marginal & observed
            stats.marginal_candidates += int(marginal.sum())
            stats.marginal_observed_trades += int(marginal_observed.sum())
            stats.marginal_winners += int((marginal & winners).sum())
            stats.marginal_losers += int((marginal & losers).sum())
            stats.marginal_profit += float(profits[marginal_observed].sum())

            stats.experiment_profit_factors.append(pf)
            stats.experiment_drawdowns.append(drawdown)
            stats.experiment_sharpes.append(sharpe)
            stats.experiment_expectancies.append(expectancy)

        return observed_count

    def _trade_labels(
        self,
        pair: str,
        frame: pd.DataFrame,
        trades: list[dict[str, Any]],
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        winners = pd.Series(False, index=frame.index)
        losers = pd.Series(False, index=frame.index)
        profits = pd.Series(0.0, index=frame.index)
        if not trades:
            return winners, losers, profits

        positions = self._date_positions.get(pair, {})
        for trade in trades:
            timestamp = self._trade_open_ns(trade)
            position = positions.get(timestamp)
            if position is None:
                continue
            profit = self._number(trade.get("profit_abs", trade.get("profit_ratio")))
            profits.iat[position] += profit
            if self._number(trade.get("profit_ratio")) > 0:
                winners.iat[position] = True
            else:
                losers.iat[position] = True
        return winners, losers, profits

    def _build_date_positions(self, frame: pd.DataFrame) -> dict[int, int]:
        dates = pd.to_datetime(frame["date"], utc=True, errors="coerce")
        return {int(value.value): index for index, value in enumerate(dates) if not pd.isna(value)}

    def _trade_open_ns(self, trade: dict[str, Any]) -> int:
        if trade.get("open_timestamp") is not None:
            return int(trade["open_timestamp"]) * 1_000_000
        date = pd.to_datetime(trade.get("open_date"), utc=True, errors="coerce")
        if pd.isna(date):
            return -1
        return int(date.value)

    def _load_trades(self, experiment: ExperimentSpec) -> dict[str, list[dict[str, Any]]] | None:
        path = self._resolve_result_path(experiment.result_path)
        if path is None or not path.exists():
            return None
        try:
            with zipfile.ZipFile(path) as archive:
                for name in archive.namelist():
                    if name.endswith(".json") and not name.endswith("_config.json") and not name.endswith(".meta.json"):
                        data = json.loads(archive.read(name))
                        strategies = data.get("strategy", {})
                        if not strategies:
                            return {}
                        payload = next(iter(strategies.values()))
                        output: dict[str, list[dict[str, Any]]] = defaultdict(list)
                        for trade in payload.get("trades", []):
                            if not trade.get("is_open", False):
                                output[str(trade.get("pair"))].append(trade)
                        return dict(output)
        except (OSError, zipfile.BadZipFile, json.JSONDecodeError):
            return None
        return {}

    def _resolve_result_path(self, result_path: str | None) -> Path | None:
        if not result_path:
            return None
        direct = Path(result_path)
        if direct.exists():
            return direct
        if result_path.startswith("/freqtrade/"):
            root = Path(__file__).resolve().parents[2]
            mapped = root / result_path.removeprefix("/freqtrade/")
            if mapped.exists():
                return mapped
        return direct

    def _update_redundancy(
        self,
        strategy: str,
        conditions: dict[str, pd.Series],
        valid: pd.Series,
        output: dict[tuple[str, str, str], RedundancyStats],
    ) -> None:
        names = list(conditions)
        for index, left in enumerate(names):
            left_values = conditions[left] & valid
            for right in names[index + 1 :]:
                right_values = conditions[right] & valid
                key = (strategy, left, right)
                stats = output.setdefault(key, RedundancyStats(strategy=strategy, left=left, right=right))
                stats.n11 += int((left_values & right_values).sum())
                stats.n10 += int((left_values & ~right_values & valid).sum())
                stats.n01 += int((~left_values & right_values & valid).sum())
                stats.n00 += int((~left_values & ~right_values & valid).sum())

    def _filter_row(self, stats: FilterStats) -> dict[str, Any]:
        approval_rate = self._safe_div(stats.approved, stats.opportunities)
        rejection_rate = self._safe_div(stats.rejected, stats.opportunities)
        approved_trade_count = stats.approved_winners + stats.approved_losers
        blocked_trade_count = stats.blocked_winners + stats.blocked_losers
        total_profit = stats.approved_profit + stats.blocked_profit
        profit_saved_ratio = self._safe_div(stats.avoided_loss_abs, stats.avoided_loss_abs + stats.eliminated_profit)
        profit_lost_ratio = self._safe_div(stats.eliminated_profit, stats.avoided_loss_abs + stats.eliminated_profit)
        opportunity_cost = stats.eliminated_profit - stats.avoided_loss_abs
        return {
            "strategy": stats.strategy,
            "filter": stats.filter_name,
            "opportunities_analyzed": stats.opportunities,
            "approved": stats.approved,
            "rejected": stats.rejected,
            "approval_rate": approval_rate,
            "rejection_rate": rejection_rate,
            "observed_trades": stats.observed_trades,
            "approved_observed_trades": approved_trade_count,
            "blocked_observed_trades": blocked_trade_count,
            "trades_eliminated_observed_proxy": blocked_trade_count,
            "profits_eliminated": stats.eliminated_profit,
            "losses_avoided_abs": stats.avoided_loss_abs,
            "profit_preserved": stats.approved_profit,
            "profit_lost": stats.eliminated_profit,
            "profit_total_observed": total_profit,
            "profit_lost_ratio": profit_lost_ratio,
            "profit_saved_ratio": profit_saved_ratio,
            "trade_frequency_lost": self._safe_div(blocked_trade_count, stats.observed_trades),
            "opportunity_cost": opportunity_cost,
            "each_eliminated_trade_worth_it": stats.avoided_loss_abs > stats.eliminated_profit,
            "avg_profit_factor_context": self._mean(stats.experiment_profit_factors),
            "avg_drawdown_context": self._mean(stats.experiment_drawdowns),
            "avg_sharpe_context": self._mean(stats.experiment_sharpes),
            "avg_expectancy_context": self._mean(stats.experiment_expectancies),
            "marginal_candidates": stats.marginal_candidates,
            "marginal_observed_trades": stats.marginal_observed_trades,
            "marginal_winners": stats.marginal_winners,
            "marginal_losers": stats.marginal_losers,
            "marginal_profit_observed": stats.marginal_profit,
        }

    def _confusion_row(self, stats: FilterStats) -> dict[str, Any]:
        tp = stats.approved_winners
        fp = stats.approved_losers
        fn = stats.blocked_winners
        tn = stats.blocked_losers
        total = tp + fp + fn + tn
        precision = self._safe_div(tp, tp + fp)
        recall = self._safe_div(tp, tp + fn)
        specificity = self._safe_div(tn, tn + fp)
        precision_value = self._none_to_zero(precision)
        recall_value = self._none_to_zero(recall)
        f1 = self._safe_div(2 * precision_value * recall_value, precision_value + recall_value)
        mcc = self._mcc(tp, fp, tn, fn)
        odds_ratio = self._odds_ratio(tp, fp, tn, fn)
        likelihood_ratio = (
            self._safe_div(recall_value, 1.0 - self._none_to_zero(specificity))
            if specificity is not None and specificity < 1.0
            else None
        )
        mutual_information = self._mutual_information(tp, fp, tn, fn)
        information_gain = self._information_gain(tp, fp, tn, fn)
        base_win_rate = self._safe_div(tp + fn, total)
        lift = self._safe_div(precision, base_win_rate)
        return {
            "strategy": stats.strategy,
            "filter": stats.filter_name,
            "true_positive_approved_winners": tp,
            "false_positive_approved_losers": fp,
            "true_negative_blocked_losers": tn,
            "false_negative_blocked_winners": fn,
            "observed_classified_trades": total,
            "information_gain": information_gain,
            "mutual_information": mutual_information,
            "precision": precision,
            "recall": recall,
            "specificity": specificity,
            "f1": f1,
            "matthews_correlation": mcc,
            "lift": lift,
            "odds_ratio": odds_ratio,
            "likelihood_ratio": likelihood_ratio,
            "metric_validity": (
                "valid_observed_entries_only"
                if total >= 30 and (tp + fn) > 0 and (fp + tn) > 0
                else "low_sample_or_single_class"
            ),
        }

    def _ranking_rows(
        self,
        matrix_rows: list[dict[str, Any]],
        confusion_rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        confusion_by_key = {(row["strategy"], row["filter"]): row for row in confusion_rows}
        raw_rows = []
        for row in matrix_rows:
            confusion = confusion_by_key[(row["strategy"], row["filter"])]
            information_value = self._none_to_zero(confusion["information_gain"]) + self._none_to_zero(confusion["mutual_information"])
            marginal_trade_loss = row["marginal_candidates"]
            marginal_contribution = (
                self._none_to_zero(confusion["matthews_correlation"])
                + self._none_to_zero(confusion["lift"]) / 5.0
                + (1.0 if row["marginal_profit_observed"] > 0 else 0.0)
            )
            opportunity_cost_score = row["losses_avoided_abs"] - row["profits_eliminated"]
            confidence = min(1.0, math.log10(max(1, confusion["observed_classified_trades"])) / 4.0)
            raw_rows.append(
                {
                    "strategy": row["strategy"],
                    "filter": row["filter"],
                    "filter_information_value_score_raw": information_value,
                    "marginal_contribution_score_raw": marginal_contribution,
                    "opportunity_cost_score_raw": opportunity_cost_score,
                    "confidence_score": confidence,
                    "marginal_trade_loss": marginal_trade_loss,
                    "matrix": row,
                    "confusion": confusion,
                }
            )

        info_values = [item["filter_information_value_score_raw"] for item in raw_rows]
        marginal_values = [item["marginal_contribution_score_raw"] for item in raw_rows]
        cost_values = [item["opportunity_cost_score_raw"] for item in raw_rows]
        ranked = []
        for item in raw_rows:
            info = self._normalize(item["filter_information_value_score_raw"], info_values)
            marginal = self._normalize(item["marginal_contribution_score_raw"], marginal_values)
            cost = self._normalize(item["opportunity_cost_score_raw"], cost_values)
            confidence = item["confidence_score"]
            utility = (0.35 * info) + (0.25 * marginal) + (0.25 * cost) + (0.15 * confidence)
            ranked.append(
                {
                    "strategy": item["strategy"],
                    "filter": item["filter"],
                    "filter_information_value_score": info,
                    "marginal_contribution_score": marginal,
                    "opportunity_cost_score": cost,
                    "overall_utility_score": utility,
                    "confidence_score": confidence,
                    "classification": self._classify_filter(
                        utility=utility,
                        confidence=confidence,
                        rejection_rate=item["matrix"]["rejection_rate"],
                        profit_lost=item["matrix"]["profit_lost"],
                        losses_avoided=item["matrix"]["losses_avoided_abs"],
                        redundancy_hint=False,
                    ),
                    "justification": self._classification_reason(item["matrix"], item["confusion"], utility, confidence),
                }
            )
        return sorted(ranked, key=lambda row: row["overall_utility_score"], reverse=True)

    def _redundancy_row(self, stats: RedundancyStats) -> dict[str, Any]:
        total = stats.n00 + stats.n01 + stats.n10 + stats.n11
        jaccard = self._safe_div(stats.n11, stats.n11 + stats.n10 + stats.n01)
        overlap = self._safe_div(stats.n11, min(stats.n11 + stats.n10, stats.n11 + stats.n01))
        correlation = self._phi(stats.n11, stats.n10, stats.n00, stats.n01)
        mutual_information = self._mutual_information(stats.n11, stats.n10, stats.n00, stats.n01)
        same = self._safe_div(stats.n11 + stats.n00, total)
        functional = (jaccard + overlap + abs(correlation) + same) / 4.0
        if functional >= 0.80:
            classification = "praticamente_equivalente"
        elif functional >= 0.55:
            classification = "complementar_ou_parcialmente_redundante"
        else:
            classification = "independente"
        return {
            "strategy": stats.strategy,
            "filter_left": stats.left,
            "filter_right": stats.right,
            "correlation": correlation,
            "mutual_information": mutual_information,
            "jaccard": jaccard,
            "overlap": overlap,
            "agreement": same,
            "functional_redundancy": functional,
            "classification": classification,
        }

    def _objective_answers(
        self,
        matrix_rows: list[dict[str, Any]],
        ranking: list[dict[str, Any]],
        confusion: list[dict[str, Any]],
        redundancy: list[dict[str, Any]],
    ) -> dict[str, Any]:
        matrix_by_key = {
            (row["strategy"], row["filter"]): row
            for row in matrix_rows
        }
        highest_avoided = max(matrix_by_key.values(), key=lambda row: row["losses_avoided_abs"], default=None)
        highest_winners_lost = max(matrix_by_key.values(), key=lambda row: row["profits_eliminated"], default=None)
        highest_ig = max(confusion, key=lambda row: self._none_to_zero(row["information_gain"]), default=None)
        low_pf_reducers = [
            row for row in matrix_by_key.values()
            if row["rejection_rate"] > 0.5 and row["avg_profit_factor_context"] <= 1.0
        ]
        low_pf_reducers = sorted(low_pf_reducers, key=lambda row: row["rejection_rate"], reverse=True)
        redundant = sorted(redundancy, key=lambda row: row["functional_redundancy"], reverse=True)
        flexibility = [
            row for row in ranking
            if row["classification"] in {"NEUTRO", "REDUNDANTE", "PREJUDICIAL"}
        ][:10]
        never_remove = [
            row for row in ranking
            if row["classification"] == "ESSENCIAL"
        ][:5]
        harmful = [
            row for row in ranking
            if row["classification"] == "PREJUDICIAL"
        ][:10]
        return {
            "qual_filtro_evita_mais_perdas": self._name_value(highest_avoided, "losses_avoided_abs"),
            "qual_filtro_elimina_mais_trades_vencedores": self._name_value(highest_winners_lost, "profits_eliminated"),
            "qual_filtro_possui_maior_information_gain": self._name_value(highest_ig, "information_gain"),
            "qual_filtro_reduz_trades_sem_melhorar_pf": low_pf_reducers[:10],
            "qual_filtro_investigar_para_flexibilizacao": flexibility,
            "qual_filtro_nunca_deveria_ser_removido": never_remove,
            "qual_filtro_parece_duplicar_outro": redundant[:10],
            "filtro_com_custo_maior_que_beneficio": harmful,
            "candidatos_para_dobrar_trades_preservando_qualidade": flexibility,
            "evidencia_para_remover_algum_filtro": (
                "Nao ha evidencia causal suficiente para remover filtros sem backtests contrafactuais. "
                "Ha evidencias observacionais para investigar flexibilizacao dos filtros classificados "
                "como NEUTRO, REDUNDANTE ou PREJUDICIAL."
            ),
        }

    def _write_outputs(self, report: dict[str, Any]) -> dict[str, Path]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        paths = {
            "html": self.output_dir / f"{REPORT_STEM}.html",
            "markdown": self.output_dir / f"{REPORT_STEM}.md",
            "json": self.output_dir / f"{REPORT_STEM}.json",
            "filter_information_matrix": self.output_dir / "filter_information_matrix.csv",
            "filter_confusion_matrix": self.output_dir / "filter_confusion_matrix.csv",
            "filter_ranking": self.output_dir / "filter_ranking.csv",
        }
        paths["json"].write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        paths["markdown"].write_text(self._markdown(report), encoding="utf-8")
        paths["html"].write_text(self._html(report), encoding="utf-8")
        self._write_csv(paths["filter_information_matrix"], report["filter_information_matrix"])
        self._write_csv(paths["filter_confusion_matrix"], report["filter_confusion_matrix"])
        self._write_csv(paths["filter_ranking"], report["filter_ranking"])
        return paths

    def _write_csv(self, path: Path, rows: list[dict[str, Any]]) -> None:
        if not rows:
            path.write_text("", encoding="utf-8")
            return
        fieldnames = sorted({key for row in rows for key in row})
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({key: self._csv_value(row.get(key)) for key in fieldnames})

    def _markdown(self, report: dict[str, Any]) -> str:
        lines = [
            "# Filter Information Value Report",
            "",
            "## Escopo",
            f"- Experimentos analisados: {report['scope']['experiments_analyzed']}",
            f"- Avaliacoes experimento/par: {report['scope']['experiment_pair_evaluations']}",
            f"- Experimentos com trades oficiais parseados: {report['scope']['parsed_trade_experiments']}",
            f"- Artefatos de trade ausentes: {report['scope']['missing_trade_artifacts']}",
            f"- Backtests executados: {report['scope']['backtests_executed']}",
            "",
            "## Limitacoes Estatisticas",
        ]
        for limitation in report["scope"]["limitations"]:
            lines.append(f"- {limitation}")

        lines.extend([
            "",
            "## Top 20 Filtros por Utility Score",
            "| Estrategia | Filtro | Utility | Information | Marginal | Opportunity Cost | Confidence | Classe |",
            "|---|---|---:|---:|---:|---:|---:|---|",
        ])
        for row in report["filter_ranking"][:20]:
            lines.append(
                f"| {row['strategy']} | {row['filter']} | {row['overall_utility_score']:.3f} | "
                f"{row['filter_information_value_score']:.3f} | {row['marginal_contribution_score']:.3f} | "
                f"{row['opportunity_cost_score']:.3f} | {row['confidence_score']:.3f} | {row['classification']} |"
            )

        lines.extend(["", "## Respostas Objetivas"])
        for key, value in report["objective_answers"].items():
            lines.append(f"- {key}: `{self._short_json(value)}`")

        lines.extend([
            "",
            "## Amostra da Matriz de Contribuicao",
            "| Estrategia | Filtro | Oportunidades | Aprovadas | Rejeitadas | Rejeicao | Trades obs. | Profit Lost | Loss Saved |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ])
        for row in sorted(report["filter_information_matrix"], key=lambda item: item["rejection_rate"], reverse=True)[:30]:
            lines.append(
                f"| {row['strategy']} | {row['filter']} | {row['opportunities_analyzed']} | {row['approved']} | "
                f"{row['rejected']} | {row['rejection_rate']:.2%} | {row['observed_trades']} | "
                f"{row['profit_lost']:.4f} | {row['losses_avoided_abs']:.4f} |"
            )
        return "\n".join(lines) + "\n"

    def _html(self, report: dict[str, Any]) -> str:
        ranking_rows = "".join(
            "<tr>"
            f"<td>{html.escape(row['strategy'])}</td>"
            f"<td>{html.escape(row['filter'])}</td>"
            f"<td>{row['overall_utility_score']:.3f}</td>"
            f"<td>{row['filter_information_value_score']:.3f}</td>"
            f"<td>{row['marginal_contribution_score']:.3f}</td>"
            f"<td>{row['opportunity_cost_score']:.3f}</td>"
            f"<td>{row['confidence_score']:.3f}</td>"
            f"<td>{html.escape(row['classification'])}</td>"
            "</tr>"
            for row in report["filter_ranking"][:50]
        )
        matrix_rows = "".join(
            "<tr>"
            f"<td>{html.escape(row['strategy'])}</td>"
            f"<td>{html.escape(row['filter'])}</td>"
            f"<td>{row['opportunities_analyzed']}</td>"
            f"<td>{row['approved']}</td>"
            f"<td>{row['rejected']}</td>"
            f"<td>{row['rejection_rate']:.2%}</td>"
            f"<td>{row['profit_lost']:.4f}</td>"
            f"<td>{row['losses_avoided_abs']:.4f}</td>"
            "</tr>"
            for row in sorted(report["filter_information_matrix"], key=lambda item: item["rejection_rate"], reverse=True)[:80]
        )
        return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <title>Filter Information Value Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #17212b; }}
    table {{ border-collapse: collapse; width: 100%; margin: 16px 0 28px; font-size: 13px; }}
    th, td {{ border: 1px solid #d9e2ec; padding: 7px; text-align: left; }}
    th {{ background: #eef3f8; }}
    pre {{ background: #f7f9fb; padding: 12px; overflow: auto; }}
    .note {{ border-left: 4px solid #6772e5; padding: 8px 12px; background: #f7f8ff; }}
  </style>
</head>
<body>
  <h1>Filter Information Value Report</h1>
  <div class="note">{html.escape(report['scope']['methodology'])}</div>
  <h2>Escopo</h2>
  <pre>{html.escape(json.dumps(report['scope'], indent=2, sort_keys=True))}</pre>
  <h2>Top 50 por Overall Utility Score</h2>
  <table><tr><th>Estrategia</th><th>Filtro</th><th>Utility</th><th>Information</th><th>Marginal</th><th>Cost</th><th>Confidence</th><th>Classe</th></tr>{ranking_rows}</table>
  <h2>Maiores Rejeicoes</h2>
  <table><tr><th>Estrategia</th><th>Filtro</th><th>Oportunidades</th><th>Aprovadas</th><th>Rejeitadas</th><th>Rejeicao</th><th>Profit Lost</th><th>Loss Saved</th></tr>{matrix_rows}</table>
  <h2>Respostas Objetivas</h2>
  <pre>{html.escape(json.dumps(report['objective_answers'], indent=2, sort_keys=True))}</pre>
</body>
</html>
"""

    def _classify_filter(
        self,
        *,
        utility: float,
        confidence: float,
        rejection_rate: float,
        profit_lost: float,
        losses_avoided: float,
        redundancy_hint: bool,
    ) -> str:
        if confidence < 0.25:
            return "NEUTRO"
        if redundancy_hint:
            return "REDUNDANTE"
        if utility >= 0.70 and losses_avoided >= profit_lost:
            return "ESSENCIAL"
        if utility >= 0.50:
            return "UTIL"
        if rejection_rate >= 0.60 and profit_lost > losses_avoided:
            return "PREJUDICIAL"
        if utility < 0.35:
            return "NEUTRO"
        return "UTIL"

    def _classification_reason(
        self,
        matrix: dict[str, Any],
        confusion: dict[str, Any],
        utility: float,
        confidence: float,
    ) -> str:
        return (
            f"utility={utility:.3f}; confidence={confidence:.3f}; "
            f"rejection={matrix['rejection_rate']:.2%}; "
            f"loss_saved={matrix['losses_avoided_abs']:.4f}; "
            f"profit_lost={matrix['profit_lost']:.4f}; "
            f"information_gain={self._none_to_zero(confusion['information_gain']):.6f}"
        )

    def _name_value(self, row: dict[str, Any] | None, field: str) -> dict[str, Any] | None:
        if not row:
            return None
        return {
            "strategy": row.get("strategy"),
            "filter": row.get("filter"),
            field: row.get(field),
        }

    def _strategy_name(self, parameters: dict[str, Any]) -> str:
        return parameters.get("strategy_plugin") or parameters.get("strategy_name") or "UNKNOWN"

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

    def _safe_div(self, numerator: float, denominator: float) -> float | None:
        if denominator == 0:
            return None
        return numerator / denominator

    def _none_to_zero(self, value: Any) -> float:
        if value is None:
            return 0.0
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return 0.0
        return 0.0 if math.isnan(parsed) or math.isinf(parsed) else parsed

    def _mean(self, values: list[float]) -> float:
        clean = [value for value in values if not math.isnan(value) and not math.isinf(value)]
        return statistics.mean(clean) if clean else 0.0

    def _normalize(self, value: float, values: list[float]) -> float:
        clean = [item for item in values if not math.isnan(item) and not math.isinf(item)]
        if not clean:
            return 0.0
        low = min(clean)
        high = max(clean)
        if high == low:
            return 0.5
        return (value - low) / (high - low)

    def _entropy(self, positives: int, negatives: int) -> float:
        total = positives + negatives
        if total == 0:
            return 0.0
        output = 0.0
        for count in (positives, negatives):
            if count:
                probability = count / total
                output -= probability * math.log2(probability)
        return output

    def _information_gain(self, tp: int, fp: int, tn: int, fn: int) -> float | None:
        total = tp + fp + tn + fn
        if total == 0:
            return None
        base = self._entropy(tp + fn, fp + tn)
        approved_total = tp + fp
        blocked_total = tn + fn
        approved_entropy = self._entropy(tp, fp)
        blocked_entropy = self._entropy(fn, tn)
        weighted = (approved_total / total) * approved_entropy + (blocked_total / total) * blocked_entropy
        return base - weighted

    def _mutual_information(self, tp: int, fp: int, tn: int, fn: int) -> float | None:
        total = tp + fp + tn + fn
        if total == 0:
            return None
        cells = {
            (1, 1): tp,
            (1, 0): fp,
            (0, 1): fn,
            (0, 0): tn,
        }
        row_totals = {1: tp + fp, 0: fn + tn}
        col_totals = {1: tp + fn, 0: fp + tn}
        value = 0.0
        for (row, col), count in cells.items():
            if count == 0 or row_totals[row] == 0 or col_totals[col] == 0:
                continue
            probability = count / total
            expected = (row_totals[row] / total) * (col_totals[col] / total)
            value += probability * math.log2(probability / expected)
        return value

    def _mcc(self, tp: int, fp: int, tn: int, fn: int) -> float | None:
        denominator = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
        if denominator == 0:
            return None
        return ((tp * tn) - (fp * fn)) / denominator

    def _phi(self, n11: int, n10: int, n00: int, n01: int) -> float | None:
        denominator = math.sqrt((n11 + n10) * (n01 + n00) * (n11 + n01) * (n10 + n00))
        if denominator == 0:
            return None
        return ((n11 * n00) - (n10 * n01)) / denominator

    def _odds_ratio(self, tp: int, fp: int, tn: int, fn: int) -> float | None:
        if fp == 0 or fn == 0:
            return None
        return (tp * tn) / (fp * fn)

    def _csv_value(self, value: Any) -> Any:
        if isinstance(value, (dict, list)):
            return json.dumps(value, sort_keys=True)
        if value is None:
            return ""
        return value

    def _short_json(self, value: Any) -> str:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
        return text if len(text) <= 600 else text[:597] + "..."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Offline filter information-value analyzer.")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--timeframe", default="5m")
    parser.add_argument("--max-experiments-per-strategy", type=int)
    parser.add_argument("--min-completed-trades", type=int, default=0)
    parser.add_argument(
        "--full-candle-reconstruction",
        action="store_true",
        help="Rebuild all candle filters from OHLCV instead of using existing signal opportunity artifacts.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    analyzer = FilterInformationValueAnalyzer(
        db_path=args.db_path,
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        timeframe=args.timeframe,
    )
    paths = analyzer.analyze(
        max_experiments_per_strategy=args.max_experiments_per_strategy,
        min_completed_trades=args.min_completed_trades,
        full_candle_reconstruction=args.full_candle_reconstruction,
    )
    print(json.dumps({key: str(path) for key, path in paths.items()}, indent=2))


if __name__ == "__main__":
    main()
