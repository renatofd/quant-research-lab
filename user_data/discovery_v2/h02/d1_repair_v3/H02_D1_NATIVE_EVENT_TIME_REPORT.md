# Discovery V2 H02 — Definitive D1 QA

Decision: `D1_QA_FAIL`

Metrics are asynchronous snapshots. Native `create_time` values remain unrounded and are used only through backward as-of joins, preventing lookahead. Each asset has 210,235/210,240 observations (99.997621766%), above the unchanged 99.9% gate. Timestamps are unique and ordered, checksums and schemas passed, and no value was filled or reconstructed. All prior reports remain immutable.
