# PH4-A07 - Volatility Compression and Subsequent Risk Expansion

Preregistered: 2026-07-14, before any PH4-A07 outcome calculation.

## Economic Mechanism and Hypotheses

A temporary decline in realized volatility relative to an older local baseline
may represent delayed information incorporation or liquidity accumulation. If
compression is informative, stronger compression should predict greater future
return magnitude after controlling the older volatility regime.

H1-A07: a continuous, causally measured compression state positively and
replicably predicts future realized volatility and improves chronological
out-of-sample risk forecasts beyond the older-volatility baseline.

H0-A07: compression adds no stable forecast information, or any apparent effect
fails placebo, temporal, cross-asset, or concentration controls.

The outcome is risk magnitude only. There is no direction, breakout rule,
threshold, squeeze label, strategy, or trading decision.

## Frozen Design

- Existing Binance spot 5m Feather OHLCV only.
- Ten USDT pairs and five development-consumed frozen blocks.
- Fixed short window: preceding 24 returns (two hours).
- Fixed older baseline window: the 288 returns (24 hours) immediately before
  the short window. The two past windows do not overlap.
- Short RV and older RV are square roots of summed squared 5m log returns.
- Compression predictor:
  `log(older_RV / short_RV)`. Positive values mean recent volatility is below
  the older baseline.
- Outcome: log realized volatility over the following 24 returns.
- Events every 24 candles; no event crosses a block boundary.
- No percentile, threshold, alternate window, horizon, direction, or subgroup.

## Forward Evaluation

Each pair/block is split chronologically at the median eligible event.

- Baseline: future log RV on intercept and older log RV.
- Full model: baseline plus continuous compression.
- Models are calibrated on the first half and frozen for the second half.
- Primary incremental contrast: `1 - MSE_full/MSE_baseline`.
- Structural coefficient: compression beta in the controlled full model on
  evaluation data.

## Controls and Inference

- Circular-shift compression by half the evaluation series inside pair/block.
- Bootstrap 1,000 deterministic replicates by complete UTC days inside each
  pair/block; equal weight across pair/block units.
- Holm correction for positive compression beta, positive incremental MSE, and
  full model versus circular placebo.
- Per-pair diagnostics are a separate family.
- Audit hashes, coverage, gaps, duplicates, timezone, invalid OHLCV, warmup,
  samples, concentration, and no lookahead.

## Success Gate

`DEVELOPMENT VOLATILITY COMPRESSION SIGNAL DETECTED - PROSPECTIVE HOLDOUT REQUIRED`
only if every condition passes:

1. compression beta positive with bootstrap CI95 above zero;
2. incremental MSE improvement positive with CI95 above zero;
3. full model beats circular placebo with CI95 above zero after Holm;
4. improvement positive in at least four of five blocks;
5. improvement positive for at least seven of ten pairs;
6. no pair, block, or UTC day contributes more than 30% of positive loss
   reduction;
7. all primary effects survive Holm;
8. integrity and sample checks pass.

Success establishes development evidence for risk only and cannot authorize a
strategy or bot.

## Rejection and Inconclusive Gates

`VOLATILITY COMPRESSION HYPOTHESIS REJECTED IN PRIMARY SCOPE` if valid data fail
any central gate.

`INCONCLUSIVE VOLATILITY COMPRESSION AUDIT` only if integrity or sample size
prevents the primary test. No alternate windows, thresholds, transforms, or
subgroups may be tested after the result.

## Planned Artifacts

- `user_data/lab/ph4_a07_volatility_compression_report.md`
- `user_data/lab/ph4_a07_volatility_compression_report.json`
- `user_data/lab/ph4_a07_volatility_compression_report.html`
- `user_data/lab/ph4_a07_volatility_compression_matrix.csv`
- `user_data/lab/ph4_a07_volatility_compression_bootstrap.csv`

