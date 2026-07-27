# PH4-A05 - Cross-Sectional Dispersion as a Market-Risk State

Preregistered: 2026-07-14, before any PH4-A05 outcome calculation.

## Economic Mechanism and Hypotheses

Large disagreement in contemporaneous asset returns can reflect heterogeneous
information, fragmented liquidity, or uneven deleveraging. If that state
persists, cross-sectional dispersion should forecast subsequent market-wide
return magnitude even without forecasting direction.

H1-A05: dispersion of trailing two-hour returns across the ten assets positively
and replicably predicts market-wide realized volatility over the next two hours,
and improves chronological out-of-sample forecast loss versus an unconditional
calibration baseline.

H0-A05: dispersion provides no stable incremental risk forecast after temporal
placebos and cross-asset diagnostics.

This does not test top-k strength, mean reversion, trend, or any trading rule.

## Frozen Design

- Existing Binance spot OHLCV 5m only.
- Ten USDT pairs; exact common timestamps in the five frozen,
  development-consumed blocks.
- One fixed horizon: 24 candles (two hours), with events every 24 candles.
- At event t, trailing return for each asset is
  `log(close_t / close_t-24)`.
- Predictor `D_t` is the population standard deviation of those ten trailing
  returns. No rank, quantile, threshold, or top-k is used.
- Outcome is market-wide future realized volatility:
  square root of the mean, across ten assets, of the sum of squared 5m log
  returns over t+1 through t+24.
- Predictor and outcome use disjoint windows and cannot cross block boundaries.
- Transform both with fixed natural log and epsilon `1e-12`.

## Forward Evaluation

Within each block, split eligible events chronologically at the median:

- first half calibrates `log(future_risk) = intercept + beta*log(D_t)` and the
  unconditional baseline mean;
- second half evaluates frozen forecasts.

Primary contrast: `1 - MSE_model/MSE_baseline`, equally weighted across blocks.
Diagnostics: beta, correlation, MAE improvement, and ten leave-one-asset-out
recalculations. Leave-one-out is a stability diagnostic, not model selection.

## Controls and Inference

- Circularly shift `D_t` by half the evaluation series inside each block.
- Bootstrap 1,000 deterministic replicates by complete UTC days within block;
  aggregate the five blocks with equal weight.
- Holm correction covers beta, MSE improvement, and model-versus-placebo.
- Leave-one-out p-values, if reported, form a separate diagnostic family.
- Unit of inference is a synchronized cross-sectional event within block.
- Audit hashes, synchronization, gaps, duplicates, timezone, invalid OHLCV,
  discarded events, concentration, and no lookahead.

## Success Gate

`DEVELOPMENT DISPERSION RISK SIGNAL DETECTED - PROSPECTIVE HOLDOUT REQUIRED`
only if all conditions pass:

1. beta positive with bootstrap CI95 entirely above zero;
2. MSE improvement positive with CI95 entirely above zero;
3. model beats circular placebo with CI95 above zero after Holm;
4. MSE improvement is positive in at least four of five blocks;
5. at least seven of ten leave-one-asset-out universes retain positive MSE
   improvement;
6. no block or UTC day contributes more than 30% of positive loss reduction;
7. all primary effects survive Holm;
8. integrity and sample checks pass.

Success establishes development evidence for risk forecasting only. It does not
establish direction, profit, causality, or permission to build a strategy.

## Rejection and Inconclusive Gates

`CROSS-SECTIONAL DISPERSION HYPOTHESIS REJECTED IN PRIMARY SCOPE` if data are
valid but any central gate fails.

`INCONCLUSIVE CROSS-SECTIONAL DISPERSION AUDIT` only if synchronization,
integrity, or sample size prevents the primary test. Negative/small effects are
rejection. No alternate horizon, dispersion measure, transform, threshold, or
subset may be tested after the result.

## Planned Artifacts

- `user_data/lab/ph4_a05_dispersion_risk_report.md`
- `user_data/lab/ph4_a05_dispersion_risk_report.json`
- `user_data/lab/ph4_a05_dispersion_risk_report.html`
- `user_data/lab/ph4_a05_dispersion_risk_matrix.csv`
- `user_data/lab/ph4_a05_dispersion_risk_bootstrap.csv`

