# Phase 4 Hypothesis Ledger

Updated: 2026-07-14

This ledger is the anti-recycling record for the laboratory. A rejected family
or hypothesis cannot be reopened by changing names, horizons, thresholds,
filters, weights, or implementation details on the same development data.

## Binding Closed Work

| ID/family | Current status | Binding reason |
|---|---|---|
| Trend score and TrendStrategy variants | CLOSED - REJECTED | PH3-GATE01 and PH3-GATE02 |
| Pullback | CLOSED - REJECTED | PH3-GATE02 |
| MeanReversionStrategy and single-asset variants | CLOSED - REJECTED | PH3-GATE02 and single-asset gates |
| ATR variants | CLOSED - REJECTED/INCONCLUSIVE | Phase 3 causal audits; no adaptive study justified |
| Entry logic and N-of-M variants | CLOSED - REJECTED | PH3-GATE02 |
| Ensembles | CLOSED - REJECTED | PH3-GATE02 |
| PH3-RST01 raw trend | CLOSED - NOT DETECTED | PH3-RST-GATE01 |
| PH3-RST02 raw mean reversion | CLOSED - NOT DETECTED | PH3-RST-GATE01 |
| PH3-RST03 directional volatility expansion | CLOSED - NOT DETECTED | PH3-RST-GATE01 |
| PH3-RST04 cross-sectional relative strength | CLOSED - NOT DETECTED | PH3-RST-GATE01 |
| PH4-A01 BTC lead-lag | CLOSED - REJECTED | Primary economic and specificity gates failed |
| A06 cross-sectional reversal | CLOSED - PROHIBITED REOPENING | Would reopen rejected mean-reversion/RST04 work on consumed data |

## Active Queue

| Priority | ID | Hypothesis | Data status | State |
|---:|---|---|---|---|
| - | A02 | Volatility persistence predicts future risk magnitude | Available, development-consumed | CLOSED - REJECTED: concentration gate failed (30.37% in one block) |
| - | A04 | Co-jumps and cross-asset propagation | Available, development-consumed | CLOSED - INCONCLUSIVE: 3/5 blocks below 30 events; no threshold retuning allowed |
| - | A05 | Cross-sectional dispersion predicts future market risk | Available, development-consumed | CLOSED - REJECTED: concentration gate failed (30.40% in one block) |
| - | A03 | Positive/negative volatility asymmetry | Partial proxy only | CLOSED - REJECTED: incremental MSE CI crossed zero; concentration 37.58% |
| - | A07 | Volatility compression predicts future magnitude | Available, development-consumed | CLOSED - REJECTED: beta was significantly negative, opposite to expansion hypothesis |
| - | A08 | OHLCV illiquidity proxy | Mechanism only partially observed | CLOSED - INCONCLUSIVE PERMANENT DATA GAP: no spread/book/trade data to validate liquidity |
| - | A09 | Abnormal volume as activity/risk proxy | Contaminated proxy | CLOSED - NO REOPENING: volume/filter family already closed; no aggressor/passive flow data |
| - | A10 | Candle-only liquidity grabs | Mechanism not identifiable from candles | CLOSED - INCONCLUSIVE PERMANENT DATA GAP: no book/trade/stop data |
| - | A11 | Calendar/session effects | Available, high multiplicity risk | CLOSED - REJECTED BY EXISTING EVIDENCE: no filter improved survival or passed cross-study consistency |

## Missing-Data Families

B12-B26 require data not present in the laboratory and are classified
`INCONCLUSIVE - PERMANENT DATA GAP IN CURRENT PROJECT`. They must not be
approximated with OHLCV. Specifically:

- B12/B13/B14/B15/B19: no funding, basis, open interest, liquidation, or perp data.
- B16/B17: no aggressor/passive trades or order book.
- B18: no synchronized multi-exchange data or transfer-friction records.
- B20/B21: no stablecoin/on-chain flows or validated exchange labels.
- B22: no macro surprise calendar with precise timestamps.
- B23: no option surface, forwards, maturities, or implied moments.
- B24/B25: no prospective event/unlock/listing/regulatory dataset.
- B26: no provenance-safe sentiment/attention dataset or prospective holdout.

No download, credential use, or external acquisition was authorized or
performed. OHLCV substitution would not measure these mechanisms.

## Data Governance

- Binance spot OHLCV, 5m, ten USDT pairs.
- Five historical blocks are development-consumed.
- There is no virgin prospective holdout.
- Positive development evidence cannot approve a strategy or bot.
- One hypothesis is executed at a time, under an immutable preregistration.
