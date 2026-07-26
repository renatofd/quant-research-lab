"""Immutable scientific budget and paths for the Discovery Engine."""

from __future__ import annotations

from pathlib import Path


DISCOVERY_ROOT = Path(__file__).resolve().parent
USER_DATA_ROOT = DISCOVERY_ROOT.parent
LEGACY_LAB_ROOT = USER_DATA_ROOT / "lab"

HYPOTHESES_DIR = DISCOVERY_ROOT / "hypotheses"
ENGINES_DIR = DISCOVERY_ROOT / "engines"
PROTOCOLS_DIR = DISCOVERY_ROOT / "protocols"
REPORTS_DIR = DISCOVERY_ROOT / "reports"
REGISTRY_DIR = DISCOVERY_ROOT / "registry"
PLUGINS_DIR = DISCOVERY_ROOT / "plugins"
DATASETS_DIR = DISCOVERY_ROOT / "datasets"
KNOWLEDGE_DIR = DISCOVERY_ROOT / "knowledge"

DATABASE_PATH = KNOWLEDGE_DIR / "discovery.sqlite"
HYPOTHESES_FILE = HYPOTHESES_DIR / "hypotheses.json"
SOURCE_MANIFEST_FILE = KNOWLEDGE_DIR / "source_manifest.json"
DATA_MANIFEST_FILE = DATASETS_DIR / "data_manifest.json"

MAX_HYPOTHESES = 30
MAX_EXPLORATORY_EXPERIMENTS_PER_HYPOTHESIS = 500
MIN_SUCCESS_PROBABILITY = 0.05

ADVANCED_GATES = (
    "positive_net_advantage",
    "robustness",
    "walk_forward",
    "independent_holdout",
)

LEGACY_SOURCE_ARTIFACTS = (
    "ph3_gate01_trend_decision.json",
    "ph3_gate02_family_portfolio_decision.json",
    "ph3_rst_gate01_final_raw_signal_gate.json",
    "btc_leadership_report.json",
    "ph4_a02_volatility_persistence_report.json",
    "ph4_a03_signed_volatility_report.json",
    "ph4_a04_cojump_propagation_report.json",
    "ph4_a05_dispersion_risk_report.json",
    "ph4_a07_volatility_compression_report.json",
    "market_eligibility_final_report.json",
)

