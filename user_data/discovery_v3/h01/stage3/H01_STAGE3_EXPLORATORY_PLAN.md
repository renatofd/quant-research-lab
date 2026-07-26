# H01 — Stage 3 Exploratory Plan

Frozen: 2026-07-24, before any development outcome was calculated  
Holdout: SEALED

## Exploratory question

Does signed, actual forced-liquidation flow contain incremental information about
same-direction future COIN-M perpetual returns after controlling for the price
move occurring in the liquidation minute?

The primary economic direction is **continuation**: forced orders move price,
the mark-price feedback loop breaches additional margin accounts, and further
forced orders continue the move. A negative response is recorded as a reversal
diagnostic but does not confirm this continuation mechanism.

## Fixed exploratory representation

- Unit: one UTC minute with at least one observed liquidation event.
- `BUY` liquidation orders are positive forced flow; `SELL` orders are negative.
- Exact full-row provider duplicates use the Stage 2 normalized layer.
- Predictor: signed `log(1 + absolute net contracts)`, standardized within asset
  using development data only.
- Control: contemporaneous perpetual open-to-close return in the event minute.
- Outcomes: raw perpetual return from the next minute's open to the close at
  exactly 1, 5, 15 and 60 minutes after the event minute.
- The four horizons form a response curve. None may be selected or renamed as
  “best”.
- Event minutes whose measurement or response window crosses a missing price
  block are excluded mechanically.
- Open-interest metrics are optional diagnostics and cannot be imputed.

## Fixed diagnostics

For each horizon:

1. OLS coefficient of standardized signed liquidation flow after the
   contemporaneous-return control;
2. incremental R² over the control-only model;
3. same-direction mean return by liquidation-intensity quartile;
4. coefficient and top-quartile effect by asset;
5. top-quartile effect in four chronological development blocks;
6. 500-replicate bootstrap by UTC day with seed `20260724`;
7. a negative control that moves every liquidation timestamp forward exactly
   seven calendar days while leaving price outcomes untouched.

No threshold, lag, asset or date may be changed after execution.

## Stage 3 screening rule

H01 advances to formal Stage 4 only if the development evidence contains at
least one pair of adjacent fixed horizons (`1/5`, `5/15`, or `15/60`) satisfying
all of:

- pooled bootstrap 95% interval for the incremental coefficient is above zero;
- top-intensity-quartile continuation-aligned mean is at least 0.10% gross;
- incremental R² is at least 0.0001;
- at least four of six assets have a positive aligned effect;
- at least three of four chronological blocks have a positive aligned effect;
- the seven-day placebo is smaller and does not reproduce the full pattern.

If no adjacent pair passes, the continuation mechanism is rejected at Stage 3
for insufficient size, stability or incremental information. Formal p-values,
Holm correction and holdout opening are prohibited unless Stage 3 passes.
