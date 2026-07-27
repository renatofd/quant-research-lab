# Discovery V3 — Inventário final de dados

| Acervo | Objetos | Bytes | Fonte | Uso |
|---|---:|---:|---|---|
| H01 Binance COIN-M liquidation/prices | 5.163 | 555.219.738 | data.binance.vision | H01 dev; holdout preservado |
| H02 Binance julho USD-M/spot/controles/funding | 1.160 | 10.302.026 | data.binance.vision + fapi.binance.com | holdout H02 selado |
| H04 Bybit linear 5m raw API | 2.170 | 50.048.568 | api.bybit.com | dev + holdout fisicamente controlados |
| H04 boundary dev-only | 10 | 54.078 | api.bybit.com | isolamento 30/06 sem abrir 01/07 |
| V2 Binance USD-M/spot | 1.440 | 321.304.758 | data.binance.vision | referência read-only de desenvolvimento |

Todos os acervos adquiridos preservam raw e hashes; arquivos Binance possuem
checksums oficiais quando fornecidos. Não houve imputação. Os dados V2 não foram
modificados.
