from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import sqlite3
import statistics
import time
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from .ablation_study import AblationStudy
    from .backtest_runner import DEFAULT_BACKTEST_TIMEOUT_SECONDS, BacktestRunner
    from .experiment_database import DEFAULT_DB_PATH, ExperimentDatabase
    from .experiment_manager import ExperimentManager
    from .neighborhood_explorer import NeighborhoodExplorer
    from .parameter_generator import ParameterGenerator
    from .ranking_engine import RankingEngine
    from .robustness_analyzer import RobustnessAnalyzer
    from .walk_forward_analyzer import WalkForwardAnalyzer
except ImportError:
    from ablation_study import AblationStudy
    from backtest_runner import DEFAULT_BACKTEST_TIMEOUT_SECONDS, BacktestRunner
    from experiment_database import DEFAULT_DB_PATH, ExperimentDatabase
    from experiment_manager import ExperimentManager
    from neighborhood_explorer import NeighborhoodExplorer
    from parameter_generator import ParameterGenerator
    from ranking_engine import RankingEngine
    from robustness_analyzer import RobustnessAnalyzer
    from walk_forward_analyzer import WalkForwardAnalyzer


DEFAULT_PAIR = "AVAX/USDT"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent
REPORT_STEM = "single_asset_report"
PAIR_METRIC_KEYS = (
    "profit_factor",
    "expectancy",
    "max_drawdown_abs",
    "sharpe",
    "winrate",
    "total_trades",
    "profit_total_abs",
)


class SingleAssetBacktestRunner(BacktestRunner):
    """Backtest runner that restricts each sandbox config to one pair."""

    def __init__(self, *, pair: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.pair = pair

    def _write_backtest_config(self, sandbox_user_data: Path, experiment_id: str) -> None:
        super()._write_backtest_config(sandbox_user_data, experiment_id)
        config_path = sandbox_user_data / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        exchange = config.setdefault("exchange", {})
        exchange["pair_whitelist"] = [self.pair]
        exchange["pair_blacklist"] = []
        config["single_asset_research"] = {
            "pair": self.pair,
            "experiment_id": experiment_id,
        }
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")


class SingleAssetExperimentManager(ExperimentManager):
    """ExperimentManager facade that only runs experiments from one session."""

    def __init__(
        self,
        *,
        pair: str,
        database: ExperimentDatabase | None = None,
        execution_mode: str = "auto",
    ) -> None:
        super().__init__(
            database=database,
            runner=SingleAssetBacktestRunner(
                pair=pair,
                strategy_name="LabPluginStrategy",
                execution_mode=execution_mode,
            ),
            strategy_name="LabPluginStrategy",
            execution_mode=execution_mode,
        )
        self.pair = pair

    def run_session(
        self,
        session_id: str,
        *,
        limit: int | None = None,
        retries: int = 0,
        timeout_seconds: int = DEFAULT_BACKTEST_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        self._mark_interrupted_experiments()
        experiments = [
            experiment
            for experiment in self.database.session_experiments(session_id)
            if experiment["status"] == "pending"
        ]
        if limit is not None:
            experiments = experiments[:limit]

        started = time.perf_counter()
        completed = 0
        failed = 0
        self.database.update_session_status(session_id, "running")
        try:
            for experiment in experiments:
                self.run_experiment(
                    experiment["id"],
                    retries=retries,
                    timeout_seconds=timeout_seconds,
                )
                current = self.database.get_experiment(experiment["id"])
                if current and current["status"] == "completed":
                    completed += 1
                else:
                    failed += 1
        finally:
            remaining = [
                experiment
                for experiment in self.database.session_experiments(session_id)
                if experiment["status"] == "pending"
            ]
            self.database.update_session_status(
                session_id,
                "paused" if remaining else "finished",
                metadata={
                    "last_single_asset_run": {
                        "pair": self.pair,
                        "completed": completed,
                        "failed": failed,
                        "remaining": len(remaining),
                        "runtime_seconds": time.perf_counter() - started,
                    }
                },
            )

        return {
            "session_id": session_id,
            "pair": self.pair,
            "attempted": len(experiments),
            "completed": completed,
            "failed": failed,
            "runtime_seconds": time.perf_counter() - started,
        }


class SingleAssetResearch:
    """Scientific campaign orchestration for one asset at a time."""

    def __init__(
        self,
        *,
        database: ExperimentDatabase | None = None,
        db_path: Path | str = DEFAULT_DB_PATH,
        output_dir: Path | str = DEFAULT_OUTPUT_DIR,
    ) -> None:
        self.database = database or ExperimentDatabase(db_path)
        self.db_path = Path(db_path)
        self.output_dir = Path(output_dir)
        self.ranking = RankingEngine(self.database)

    def plan(
        self,
        *,
        pair: str = DEFAULT_PAIR,
        strategy_plugin: str,
        count: int,
        mode: str = "random",
        session_id: str | None = None,
        seed: int | None = None,
    ) -> dict[str, Any]:
        if count <= 0:
            raise ValueError("count must be positive.")
        if mode not in {"random", "grid"}:
            raise ValueError("mode must be random or grid.")

        session_id = session_id or self._session_id(pair, strategy_plugin)
        generator = ParameterGenerator(seed=seed, strategy_plugins=[strategy_plugin])
        parameter_sets = (
            generator.generate_plugin_grid(strategy_plugins=[strategy_plugin], limit=count)
            if mode == "grid"
            else generator.generate_plugin_random(count, strategy_plugins=[strategy_plugin])
        )
        strategy_hash = ExperimentManager(database=self.database).strategy_hash()

        self.database.create_session(
            session_id=session_id,
            objective=f"Single-asset scientific research for {pair} using {strategy_plugin}.",
            strategy_name="LabPluginStrategy",
            search_method=f"single_asset_{mode}",
            goals={
                "pair": pair,
                "strategy_plugin": strategy_plugin,
                "count": count,
                "mode": mode,
            },
            metadata={
                "study_type": "single_asset_research",
                "pair": pair,
                "strategy_plugin": strategy_plugin,
                "ranking_scope": "pair_only",
                "pipeline": [
                    "main_search",
                    "ranking",
                    "robustness",
                    "neighborhood",
                    "ablation",
                    "walk_forward",
                    "comparison",
                ],
            },
            status="paused",
        )

        created = []
        for index, parameters in enumerate(parameter_sets):
            payload = {
                **parameters,
                "single_asset": {
                    "pair": pair,
                    "session_id": session_id,
                    "campaign_index": index,
                },
            }
            experiment_id = self._experiment_id(session_id, payload)
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
            "pair": pair,
            "strategy_plugin": strategy_plugin,
            "mode": mode,
            "created_experiments": len(created),
            "experiments": created,
        }

    def run(
        self,
        *,
        session_id: str,
        limit: int | None = None,
        retries: int = 0,
        timeout_seconds: int = DEFAULT_BACKTEST_TIMEOUT_SECONDS,
        execution_mode: str = "auto",
    ) -> dict[str, Any]:
        session = self._require_session(session_id)
        pair = session.get("metadata", {}).get("pair") or session.get("goals", {}).get("pair")
        if not pair:
            raise ValueError(f"Session {session_id} does not define a single pair.")
        manager = SingleAssetExperimentManager(
            pair=pair,
            database=self.database,
            execution_mode=execution_mode,
        )
        return manager.run_session(
            session_id,
            limit=limit,
            retries=retries,
            timeout_seconds=timeout_seconds,
        )

    def analyze(
        self,
        *,
        pair: str = DEFAULT_PAIR,
        session_id: str | None = None,
        strategy_plugin: str | None = None,
        top: int = 100,
    ) -> dict[str, Path]:
        report = self.build_report(
            pair=pair,
            session_id=session_id,
            strategy_plugin=strategy_plugin,
            top=top,
        )
        return self.write_reports(report)

    def build_report(
        self,
        *,
        pair: str = DEFAULT_PAIR,
        session_id: str | None = None,
        strategy_plugin: str | None = None,
        top: int = 100,
    ) -> dict[str, Any]:
        experiments = self._experiments(session_id=session_id)
        rows = [
            row
            for row in (self._pair_row(experiment, pair) for experiment in experiments)
            if row is not None
            and (strategy_plugin is None or row["strategy_plugin"] == strategy_plugin)
        ]
        ranked = sorted(rows, key=lambda row: row["pair_score"], reverse=True)
        strategy_summary = self._strategy_summary(rows)
        comparison = self._comparison(rows, pair)
        phase_status = self._phase_status(session_id=session_id, pair=pair)

        report = {
            "generated_at": datetime.now(UTC).isoformat(),
            "scope": {
                "pair": pair,
                "session_id": session_id,
                "strategy_plugin": strategy_plugin,
                "experiment_count": len(experiments),
                "matched_pair_experiments": len(rows),
                "top": top,
                "read_only_analysis": True,
            },
            "ranking": ranked[:top],
            "best_experiment": ranked[0] if ranked else None,
            "strategy_summary": strategy_summary,
            "comparison": comparison,
            "pipeline_status": phase_status,
            "recommendations": self._recommendations(ranked, strategy_summary, phase_status),
        }
        return report

    def write_reports(self, report: dict[str, Any]) -> dict[str, Path]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        json_path = self.output_dir / f"{REPORT_STEM}.json"
        markdown_path = self.output_dir / f"{REPORT_STEM}.md"
        html_path = self.output_dir / f"{REPORT_STEM}.html"
        json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        markdown_path.write_text(self._markdown(report), encoding="utf-8")
        html_path.write_text(self._html(report), encoding="utf-8")
        return {"json": json_path, "markdown": markdown_path, "html": html_path}

    def plan_robustness(self, session_id: str) -> dict[str, Path]:
        return RobustnessAnalyzer(db_path=self.db_path, output_dir=self.output_dir).write_reports(
            session_id
        )

    def analyze_neighborhood(self, session_id: str) -> dict[str, Any]:
        return NeighborhoodExplorer(database=self.database, output_dir=self.output_dir).analyze(
            session_id
        )

    def analyze_ablation(self, session_id: str) -> dict[str, Any]:
        return AblationStudy(database=self.database, output_dir=self.output_dir).analyze(
            session_id
        )

    def analyze_walk_forward(self, session_id: str) -> dict[str, Any]:
        return WalkForwardAnalyzer(
            database=self.database,
            output_dir=self.output_dir,
        ).analyze(session_id)

    def _experiments(self, *, session_id: str | None) -> list[dict[str, Any]]:
        if session_id:
            return self.database.session_experiments(session_id)
        return self.database.list_experiments(status="completed")

    def _pair_row(self, experiment: dict[str, Any], pair: str) -> dict[str, Any] | None:
        if experiment.get("status") != "completed" or not experiment.get("metrics"):
            return None
        pair_metrics = experiment["metrics"].get("profit_by_pair", {}).get(pair)
        if not isinstance(pair_metrics, dict):
            return None
        total_trades = self._trade_count(pair_metrics)
        if total_trades <= 0:
            return None
        strategy_plugin = self._strategy_plugin(experiment)
        normalized = self._normalize_pair_metrics(pair_metrics)
        pair_score = self._pair_score(normalized)
        return {
            "experiment_id": experiment["id"],
            "strategy_plugin": strategy_plugin,
            "parameters": experiment.get("parameters", {}),
            "pair": pair,
            "pair_metrics": normalized,
            "pair_score": pair_score,
            "global_score": self._number(experiment.get("score")),
            "runtime_seconds": self._number(experiment.get("runtime_seconds")),
            "result_path": experiment.get("result_path"),
        }

    def _normalize_pair_metrics(self, metrics: dict[str, Any]) -> dict[str, Any]:
        total_trades = self._trade_count(metrics)
        profit_total_abs = self._number(
            metrics.get("profit_total_abs", metrics.get("profit_abs", metrics.get("profit_total")))
        )
        return {
            "profit_factor": self._number(metrics.get("profit_factor")),
            "expectancy": self._number(metrics.get("expectancy")),
            "max_drawdown_abs": self._number(metrics.get("max_drawdown_abs")),
            "sharpe": self._number(metrics.get("sharpe")),
            "winrate": self._winrate(metrics),
            "total_trades": total_trades,
            "profit_total_abs": profit_total_abs,
            "wins": int(self._number(metrics.get("wins"))),
            "losses": int(self._number(metrics.get("losses"))),
            "draws": int(self._number(metrics.get("draws"))),
            "raw": metrics,
        }

    def _strategy_summary(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[row["strategy_plugin"]].append(row)

        summary = []
        for strategy_plugin, items in grouped.items():
            profit_factors = [item["pair_metrics"]["profit_factor"] for item in items]
            scores = [item["pair_score"] for item in items]
            profitable = [value for value in profit_factors if value > 1.0]
            best = max(items, key=lambda item: item["pair_score"])
            summary.append(
                {
                    "strategy_plugin": strategy_plugin,
                    "experiments": len(items),
                    "best_experiment_id": best["experiment_id"],
                    "best_pair_score": best["pair_score"],
                    "best_profit_factor": best["pair_metrics"]["profit_factor"],
                    "median_profit_factor": statistics.median(profit_factors),
                    "mean_profit_factor": statistics.mean(profit_factors),
                    "pf_gt_1_ratio": len(profitable) / len(items),
                    "mean_pair_score": statistics.mean(scores),
                }
            )
        return sorted(summary, key=lambda item: item["best_pair_score"], reverse=True)

    def _comparison(self, rows: list[dict[str, Any]], pair: str) -> dict[str, Any]:
        if not rows:
            return {
                "pair": pair,
                "status": "no_completed_pair_results",
                "message": "No completed experiment contains metrics for this pair.",
            }
        best = max(rows, key=lambda item: item["pair_score"])
        profitable = [row for row in rows if row["pair_metrics"]["profit_factor"] > 1.0]
        robust = [
            row
            for row in profitable
            if row["pair_metrics"]["total_trades"] >= 20
            and row["pair_metrics"]["max_drawdown_abs"] >= 0
        ]
        return {
            "pair": pair,
            "status": "analyzed",
            "best_strategy_plugin": best["strategy_plugin"],
            "best_experiment_id": best["experiment_id"],
            "best_profit_factor": best["pair_metrics"]["profit_factor"],
            "best_expectancy": best["pair_metrics"]["expectancy"],
            "experiments_with_pf_gt_1": len(profitable),
            "experiments_with_min_trade_support": len(robust),
            "single_asset_research_needed": True,
        }

    def _phase_status(self, *, session_id: str | None, pair: str) -> dict[str, Any]:
        sessions = self.database.list_sessions()
        related = []
        for session in sessions:
            metadata = session.get("metadata", {})
            goals = session.get("goals", {})
            if session_id and session["id"] == session_id:
                related.append(session)
            elif metadata.get("pair") == pair or goals.get("pair") == pair:
                related.append(session)

        counts = defaultdict(int)
        for session in related:
            study_type = session.get("metadata", {}).get("study_type", session["search_method"])
            counts[study_type] += 1
        return {
            "related_sessions": len(related),
            "by_study_type": dict(sorted(counts.items())),
            "required_pipeline": {
                "main_search": counts.get("single_asset_research", 0) > 0,
                "ranking": True,
                "robustness": counts.get("robustness", 0) > 0,
                "neighborhood": counts.get("neighborhood_exploration", 0) > 0,
                "ablation": counts.get("ablation", 0) > 0,
                "walk_forward": counts.get("walk_forward", 0) > 0,
                "comparison": True,
            },
        }

    def _recommendations(
        self,
        ranked: list[dict[str, Any]],
        strategy_summary: list[dict[str, Any]],
        phase_status: dict[str, Any],
    ) -> dict[str, Any]:
        if not ranked:
            return {
                "status": "insufficient_data",
                "next_action": "plan_single_asset_campaign",
                "reason": "No completed pair-specific metrics are available yet.",
            }
        best = ranked[0]
        missing = [
            name
            for name, ready in phase_status["required_pipeline"].items()
            if not ready
        ]
        if missing:
            return {
                "status": "incomplete_pipeline",
                "next_action": f"complete phases: {', '.join(missing)}",
                "best_current_strategy": best["strategy_plugin"],
                "best_current_experiment": best["experiment_id"],
            }
        return {
            "status": "pipeline_ready_for_review",
            "next_action": "review robustness, walk-forward and comparison evidence",
            "best_current_strategy": best["strategy_plugin"],
            "best_current_experiment": best["experiment_id"],
            "strategy_summary": strategy_summary[:5],
        }

    def _pair_score(self, metrics: dict[str, Any]) -> float:
        return (
            metrics["profit_factor"] * 0.40
            + metrics["expectancy"] * 0.20
            + metrics["profit_total_abs"] * 0.20
            + metrics["sharpe"] * 0.10
            - metrics["max_drawdown_abs"] * 0.10
        )

    def _trade_count(self, metrics: dict[str, Any]) -> int:
        direct = self._number(metrics.get("total_trades", metrics.get("trades")))
        if direct:
            return int(direct)
        return int(
            self._number(metrics.get("wins"))
            + self._number(metrics.get("losses"))
            + self._number(metrics.get("draws"))
        )

    def _winrate(self, metrics: dict[str, Any]) -> float:
        direct = metrics.get("winrate", metrics.get("win_rate"))
        if direct is not None:
            value = self._number(direct)
            return value / 100 if value > 1 else value
        trades = self._trade_count(metrics)
        return self._number(metrics.get("wins")) / trades if trades else 0.0

    def _strategy_plugin(self, experiment: dict[str, Any]) -> str:
        parameters = experiment.get("parameters", {})
        return (
            parameters.get("strategy_plugin")
            or experiment.get("strategy_plugin")
            or experiment.get("strategy_name")
            or "UNKNOWN"
        )

    def _require_session(self, session_id: str) -> dict[str, Any]:
        session = self.database.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found.")
        return session

    def _session_id(self, pair: str, strategy_plugin: str) -> str:
        safe_pair = pair.replace("/", "-").replace(":", "-").lower()
        safe_strategy = strategy_plugin.replace("Strategy", "").lower()
        return f"single-asset-{safe_pair}-{safe_strategy}-{uuid.uuid4().hex[:10]}"

    def _experiment_id(self, session_id: str, payload: dict[str, Any]) -> str:
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode("utf-8")
        ).hexdigest()[:12]
        return f"single-asset-exp-{uuid.uuid5(uuid.NAMESPACE_DNS, session_id).hex[:8]}-{digest}"

    def _number(self, value: Any) -> float:
        try:
            if value is None or isinstance(value, bool):
                return 0.0
            parsed = float(value)
        except (TypeError, ValueError):
            return 0.0
        return 0.0 if math.isnan(parsed) or math.isinf(parsed) else parsed

    def _markdown(self, report: dict[str, Any]) -> str:
        scope = report["scope"]
        best = report["best_experiment"]
        lines = [
            "# Single Asset Research",
            "",
            "## Scope",
            f"- Pair: {scope['pair']}",
            f"- Session: {scope['session_id'] or 'all completed experiments'}",
            f"- Strategy filter: {scope['strategy_plugin'] or 'all strategies'}",
            f"- Matched experiments: {scope['matched_pair_experiments']}",
            "",
            "## Best Experiment",
        ]
        if best:
            metrics = best["pair_metrics"]
            lines.extend(
                [
                    f"- Experiment: {best['experiment_id']}",
                    f"- Strategy: {best['strategy_plugin']}",
                    f"- Pair score: {best['pair_score']:.4f}",
                    f"- Profit Factor: {metrics['profit_factor']:.4f}",
                    f"- Expectancy: {metrics['expectancy']:.6f}",
                    f"- Drawdown: {metrics['max_drawdown_abs']:.4f}",
                    f"- Trades: {metrics['total_trades']}",
                ]
            )
        else:
            lines.append("- No completed pair-specific result found.")
        lines.extend(
            [
                "",
                "## Strategy Ranking",
                "| Strategy | Experiments | Best PF | Median PF | PF > 1 | Best experiment |",
                "|---|---:|---:|---:|---:|---|",
            ]
        )
        for row in report["strategy_summary"]:
            lines.append(
                "| {strategy} | {experiments} | {best_pf:.4f} | {median_pf:.4f} | {pf_ratio:.2%} | {experiment} |".format(
                    strategy=row["strategy_plugin"],
                    experiments=row["experiments"],
                    best_pf=row["best_profit_factor"],
                    median_pf=row["median_profit_factor"],
                    pf_ratio=row["pf_gt_1_ratio"],
                    experiment=row["best_experiment_id"],
                )
            )
        lines.extend(
            [
                "",
                "## Pipeline Status",
                "```json",
                json.dumps(report["pipeline_status"], indent=2, sort_keys=True),
                "```",
                "",
                "## Recommendation",
                f"- Status: {report['recommendations']['status']}",
                f"- Next action: {report['recommendations']['next_action']}",
            ]
        )
        return "\n".join(lines) + "\n"

    def _html(self, report: dict[str, Any]) -> str:
        rows = "\n".join(
            "<tr><td>{strategy}</td><td>{experiments}</td><td>{best_pf:.4f}</td>"
            "<td>{median_pf:.4f}</td><td>{pf_ratio:.2%}</td><td>{experiment}</td></tr>".format(
                strategy=html.escape(row["strategy_plugin"]),
                experiments=row["experiments"],
                best_pf=row["best_profit_factor"],
                median_pf=row["median_profit_factor"],
                pf_ratio=row["pf_gt_1_ratio"],
                experiment=html.escape(row["best_experiment_id"]),
            )
            for row in report["strategy_summary"]
        )
        best = report["best_experiment"]
        best_html = "<p>No completed pair-specific result found.</p>"
        if best:
            metrics = best["pair_metrics"]
            best_html = (
                f"<p><strong>{html.escape(best['strategy_plugin'])}</strong> "
                f"{html.escape(best['experiment_id'])}</p>"
                f"<ul><li>PF: {metrics['profit_factor']:.4f}</li>"
                f"<li>Expectancy: {metrics['expectancy']:.6f}</li>"
                f"<li>Drawdown: {metrics['max_drawdown_abs']:.4f}</li>"
                f"<li>Trades: {metrics['total_trades']}</li></ul>"
            )
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Single Asset Research</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #1f2933; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 16px; }}
    th, td {{ border: 1px solid #d9e2ec; padding: 8px; text-align: left; }}
    th {{ background: #f0f4f8; }}
    code, pre {{ background: #f7f9fb; padding: 8px; display: block; overflow: auto; }}
  </style>
</head>
<body>
  <h1>Single Asset Research</h1>
  <h2>Scope</h2>
  <ul>
    <li>Pair: {html.escape(str(report['scope']['pair']))}</li>
    <li>Matched experiments: {report['scope']['matched_pair_experiments']}</li>
    <li>Read-only analysis: {report['scope']['read_only_analysis']}</li>
  </ul>
  <h2>Best Experiment</h2>
  {best_html}
  <h2>Strategy Ranking</h2>
  <table>
    <thead><tr><th>Strategy</th><th>Experiments</th><th>Best PF</th><th>Median PF</th><th>PF &gt; 1</th><th>Best experiment</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <h2>Pipeline Status</h2>
  <pre>{html.escape(json.dumps(report['pipeline_status'], indent=2, sort_keys=True))}</pre>
  <h2>Recommendation</h2>
  <p>{html.escape(json.dumps(report['recommendations'], sort_keys=True))}</p>
</body>
</html>
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Single-asset research orchestration using existing lab infrastructure.",
    )
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    subparsers = parser.add_subparsers(dest="command")

    plan = subparsers.add_parser("plan", help="Create a paused single-asset campaign.")
    plan.add_argument("--pair", default=DEFAULT_PAIR)
    plan.add_argument("--strategy", required=True, dest="strategy_plugin")
    plan.add_argument("--count", type=int, default=100)
    plan.add_argument("--mode", choices=("random", "grid"), default="random")
    plan.add_argument("--session-id")
    plan.add_argument("--seed", type=int)

    run = subparsers.add_parser("run", help="Run pending experiments from one campaign.")
    run.add_argument("--session-id", required=True)
    run.add_argument("--limit", type=int)
    run.add_argument("--retries", type=int, default=0)
    run.add_argument("--timeout-seconds", type=int, default=DEFAULT_BACKTEST_TIMEOUT_SECONDS)
    run.add_argument("--execution-mode", choices=("auto", "docker", "freqtrade"), default="auto")

    analyze = subparsers.add_parser("analyze", help="Generate single-asset reports.")
    analyze.add_argument("--pair", default=DEFAULT_PAIR)
    analyze.add_argument("--session-id")
    analyze.add_argument("--strategy", dest="strategy_plugin")
    analyze.add_argument("--top", type=int, default=100)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    research = SingleAssetResearch(db_path=args.db_path, output_dir=args.output_dir)

    if args.command == "plan":
        result = research.plan(
            pair=args.pair,
            strategy_plugin=args.strategy_plugin,
            count=args.count,
            mode=args.mode,
            session_id=args.session_id,
            seed=args.seed,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
    elif args.command == "run":
        result = research.run(
            session_id=args.session_id,
            limit=args.limit,
            retries=args.retries,
            timeout_seconds=args.timeout_seconds,
            execution_mode=args.execution_mode,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
    elif args.command == "analyze":
        result = research.analyze(
            pair=args.pair,
            session_id=args.session_id,
            strategy_plugin=args.strategy_plugin,
            top=args.top,
        )
        print(json.dumps({key: str(path) for key, path in result.items()}, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
