# H01 — Stage 2 Final Data Decision

Decision: **PASS TO STAGE 3**  
Decision date: 2026-07-24  
Holdout: **SEALED**

## Evidence chain

- 5,163 official Binance Data Vision archives were acquired.
- Every acquired archive matched its provider SHA-256 sidecar.
- All ZIPs passed CRC, schema, timestamp ordering and structural QA.
- Raw liquidation archives contained 245,912 rows.
- The provider duplicated liquidation rows. The immutable raw files were
  preserved; a derived, hashed layer collapsed only exact full-row duplicates.
- The normalized layer contains 122,941 distinct rows and has SHA-256
  `15ed6ca3123099a46fe4a5a0c55c569f4a6f588576af9806e16b4214d7a5df9d`.

## Coverage failure and legitimate repair

The first complete minute-grid audit failed:

- four-way aligned coverage was 99.157058%;
- 5,760 minutes were absent from every COIN-M price family on
  2023-08-28 through 2023-08-31;
- a further 30 mark/index minutes were absent on 2024-06-07.

The gate was not relaxed. The same official source contained daily archives for
the four missing full days. Exactly 84 daily ZIPs were retrieved using the same
provider, market, schema and interval, each with its own official checksum.
Monthly archives were not changed.

After repair:

- perpetual coverage is 100% for every asset;
- aligned perpetual/mark/index/spot coverage is 99.995632% for every asset;
- the only remaining limitation is the same 30-minute mark/index block,
  2024-06-07 09:19–09:48 UTC;
- the unchanged 99.9% PASS gate is satisfied.

Repair-manifest SHA-256:
`0120a5b7e280ecf325f6a6aa4652d9690874ec120fd70cffa7d95357c2676b36`.

## Documented limitations

1. `liquidationSnapshot` is an event-partitioned archive: less-liquid contracts
   have fewer daily objects, and every present partition contains events. An
   absent partition cannot be used as affirmative proof that the venue had zero
   liquidations. Stage 3 must use observed event minutes and draw controls only
   from event-positive days.
2. Open-interest metrics contain a large official gap around March–June 2024.
   They are an optional state diagnostic, not a mandatory predictor or filter.
   They may not be imputed.
3. The archive ends in October 2024. It supports discovery and a sealed
   historical holdout, not prospective confirmation.
4. One common 30-minute mark/index gap remains. Any event whose measurement or
   response window touches that block must be excluded mechanically.

## Holdout contract

- Development: 2023-06-25 through 2024-07-09.
- Sealed historical holdout: 2024-07-10 through 2024-10-13.
- Split rule: last 20% of the common calendar interval.
- No forward return, response, PnL, correlation or regression was computed in
  Stage 2.

## Stage 2 decision

The required actual-event and aligned-price data now pass mechanical QA under
the unchanged coverage gate. H01 advances to exploratory Stage 3. Only
development outcomes may be opened.
