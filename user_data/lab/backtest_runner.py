from __future__ import annotations

import json
import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DEFAULT_BACKTEST_TIMEOUT_SECONDS = 900
DEFAULT_DOCKER_CHECK_TIMEOUT_SECONDS = 5


class BacktestRunner:
    def __init__(
        self,
        *,
        project_root: Path | str | None = None,
        docker_service: str = "freqtrade",
        strategy_name: str = "EmaRsiVolumeStrategy",
        execution_mode: str = "auto",
    ) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[2])
        self.user_data_dir = self.project_root / "user_data"
        self.docker_service = docker_service
        self.strategy_name = strategy_name
        self.execution_mode = self._resolve_execution_mode(execution_mode)

    def prepare_sandbox(
        self,
        experiment_id: str,
        parameters: dict[str, Any],
    ) -> Path:
        run_dir = self.user_data_dir / "lab" / "runs" / experiment_id
        sandbox_user_data = run_dir / "user_data"
        if sandbox_user_data.exists():
            shutil.rmtree(sandbox_user_data)

        sandbox_user_data.mkdir(parents=True, exist_ok=True)
        self._copy_required_user_data(sandbox_user_data)
        if self._is_plugin_experiment(parameters):
            self._write_lab_plugin_config(sandbox_user_data, parameters)
        else:
            self._write_strategy_params(sandbox_user_data, parameters)
        self._write_channel_config(sandbox_user_data, parameters)
        self._write_backtest_config(sandbox_user_data, experiment_id)

        return sandbox_user_data

    def run(
        self,
        experiment_id: str,
        parameters: dict[str, Any],
        *,
        retries: int = 0,
        timeout_seconds: int = DEFAULT_BACKTEST_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        start = time.perf_counter()
        run_dir = self.user_data_dir / "lab" / "runs" / experiment_id
        run_dir.mkdir(parents=True, exist_ok=True)
        log_path = run_dir / "backtest.log"
        sandbox_user_data: Path | None = None
        attempts = 0
        last_result: subprocess.CompletedProcess[str] | None = None
        error_message = ""
        timings: dict[str, Any] = {}

        if timeout_seconds is None or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be a positive integer.")

        try:
            docker_check_start = time.perf_counter()
            docker_check = self._check_docker()
            timings["docker_check_seconds"] = time.perf_counter() - docker_check_start
            if not docker_check["ok"]:
                runtime_seconds = time.perf_counter() - start
                error_message = docker_check["error"]
                log_path.write_text(
                    self._format_failure_log(
                        command=docker_check["command"],
                        attempt=0,
                        runtime_seconds=runtime_seconds,
                        error_type="DockerUnavailable",
                        error_message=error_message,
                        stdout=docker_check.get("stdout", ""),
                        stderr=docker_check.get("stderr", ""),
                        timings=timings,
                    ),
                    encoding="utf-8",
                )
                return self._failure_result(
                    parameters=parameters,
                    log_path=log_path,
                    runtime_seconds=runtime_seconds,
                    error_message=error_message,
                    sandbox_user_data=run_dir / "user_data",
                )

            sandbox_start = time.perf_counter()
            sandbox_user_data = self.prepare_sandbox(experiment_id, parameters)
            timings["sandbox_prepare_seconds"] = time.perf_counter() - sandbox_start

            while attempts <= retries:
                attempts += 1
                command = self._command(experiment_id, parameters)
                try:
                    backtest_start = time.perf_counter()
                    last_result = subprocess.run(
                        command,
                        cwd=self.project_root,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        capture_output=True,
                        timeout=timeout_seconds,
                    )
                    timings["backtest_seconds"] = time.perf_counter() - backtest_start
                except subprocess.TimeoutExpired as exc:
                    runtime_seconds = time.perf_counter() - start
                    timings["backtest_seconds"] = time.perf_counter() - backtest_start
                    timings["timeout_phase"] = "backtest"
                    error_message = (
                        f"Backtest timed out after {timeout_seconds} seconds."
                    )
                    self._cleanup_timeout_processes(experiment_id, timings)
                    cleanup_start = time.perf_counter()
                    if sandbox_user_data is not None:
                        self._cleanup_timeout_sandbox(sandbox_user_data)
                        sandbox_user_data = None
                    timings["timeout_sandbox_cleanup_seconds"] = (
                        time.perf_counter() - cleanup_start
                    )
                    log_path.write_text(
                        self._format_failure_log(
                            command=command,
                            attempt=attempts,
                            runtime_seconds=runtime_seconds,
                            error_type="TimeoutExpired",
                            error_message=error_message,
                            stdout=self._decode_output(exc.stdout),
                            stderr=self._decode_output(exc.stderr),
                            timings=timings,
                        ),
                        encoding="utf-8",
                    )
                    return self._failure_result(
                        parameters=parameters,
                        log_path=log_path,
                        runtime_seconds=runtime_seconds,
                        error_message=error_message,
                        sandbox_user_data=run_dir / "user_data",
                    )
                except (OSError, subprocess.SubprocessError) as exc:
                    runtime_seconds = time.perf_counter() - start
                    error_message = repr(exc)
                    timings.setdefault(
                        "backtest_seconds",
                        time.perf_counter() - backtest_start,
                    )
                    log_path.write_text(
                        self._format_failure_log(
                            command=command,
                            attempt=attempts,
                            runtime_seconds=runtime_seconds,
                            error_type=exc.__class__.__name__,
                            error_message=error_message,
                            timings=timings,
                        ),
                        encoding="utf-8",
                    )
                    return self._failure_result(
                        parameters=parameters,
                        log_path=log_path,
                        runtime_seconds=runtime_seconds,
                        error_message=error_message,
                        sandbox_user_data=sandbox_user_data,
                    )

                log_path.write_text(
                    self._format_log(command, last_result, attempts, timings=timings),
                    encoding="utf-8",
                )

                if last_result.returncode == 0:
                    break
        except Exception as exc:
            runtime_seconds = time.perf_counter() - start
            error_message = repr(exc)
            log_path.write_text(
                self._format_failure_log(
                    command=[],
                    attempt=attempts,
                    runtime_seconds=runtime_seconds,
                    error_type=exc.__class__.__name__,
                    error_message=error_message,
                    timings=timings,
                ),
                encoding="utf-8",
            )
            return self._failure_result(
                parameters=parameters,
                log_path=log_path,
                runtime_seconds=runtime_seconds,
                error_message=error_message,
                sandbox_user_data=sandbox_user_data or run_dir / "user_data",
            )
        finally:
            if sandbox_user_data is not None:
                try:
                    self._cleanup_sandbox_artifacts(sandbox_user_data)
                except Exception as exc:
                    with log_path.open("a", encoding="utf-8") as log_file:
                        log_file.write(
                            "\n\nCLEANUP ERROR:\n"
                            f"{exc.__class__.__name__}: {exc!r}\n"
                        )

        runtime_seconds = time.perf_counter() - start
        backtest_results_dir = (sandbox_user_data or run_dir / "user_data") / "backtest_results"

        return {
            "ok": bool(last_result and last_result.returncode == 0),
            "returncode": last_result.returncode if last_result else None,
            "runtime_seconds": runtime_seconds,
            "log_path": log_path,
            "backtest_results_dir": backtest_results_dir,
            "sandbox_user_data": sandbox_user_data,
            "stderr": last_result.stderr if last_result else "",
            "stdout": last_result.stdout if last_result else "",
            "strategy_name": self._strategy_class_for(parameters),
        }

    def _copy_required_user_data(self, sandbox_user_data: Path) -> None:
        for directory in ("strategies", "indicators", "channels", "evaluation", "reports"):
            source = self.user_data_dir / directory
            if source.exists():
                shutil.copytree(source, sandbox_user_data / directory)

        self._copy_plugin_infrastructure(sandbox_user_data)
        (sandbox_user_data / "backtest_results").mkdir(parents=True, exist_ok=True)

    def _copy_plugin_infrastructure(self, sandbox_user_data: Path) -> None:
        plugin_source = self.user_data_dir / "lab" / "strategy_plugins"
        adapter_source = self.user_data_dir / "lab" / "plugin_strategy_adapter.py"

        if plugin_source.exists():
            shutil.copytree(plugin_source, sandbox_user_data / "strategy_plugins")
        if adapter_source.exists():
            shutil.copy2(
                adapter_source,
                sandbox_user_data / "strategies" / "LabPluginStrategy.py",
            )

    def _write_strategy_params(
        self,
        sandbox_user_data: Path,
        parameters: dict[str, Any],
    ) -> None:
        strategy_params = {
            "strategy_name": self.strategy_name,
            "params": {
                "buy": {
                    "buy_ema_fast": parameters["buy_ema_fast"],
                    "buy_ema_slow": parameters["buy_ema_slow"],
                    "buy_ema_trend": parameters["buy_ema_trend"],
                    "buy_rsi_min": parameters["buy_rsi_min"],
                    "buy_rsi_max": parameters["buy_rsi_max"],
                    "buy_volume_mult": parameters["buy_volume_mult"],
                },
                "roi": {"0": parameters["roi"]},
                "stoploss": {"stoploss": parameters["stoploss"]},
            },
            "ft_stratparam_v": 1,
            "export_time": datetime.now(UTC).isoformat(),
        }
        params_path = sandbox_user_data / "strategies" / f"{self.strategy_name}.json"
        params_path.write_text(json.dumps(strategy_params, indent=2), encoding="utf-8")

    def _write_lab_plugin_config(
        self,
        sandbox_user_data: Path,
        parameters: dict[str, Any],
    ) -> None:
        plugin_config = {
            "strategy_plugin": parameters["strategy_plugin"],
            "parameters": parameters.get("plugin_parameters", parameters),
            "export_time": datetime.now(UTC).isoformat(),
        }
        config_path = sandbox_user_data / "lab_plugin_config.json"
        config_path.write_text(json.dumps(plugin_config, indent=2), encoding="utf-8")

    def _write_channel_config(
        self,
        sandbox_user_data: Path,
        parameters: dict[str, Any],
    ) -> None:
        source_path = self.user_data_dir / "channels" / "config.json"
        config = json.loads(source_path.read_text(encoding="utf-8"))
        martingale = config.setdefault("martingale", {})
        if "martingale_multiplier" in parameters:
            martingale["multiplier"] = parameters["martingale_multiplier"]
        if "max_martingale_level" in parameters:
            martingale["max_level"] = parameters["max_martingale_level"]
        if "reset_after_losses" in parameters:
            martingale["reset_after_losses"] = parameters["reset_after_losses"]

        target_path = sandbox_user_data / "channels" / "config.json"
        target_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    def _write_backtest_config(self, sandbox_user_data: Path, experiment_id: str) -> None:
        source_path = self.user_data_dir / "config.json"
        config = json.loads(source_path.read_text(encoding="utf-8"))
        container_userdir = f"/freqtrade/user_data/lab/runs/{experiment_id}/user_data"
        config["dry_run"] = True
        config["datadir"] = "/freqtrade/user_data/data/binance"
        config["exportdirectory"] = f"{container_userdir}/backtest_results"
        config["export"] = "trades"

        target_path = sandbox_user_data / "config.json"
        target_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    def _command(
        self,
        experiment_id: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[str]:
        container_userdir = f"/freqtrade/user_data/lab/runs/{experiment_id}/user_data"
        strategy_class = self._strategy_class_for(parameters or {})
        if self.execution_mode == "freqtrade":
            return [
                "freqtrade",
                "backtesting",
                "--userdir",
                container_userdir,
                "--config",
                f"{container_userdir}/config.json",
                "--strategy",
                strategy_class,
                "--datadir",
                "/freqtrade/user_data/data/binance",
                "--cache",
                "none",
            ]

        return [
            "docker",
            "compose",
            "run",
            "--rm",
            "--name",
            self._container_name(experiment_id),
            self.docker_service,
            "backtesting",
            "--userdir",
            container_userdir,
            "--config",
            f"{container_userdir}/config.json",
            "--strategy",
            strategy_class,
            "--datadir",
            "/freqtrade/user_data/data/binance",
            "--cache",
            "none",
        ]

    def _is_plugin_experiment(self, parameters: dict[str, Any]) -> bool:
        return bool(parameters.get("strategy_plugin"))

    def _strategy_class_for(self, parameters: dict[str, Any]) -> str:
        return "LabPluginStrategy" if self._is_plugin_experiment(parameters) else self.strategy_name

    def _container_name(self, experiment_id: str) -> str:
        return f"lab-{experiment_id}"

    def _resolve_execution_mode(self, execution_mode: str) -> str:
        if execution_mode != "auto":
            if execution_mode not in {"docker", "freqtrade"}:
                raise ValueError("execution_mode must be auto, docker, or freqtrade.")
            return execution_mode

        return "freqtrade" if Path("/freqtrade/user_data").exists() else "docker"

    def _format_log(
        self,
        command: list[str],
        result: subprocess.CompletedProcess[str],
        attempt: int,
        *,
        timings: dict[str, Any] | None = None,
    ) -> str:
        parts = [
            f"attempt={attempt}",
            "command=" + " ".join(self._safe_text(item) for item in command),
            f"returncode={result.returncode}",
            "",
            "STDOUT:",
            result.stdout,
            "",
            "STDERR:",
            result.stderr,
            *self._format_timings(timings),
        ]
        return "\n".join(self._safe_text(part) for part in parts)

    def _format_failure_log(
        self,
        *,
        command: list[str],
        attempt: int,
        runtime_seconds: float,
        error_type: str,
        error_message: str,
        stdout: str = "",
        stderr: str = "",
        timings: dict[str, Any] | None = None,
    ) -> str:
        parts = [
            f"attempt={attempt}",
            "command=" + " ".join(self._safe_text(item) for item in command),
            f"runtime_seconds={runtime_seconds:.3f}",
            f"error_type={error_type}",
            f"error={error_message}",
            "",
            "STDOUT:",
            stdout,
            "",
            "STDERR:",
            stderr,
            *self._format_timings(timings),
        ]
        return "\n".join(self._safe_text(part) for part in parts)

    def _format_timings(self, timings: dict[str, Any] | None) -> list[str]:
        if not timings:
            return []

        lines = ["", "TIMINGS:"]
        for key, value in timings.items():
            if isinstance(value, (int, float)):
                lines.append(f"{key}={value:.3f}")
            else:
                lines.append(f"{key}={self._safe_text(value)}")
        return lines

    def _safe_text(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value)

    def _failure_result(
        self,
        *,
        parameters: dict[str, Any],
        log_path: Path,
        runtime_seconds: float,
        error_message: str,
        sandbox_user_data: Path,
    ) -> dict[str, Any]:
        return {
            "ok": False,
            "returncode": None,
            "runtime_seconds": runtime_seconds,
            "log_path": log_path,
            "backtest_results_dir": sandbox_user_data / "backtest_results",
            "sandbox_user_data": sandbox_user_data,
            "stderr": error_message,
            "stdout": "",
            "strategy_name": self._strategy_class_for(parameters),
        }

    def _check_docker(self) -> dict[str, Any]:
        if self.execution_mode == "freqtrade":
            return {"ok": True, "command": [], "stdout": "", "stderr": ""}

        command = ["docker", "ps", "--format", "{{.Names}}"]
        try:
            result = subprocess.run(
                command,
                cwd=self.project_root,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=DEFAULT_DOCKER_CHECK_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            return {
                "ok": False,
                "command": command,
                "stdout": self._decode_output(exc.stdout),
                "stderr": self._decode_output(exc.stderr),
                "error": (
                    "Docker did not respond within "
                    f"{DEFAULT_DOCKER_CHECK_TIMEOUT_SECONDS} seconds."
                ),
            }
        except (OSError, subprocess.SubprocessError) as exc:
            return {
                "ok": False,
                "command": command,
                "stdout": "",
                "stderr": repr(exc),
                "error": repr(exc),
            }

        return {
            "ok": result.returncode == 0,
            "command": command,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "error": result.stderr or f"Docker returned {result.returncode}.",
        }

    def _decode_output(self, output: str | bytes | None) -> str:
        return self._safe_text(output)

    def _cleanup_timeout_sandbox(self, sandbox_user_data: Path) -> None:
        if sandbox_user_data.exists():
            shutil.rmtree(sandbox_user_data)

    def _cleanup_timeout_processes(
        self,
        experiment_id: str,
        timings: dict[str, Any],
    ) -> None:
        if self.execution_mode != "docker":
            return

        cleanup_start = time.perf_counter()
        command = ["docker", "rm", "-f", self._container_name(experiment_id)]
        try:
            result = subprocess.run(
                command,
                cwd=self.project_root,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=15,
            )
        except subprocess.TimeoutExpired as exc:
            timings["timeout_process_cleanup_seconds"] = (
                time.perf_counter() - cleanup_start
            )
            timings["timeout_process_cleanup_error"] = (
                "Docker container cleanup timed out: "
                f"{self._decode_output(exc.stderr)}"
            )
            return
        except (OSError, subprocess.SubprocessError) as exc:
            timings["timeout_process_cleanup_seconds"] = (
                time.perf_counter() - cleanup_start
            )
            timings["timeout_process_cleanup_error"] = repr(exc)
            return

        timings["timeout_process_cleanup_seconds"] = (
            time.perf_counter() - cleanup_start
        )
        if result.returncode != 0:
            timings["timeout_process_cleanup_error"] = (
                result.stderr or f"Docker rm returned {result.returncode}."
            )

    def _cleanup_sandbox_artifacts(self, sandbox_user_data: Path) -> None:
        reports_dir = sandbox_user_data / "reports"
        generated_dirs = [
            reports_dir / "research_features",
            reports_dir / "__pycache__",
            sandbox_user_data / "strategies" / "__pycache__",
            sandbox_user_data / "indicators" / "__pycache__",
            sandbox_user_data / "channels" / "__pycache__",
            sandbox_user_data / "evaluation" / "__pycache__",
            sandbox_user_data / "strategy_plugins" / "__pycache__",
        ]
        for directory in generated_dirs:
            if directory.exists():
                shutil.rmtree(directory)

        for pattern in (
            "framework_report_*.json",
            "framework_report_*.html",
            "framework_report_latest.json",
            "framework_report_latest.html",
            "research_trades_*.csv",
            "research_trades_latest.csv",
        ):
            for path in reports_dir.glob(pattern):
                if path.is_file():
                    path.unlink()
