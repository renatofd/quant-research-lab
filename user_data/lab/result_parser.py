from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from zipfile import ZipFile


class ResultParser:
    def parse_latest(
        self,
        backtest_results_dir: Path | str,
        *,
        strategy_name: str | None = None,
    ) -> dict[str, Any]:
        backtest_results_dir = Path(backtest_results_dir)
        latest_path = backtest_results_dir / ".last_result.json"

        if latest_path.is_file():
            latest = json.loads(latest_path.read_text(encoding="utf-8"))
            result_path = backtest_results_dir / latest["latest_backtest"]
        else:
            result_path = max(
                backtest_results_dir.glob("*.zip"),
                key=lambda path: path.stat().st_mtime,
            )

        return self.parse(result_path, strategy_name=strategy_name)

    def parse(
        self,
        result_path: Path | str,
        *,
        strategy_name: str | None = None,
    ) -> dict[str, Any]:
        result_path = Path(result_path)
        result = self._load_result_json(result_path)
        strategy_result = self._strategy_result(result, strategy_name)
        metrics = self._extract_metrics(strategy_result)
        metrics["result_path"] = str(result_path)
        return metrics

    def _load_result_json(self, result_path: Path) -> dict[str, Any]:
        if result_path.suffix == ".json":
            return json.loads(result_path.read_text(encoding="utf-8"))

        with ZipFile(result_path) as archive:
            result_names = [
                name
                for name in archive.namelist()
                if name.endswith(".json") and not name.endswith("_config.json")
            ]
            for name in result_names:
                parsed = json.loads(archive.read(name))
                if isinstance(parsed, dict) and "strategy" in parsed:
                    return parsed

        raise FileNotFoundError(f"No official backtest JSON found in {result_path}.")

    def _strategy_result(
        self,
        result: dict[str, Any],
        strategy_name: str | None,
    ) -> dict[str, Any]:
        strategies = result.get("strategy", {})
        if strategy_name and strategy_name in strategies:
            return strategies[strategy_name]
        if len(strategies) == 1:
            return next(iter(strategies.values()))

        available = ", ".join(strategies.keys())
        raise ValueError(f"Strategy is ambiguous. Available strategies: {available}")

    def _extract_metrics(self, strategy: dict[str, Any]) -> dict[str, Any]:
        trades = strategy.get("trades", [])
        pair_results = {
            row.get("key", row.get("pair", "UNKNOWN")): row
            for row in strategy.get("results_per_pair", [])
        }

        return {
            "profit_total_abs": strategy.get("profit_total_abs"),
            "profit_total": strategy.get("profit_total"),
            "total_trades": strategy.get("total_trades"),
            "winrate": strategy.get("winrate"),
            "profit_factor": strategy.get("profit_factor"),
            "expectancy": strategy.get("expectancy"),
            "sharpe": strategy.get("sharpe"),
            "sortino": strategy.get("sortino"),
            "calmar": strategy.get("calmar"),
            "max_drawdown_abs": strategy.get("max_drawdown_abs"),
            "max_relative_drawdown": strategy.get("max_relative_drawdown"),
            "holding_avg": strategy.get("holding_avg"),
            "holding_avg_s": strategy.get("holding_avg_s"),
            "best_trade": self._best_trade(trades),
            "worst_trade": self._worst_trade(trades),
            "profit_by_pair": pair_results,
            "backtest_start": strategy.get("backtest_start"),
            "backtest_end": strategy.get("backtest_end"),
        }

    def _best_trade(self, trades: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not trades:
            return None
        return max(trades, key=lambda trade: trade.get("profit_abs", 0.0) or 0.0)

    def _worst_trade(self, trades: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not trades:
            return None
        return min(trades, key=lambda trade: trade.get("profit_abs", 0.0) or 0.0)
