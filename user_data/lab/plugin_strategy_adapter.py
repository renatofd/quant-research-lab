from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from pandas import DataFrame

from freqtrade.strategy import IStrategy

USER_DATA_DIR = Path(__file__).resolve().parents[1]
if str(USER_DATA_DIR) not in sys.path:
    sys.path.append(str(USER_DATA_DIR))

from strategy_plugins import create_plugin


class LabPluginStrategy(IStrategy):
    """Freqtrade adapter used only by the laboratory plugin system."""

    INTERFACE_VERSION = 3

    timeframe = "5m"
    can_short = False
    startup_candle_count = 220
    process_only_new_candles = True

    minimal_roi = {"0": 0.01}
    stoploss = -0.05

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    position_adjustment_enable = False
    max_entry_position_adjustment = 0

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        lab_config = self._load_lab_plugin_config(config)
        self.plugin_name = lab_config["strategy_plugin"]
        self.plugin_parameters = lab_config.get("parameters", {})
        self.plugin = create_plugin(self.plugin_name, self.plugin_parameters)

        roi = self.plugin_parameters.get("roi")
        stoploss = self.plugin_parameters.get("stoploss")
        if roi is not None:
            self.minimal_roi = {"0": float(roi)}
        if stoploss is not None:
            self.stoploss = float(stoploss)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return self.plugin.populate_entry(dataframe, metadata, self.plugin_parameters)

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return self.plugin.populate_exit(dataframe, metadata, self.plugin_parameters)

    def _load_lab_plugin_config(self, config: dict) -> dict[str, Any]:
        user_data_dir = Path(config.get("user_data_dir", "/freqtrade/user_data"))
        config_path = user_data_dir / "lab_plugin_config.json"
        if not config_path.is_file():
            raise FileNotFoundError(f"Lab plugin config not found: {config_path}")
        return json.loads(config_path.read_text(encoding="utf-8"))
