# Final Research Report

Date: 2026-07-14

## Executive Decision

# BOT REJEITADO

No tested operational family, raw directional concept, causal component
intervention, or Phase 4 economic hypothesis produced evidence sufficient to
approve a bot. The project has generated valid negative and limited
risk-forecasting evidence, but no liquid, replicable, non-concentrated trading
advantage with acceptable out-of-sample survival.

The laboratory is scientifically closed under the current data boundary. No
strategy, component, filter, threshold, pair specialization, or ensemble is
approved for real capital. Historical operational code remains research/legacy
material and is not validated by this report.

## Scope and Evidence Boundary

- Data: Binance spot OHLCV, Feather, 5m.
- Universe: BTC, ETH, SOL, BNB, XRP, ADA, DOGE, LINK, AVAX and LTC versus USDT.
- Development coverage used by the final programs: five non-overlapping blocks
  from 2025-07-31 to 2026-01-27, plus the later Phase 3 block through 2026-05-03.
- All available periods have been consumed for development.
- No virgin prospective holdout exists.
- No funding, basis, open interest, liquidation, aggressor/passive trade, order
  book, multi-exchange, options, on-chain, macro surprise, unlock/event, or
  provenance-safe sentiment dataset exists in the project.
- The Phase 4 offline studies did not execute Freqtrade backtests and did not
  modify trading logic, ROI, stoploss, martingale, Hyperopt, exchange, config,
  SQLite, or OHLCV.

## Binding Gates Before Phase 4

### Operational families

`PH3-GATE02`: `STOP ALL EXISTING FAMILIES - SCIENTIFIC RESET`.

| Family | Final evidence | Binding conclusion |
|---|---|---|
| Trend/score/entry variants | PF and expectancy below production criteria; Survival 0; causal interventions not replicable | Rejected |
| Pullback | Low PF, no robust region, missing positive OOS confirmation | Rejected |
| Mean Reversion multi-pair | Few-trade maxima, Survival 0, no robust region | Rejected |
| AVAX Mean Reversion | No robust region or >=100-trade PF>1 result | Rejected |
| LTC Mean Reversion | Local hints but no >=100-trade PF>1, no robust region, no independent WF | Rejected by portfolio gate |
| N-of-M and entry-logic variants | PF OOS below 1 and Survival poor | Rejected |
| ATR/component variants | No reliable Walk-Forward survival; adaptation not justified | Rejected |
| Ensembles | No complete architecture PF>1; Survival proxy 0 | Rejected |

### Raw signals

`PH3-RST-GATE01`: `STOP RAW SIGNAL SEARCH - NO ARCHITECTURE JUSTIFIED`.

| Study | Conservative mean net | Main comparison | Final decision |
|---|---:|---|---|
| RST01 raw trend 2h | -0.3357% | Conditional effect -0.0213% | Not detected |
| RST02 raw mean reversion 2h | -0.2931% | Relative effect +0.0214%, but economically negative | Not detected |
| RST03 directional vol expansion | -0.2619% | Incremental effect +0.0695%, but all units remained negative | Not detected |
| RST04 cross-sectional top-2 | -0.3285% | Underperformed equal-weight/placebo | Not detected |

The positive relative effects in RST02/RST03 remain scientific information;
they do not authorize composition, threshold changes, or retuning.

## Phase 4 Economic Hypotheses

### Applicability of the laboratory protocol

PH4-A02/A03/A05/A07 had no tunable parameter space, so a neighborhood search
would be scientifically meaningless. Robustness was tested directly through
1,000 day-block bootstrap replicates, pair/block consistency, leave-one-asset-out
where applicable, placebos and concentration gates. Their first-half calibration
and second-half evaluation inside every frozen block supplied the chronological
forward test. A04 stopped at its preregistered sample-size gate. No Phase 4
candidate reached a valid reason to execute strategy backtests, Hyperopt, or a
prospective holdout; no virgin holdout was available in any case.

### A01 - BTC leadership over altcoins

- Primary equal-block beta: `0.1022`, bootstrap CI95 `[0.0150, 0.1307]`.
- Conservative conditional mean net: `-0.2999%`.
- Conditional-minus-unconditional effect: `+0.00039%`, CI95 crossed zero.
- Hit rate: `4.72%`.
- BTC did not beat pseudo-leaders or circular shift after Holm.
- Reverse-time control was also positive, weakening directional interpretation.

Decision: `BTC LEAD-LAG HYPOTHESIS REJECTED IN PRIMARY SCOPE`.

### A02 - Volatility persistence as risk forecasting

- Equal-unit beta: `0.5918`, CI95 `[0.5528, 0.5981]`.
- Out-of-sample MSE improvement: `37.50%`, CI95 `[34.60%, 38.54%]`.
- Positive in `5/5` blocks and `10/10` pairs; placebo defeated after Holm.
- Concentration: one block supplied `30.3708%` of positive loss reduction,
  above the preregistered `30%` limit.

Decision: `VOLATILITY PERSISTENCE HYPOTHESIS REJECTED IN PRIMARY SCOPE`.

Interpretation: strong development evidence that volatility clusters, but the
strict generalization gate failed. This is risk information, not a trading edge.

### A03 - Negative versus positive semivariance

- Controlled signed-imbalance beta: `0.0641`, CI95 `[0.0433, 0.0818]`.
- Incremental MSE improvement: `0.1313%`, CI95 `[-0.2104%, 0.4124%]`.
- Positive in `4/5` blocks and `7/10` pairs.
- One block supplied `37.5847%` of positive loss reduction.

Decision: `SIGNED VOLATILITY ASYMMETRY HYPOTHESIS REJECTED IN PRIMARY SCOPE`.

Interpretation: a descriptive asymmetry exists, but it did not add stable
forecast utility beyond total volatility.

### A04 - Co-jumps and propagation

- De-clustered valid events by block: `15, 29, 32, 28, 44`.
- Three of five blocks fell below the preregistered minimum of 30 events.
- Integrity passed; thresholds were not relaxed and no PnL inference was made.

Decision: `INCONCLUSIVE CO-JUMP PROPAGATION AUDIT` due permanent sample
insufficiency under the frozen definition and current dataset.

### A05 - Cross-sectional dispersion as risk state

- Equal-block beta: `0.3652`, CI95 `[0.2924, 0.4258]`.
- Out-of-sample MSE improvement: `16.29%`, CI95 `[11.32%, 21.00%]`.
- Positive in `5/5` blocks and all ten leave-one-asset-out universes.
- One block supplied `30.3991%` of positive loss reduction, above the 30% gate.

Decision: `CROSS-SECTIONAL DISPERSION HYPOTHESIS REJECTED IN PRIMARY SCOPE`.

Interpretation: dispersion contains development information about risk, but the
non-concentration criterion failed. It does not imply direction or profitability.

### A06 - Cross-sectional reversal

Decision: closed without a new experiment. Executing it on the consumed data
would reopen rejected Mean Reversion/RST04 work through a new horizon or label,
which the scientific reset explicitly prohibits.

### A07 - Compression followed by expansion

- Compression beta: `-0.5334`, CI95 `[-0.5351, -0.4901]`.
- Full model MSE improvement: `26.80%`, positive in `5/5` blocks and `10/10`
  pairs, with acceptable concentration.
- The coefficient sign is opposite the preregistered expansion hypothesis:
  recent low volatility predicted continued lower risk, not expansion.

Decision: `VOLATILITY COMPRESSION HYPOTHESIS REJECTED IN PRIMARY SCOPE`.

No percentile, squeeze threshold, or alternate window was tried.

### A08-A11 - Data adequacy and existing evidence

| ID | Hypothesis | Classification | Reason |
|---|---|---|---|
| A08 | OHLCV illiquidity/impact proxy | Inconclusive - permanent data gap | Candles do not identify spread, depth or realized impact; no validation dataset exists |
| A09 | Abnormal volume/flow proxy | Closed - no reopening | Volume/filter family is already closed; OHLCV volume cannot identify aggressor/passive or institutional flow |
| A10 | Candle-only liquidity grabs | Inconclusive - permanent data gap | Stop runs/liquidity withdrawal require book/trade evidence; candle shapes are not mechanism identification |
| A11 | Calendar/session/weekend | Rejected by existing evidence | No time filter improved Survival; best documented WF survival was 40% with PF OOS 0.776; no filter passed cross-study consistency |

## Hypotheses Requiring Missing Data

These hypotheses remain economically plausible in general, but are classified
`INCONCLUSIVE - PERMANENT DATA GAP IN CURRENT PROJECT`. They were not replaced
with misleading OHLCV proxies.

| IDs | Mechanism | Missing indispensable evidence |
|---|---|---|
| B12-B15, B19 | Funding, basis, OI, liquidations, spot-perp discovery, carry dispersion | Derivatives/perp panel with timestamps and costs |
| B16-B17 | Aggressor flow, order-book imbalance/depth | Tick trades and depth snapshots |
| B18 | Multi-exchange fragmentation/arbitrage | Synchronized exchange prices, fees and transfer constraints |
| B20-B21 | Stablecoin/on-chain exchange flows | Validated labels and provenance-safe flows |
| B22 | Macro surprises | Consensus/surprise series with exact release timestamps |
| B23 | Option-implied risk premia | Option surface, forwards, maturities and realized outcomes |
| B24-B25 | Unlocks, listings, delistings, regulation | Prospectively curated event datasets |
| B26 | Attention/sentiment | Leakage-controlled source data and prospective holdout |

No network acquisition, credentials, licensing, or external spend was assumed.

## Scientific Ranking

This ranking measures knowledge gained, not trade attractiveness.

1. **A02 volatility persistence** - strongest and broadest risk information,
   but failed the exact non-concentration gate and has no directional edge.
2. **A05 cross-sectional dispersion** - useful market-risk state in development,
   but failed non-concentration by a narrow, binding margin.
3. **A03 signed semivariance** - positive structural coefficient, but negligible
   and uncertain incremental forecast improvement.
4. **A07 compression** - robust result in the opposite direction; falsified the
   expansion hypothesis and reinforced volatility persistence.
5. **A01 BTC lead-lag** - positive statistical beta without economic return or
   BTC specificity after Holm.
6. **A04 co-jumps** - valid design but insufficient events under the frozen
   definition.
7. **All operational/raw trading families** - economically negative, unstable,
   sparse, concentrated, or overfit under their valid gates.

## Permanent Negative Conclusions Within Scope

- None of the implemented strategy families is suitable for production.
- No raw 2h trend, raw 2h mean reversion, directional volatility expansion, or
  cross-sectional top-2 signal generated positive liquid economics.
- BTC does not demonstrate specific, economically useful 5m leadership over the
  nine altcoins in the tested design.
- Volatility compression did not precede expansion under the frozen continuous
  test; it predicted persistence in the opposite direction.
- Time/pair/regime filters did not establish reliable Walk-Forward survival.
- Statistical risk predictability cannot be converted into a trading strategy
  without a separately preregistered economic edge and prospective holdout.

## Limitations

- All OHLCV periods are development-consumed; no result has virgin holdout
  confirmation.
- Five blocks are enough for disciplined falsification but weak for estimating
  regime stability; the strict concentration gate exposed that limitation.
- OHLCV candles do not identify order flow, spread, depth, liquidations, funding,
  basis or causal market microstructure.
- The universe is limited to ten Binance spot USDT pairs and 5m data.
- Costs used in directional raw studies were fixed approximations, not measured
  execution slippage.
- Multiple hypotheses were controlled within studies, but the entire program
  accumulated development exposure; retrospective selection is prohibited.

## Infrastructure and Operational State

- The laboratory produced valid negative evidence and caught overfitting,
  concentration, sparse-event and path-dependence problems.
- At closure, SQLite contains `3,371 completed`, `255 error`, `228 pending`
  experiment records; there are zero experiments marked `running`.
- It also contains 25 historical sessions marked `running`, but no laboratory
  container/process is active. These stale legacy statuses were left untouched
  to preserve the database and the instruction not to execute old pending work.
- The operational Freqtrade container was not changed or stopped.

## Future Lines, Only Under Genuinely New Evidence

The current project is closed. Reopening requires one of:

1. a prospectively reserved temporal holdout not used for hypothesis design;
2. a provenance-safe derivatives dataset, beginning with B12 funding/basis;
3. tick/order-book data for a single preregistered microstructure mechanism;
4. a documented external change in fees/market structure before analysis.

Reopening does not permit retuning A01-A07, changing RST horizons, combining the
least negative signals, or renaming rejected strategy families.

## Final Classification

- Confirmed trading hypotheses: **0**.
- Rejected/closed hypotheses and families: all testable operational, raw, and
  OHLCV economic candidates listed above.
- Inconclusive due permanent data/sample gaps: A04, A08, A10, B12-B26.
- Approved bot: **none**.

# FINAL DECISION: BOT REJEITADO

The scientifically correct next action is to stop strategy development and not
deploy capital. The project is complete under its current data, universe,
timeframe, cost assumptions, and evidence standards.
