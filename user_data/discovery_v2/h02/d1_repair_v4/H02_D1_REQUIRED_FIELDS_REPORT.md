# Discovery V2 H02 — Definitive Required-Field QA

Decision: `D1_QA_PASS_REQUIRED_FIELDS`

All required H02 fields (open interest, open-interest value and taker-flow ratio) are parseable at every observed timestamp. Each asset has 210,235/210,240 observations (99.997621766%), above the unchanged 99.9% gate. Optional trader long/short ratios contain documented blanks and are excluded, never imputed. Native publication timestamps are retained for strict backward as-of joins.
