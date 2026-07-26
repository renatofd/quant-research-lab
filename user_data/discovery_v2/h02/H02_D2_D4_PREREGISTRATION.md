# Discovery V2 H02 — D2–D4 Preregistration

H02 tests one mechanism: whether extreme positive funding becomes economically informative when it coincides with high positive OI growth and taker-buy dominance. Every metric is joined backward using its native publication time, strictly before the decision event.

Crowding requires positive funding and OI growth, both in the top cross-sectional quartile, plus taker ratio above one. The incremental comparison is against high positive funding events that are not crowded. A fully collateralized perpetual short is opened five minutes after the funding observation and closed five minutes after the next funding event. Net return deducts the immutable 0.2% roundtrip envelope.

Development and sealed holdout use 10,000 event-week cluster bootstraps, cross-asset and three-block temporal replication, Holm correction and two negative OI controls. All gates in the JSON must pass. No threshold, quartile, horizon, cost or control may change after outcomes.
