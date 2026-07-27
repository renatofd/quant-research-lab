# Discovery V2 H01 — D2–D4 Preregistration v1.0.0

This protocol was frozen with the historical holdout sealed and no economic outcome inspected. It does not revise an older economic protocol: none existed. It operationalizes the already approved H01/D0 mechanism without optimization.

## Economic hypothesis

Persistent positive perpetual funding and a positive spot–perpetual basis reflect levered long demand. A fully funded long-spot/short-perpetual position supplies balance sheet and receives carry. The effect is real only if it remains positive after a fixed conservative cost envelope, is directionally neutral and replicates across assets and time.

The mechanism is grounded in the cash-and-carry and perpetual-futures literature: [BIS Working Paper 1087](https://www.bis.org/publ/work1087.htm) and [Fundamentals of Perpetual Futures](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4301150).

## Frozen economic observation

At official funding time `t`, the observed funding rate and the last completed five-minute spot/perpetual candle are available. Eligibility requires both funding and basis to be strictly positive. If flat, both legs enter at the first common candle open strictly after `t`. The fully funded matched position stays open while eligibility persists and exits at the first common open after an ineligible funding event. Funding received or paid while the position is open is included. Stage-boundary positions are force-closed and flagged.

Net episode return equals the long-spot return plus the short-perpetual return plus funding cashflows, minus a single immutable 0.6% roundtrip envelope per matched notional. Two units of capital are committed per matched unit. No leverage, reverse carry, spot borrow, favorable fee tier or maker rebate is assumed.

For any globally excluded UTC day, an open episode is force-closed at the last common candle close before the block. Events inside the block are ignored, and re-entry is allowed only from the first eligible funding event after it. This rule is identical for the real missing block and every matched sensitivity block.

## D2 — Development

Development is July 2024 through December 2025. Uncertainty uses 10,000 UTC entry-week cluster-bootstrap resamples with seed 4101. Holm correction is applied separately to asset, temporal-block and negative-control families.

D2 passes only if all gates in the JSON preregistration pass: sufficient episodes for at least eight assets; positive aggregate effect with lower 95% bound above zero; at least 10% annualized committed-capital return; cross-asset and three-block temporal replication; failure of both negative controls; and a market-neutrality beta no larger than 0.10 in magnitude whose interval contains zero.

## D3 — Sealed historical holdout

The holdout is January–June 2026, opened exactly once after the protocol and instrument hashes are frozen. The same pipeline and gates apply, with the preregistered minimum of ten completed episodes per asset and three fixed two-month temporal blocks.

## D4 — Documented-limitation sensitivity

The official missing day is removed globally from all assets and feeds. Then every eligible fully observed UTC day of equal length is deleted globally, one at a time, and the exact D2/D3 decisions are rerun. If any deletion changes either stage decision or the final conclusion, H01 is `INCONCLUSIVE`. Sensitivity cannot rescue a failed primary gate.

Passing all historical gates yields only `CONFIRMED_READY_FOR_PROSPECTIVE_CONFIRMATION`. It never authorizes a bot; prospective replication and execution-level viability remain mandatory.
