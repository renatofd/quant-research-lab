# PH4-A02 - Volatility Persistence as Risk Forecasting

Preregistered: 2026-07-14, before any PH4-A02 outcome calculation.

## Mandate

PH4-A02 tests whether past realized volatility predicts future return magnitude.
It is a risk-forecasting hypothesis, not a directional return hypothesis, trading
rule, eligibility filter, position-sizing rule, or strategy.

## Economic Hypothesis

Volatility clustering can arise because information, leverage adjustment, and
liquidity conditions dissipate gradually. If present, a high-risk state should
carry information about the magnitude of subsequent returns even when direction
is ignored.

H1-A02: realized volatility over the preceding two hours positively and
replicably predicts realized volatility over the following two hours, and a
fixed linear forecast improves out-of-sample loss versus a calibration-period
unconditional-volatility baseline.

H0-A02: past realized volatility provides no stable incremental risk forecast;
the coefficient is non-positive or uncertain, forecast loss does not improve,
or the result fails temporal/cross-asset controls.

## Frozen Data and Sampling

- Exchange/data: existing Binance spot Feather OHLCV only.
- Timeframe: 5 minutes.
- Universe: BTC, ETH, SOL, BNB, XRP, ADA, DOGE, LINK, AVAX, LTC versus USDT.
- Blocks: the five non-overlapping windows in
  `user_data/lab/ph3_c03r_windows.json`.
- All blocks are development-consumed; none is a virgin holdout.
- Per pair/block, use the block's exact 5m grid after integrity checks.
- Fixed horizon: 24 candles (two hours), with no secondary horizon.
- Events are spaced by 24 candles and cannot cross a block boundary.
- Past realized volatility at event t is
  `sqrt(sum(log(close_i / close_i-1)^2))` over the preceding 24 returns.
- Future realized volatility is the same quantity over the following 24
  returns. No future observation enters the predictor.
- The first 24 and final 24 candles of each block are unavailable by design.

## Forward Evaluation

Each pair/block is split chronologically at the median eligible event:

- first half: calibration only;
- second half: evaluation only.

On calibration events, fit one fixed model:

`log(RV_future) = intercept + beta * log(RV_past)`

The baseline forecast is the calibration mean of `log(RV_future)`. Both model
and baseline are frozen before evaluating the second half. No coefficient,
horizon, transform, threshold, or subgroup is selected from evaluation results.

Primary out-of-sample contrast:

`MSE improvement = 1 - MSE_model / MSE_baseline`

Secondary diagnostics fixed in advance are MAE improvement, Pearson correlation
between past and future log RV, beta, and calibration-to-evaluation stability.

## Inference and Controls

- Unit of analysis: pair/block evaluation series; candles are not independent
  inferential units.
- Estimate all metrics separately for every pair/block.
- Aggregate with equal weight across pair/block units and also report equal
  weight by block and by pair.
- Bootstrap 1,000 deterministic replicates by complete UTC days within each
  pair/block evaluation half; never bootstrap individual candles.
- Primary CI95 applies to equal-weight MSE improvement and equal-weight beta.
- Circular-shift placebo: shift `log(RV_past)` by half the evaluation series
  within pair/block, keeping future RV fixed.
- Baseline: calibration-period unconditional mean forecast.
- Holm correction covers the primary beta, primary MSE improvement, and
  model-versus-placebo contrasts. Per-pair diagnostics form a separate family.
- Audit concentration of positive improvement by pair, block, and UTC day.
- Audit hashes, coverage, timezone, strict ordering, duplicates, missing 5m
  timestamps, invalid OHLCV, eligible/discarded events, and no lookahead.

## Success Gate

`DEVELOPMENT VOLATILITY PERSISTENCE DETECTED - PROSPECTIVE HOLDOUT REQUIRED`
only if every condition passes:

1. equal-weight evaluation beta is positive and its bootstrap CI95 is entirely
   above zero;
2. equal-weight MSE improvement is positive and its bootstrap CI95 is entirely
   above zero;
3. model-versus-circular-placebo MSE improvement is positive after Holm;
4. MSE improvement is positive in at least four of five blocks;
5. MSE improvement is positive for at least seven of ten pairs;
6. no pair, block, or UTC day contributes more than 30% of total positive loss
   reduction;
7. integrity, sample size, and lookahead audits pass;
8. primary effects remain significant after Holm.

This decision establishes only development evidence for risk forecasting. It
does not establish return predictability, economic profitability, causal
identification, or permission to build a strategy.

## Rejection and Inconclusive Gates

`VOLATILITY PERSISTENCE HYPOTHESIS REJECTED IN PRIMARY SCOPE` if integrity is
sufficient but any central gate fails: beta or MSE improvement is non-positive
or uncertain, placebo is not beaten, temporal/cross-asset consistency fails, or
the effect is materially concentrated.

`INCONCLUSIVE VOLATILITY PERSISTENCE AUDIT` only when missing/corrupt data,
insufficient eligible events, or an invalid implementation prevents the primary
contrast. A small, negative, or statistically uncertain effect is rejection,
not inconclusive.

After rejection, no alternate horizon, transform, threshold, model, subset, or
volatility definition may be tried on these consumed data.

## Planned Artifacts

- `user_data/lab/ph4_a02_volatility_persistence_report.md`
- `user_data/lab/ph4_a02_volatility_persistence_report.json`
- `user_data/lab/ph4_a02_volatility_persistence_report.html`
- `user_data/lab/ph4_a02_volatility_persistence_matrix.csv`
- `user_data/lab/ph4_a02_volatility_persistence_bootstrap.csv`

