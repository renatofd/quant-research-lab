# PH4-A04 - Co-Jumps and Cross-Asset Propagation

Preregistered: 2026-07-14, before any PH4-A04 outcome calculation.

## Economic Mechanism and Hypotheses

Simultaneous extreme returns in several cryptoassets may reveal a market-wide
information or liquidity shock. If price discovery is incomplete, assets not
yet strongly affected in the event candle may respond in the same direction in
the immediately following candle.

H1-A04: a same-direction co-jump in at least three assets predicts a positive
direction-aligned return, net of fixed costs, in the equal-weight portfolio of
assets that did not jump in that event candle. The effect is replicable across
blocks/assets and exceeds temporal placebos.

H0-A04: apparent propagation is absent, economically negative after costs,
unstable, concentrated, or indistinguishable from common volatility and
temporally shifted event labels.

This is an event-study association. OHLCV cannot identify the underlying order
flow or prove causal contagion.

## Frozen Design

- Existing Binance spot 5m Feather OHLCV only.
- Ten USDT pairs and the five development-consumed blocks in
  `user_data/lab/ph3_c03r_windows.json`.
- Exact intersection of timestamps across all ten pairs inside each block.
- Return: close-to-close log return.
- Causal scale estimate per pair/time t: root-mean-square of the preceding
  2,016 five-minute returns (seven days), shifted one candle so return t is
  excluded.
- A jump is `abs(return_t) > 4 * past_RMS_t`.
- A co-jump event requires at least three jumps with the same sign at t.
- If both signs meet the count, the larger count defines direction; an exact
  tie is discarded.
- The response portfolio contains only assets not classified as jumps at t.
- Event outcome is the equal-weight next-candle return of response assets,
  multiplied by event direction.
- Events are kept at least 12 candles (one hour) apart; the first chronological
  event wins. This is a fixed de-clustering rule, not an optimized parameter.
- No alternate threshold, jump count, lag, holding period, universe, or
  de-clustering interval is tested.

## Costs and Primary Estimand

The gross direction-aligned next-candle response is reduced by the two fixed
scenarios used in Phase 3/PH4-A01:

- fee-only: 0.1% per side;
- conservative: fee plus 5 bps slippage per side, total round-trip 0.3%.

The conservative scenario is decisional. Costs are an economic contrast, not a
simulation of execution.

Primary estimand: equal-block-weight mean conservative net response. Supporting
metrics: median, hit rate, effect versus circular-shift placebo, result by block
and response asset, and event prevalence.

## Controls, Inference, and Integrity

- Circular-shift placebo: shift event timestamp/direction by half of the
  eligible block while preserving the number of events.
- Unconditional control: apply observed event directions to next-candle
  response at the shifted timestamps.
- Common-factor control: response assets must be non-jump assets at t; report
  their contemporaneous direction-aligned return and require the future effect
  not to be fully explained by it in a fixed OLS control.
- Reverse-time falsification: the future response must not show equal or greater
  association when used to explain the pre-event response.
- Bootstrap 1,000 deterministic replicates by complete UTC event days within
  each block, then aggregate blocks with equal weight.
- Unit of inference: event within block. Assets in one event are not independent
  primary observations.
- Holm correction covers positive net mean, event-minus-placebo effect, and the
  common-factor-controlled event coefficient.
- Diagnostic per-asset p-values form a separate Holm family.
- Audit hashes, coverage, exact synchronization, timezone, duplicates, gaps,
  invalid OHLCV, warmup, discarded ties, de-clustered events, incomplete labels,
  and absence of lookahead.

## Success Gate

`DEVELOPMENT CO-JUMP PROPAGATION DETECTED - PROSPECTIVE HOLDOUT REQUIRED` only
if all conditions pass:

1. conservative mean and median net response are positive;
2. bootstrap CI95 of conservative mean is entirely above zero;
3. event-minus-placebo effect is positive with CI95 above zero and survives
   Holm;
4. conservative net hit rate exceeds 52%;
5. net mean is positive in at least four of five blocks;
6. diagnostic net mean is positive for at least seven of ten assets when each
   has at least 30 response observations;
7. no pair, block, day, or event direction accounts for more than 30% of total
   positive contribution;
8. the controlled event coefficient is positive and survives Holm;
9. reverse-time falsification does not equal or exceed the forward effect;
10. every block has at least 30 valid events and integrity checks pass.

Success is development evidence only and cannot authorize a strategy.

## Rejection and Inconclusive Gates

`CO-JUMP PROPAGATION HYPOTHESIS REJECTED IN PRIMARY SCOPE` when data are valid
but any central economic, placebo, consistency, concentration, or control gate
fails.

`INCONCLUSIVE CO-JUMP PROPAGATION AUDIT` only if fewer than 30 events exist in a
block, integrity fails, or the response cannot be constructed. A negative or
small effect is rejection, not inconclusive.

No threshold, count, lag, subgroup, or holding period may be changed after the
result.

## Planned Artifacts

- `user_data/lab/ph4_a04_cojump_propagation_report.md`
- `user_data/lab/ph4_a04_cojump_propagation_report.json`
- `user_data/lab/ph4_a04_cojump_propagation_report.html`
- `user_data/lab/ph4_a04_cojump_propagation_matrix.csv`
- `user_data/lab/ph4_a04_cojump_propagation_bootstrap.csv`

