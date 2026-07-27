# H01 — Liquidation Cascades: Stage 1 Data Inventory

Decision: **PASS TO STAGE 2**  
Inventory date: 2026-07-24  
No Discovery V3 market data was downloaded and no outcome was inspected.

## Minimum scientific data contract

H01 cannot be tested from price, volume or volatility proxies. The minimum
contract requires:

1. actual forced-liquidation events with native timestamps, direction, executed
   size and price;
2. the matching perpetual contract price after the event;
3. mark and index prices to separate venue dislocation from underlying movement;
4. spot price to test transmission outside the liquidated contract;
5. open interest and funding as state controls, not as signal substitutes;
6. a chronological development/holdout split sealed before any outcome is read.

Trade-level or order-book data would improve execution modelling but is not
required to decide whether forced flow has an incremental forward response.
Operational promotion would require a later prospective test with realistic
latency and slippage.

## Existing local data

The read-only Discovery V2 archive contains official Binance data for ten USD-M
assets from July 2024 through June 2026:

| Dataset | Files | Approximate size | Reuse |
|---|---:|---:|---|
| Spot 5-minute klines | 240 | 93.4 MB | Partial auxiliary overlap only |
| USD-M perpetual 5-minute klines | 240 | 88.4 MB | Not the same contract family |
| USD-M mark 5-minute klines | 240 | 46.1 MB | Not the same contract family |
| USD-M index 5-minute klines | 240 | 50.5 MB | Auxiliary underlying control |
| USD-M premium 5-minute klines | 240 | 42.8 MB | Optional state control |
| USD-M funding | 240 | 0.2 MB | Optional state control |
| USD-M 5-minute metrics | 14,600 | 83.7 MB | Partial auxiliary overlap |

These files do **not** contain actual liquidation events. They cannot establish
H01 and will not be copied or modified. Their checksums and provenance may be
referenced only if a later alignment audit shows an exact overlap.

## Official-source audit

### Binance — selected primary source

The official Binance Data Vision S3 inventory exposes
`futures/cm/daily/liquidationSnapshot` with both ZIP files and official checksum
sidecars. The inventory contains 118 contract prefixes, including perpetual
contracts for BTC, ETH, BNB, ADA, LINK and LTC.

For `BTCUSD_PERP`, the official inventory contains 944 objects: 472 daily ZIPs
and 472 checksum files, from 2023-06-25 through 2024-10-14. The corresponding
USD-M prefix for `BTCUSDT` contains zero objects. Therefore, H01 must use the
COIN-M contract family and may not mix the USD-M V2 outcomes into its primary
panel.

Official inventory:

- <https://data.binance.vision/>
- <https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?delimiter=/&prefix=data/futures/cm/daily/liquidationSnapshot/>
- <https://github.com/binance/binance-public-data>

Candidate primary panel, subject to mechanical common-window QA in Stage 2:

- `BTCUSD_PERP`
- `ETHUSD_PERP`
- `BNBUSD_PERP`
- `ADAUSD_PERP`
- `LINKUSD_PERP`
- `LTCUSD_PERP`

Required official Binance families:

- COIN-M daily `liquidationSnapshot`;
- COIN-M 1-minute perpetual `klines`;
- COIN-M 1-minute `markPriceKlines`;
- COIN-M 1-minute `indexPriceKlines`;
- COIN-M `metrics` for open interest and market state;
- spot 1-minute `klines` for the matching underlying where an official liquid
  spot pair exists.

All available official `.CHECKSUM` sidecars are mandatory. An asset is excluded
mechanically, before outcomes, if the event archive or matching prices do not
cover the common development and holdout windows.

### Bybit

Bybit publishes historical public trade files, and its official
`allLiquidation.{symbol}` stream reports full liquidations every 500 ms.
However, the full stream was introduced on 2025-02-20 and the official interface
is real-time; no complete historical full-liquidation archive with checksum
provenance was identified. Bybit cannot supply the primary historical event
panel without prospective collection.

Official references:

- <https://public.bybit.com/trading/>
- <https://bybit-exchange.github.io/docs/v5/websocket/public/all-liquidation>
- <https://bybit-exchange.github.io/docs/changelog/v5>

### OKX

OKX documents public liquidation-order information, but Stage 1 did not identify
an official immutable bulk archive with complete historical coverage and
checksum sidecars comparable to Binance Data Vision. It is not selected for the
primary panel.

Official reference: <https://www.okx.com/docs-v5/en/>

### Deribit

Deribit's public historical trade API includes an explicit `liquidation` field
(`M`, `T`, or `MT`) and its dedicated history service documents public trade
history since launch. This is a legitimate independent replication source for
BTC and ETH, but retrieving the complete trade tape is materially more
expensive than the Binance event archive. It is reserved for independent
replication only if the Binance development evidence survives Stage 3.

Official references:

- <https://docs.deribit.com/api-reference/market-data/public-get_last_trades_by_instrument_and_time>
- <https://history.deribit.com/api/v2/public/get_last_trades_by_instrument_and_time>

### Coinbase

Coinbase documents public real-time order and trade feeds for its spot and
international markets. Stage 1 found no official historical public feed that
labels forced-liquidation trades. It is not usable as the H01 event source.

Official reference:
<https://docs.cdp.coinbase.com/international-exchange/websocket-feed/websocket-overview>

## Stage 2 acquisition boundary

Stage 2 will acquire only the six-candidate Binance COIN-M panel and the data
families listed above. It will:

- discover the exact common interval from official inventories;
- download raw archives and checksum sidecars without alteration;
- verify provider SHA-256 values and ZIP CRC;
- record URL, retrieval time, size, ETag when available and local SHA-256;
- validate schemas, timestamps, duplicates, ordering, coverage and cross-source
  alignment without calculating forward returns;
- freeze a chronological holdout from the last 20% of the mechanically valid
  common interval;
- write a seal containing only dates, file hashes and schema metadata.

Deribit data will not be downloaded in Stage 2 unless the Binance development
effect survives Stage 3. This cost gate avoids downloading a very large complete
trade tape before there is evidence worth replicating.

## Stage 1 decision

The necessary non-proxy event data exists publicly, officially and with
provider checksums. H01 is therefore executable and advances to Stage 2. The
archive is historical and ends in 2024, so it can support discovery and sealed
historical holdout, but not final prospective confirmation.
