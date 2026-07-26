# Discovery V3 — Scientific Ledger

| Hypothesis | Current stage | Status | Decision date | Evidence |
|---|---:|---|---|---|
| H01 — Liquidation Cascades | 3 | REJECTED | 2026-07-24 | Continuation failed size, asset and temporal gates; holdout unopened |
| H02 — Spot × Perpetual Divergence | 3 | REJECTED | 2026-07-24 | Statistical convergence existed but gross mean was 1.23 bp versus 30 bp cost envelope; 0/10 assets and 0/4 blocks net positive; holdout unopened |
| H03 — Extreme Funding | 0 | REJECTED | 2026-07-24 | No novel incremental mechanism: V2 funding-only baseline was negative in development and near zero in holdout; no new data justify reopening |
| H04 — Cross-Exchange Leadership | 3 | REJECTED | 2026-07-24 | Binance leadership statistically real but gross effect 0.37 bp versus 15 bp cost; 0/10 assets and 0/4 blocks net positive; holdout unopened |
| H05 — Liquidity Regimes | 1 | BLOCKED | 2026-07-24 | Requires point-in-time sequenced order book; OHLCV proxy forbidden by prior A08 rejection |
| H06 — On-chain Flows | 1 | BLOCKED | 2026-07-24 | Requires versioned point-in-time exchange-address labels; raw public chain alone insufficient |
| H07 — ETF Flows | 1 | BLOCKED | 2026-07-24 | Requires official/audited fund-level flow vintages and actual release timestamps; AUM proxy invalid |
| H08 — Options Market | 1 | BLOCKED | 2026-07-24 | Requires historical point-in-time option quote surface; public trades/limited marks insufficient |
| H09 — Order Flow / CVD | 1 | REJECTED | 2026-07-24 | Correct trade+book experiment cost exceeds expected information; 5m CVD proxy invalid; no implementation |
| H10 — Cross-Asset Relative Strength | 0 | REJECTED | 2026-07-24 | Would reopen definitive prior OHLCV/momentum conclusion without materially new economic data |

**Project status:** `CONCLUDED_NO_ROBUST_EDGE`.

No hypothesis was confirmed. H01–H04, H09 and H10 are rejected; H05–H08 are blocked by decisive unavailable data. No hypothesis remains active.
