from copy import deepcopy
import json
from pathlib import Path


DEFAULT_CHANNEL_CONFIG = {
    "defaults": {
        "base_stake": 10.0,
        "volume_mult": 1.5,
        "rsi_min": 45,
        "rsi_max": 58,
    },
    "martingale": {
        "multiplier": 1.5,
        "reset_after_losses": 5,
        "max_level": 4,
        "max_channel_stake": 60.0,
    },
    "monitoring": {
        "log_interval_seconds": 60,
    },
    "pairs": {
        "BTC/USDT": {
            "base_stake": 10.0,
            "volume_mult": 1.5,
            "rsi_min": 45,
            "rsi_max": 58,
        },
        "SOL/USDT": {
            "base_stake": 10.0,
            "volume_mult": 1.5,
            "rsi_min": 45,
            "rsi_max": 58,
        },
        "LTC/USDT": {
            "base_stake": 10.0,
            "volume_mult": 1.5,
            "rsi_min": 45,
            "rsi_max": 58,
        },
        "ADA/USDT": {
            "base_stake": 10.0,
            "volume_mult": 1.5,
            "rsi_min": 45,
            "rsi_max": 58,
        },
        "ETH/USDT": {
            "base_stake": 5.0,
            "volume_mult": 2.0,
            "rsi_min": 46,
            "rsi_max": 56,
        },
        "LINK/USDT": {
            "base_stake": 5.0,
            "volume_mult": 2.0,
            "rsi_min": 46,
            "rsi_max": 56,
        },
        "DOGE/USDT": {
            "base_stake": 5.0,
            "volume_mult": 2.0,
            "rsi_min": 46,
            "rsi_max": 56,
        },
        "XRP/USDT": {
            "base_stake": 3.0,
            "volume_mult": 2.2,
            "rsi_min": 47,
            "rsi_max": 55,
        },
    },
}


def _merge_config(defaults: dict, loaded: dict) -> dict:
    config = deepcopy(defaults)

    for section in ("defaults", "martingale", "monitoring"):
        config[section].update(loaded.get(section, {}))

    pairs = loaded.get("pairs", {})
    for pair, settings in pairs.items():
        pair_settings = deepcopy(config["defaults"])
        pair_settings.update(settings)
        config["pairs"][pair] = pair_settings

    return config


def load_channel_config(user_data_dir: Path | str | None = None) -> dict:
    base_dir = Path(user_data_dir) if user_data_dir else Path(__file__).resolve().parents[1]
    config_path = base_dir / "channels" / "config.json"

    if not config_path.is_file():
        return deepcopy(DEFAULT_CHANNEL_CONFIG)

    with config_path.open("r", encoding="utf-8") as config_file:
        loaded_config = json.load(config_file)

    return _merge_config(DEFAULT_CHANNEL_CONFIG, loaded_config)
