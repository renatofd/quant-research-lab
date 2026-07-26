# Hypothesis Ledger Final

Generated: `2026-07-14T16:41:13.230482+00:00`

Scientific budget: `26/30` hypotheses registered.

| ID | Family | State | Data | Priority | Result / reason |
|---|---|---|---|---:|---|
| A01 | BTC leadership and delayed altcoin price discovery | rejected | available | 1 | Economic effect was negative; BTC failed pseudo-leader and Holm specificity gates. |
| A02 | Volatility persistence as risk forecasting | rejected | available | 1 | One block contributed 30.3708% of positive loss reduction, above the frozen 30% gate. |
| A03 | Negative versus positive semivariance | rejected | available | 2 | Incremental MSE CI crossed zero and one block contributed 37.58% of positive improvement. |
| A04 | Co-jumps and cross-asset propagation | inconclusive_sample | available | 1 | Three of five blocks had fewer than 30 valid de-clustered events; thresholds cannot be retuned. |
| A05 | Cross-sectional dispersion as a market-risk state | rejected | available | 1 | One block contributed 30.3991% of positive loss reduction. |
| A06 | Cross-sectional reversal | closed | unavailable | 3 | Would reopen rejected Mean Reversion and cross-sectional ranking on consumed data. |
| A07 | Volatility compression followed by expansion | rejected | available | 2 | Compression beta was significantly negative; no squeeze threshold may be searched. |
| A08 | OHLCV proxy for illiquidity and price impact | blocked_data | unavailable | 3 | Candles cannot identify spread, depth, or realized impact. |
| A09 | Abnormal volume and flow persistence | closed | unavailable | 3 | Volume/filter family is closed and OHLCV volume cannot identify flow. |
| A10 | False breakouts and liquidity grabs | blocked_data | unavailable | 4 | Candles cannot identify the proposed liquidity mechanism. |
| A11 | Session, weekday, and weekend seasonality | rejected | available | 4 | No filter improved Survival; best documented OOS PF remained below 1. |
| B12 | Funding and basis carry/crowding | blocked_data | unavailable | 1 | No funding, basis, or perp dataset exists. |
| B13 | Open interest plus funding crowding | blocked_data | unavailable | 1 | No OI or funding panel exists. |
| B14 | Liquidation cascades and forced-flow overshoot | blocked_data | unavailable | 1 | No liquidation event dataset exists. |
| B15 | Spot versus perpetual price discovery | blocked_data | unavailable | 1 | Only spot OHLCV is available. |
| B16 | Aggressor/passive order-flow imbalance | blocked_data | unavailable | 2 | No tick/aggressor dataset exists. |
| B17 | Order-book depth, imbalance, and liquidity withdrawal | blocked_data | unavailable | 2 | No order-book dataset exists. |
| B18 | Cross-exchange fragmentation and arbitrage limits | blocked_data | unavailable | 2 | No synchronized multi-exchange or transfer-cost dataset exists. |
| B19 | Cross-sectional funding and carry dispersion | blocked_data | unavailable | 2 | No funding/carry panel exists. |
| B20 | Stablecoin flows to exchanges | blocked_data | unavailable | 3 | No stablecoin flow or exchange-label dataset exists. |
| B21 | On-chain exchange inflows and outflows | blocked_data | unavailable | 3 | No on-chain flow or validated label dataset exists. |
| B22 | Macroeconomic announcements and surprises | blocked_data | unavailable | 3 | No consensus/surprise dataset exists. |
| B23 | Option-implied variance, jump, and skew premia | blocked_data | unavailable | 3 | No option surface or forwards dataset exists. |
| B24 | Token unlock and vesting supply shocks | blocked_data | unavailable | 3 | No prospective unlock/free-float dataset exists. |
| B25 | Listings, delistings, and regulatory events | blocked_data | unavailable | 4 | No prospective event/surprise dataset exists. |
| B26 | Attention and sentiment | blocked_data | unavailable | 4 | No provenance-safe sentiment dataset or prospective holdout exists. |

Anti-recycling rule: a new name, threshold, lag, weight, vote, score, EMA, RSI, ATR, or N-of-M variant does not create a new hypothesis.
