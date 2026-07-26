from __future__ import annotations

import argparse
import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any

try:
    from .backtest_runner import DEFAULT_BACKTEST_TIMEOUT_SECONDS, BacktestRunner
    from .experiment_database import ExperimentDatabase
    from .parameter_generator import ParameterGenerator
    from .ranking_engine import RankingEngine
    from .result_parser import ResultParser
except ImportError:
    from backtest_runner import DEFAULT_BACKTEST_TIMEOUT_SECONDS, BacktestRunner
    from experiment_database import ExperimentDatabase
    from parameter_generator import ParameterGenerator
    from ranking_engine import RankingEngine
    from result_parser import ResultParser


class ExperimentManager:
    def __init__(
        self,
        *,
        database: ExperimentDatabase | None = None,
        generator: ParameterGenerator | None = None,
        runner: BacktestRunner | None = None,
        parser: ResultParser | None = None,
        ranking: RankingEngine | None = None,
        strategy_name: str = "EmaRsiVolumeStrategy",
        execution_mode: str = "auto",
    ) -> None:
        self.database = database or ExperimentDatabase()
        self.generator = generator or ParameterGenerator()
        self.runner = runner or BacktestRunner(
            strategy_name=strategy_name,
            execution_mode=execution_mode,
        )
        self.parser = parser or ResultParser()
        self.ranking = ranking or RankingEngine(self.database)
        self.strategy_name = strategy_name
        self.project_root = Path(__file__).resolve().parents[2]

    def generate_experiments(
        self,
        *,
        count: int,
        mode: str = "random",
        experiment_kind: str = "parameters",
    ) -> list[str]:
        if experiment_kind == "plugin":
            parameter_sets = (
                self.generator.generate_plugin_grid(limit=count)
                if mode == "grid"
                else self.generator.generate_plugin_random(count)
            )
            database_strategy_name = "LabPluginStrategy"
        elif experiment_kind == "parameters":
            parameter_sets = (
                self.generator.generate_grid(limit=count)
                if mode == "grid"
                else self.generator.generate_random(count)
            )
            database_strategy_name = self.strategy_name
        else:
            raise ValueError("experiment_kind must be parameters or plugin.")

        experiment_ids = []
        strategy_hash = self.strategy_hash()

        for parameters in parameter_sets:
            experiment_id = self._experiment_id(parameters)
            self.database.create_experiment(
                experiment_id=experiment_id,
                strategy_name=database_strategy_name,
                strategy_hash=strategy_hash,
                parameters=parameters,
            )
            experiment_ids.append(experiment_id)

        return experiment_ids

    def run_pending(
        self,
        *,
        limit: int | None = None,
        retries: int = 0,
        timeout_seconds: int = DEFAULT_BACKTEST_TIMEOUT_SECONDS,
    ) -> None:
        self._mark_interrupted_experiments()

        for experiment in self.database.pending(limit=limit):
            try:
                self.run_experiment(
                    experiment["id"],
                    retries=retries,
                    timeout_seconds=timeout_seconds,
                )
            except Exception as exc:
                self.database.update_status(
                    experiment["id"],
                    "error",
                    error=f"Experiment manager failure: {exc!r}",
                )
                continue

    def run_experiment(
        self,
        experiment_id: str,
        *,
        retries: int = 0,
        timeout_seconds: int = DEFAULT_BACKTEST_TIMEOUT_SECONDS,
    ) -> None:
        experiment = self.database.get_experiment(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found.")

        result: dict[str, Any] | None = None
        manager_timings: dict[str, float] = {}
        self.database.update_status(experiment_id, "running")
        try:
            result = self.runner.run(
                experiment_id,
                experiment["parameters"],
                retries=retries,
                timeout_seconds=timeout_seconds,
            )

            if not result["ok"]:
                sqlite_start = time.perf_counter()
                self.database.update_status(
                    experiment_id,
                    "error",
                    error=result.get("stderr") or "Backtest failed.",
                    log_path=result["log_path"],
                    runtime_seconds=result["runtime_seconds"],
                )
                manager_timings["sqlite_status_seconds"] = (
                    time.perf_counter() - sqlite_start
                )
                self._append_manager_timings(result.get("log_path"), manager_timings)
                return

            parser_start = time.perf_counter()
            metrics = self.parser.parse_latest(
                result["backtest_results_dir"],
                strategy_name=result.get("strategy_name", self.strategy_name),
            )
            manager_timings["parser_seconds"] = time.perf_counter() - parser_start

            score_start = time.perf_counter()
            score = self.ranking.composite_score(metrics)
            manager_timings["score_seconds"] = time.perf_counter() - score_start

            sqlite_start = time.perf_counter()
            self.database.save_metrics(
                experiment_id,
                metrics,
                score=score,
                runtime_seconds=result["runtime_seconds"],
                result_path=metrics.get("result_path"),
                log_path=result["log_path"],
            )
            manager_timings["sqlite_save_seconds"] = (
                time.perf_counter() - sqlite_start
            )
            self._append_manager_timings(result.get("log_path"), manager_timings)
        except Exception as exc:
            sqlite_start = time.perf_counter()
            self.database.update_status(
                experiment_id,
                "error",
                error=f"{exc.__class__.__name__}: {exc!r}",
                log_path=result.get("log_path") if result else None,
                runtime_seconds=result.get("runtime_seconds") if result else None,
            )
            manager_timings["sqlite_status_seconds"] = (
                time.perf_counter() - sqlite_start
            )
            self._append_manager_timings(
                result.get("log_path") if result else None,
                manager_timings,
            )
            return
        finally:
            current = self.database.get_experiment(experiment_id)
            if current and current["status"] == "running":
                sqlite_start = time.perf_counter()
                self.database.update_status(
                    experiment_id,
                    "error",
                    error="Interrupted",
                    log_path=result.get("log_path") if result else None,
                    runtime_seconds=result.get("runtime_seconds") if result else None,
                )
                manager_timings["sqlite_interrupted_seconds"] = (
                    time.perf_counter() - sqlite_start
                )
                self._append_manager_timings(
                    result.get("log_path") if result else None,
                    manager_timings,
                )

    def reproduce_command(self, experiment_id: str) -> list[str]:
        experiment = self.database.get_experiment(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found.")
        self.runner.prepare_sandbox(experiment_id, experiment["parameters"])
        return self.runner._command(experiment_id, experiment["parameters"])

    def strategy_hash(self) -> str:
        user_data = self.project_root / "user_data"
        strategy_files = [
            user_data / "strategies" / f"{self.strategy_name}.py",
            user_data / "strategies" / "BaseStrategy.py",
        ]
        dependency_files = [
            *sorted((user_data / "indicators").glob("*.py")),
            *sorted((user_data / "channels").glob("*.py")),
            user_data / "lab" / "plugin_strategy_adapter.py",
            *sorted((user_data / "lab" / "strategy_plugins").glob("*.py")),
        ]

        digest = hashlib.sha256()
        for path in [*strategy_files, *dependency_files]:
            if path.is_file():
                digest.update(str(path.relative_to(self.project_root)).encode("utf-8"))
                digest.update(path.read_bytes())
        return digest.hexdigest()

    def _experiment_id(self, parameters: dict[str, Any]) -> str:
        payload = json.dumps(parameters, sort_keys=True)
        prefix = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]
        return f"exp-{prefix}-{uuid.uuid4().hex[:8]}"

    def _mark_interrupted_experiments(self) -> None:
        for experiment in self.database.list_experiments(status="running"):
            self.database.update_status(
                experiment["id"],
                "error",
                error="Interrupted",
                log_path=experiment.get("log_path"),
                runtime_seconds=experiment.get("runtime_seconds"),
            )

    def _append_manager_timings(
        self,
        log_path: Path | str | None,
        timings: dict[str, float],
    ) -> None:
        if not log_path or not timings:
            return

        path = Path(log_path)
        lines = ["", "MANAGER_TIMINGS:"]
        lines.extend(f"{key}={value:.3f}" for key, value in timings.items())
        try:
            with path.open("a", encoding="utf-8") as log_file:
                log_file.write("\n".join(lines))
                log_file.write("\n")
        except OSError:
            return


def main() -> None:
    parser = argparse.ArgumentParser(description="Automated Freqtrade experiment manager.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate")
    generate.add_argument("--count", type=int, required=True)
    generate.add_argument("--mode", choices=("random", "grid"), default="random")
    generate.add_argument(
        "--experiment-kind",
        choices=("parameters", "plugin"),
        default="parameters",
    )

    run = subparsers.add_parser("run-pending")
    run.add_argument("--limit", type=int)
    run.add_argument("--retries", type=int, default=0)
    run.add_argument("--timeout-seconds", type=int, default=DEFAULT_BACKTEST_TIMEOUT_SECONDS)
    run.add_argument("--execution-mode", choices=("auto", "docker", "freqtrade"), default="auto")

    reproduce = subparsers.add_parser("reproduce")
    reproduce.add_argument("experiment_id")

    args = parser.parse_args()
    manager_kwargs = {}
    if getattr(args, "execution_mode", None):
        manager_kwargs["execution_mode"] = args.execution_mode
    manager = ExperimentManager(**manager_kwargs)

    if args.command == "generate":
        ids = manager.generate_experiments(
            count=args.count,
            mode=args.mode,
            experiment_kind=args.experiment_kind,
        )
        print("\n".join(ids))
    elif args.command == "run-pending":
        manager.run_pending(
            limit=args.limit,
            retries=args.retries,
            timeout_seconds=args.timeout_seconds,
        )
    elif args.command == "reproduce":
        print(" ".join(manager.reproduce_command(args.experiment_id)))


if __name__ == "__main__":
    main()
