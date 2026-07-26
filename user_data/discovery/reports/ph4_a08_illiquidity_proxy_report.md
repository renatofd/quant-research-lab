# PH4-A08 - OHLCV Illiquidity-Proxy Risk Forecasting

Generated: `2026-07-14T18:26:34.932401+00:00`

**Decision:** OHLCV ILLIQUIDITY-PROXY HYPOTHESIS REJECTED IN PRIMARY SCOPE

At least one central economic, placebo, multiplicity, or replication gate failed on valid data.

## Frozen Design

- Ten Binance spot USDT pairs, 5m OHLCV, and the five frozen PH3-C03R blocks.
- Fixed 24-candle past and 24-candle future windows; events every 24 candles.
- Chronological calibration/evaluation split inside every pair/block.
- Primary P1 is mean absolute log return per approximate quote volume; P2 is diagnostic only.
- Outcome is log future realized volatility. No trades, fees, strategy, or directional return are modeled.
- All data are development-consumed; there is no prospective holdout.

## Primary P1 Results

- Informative units: `50`
- Calibration/evaluation events: `10750` / `10750`
- Equal-weight beta1_eval: `-0.071280508`; CI95 `[-0.11137750476608084, -0.029529188858250805]`
- Equal-weight MSE improvement: `-0.0039043222`; CI95 `[-0.0073766344231421, -0.0008104881319224767]`
- Circular-placebo loss reduction: `0.048189759`; CI95 `[0.029651146433488387, 0.04792862758406236]`
- Pairing-placebo loss reduction: `0.020498497`; CI95 `[0.01576838136855982, 0.025024647388225036]`
- MAE improvement: `-0.0028491479`
- Partial correlation: `-0.038658188`
- Incremental R2: `-0.0026602982`
- Positive pairs/blocks: `4/10`, `0/5`

## Multiplicity

- P1 bootstrap p-values: `{'beta': 1.0, 'mse_improvement': 0.994005994005994, 'circular_loss_reduction': 0.000999000999000999, 'pairing_loss_reduction': 0.000999000999000999}`
- P1 Holm-adjusted p-values: `{'beta': 1.0, 'mse_improvement': 1.0, 'circular_loss_reduction': 0.003996003996003996, 'pairing_loss_reduction': 0.003996003996003996}`
- P2 diagnostic Holm family: `{'beta': 1.0, 'mse_improvement': 1.0, 'circular_loss_reduction': 0.002997002997002997}`

## P2 Diagnostic

- beta2_eval: `-0.18861994`; CI95 `[-0.2501533384186887, -0.13928322190932121]`
- MSE improvement: `-0.0039647869`; CI95 `[-0.0077749594729528354, 0.00036880314381846046]`
- Circular-placebo loss reduction: `0.12311879`
- P2 cannot replace or rescue a failed P1 result.

## Concentration

- Maximum pair share: `0.1317377` (LTC/USDT)
- Maximum block share: `0.27795326` (4)
- Maximum UTC-day share: `0.036815838` (2026-01-24)

## Decision Gates

- `beta_positive_ci95`: `False`
- `mse_improvement_at_least_5pct_with_positive_ci95`: `False`
- `beats_circular_placebo_ci95`: `True`
- `beats_pairing_placebo_ci95`: `True`
- `all_four_p1_tests_survive_holm`: `False`
- `positive_in_at_least_4_of_5_blocks`: `False`
- `positive_in_at_least_7_of_10_pairs`: `False`
- `no_concentration_above_30pct`: `True`
- `controls_included_and_frozen`: `True`
- `integrity_and_sample_pass`: `True`

## Integrity and Limitations

- Integrity sufficient: `True`
- Discarded events: `{}`
- OHLCV does not observe spread, depth, order direction, realized slippage, or causal price impact.
- A positive result would be predictive association for risk only, never proof of liquidity causality.
- Existing blocks are development-consumed and cannot provide final confirmation.

## Artifact Inventory

- `/freqtrade/user_data/discovery/reports/ph4_a08_illiquidity_proxy_report.md`
- `/freqtrade/user_data/discovery/reports/ph4_a08_illiquidity_proxy_report.json`
- `/freqtrade/user_data/discovery/reports/ph4_a08_illiquidity_proxy_report.html`
- `/freqtrade/user_data/discovery/reports/ph4_a08_illiquidity_proxy_matrix.csv`
- `/freqtrade/user_data/discovery/reports/ph4_a08_illiquidity_proxy_bootstrap.csv`
