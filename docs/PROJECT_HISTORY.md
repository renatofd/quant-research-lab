# Project History

## Origin

The project began as a Freqtrade customization focused on strategies,
indicators, Hyperopt, and deployment. That product-oriented scope changed when
Generalization, robustness, and falsification became the primary objectives.

## Phases 1 and 2: Infrastructure and Exploration

The first two phases produced an experiment manager, research database,
backtest runner, ranking system, parameter generation, plugins, reports,
robustness analysis, neighborhood analysis, and Walk-Forward Analysis.

Trend, Pullback, Mean Reversion, N-of-M, and Ensemble families were evaluated.
Promising in-sample peaks repeatedly failed out of sample.

## Phase 3: Causal Interventions

The research question changed from “Which parameter maximizes Profit Factor?”
to “Does this component add value?” Filters and components were neutralized one
at a time without retuning. The interventions did not produce reliable
Walk-Forward survival, and the operational families were closed.

## Phase 4: Economic Hypotheses

Technical indicators were no longer accepted as a starting point. The Research
Pipeline evaluated leadership, risk persistence, asymmetry, co-jumps,
dispersion, compression, illiquidity proxies, volume, and seasonality.
Statistical relationships existed, but none produced a robust net economic
edge.

## Discovery V2: Derivatives Data and Data Governance

Discovery V2 introduced formal acquisition and mechanical QA for derivatives
data. A uniform, officially documented provider gap led to an important
methodological distinction:

- `PASS`;
- `PASS WITH DOCUMENTED DATASET LIMITATION`;
- `FAIL`.

The policy did not relax data-quality gates for a favored Hypothesis. It created
a permanent, auditable classification for unavoidable external limitations.

## Discovery V3: Mechanism-First Research

Discovery V3 began with economic mechanisms and data availability:

- liquidation cascades;
- spot–perpetual divergence;
- extreme funding;
- cross-exchange leadership;
- liquidity, on-chain, ETF, options, order-flow, and relative-strength effects.

H01, H02, and H04 reached development analysis, but their gross effects were
below costs or failed replication. H03, H09, and H10 were stopped before
unnecessary implementation or compute. H05–H08 were blocked because causally
adequate data was unavailable.

Discovery V3 closed on 2026-07-24 with zero promoted Hypotheses.

## Version 1.0.0

The first public release presents the repository as a portfolio of scientific
method, research engineering, and disciplined decision-making. Its central
result is negative: the Evidence did not justify a bot.

Publishing that result preserves information that would otherwise be lost to
selection bias and repeated, unproductive experimentation.
