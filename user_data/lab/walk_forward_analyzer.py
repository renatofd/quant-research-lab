from __future__ import annotations

import argparse
import hashlib
import json
import math
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from statistics import mean, median, pstdev
from typing import Any

try:
    from .backtest_runner import DEFAULT_BACKTEST_TIMEOUT_SECONDS, BacktestRunner
    from .experiment_database import ExperimentDatabase
    from .experiment_manager import ExperimentManager
    from .ranking_engine import RankingEngine
except ImportError:
    from backtest_runner import DEFAULT_BACKTEST_TIMEOUT_SECONDS, BacktestRunner
    from experiment_database import ExperimentDatabase
    from experiment_manager import ExperimentManager
    from ranking_engine import RankingEngine


DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent
WALK_FORWARD_METRICS = (
    "profit_factor",
    "sharpe",
    "max_drawdown_abs",
    "expectancy",
    "total_trades",
)


@dataclass(frozen=True)
class WalkForwardFold:
    index: int
    train_start: date
    train_end: date
    test_start: date
    test_end: date

    @property
    def train_timerange(self) -> str:
        return self._timerange(self.train_start, self.train_end)

    @property
    def test_timerange(self) -> str:
        return self._timerange(self.test_start, self.test_end)

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "train_start": self.train_start.isoformat(),
            "train_end": self.train_end.isoformat(),
            "train_timerange": self.train_timerange,
            "test_start": self.test_start.isoformat(),
            "test_end": self.test_end.isoformat(),
            "test_timerange": self.test_timerange,
        }

    def _timerange(self, start: date, end: date) -> str:
        return f"{start:%Y%m%d}-{end:%Y%m%d}"


class WalkForwardBacktestRunner(BacktestRunner):
    """BacktestRunner with per-experiment Freqtrade timerange support."""

    def _command(
        self,
        experiment_id: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[str]:
        command = super()._command(experiment_id, parameters)
        timerange = (parameters or {}).get("walk_forward", {}).get("timerange")
        if timerange:
            command.extend(["--timerange", str(timerange)])
        return command


class WalkForwardAnalyzer:
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

    def plan(
        self,
        *,
        session_id: str | None = None,
        start_date: str,
        train_days: int,
        test_days: int,
        shift_days: int,
        folds: int,
        candidate_session_id: str | None = None,
        candidate_experiment_ids: list[str] | None = None,
        candidate_limit: int = 20,
        strategy_plugin: str | None = None,
    ) -> dict[str, Any]:
        if train_days <= 0 or test_days <= 0 or shift_days <= 0 or folds <= 0:
            raise ValueError("train_days, test_days, shift_days and folds must be positive.")

        candidates = self._candidate_experiments(
            candidate_session_id=candidate_session_id,
            candidate_experiment_ids=candidate_experiment_ids,
            candidate_limit=candidate_limit,
            strategy_plugin=strategy_plugin,
        )
        if not candidates:
            raise ValueError("No completed candidate experiments found.")

        session_id = session_id or self._session_id()
        fold_rows = self._folds(
            start_date=self._parse_date(start_date),
            train_days=train_days,
            test_days=test_days,
            shift_days=shift_days,
            folds=folds,
        )
        strategy_hash = ExperimentManager(database=self.database).strategy_hash()

        self.database.create_session(
            session_id=session_id,
            objective="Walk-forward analysis with train optimization and OOS test folds.",
            strategy_name="LabPluginStrategy",
            search_method="walk_forward",
            goals={
                "start_date": start_date,
                "train_days": train_days,
                "test_days": test_days,
                "shift_days": shift_days,
                "folds": folds,
                "candidate_limit": candidate_limit,
            },
            metadata={
                "study_type": "walk_forward",
                "candidate_session_id": candidate_session_id,
                "candidate_experiment_ids": candidate_experiment_ids or [],
                "strategy_plugin": strategy_plugin,
                "folds": [fold.as_dict() for fold in fold_rows],
                "selected_tests_created": False,
            },
            status="paused",
        )

        created = []
        for fold in fold_rows:
            for candidate_index, candidate in enumerate(candidates):
                payload = {
                    **candidate["parameters"],
                    "walk_forward": {
                        "session_id": session_id,
                        "fold_index": fold.index,
                        "phase": "train",
                        "candidate_index": candidate_index,
                        "source_experiment_id": candidate["id"],
                        "timerange": fold.train_timerange,
                        "train_timerange": fold.train_timerange,
                        "test_timerange": fold.test_timerange,
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
                created.append(experiment_id)

        return {
            "session_id": session_id,
            "folds": [fold.as_dict() for fold in fold_rows],
            "candidate_count": len(candidates),
            "train_experiments_created": len(created),
            "train_experiments": created,
        }

    def run_phase(
        self,
        session_id: str,
        *,
        phase: str,
        limit: int | None = None,
        retries: int = 0,
        timeout_seconds: int = DEFAULT_BACKTEST_TIMEOUT_SECONDS,
        execution_mode: str = "auto",
    ) -> dict[str, Any]:
        runner = WalkForwardBacktestRunner(execution_mode=execution_mode)
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
            and self._walk_forward_meta(experiment).get("phase") == phase
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
                    error=f"Walk-forward runner failure: {exc.__class__.__name__}: {exc!r}",
                )
            current = self.database.get_experiment(experiment["id"])
            items.append(
                {
                    "id": experiment["id"],
                    "status": current.get("status") if current else "missing",
                    "phase": phase,
                    "runtime_seconds": current.get("runtime_seconds") if current else None,
                    "error": current.get("error") if current else "missing experiment",
                }
            )

        experiments = self.database.session_experiments(session_id)
        counts = self._phase_status_counts(experiments)
        if self._all_planned_finished(experiments):
            self.database.update_session_status(session_id, "finished")
        return {"session_id": session_id, "phase": phase, "counts": counts, "items": items}

    def select(self, session_id: str, *, order_by: str = "score") -> dict[str, Any]:
        session = self._require_session(session_id)
        train_by_fold = self._completed_by_fold(session_id, phase="train")
        if not train_by_fold:
            raise ValueError("No completed training experiments found.")

        strategy_hash = ExperimentManager(database=self.database).strategy_hash()
        created = []
        selected = []
        existing_tests = self._existing_test_keys(session_id)
        for fold in session["metadata"].get("folds", []):
            fold_index = int(fold["index"])
            train_rows = train_by_fold.get(fold_index, [])
            if not train_rows:
                continue
            best = sorted(
                train_rows,
                key=lambda experiment: self._rank_value(experiment, order_by),
                reverse=True,
            )[0]
            best_meta = self._walk_forward_meta(best)
            selected.append(
                {
                    "fold_index": fold_index,
                    "train_experiment_id": best["id"],
                    "source_experiment_id": best_meta.get("source_experiment_id"),
                    "train_metrics": self._metric_subset(best.get("metrics", {})),
                }
            )
            key = (fold_index, best_meta.get("candidate_index"))
            if key in existing_tests:
                continue

            payload = {
                **self._without_walk_forward(best["parameters"]),
                "walk_forward": {
                    "session_id": session_id,
                    "fold_index": fold_index,
                    "phase": "test",
                    "candidate_index": best_meta.get("candidate_index"),
                    "source_experiment_id": best_meta.get("source_experiment_id"),
                    "selected_train_experiment_id": best["id"],
                    "timerange": fold["test_timerange"],
                    "train_timerange": fold["train_timerange"],
                    "test_timerange": fold["test_timerange"],
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
            created.append(experiment_id)

        self.database.update_session_status(
            session_id,
            "paused",
            metadata={"selected_tests_created": True, "selection_metric": order_by},
        )
        return {
            "session_id": session_id,
            "selected": selected,
            "test_experiments_created": len(created),
            "test_experiments": created,
        }

    def analyze(self, session_id: str) -> dict[str, Any]:
        session = self._require_session(session_id)
        experiments = self.database.session_experiments(session_id)
        train_by_fold = self._completed_by_fold(session_id, phase="train")
        test_by_fold = self._completed_by_fold(session_id, phase="test")
        folds = []
        for fold in session["metadata"].get("folds", []):
            fold_index = int(fold["index"])
            test_rows = test_by_fold.get(fold_index, [])
            selected_test = test_rows[0] if test_rows else None
            train_rows = train_by_fold.get(fold_index, [])
            selected_train = self._selected_train_for_test(selected_test, train_rows)
            folds.append(
                self._fold_result(
                    fold=fold,
                    train_experiment=selected_train,
                    test_experiment=selected_test,
                )
            )

        return {
            "session_id": session_id,
            "generated_at": datetime.now(UTC).isoformat(),
            "status_counts": self._phase_status_counts(experiments),
            "folds": folds,
            "aggregate": self._aggregate(folds),
            "generalization": self._generalization(folds),
        }

    def write_reports(self, session_id: str) -> dict[str, Path]:
        analysis = self.analyze(session_id)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        json_path = self.output_dir / f"walk_forward_report_{session_id}.json"
        html_path = self.output_dir / f"walk_forward_report_{session_id}.html"
        md_path = self.output_dir / f"walk_forward_report_{session_id}.md"
        json_path.write_text(
            json.dumps(analysis, indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        html_path.write_text(self._render_html(analysis), encoding="utf-8")
        md_path.write_text(self._render_markdown(analysis), encoding="utf-8")
        return {"json": json_path, "html": html_path, "markdown": md_path}

    def _candidate_experiments(
        self,
        *,
        candidate_session_id: str | None,
        candidate_experiment_ids: list[str] | None,
        candidate_limit: int,
        strategy_plugin: str | None,
    ) -> list[dict[str, Any]]:
        if candidate_experiment_ids:
            candidates = [
                self.database.get_experiment(experiment_id)
                for experiment_id in candidate_experiment_ids
            ]
            rows = [candidate for candidate in candidates if candidate]
        elif candidate_session_id:
            rows = self.database.session_experiments(candidate_session_id)
        else:
            rows = self.database.list_experiments(status="completed")

        completed = [
            row
            for row in rows
            if row
            and row["status"] == "completed"
            and row.get("metrics")
            and self._is_plugin_candidate(row)
            and (not strategy_plugin or self._strategy_plugin(row) == strategy_plugin)
        ]
        for row in completed:
            row["computed_score"] = self.ranking.composite_score(row.get("metrics", {}))
        completed.sort(key=lambda row: row.get("computed_score", row.get("score") or 0.0), reverse=True)
        return completed[:candidate_limit]

    def _folds(
        self,
        *,
        start_date: date,
        train_days: int,
        test_days: int,
        shift_days: int,
        folds: int,
    ) -> list[WalkForwardFold]:
        output = []
        for index in range(folds):
            train_start = start_date + timedelta(days=index * shift_days)
            train_end = train_start + timedelta(days=train_days)
            test_start = train_end
            test_end = test_start + timedelta(days=test_days)
            output.append(
                WalkForwardFold(
                    index=index,
                    train_start=train_start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                )
            )
        return output

    def _fold_result(
        self,
        *,
        fold: dict[str, Any],
        train_experiment: dict[str, Any] | None,
        test_experiment: dict[str, Any] | None,
    ) -> dict[str, Any]:
        train_metrics = self._metric_subset(train_experiment.get("metrics", {})) if train_experiment else {}
        test_metrics = self._metric_subset(test_experiment.get("metrics", {})) if test_experiment else {}
        return {
            **fold,
            "train_experiment_id": train_experiment.get("id") if train_experiment else None,
            "test_experiment_id": test_experiment.get("id") if test_experiment else None,
            "train_metrics": train_metrics,
            "test_metrics": test_metrics,
            "degradation": self._degradation(train_metrics, test_metrics),
            "survived": bool(test_metrics and test_metrics.get("profit_factor", 0.0) > 1.0),
        }

    def _aggregate(self, folds: list[dict[str, Any]]) -> dict[str, Any]:
        output = {}
        for side in ("train", "test"):
            side_rows = [
                fold[f"{side}_metrics"]
                for fold in folds
                if fold.get(f"{side}_metrics")
            ]
            output[side] = {
                metric: self._metric_stats([row.get(metric, 0.0) for row in side_rows])
                for metric in WALK_FORWARD_METRICS
            }
        output["degradation"] = {
            metric: self._metric_stats(
                [
                    fold.get("degradation", {}).get(metric, 0.0)
                    for fold in folds
                    if fold.get("degradation")
                ]
            )
            for metric in WALK_FORWARD_METRICS
        }
        return output

    def _generalization(self, folds: list[dict[str, Any]]) -> dict[str, Any]:
        completed = [fold for fold in folds if fold.get("test_metrics")]
        if not completed:
            return {
                "survival_rate": 0.0,
                "stability_index": 0.0,
                "conclusion": "No completed OOS folds available.",
            }
        survival_rate = sum(1 for fold in completed if fold["survived"]) / len(completed)
        test_pfs = [fold["test_metrics"].get("profit_factor", 0.0) for fold in completed]
        test_pf_mean = mean(test_pfs)
        test_pf_std = pstdev(test_pfs) if len(test_pfs) > 1 else 0.0
        degradation = [
            fold.get("degradation", {}).get("profit_factor", 0.0)
            for fold in completed
        ]
        avg_degradation = mean(degradation) if degradation else 0.0
        stability_index = max(
            0.0,
            survival_rate
            * (test_pf_mean / (test_pf_mean + test_pf_std + 1e-12))
            * (1.0 - min(1.0, max(0.0, avg_degradation) / 100.0)),
        )
        if survival_rate >= 0.70 and stability_index >= 0.50:
            conclusion = "Evidence supports moderate to strong generalization."
        elif survival_rate >= 0.50:
            conclusion = "Evidence supports limited generalization with meaningful risk."
        else:
            conclusion = "Evidence does not support reliable generalization."
        return {
            "survival_rate": survival_rate,
            "stability_index": stability_index,
            "test_profit_factor_mean": test_pf_mean,
            "test_profit_factor_std": test_pf_std,
            "average_profit_factor_degradation_pct": avg_degradation,
            "conclusion": conclusion,
        }

    def _degradation(
        self,
        train_metrics: dict[str, float],
        test_metrics: dict[str, float],
    ) -> dict[str, float]:
        output = {}
        for metric in WALK_FORWARD_METRICS:
            train_value = train_metrics.get(metric, 0.0)
            test_value = test_metrics.get(metric, 0.0)
            denominator = max(abs(train_value), 1e-12)
            if metric == "max_drawdown_abs":
                output[metric] = ((test_value - train_value) / denominator) * 100.0
            else:
                output[metric] = ((train_value - test_value) / denominator) * 100.0
        return output

    def _completed_by_fold(
        self,
        session_id: str,
        *,
        phase: str,
    ) -> dict[int, list[dict[str, Any]]]:
        grouped: dict[int, list[dict[str, Any]]] = {}
        for experiment in self.database.session_experiments(session_id):
            meta = self._walk_forward_meta(experiment)
            if experiment["status"] != "completed" or meta.get("phase") != phase:
                continue
            grouped.setdefault(int(meta["fold_index"]), []).append(experiment)
        return grouped

    def _selected_train_for_test(
        self,
        test_experiment: dict[str, Any] | None,
        train_rows: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if not test_experiment:
            return None
        selected_id = self._walk_forward_meta(test_experiment).get("selected_train_experiment_id")
        for train in train_rows:
            if train["id"] == selected_id:
                return train
        return None

    def _existing_test_keys(self, session_id: str) -> set[tuple[int, Any]]:
        keys = set()
        for experiment in self.database.session_experiments(session_id):
            meta = self._walk_forward_meta(experiment)
            if meta.get("phase") == "test":
                keys.add((int(meta["fold_index"]), meta.get("candidate_index")))
        return keys

    def _phase_status_counts(self, experiments: list[dict[str, Any]]) -> dict[str, Any]:
        counts: dict[str, Any] = {}
        for phase in ("train", "test"):
            phase_rows = [
                experiment
                for experiment in experiments
                if self._walk_forward_meta(experiment).get("phase") == phase
            ]
            counts[phase] = {
                status: sum(1 for row in phase_rows if row["status"] == status)
                for status in ("pending", "running", "completed", "error")
            }
        return counts

    def _all_planned_finished(self, experiments: list[dict[str, Any]]) -> bool:
        return not any(
            experiment["status"] in {"pending", "running"} for experiment in experiments
        )

    def _walk_forward_meta(self, experiment: dict[str, Any]) -> dict[str, Any]:
        meta = experiment.get("parameters", {}).get("walk_forward")
        return meta if isinstance(meta, dict) else {}

    def _without_walk_forward(self, parameters: dict[str, Any]) -> dict[str, Any]:
        clean = dict(parameters)
        clean.pop("walk_forward", None)
        return clean

    def _rank_value(self, experiment: dict[str, Any], order_by: str) -> float:
        if order_by == "score":
            return self.ranking.composite_score(experiment.get("metrics", {}))
        return self._number(experiment.get("metrics", {}).get(order_by)) or 0.0

    def _metric_subset(self, metrics: dict[str, Any]) -> dict[str, float]:
        return {metric: self._metric(metrics, metric) for metric in WALK_FORWARD_METRICS}

    def _metric(self, metrics: dict[str, Any], metric: str) -> float:
        if metric == "max_drawdown_abs":
            return (
                self._number(metrics.get("max_drawdown_abs"))
                or self._number(metrics.get("max_relative_drawdown"))
                or 0.0
            )
        return self._number(metrics.get(metric)) or 0.0

    def _metric_stats(self, values: list[float]) -> dict[str, float]:
        if not values:
            return {"count": 0, "mean": 0.0, "median": 0.0, "std": 0.0, "min": 0.0, "max": 0.0}
        return {
            "count": len(values),
            "mean": mean(values),
            "median": median(values),
            "std": pstdev(values) if len(values) > 1 else 0.0,
            "min": min(values),
            "max": max(values),
        }

    def _is_plugin_candidate(self, experiment: dict[str, Any]) -> bool:
        return bool(experiment.get("parameters", {}).get("strategy_plugin"))

    def _strategy_plugin(self, experiment: dict[str, Any]) -> str | None:
        return experiment.get("parameters", {}).get("strategy_plugin")

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

    def _parse_date(self, value: str) -> date:
        return datetime.strptime(value, "%Y-%m-%d").date()

    def _require_session(self, session_id: str) -> dict[str, Any]:
        session = self.database.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found.")
        return session

    def _experiment_id(self, payload: dict[str, Any]) -> str:
        meta = payload["walk_forward"]
        digest = hashlib.sha1(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:12]
        return (
            f"wf-f{meta['fold_index']}-{meta['phase']}-"
            f"{digest}-{uuid.uuid4().hex[:8]}"
        )

    def _session_id(self) -> str:
        stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        return f"walk-forward-{stamp}-{uuid.uuid4().hex[:8]}"

    def _render_markdown(self, analysis: dict[str, Any]) -> str:
        lines = [
            "# Walk-Forward Analysis\n\n",
            f"Session: `{analysis['session_id']}`\n\n",
            "## Fold Results\n\n",
            "| Fold | Train PF | Test PF | Train Sharpe | Test Sharpe | Train DD | Test DD | PF degradation % | Survived |\n",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---|\n",
        ]
        for fold in analysis["folds"]:
            train = fold.get("train_metrics", {})
            test = fold.get("test_metrics", {})
            degradation = fold.get("degradation", {})
            lines.append(
                "| {fold} | {train_pf:.4f} | {test_pf:.4f} | {train_sharpe:.4f} | "
                "{test_sharpe:.4f} | {train_dd:.4f} | {test_dd:.4f} | "
                "{pf_deg:.2f} | {survived} |\n".format(
                    fold=fold["index"],
                    train_pf=train.get("profit_factor", 0.0),
                    test_pf=test.get("profit_factor", 0.0),
                    train_sharpe=train.get("sharpe", 0.0),
                    test_sharpe=test.get("sharpe", 0.0),
                    train_dd=train.get("max_drawdown_abs", 0.0),
                    test_dd=test.get("max_drawdown_abs", 0.0),
                    pf_deg=degradation.get("profit_factor", 0.0),
                    survived="yes" if fold.get("survived") else "no",
                )
            )
        generalization = analysis["generalization"]
        lines.extend(
            [
                "\n## Generalization\n\n",
                f"- Survival rate: {generalization['survival_rate']:.2%}\n",
                f"- Stability index: {generalization['stability_index']:.4f}\n",
                "- Conclusion: " + generalization["conclusion"] + "\n",
            ]
        )
        return "".join(lines)

    def _render_html(self, analysis: dict[str, Any]) -> str:
        payload = json.dumps(analysis, ensure_ascii=False)
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Walk-Forward Analysis</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2933; }}
    table {{ border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 13px; }}
    th, td {{ border: 1px solid #d9e2ec; padding: 7px 9px; text-align: left; }}
    th {{ background: #f0f4f8; }}
    canvas {{ width: 100%; height: 260px; border: 1px solid #d9e2ec; margin: 12px 0; }}
    .metric {{ display: inline-block; border: 1px solid #d9e2ec; padding: 8px 10px; margin: 4px 8px 4px 0; }}
  </style>
</head>
<body>
  <h1>Walk-Forward Analysis</h1>
  <p><strong>Session:</strong> <span id="session"></span></p>
  <div id="summary"></div>
  <canvas id="pf"></canvas>
  <canvas id="degradation"></canvas>
  <h2>Fold Results</h2>
  <table id="folds"></table>
  <script>
    const data = {payload};
    const folds = data.folds || [];
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
    document.getElementById('summary').innerHTML =
      `<span class="metric"><strong>Survival</strong><br>${{(data.generalization.survival_rate * 100).toFixed(2)}}%</span>` +
      `<span class="metric"><strong>Stability</strong><br>${{f(data.generalization.stability_index)}}</span>` +
      `<span class="metric"><strong>Conclusion</strong><br>${{data.generalization.conclusion}}</span>`;
    table('folds',
      ['Fold', 'Train PF', 'Test PF', 'Train Sharpe', 'Test Sharpe', 'Train DD', 'Test DD', 'PF degradation %', 'Survived'],
      folds.map(row => [
        row.index,
        f(row.train_metrics.profit_factor),
        f(row.test_metrics.profit_factor),
        f(row.train_metrics.sharpe),
        f(row.test_metrics.sharpe),
        f(row.train_metrics.max_drawdown_abs),
        f(row.test_metrics.max_drawdown_abs),
        f(row.degradation.profit_factor, 2),
        row.survived ? 'yes' : 'no',
      ])
    );
    function drawLine(id, leftMetric, rightMetric, title) {{
      const canvas = document.getElementById(id);
      const ctx = canvas.getContext('2d');
      canvas.width = canvas.clientWidth * devicePixelRatio;
      canvas.height = canvas.clientHeight * devicePixelRatio;
      ctx.scale(devicePixelRatio, devicePixelRatio);
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      ctx.clearRect(0, 0, w, h);
      ctx.fillText(title, 12, 18);
      const train = folds.map(row => n(row.train_metrics[leftMetric]));
      const test = folds.map(row => n(row.test_metrics[rightMetric]));
      const values = [...train, ...test];
      const min = Math.min(...values, 0);
      const max = Math.max(...values, 1);
      function draw(values, color) {{
        ctx.strokeStyle = color;
        ctx.beginPath();
        values.forEach((value, index) => {{
          const x = 36 + index * (w - 60) / Math.max(1, values.length - 1);
          const y = h - 28 - ((value - min) / (max - min || 1)) * (h - 58);
          if (index === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }});
        ctx.stroke();
      }}
      draw(train, '#2f6f73');
      draw(test, '#b15533');
    }}
    drawLine('pf', 'profit_factor', 'profit_factor', 'Train vs Test Profit Factor');
    const degradationCanvas = document.getElementById('degradation');
    const ctx = degradationCanvas.getContext('2d');
    degradationCanvas.width = degradationCanvas.clientWidth * devicePixelRatio;
    degradationCanvas.height = degradationCanvas.clientHeight * devicePixelRatio;
    ctx.scale(devicePixelRatio, devicePixelRatio);
    const w = degradationCanvas.clientWidth;
    const h = degradationCanvas.clientHeight;
    ctx.fillText('Profit Factor degradation %', 12, 18);
    const values = folds.map(row => n(row.degradation.profit_factor));
    const min = Math.min(...values, 0), max = Math.max(...values, 1);
    values.forEach((value, index) => {{
      const x = 24 + index * (w - 48) / Math.max(1, values.length);
      const barWidth = (w - 48) / Math.max(1, values.length) - 3;
      const barHeight = ((value - min) / (max - min || 1)) * (h - 58);
      ctx.fillStyle = value <= 0 ? '#2f6f73' : '#b15533';
      ctx.fillRect(x, h - 28 - barHeight, barWidth, barHeight);
    }});
  </script>
</body>
</html>
"""


def _parse_ids(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Walk-forward analysis runner.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("--session-id")
    plan_parser.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    plan_parser.add_argument("--train-days", type=int, required=True)
    plan_parser.add_argument("--test-days", type=int, required=True)
    plan_parser.add_argument("--shift-days", type=int, required=True)
    plan_parser.add_argument("--folds", type=int, required=True)
    plan_parser.add_argument("--candidate-session-id")
    plan_parser.add_argument("--candidate-experiment-ids")
    plan_parser.add_argument("--candidate-limit", type=int, default=20)
    plan_parser.add_argument("--strategy-plugin")

    run_train = subparsers.add_parser("run-train")
    run_train.add_argument("session_id")
    run_train.add_argument("--limit", type=int)
    run_train.add_argument("--timeout-seconds", type=int, default=DEFAULT_BACKTEST_TIMEOUT_SECONDS)
    run_train.add_argument("--retries", type=int, default=0)
    run_train.add_argument("--execution-mode", choices=("auto", "docker", "freqtrade"), default="auto")

    select_parser = subparsers.add_parser("select")
    select_parser.add_argument("session_id")
    select_parser.add_argument("--order-by", default="score")

    run_test = subparsers.add_parser("run-test")
    run_test.add_argument("session_id")
    run_test.add_argument("--limit", type=int)
    run_test.add_argument("--timeout-seconds", type=int, default=DEFAULT_BACKTEST_TIMEOUT_SECONDS)
    run_test.add_argument("--retries", type=int, default=0)
    run_test.add_argument("--execution-mode", choices=("auto", "docker", "freqtrade"), default="auto")

    analyze_parser = subparsers.add_parser("analyze")
    analyze_parser.add_argument("session_id")
    analyze_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)

    args = parser.parse_args()
    analyzer = WalkForwardAnalyzer(output_dir=getattr(args, "output_dir", DEFAULT_OUTPUT_DIR))

    if args.command == "plan":
        result = analyzer.plan(
            session_id=args.session_id,
            start_date=args.start_date,
            train_days=args.train_days,
            test_days=args.test_days,
            shift_days=args.shift_days,
            folds=args.folds,
            candidate_session_id=args.candidate_session_id,
            candidate_experiment_ids=_parse_ids(args.candidate_experiment_ids),
            candidate_limit=args.candidate_limit,
            strategy_plugin=args.strategy_plugin,
        )
    elif args.command == "run-train":
        result = analyzer.run_phase(
            args.session_id,
            phase="train",
            limit=args.limit,
            retries=args.retries,
            timeout_seconds=args.timeout_seconds,
            execution_mode=args.execution_mode,
        )
    elif args.command == "select":
        result = analyzer.select(args.session_id, order_by=args.order_by)
    elif args.command == "run-test":
        result = analyzer.run_phase(
            args.session_id,
            phase="test",
            limit=args.limit,
            retries=args.retries,
            timeout_seconds=args.timeout_seconds,
            execution_mode=args.execution_mode,
        )
    elif args.command == "analyze":
        paths = analyzer.write_reports(args.session_id)
        result = {key: str(path) for key, path in paths.items()}
    else:
        raise ValueError(f"Unknown command {args.command}")

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
