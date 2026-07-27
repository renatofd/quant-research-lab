"""
Automated backtesting laboratory.

This package is intentionally isolated from the operational strategy.  It can
prepare experiments, run Freqtrade backtests in sandboxed user_data folders,
parse official backtest outputs, persist metrics, and generate dashboards.

AutoResearch modules add resumable research sessions, search strategies,
parameter-space analysis, candidate selection, and comparison reports without
modifying operational strategy files.

Strategy Plugin modules let the laboratory compare independent strategy ideas
through a lab-only adapter strategy, while keeping operational strategies
unchanged.

Trend research modules provide a two-phase scientific workflow for
TrendStrategy: broad exploration, adaptive refinement, sensitivity analysis,
parameter interactions, convergence tracking, and HTML/JSON reports.
"""
