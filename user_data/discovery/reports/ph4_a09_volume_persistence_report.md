# PH4-A09 - OHLCV Volume Persistence

Generated: `2026-07-14T19:20:30.122103+00:00`

**Decision:** OHLCV VOLUME-PERSISTENCE HYPOTHESIS REJECTED IN PRIMARY SCOPE

P1 activity failed at least one pre-registered economic, statistical, control, or robustness gate.

## Frozen Design

- Ten synchronized Binance spot pairs, 5m OHLCV, five frozen development-consumed blocks.
- One 12-candle future horizon, one 12-candle risk lookback, 60/40 split, 12-candle embargo.
- Hour-of-week fixed effects and frozen train coefficients; no threshold, strategy, or trading model.
- Bootstrap: 1,000 complete-UTC-day replicates, equal-weight pair/block units, seed 2026071409.

## P1 Activity

- Beta: `0.19382212`; aggregate CI95 `[0.19117845425023453, 0.19646578267508205]`
- Partial correlation: `0.22030586`
- MSE improvement: `0.14066916`; CI95 `[0.10918780209816997, 0.1409432545034507]`; Holm `0.011988011988011988`
- MAE improvement: `0.054506148`; CI95 `[0.050744120488990276, 0.05669965144863809]`; Holm `0.011988011988011988`
- Incremental R2: `0.2595639`
- Positive pairs/blocks: `10/10`, `5/5`

## P2 Risk

- Beta: `0.0012058599`; aggregate CI95 `[0.0011620201512202934, 0.0012496996333705278]`
- Partial correlation: `0.069930319`
- MSE improvement: `0.0068364418`; CI95 `[0.006001941549473902, 0.009756389987190991]`; Holm `0.011988011988011988`
- MAE improvement: `0.0066341898`; CI95 `[0.005660202805038479, 0.007612593604850794]`; Holm `0.011988011988011988`
- Incremental R2: `0.0051592238`
- Positive pairs/blocks: `10/10`, `4/5`

## Negative Controls

- activity vs circular: `0.14067027`; CI95 `[0.10918130898240903, 0.14095306300948557]`; Holm `0.011988011988011988`
- activity vs day_permutation: `0.13950196`; CI95 `[0.10814313982082421, 0.13978404914527223]`; Holm `0.011988011988011988`
- activity vs cross_asset: `0.14066916`; CI95 `[0.10918780209816997, 0.1409432545034507]`; Holm `0.011988011988011988`
- activity vs reverse_time: `0.13970419`; CI95 `[0.10809302285807024, 0.13996259865649305]`; Holm `0.011988011988011988`
- risk vs circular: `0.0068627352`; CI95 `[0.006028774563480781, 0.009776676003888592]`; Holm `0.011988011988011988`
- risk vs day_permutation: `0.0067508796`; CI95 `[0.005921194957914894, 0.009656044376042255]`; Holm `0.011988011988011988`
- risk vs cross_asset: `0.0068364418`; CI95 `[0.006001941549473902, 0.009756389987190991]`; Holm `0.011988011988011988`
- risk vs reverse_time: `0.0067084529`; CI95 `[0.005880359250515787, 0.009615762321143806]`; Holm `0.011988011988011988`

## Concentration

- activity pair: max `0.32142558` at `AVAX/USDT`
- activity block: max `0.74285149` at `1`
- activity day: max `0.69117747` at `2025-10-10`
- risk pair: max `0.43801433` at `AVAX/USDT`
- risk block: max `0.67633783` at `1`
- risk day: max `0.6256757` at `2025-10-10`

## Gates

### P1 Activity

- `mse_improvement_at_least_5pct`: `True`
- `mae_improvement_at_least_5pct`: `True`
- `mse_ci95_positive`: `True`
- `mae_ci95_positive`: `True`
- `mse_survives_holm`: `True`
- `mae_survives_holm`: `True`
- `beta_positive_ci95`: `True`
- `positive_at_least_7_of_10_pairs`: `True`
- `positive_at_least_4_of_5_blocks`: `True`
- `all_controls_survive_holm`: `True`
- `concentration_at_most_30pct`: `False`

### P2 Risk

- `mse_improvement_at_least_5pct`: `False`
- `mae_improvement_at_least_5pct`: `False`
- `mse_ci95_positive`: `True`
- `mae_ci95_positive`: `True`
- `mse_survives_holm`: `True`
- `mae_survives_holm`: `True`
- `beta_positive_ci95`: `True`
- `positive_at_least_7_of_10_pairs`: `True`
- `positive_at_least_4_of_5_blocks`: `True`
- `all_controls_survive_holm`: `True`
- `concentration_at_most_30pct`: `False`

## Integrity and Scope

- Integrity sufficient: `True`
- Informative units: `50`
- Protocol SHA-256: `40460d4f4c6c25cf7c54fb42d0eb5696344be046c1c746432d256b80d8ded937`
- Volume is an OHLCV activity/attention proxy, not institutional flow or liquidity.
- Current blocks are development-consumed and are not prospective confirmation.
- Operational experiment justified: `False`

## Artifacts

- `/freqtrade/user_data/discovery/reports/ph4_a09_volume_persistence_report.md`
- `/freqtrade/user_data/discovery/reports/ph4_a09_volume_persistence_report.html`
- `/freqtrade/user_data/discovery/reports/ph4_a09_volume_persistence_report.json`
- `/freqtrade/user_data/discovery/reports/ph4_a09_volume_persistence_matrix.csv`
- `/freqtrade/user_data/discovery/reports/ph4_a09_volume_persistence_bootstrap.csv`
