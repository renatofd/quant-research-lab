# PH4-A03 - Incremental Risk Information in Negative Semivariance

Preregistered: 2026-07-14, before any PH4-A03 outcome calculation.

## Economic Mechanism and Hypotheses

Negative shocks can be associated with deleveraging and liquidity withdrawal,
while positive shocks need not produce the same persistence of risk. Candles
cannot identify liquidations or order flow, but they can test whether negative
realized semivariance contains incremental forecasting information beyond total
realized volatility.

H1-A03: conditional on total past realized volatility, a greater share of
negative semivariance predicts higher future realized volatility and improves
chronological out-of-sample risk forecasts.

H0-A03: signed semivariance adds no stable incremental information beyond total
volatility, or any apparent effect fails placebo, temporal, cross-asset, or
concentration controls.

The outcome is risk magnitude, never return direction. This does not reopen
mean reversion, trend, ATR, or any strategy family.

## Frozen Design

- Existing Binance spot 5m Feather OHLCV only.
- Ten USDT pairs and the five development-consumed frozen blocks.
- One fixed horizon: 24 candles (two hours), with non-overlapping events every
  24 candles.
- Past positive semivariance: sum of squared positive 5m log returns over the
  preceding 24 candles.
- Past negative semivariance: sum of squared negative 5m log returns over the
  same window.
- Total volatility control: log square root of total semivariance.
- Signed imbalance: `(negative_semivariance - positive_semivariance) /
  (total_semivariance + 1e-12)`.
- Outcome: log realized volatility over the following 24 candles.
- No jump threshold, quantile, alternate horizon, or event selection.

## Forward Evaluation

Each pair/block is split chronologically at the median eligible event.

- Baseline calibration model: future log RV on intercept and past total log RV.
- Full calibration model: baseline plus signed imbalance.
- Both models are frozen before evaluation.
- Primary forecast contrast:
  `1 - MSE_full / MSE_baseline` on the evaluation half.
- Primary structural coefficient: signed-imbalance beta from the same full
  specification on evaluation data.

## Controls and Inference

- Circular-shift placebo: shift signed imbalance by half the evaluation series
  inside pair/block, keeping total volatility and outcomes fixed.
- Sign-swap falsification is algebraically equivalent to multiplying imbalance
  by -1 and is reported descriptively; it cannot be selected as an alternative.
- Bootstrap 1,000 deterministic replicates by complete UTC days within each
  pair/block; aggregate pair/block units with equal weight.
- Holm correction covers positive imbalance beta, positive incremental MSE
  improvement, and full-model advantage over circular placebo.
- Per-pair diagnostics form a separate family.
- Audit hashes, coverage, gaps, duplicates, timezone, invalid OHLCV, event
  counts, concentration, and no lookahead.

## Success Gate

`DEVELOPMENT NEGATIVE SEMIVARIANCE RISK SIGNAL DETECTED - PROSPECTIVE HOLDOUT REQUIRED`
only if all conditions pass:

1. equal-unit imbalance beta is positive with bootstrap CI95 above zero;
2. incremental MSE improvement is positive with CI95 above zero;
3. full model beats circular-shift placebo with CI95 above zero after Holm;
4. improvement is positive in at least four of five blocks;
5. improvement is positive for at least seven of ten pairs;
6. no pair, block, or UTC day contributes more than 30% of positive loss
   reduction;
7. all primary effects survive Holm;
8. integrity and sample checks pass.

Success is development evidence about risk only; it does not authorize a bot.

## Rejection and Inconclusive Gates

`SIGNED VOLATILITY ASYMMETRY HYPOTHESIS REJECTED IN PRIMARY SCOPE` if valid data
fail any central gate.

`INCONCLUSIVE SIGNED VOLATILITY AUDIT` only if data integrity or sample size
prevents the primary contrast. No threshold, horizon, transform, subgroup, or
directional rule may be introduced after the result.

## Planned Artifacts

- `user_data/lab/ph4_a03_signed_volatility_report.md`
- `user_data/lab/ph4_a03_signed_volatility_report.json`
- `user_data/lab/ph4_a03_signed_volatility_report.html`
- `user_data/lab/ph4_a03_signed_volatility_matrix.csv`
- `user_data/lab/ph4_a03_signed_volatility_bootstrap.csv`

