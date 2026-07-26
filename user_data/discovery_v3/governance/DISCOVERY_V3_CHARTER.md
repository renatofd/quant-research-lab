# Discovery V3 — Scientific Charter

Status: ACTIVE  
Started: 2026-07-24  
Objective: determine whether a genuine economic edge exists; do not build a bot.

## Fixed hypothesis order

1. H01 — Liquidation Cascades
2. H02 — Spot × Perpetual Divergence
3. H03 — Extreme Funding
4. H04 — Cross-Exchange Leadership
5. H05 — Liquidity Regimes
6. H06 — On-chain Flows
7. H07 — ETF Flows
8. H08 — Options Market
9. H09 — Order Flow / CVD
10. H10 — Cross-Asset Relative Strength

The order is immutable. Only one hypothesis may be active at a time.

## Mandatory stage gates

Every hypothesis must pass, in order:

0. literature and economic-mechanism review;
1. data inventory;
2. acquisition, provenance, QA, versioning, checksums and sealed holdout;
3. exploratory research using development data only;
4. immutable pre-registration;
5. isolated scientific implementation under `user_data/discovery_v3/`;
6. development, holdout, bootstrap, placebo, negative-control and sensitivity execution;
7. classification and ledger update.

Valid terminal classifications are `CONFIRMED`, `REJECTED`, `INCONCLUSIVE` and
`BLOCKED`.

## Permanent constraints

- No strategy, bot, operational rule, Hyperopt or parameter search before a
  hypothesis is confirmed.
- No searching for alternative lags or repeating a test to improve a result.
- No outcomes may be inspected before the holdout is sealed.
- A hypothesis is stopped when its mechanism is refuted, its effect is below
  operational relevance, replication fails, holdout is negative, controls fail,
  or expected information no longer justifies cost.
- Data sources must be public or officially documented.
- Existing projects and operational code are read-only to Discovery V3.

## Program stopping conditions

The program ends when one hypothesis is strong enough for prospective
confirmation, all hypotheses are closed, or permanent data unavailability makes
continuation impossible.
