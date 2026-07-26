# H01 — Final Scientific Decision

Classification: **REJECTED AT STAGE 3**  
Decision date: 2026-07-24  
Holdout: **SEALED AND UNOPENED**

## Tested mechanism

Actual signed forced-liquidation flow should create same-direction continuation
because market impact and mark-price feedback trigger additional margin
breaches. The development-only analysis controlled the contemporaneous
event-minute return and used a fixed 1/5/15/60-minute response curve.

## Evidence

- 49,449 development event-minute observations entered each horizon.
- The 1-minute incremental flow coefficient was negative, with a day-bootstrap
  interval spanning zero.
- The 5-, 15- and 60-minute coefficients had intervals spanning zero.
- Incremental R² was below the required floor at 1 and 60 minutes.
- The highest-intensity quartile had continuation-aligned means of:
  - −0.007487% at 1 minute;
  - −0.043912% at 5 minutes;
  - −0.070072% at 15 minutes;
  - −0.100212% at 60 minutes.
- Positive asset replication was 1/6 at 1 minute and 0/6 at every later
  horizon.
- Positive temporal replication was 0/4 at 1 minute and 1/4 thereafter.
- No fixed horizon passed all screening components and no adjacent pair passed.

## Reversal diagnostic

The negative aligned response, particularly the approximately 10-basis-point
gross mean at 60 minutes, is consistent with temporary-impact reversal after
forced flow exhausts. It is not promoted because:

1. continuation was the frozen primary direction;
2. selecting reversal and 60 minutes after observing the curve would redefine
   the hypothesis and select a horizon ex post;
3. the effect is gross, close to a plausible execution-cost envelope and lacks
   the prospective order-book evidence needed for tradability;
4. the fourth temporal block did not reproduce the negative direction.

This diagnostic is retained in the knowledge base but cannot reopen H01 or
justify a reversal strategy.

## Decision

The liquidation-cascade continuation mechanism lacks sufficient incremental
size, cross-asset stability and temporal replication to justify Stage 4.
Formal protocolization, Holm testing, holdout opening and Deribit replication
are not scientifically warranted. H01 is closed as `REJECTED`.
