# DISCOVERY V2 — V2-H01 D1 ACQUISITION AND STRUCTURAL QA

## Resultado mecânico

**D1_QA_MECHANICAL_FAIL**

Este resultado é exclusivamente mecânico. H01 continua `SELECTED_PENDING_DATA`, não ativa e não testada.

## Aquisição

- Objetos no inventário: **1440**
- Checksum válido: **1440**
- Downloads válidos nesta execução: **1440**
- Raw reutilizado e revalidado: **0**
- Falhas: **0**
- Raw: `/workspace/user_data/discovery_v2/h01/d1/raw`
- Arquivos raw válidos: **1440**
- Bytes raw: **321304758**

## QA por família

| Família | Objetos | Checksum | ZIP válido | QA PASS | Duplicatas | Missing 5m | Intervalos irregulares |
|---|---|---|---|---|---|---|---|
| spot_klines_5m | 240 | 240 | 240 | 240 | 0 | 0 | 0 |
| usd_m_perp_klines_5m | 240 | 240 | 240 | 240 | 0 | 0 | 0 |
| usd_m_markPriceKlines_5m | 240 | 240 | 240 | 240 | 0 | 2880 | 10 |
| usd_m_indexPriceKlines_5m | 240 | 240 | 240 | 240 | 0 | 2880 | 10 |
| usd_m_premiumIndexKlines_5m | 240 | 240 | 240 | 240 | 0 | 2880 | 10 |
| usd_m_fundingRate | 240 | 240 | 240 | 240 | 0 | NA | 12310 |

`Missing 5m` é `NA` para funding, que não possui grade de cinco minutos.

## QA por ativo

| Ativo | Checksum | ZIP válido | QA PASS | Sincronização comum | Sync gate | Funding gate |
|---|---|---|---|---|---|---|
| ADAUSDT | 144 | 144 | 144 | 99.863014% | PASS | PASS |
| AVAXUSDT | 144 | 144 | 144 | 99.863014% | PASS | PASS |
| BNBUSDT | 144 | 144 | 144 | 99.863014% | PASS | PASS |
| BTCUSDT | 144 | 144 | 144 | 99.863014% | PASS | PASS |
| DOGEUSDT | 144 | 144 | 144 | 99.863014% | PASS | PASS |
| ETHUSDT | 144 | 144 | 144 | 99.863014% | PASS | PASS |
| LINKUSDT | 144 | 144 | 144 | 99.863014% | PASS | PASS |
| LTCUSDT | 144 | 144 | 144 | 99.863014% | PASS | PASS |
| SOLUSDT | 144 | 144 | 144 | 99.863014% | PASS | PASS |
| XRPUSDT | 144 | 144 | 144 | 99.863014% | PASS | PASS |

## Critérios pré-registrados

| Critério | Resultado |
|---|---|
| downloads_1440_and_100pct_checksum | PASS |
| all_zips_valid_no_path_traversal | PASS |
| schemas_identified_or_documented | PASS |
| timestamps_parseable_ordered_normalized | PASS |
| no_material_duplicates | PASS |
| all_kline_symbol_family_coverage_ge_99_9pct | FAIL |
| sync_ge_99_5pct_for_at_least_8_assets | PASS |
| funding_ordered_no_material_gaps_for_at_least_8_assets | PASS |
| holdout_sealed_zero_outcome_inspection | PASS |
| no_gap_fill_or_raw_mutation | PASS |

## Schema e timestamp

| Família | Schemas detectados | Unidades detectadas |
|---|---|---|
| spot_klines_5m | {"kline_12cols_absent_ts0": 240} | {"ms": 60, "us": 180} |
| usd_m_perp_klines_5m | {"kline_12cols_present_ts0": 240} | {"ms": 240} |
| usd_m_markPriceKlines_5m | {"kline_12cols_present_ts0": 240} | {"ms": 240} |
| usd_m_indexPriceKlines_5m | {"kline_12cols_present_ts0": 240} | {"ms": 240} |
| usd_m_premiumIndexKlines_5m | {"kline_12cols_present_ts0": 240} | {"ms": 240} |
| usd_m_fundingRate | {"funding_3cols_present_ts0": 240} | {"ms": 240} |

A mudança documentada de timestamp spot a partir de 2025-01 foi detectada por arquivo e registrada na matriz. Futures não herdou essa premissa: sua unidade foi detectada independentemente.

## Holdout

- Development: `2024-07-01T00:00:00Z` a `2025-12-31T23:59:59.999Z`.
- `SEALED_HISTORICAL_HOLDOUT`: `2026-01-01T00:00:00Z` a `2026-06-30T23:59:59.999Z`.
- Holdout permanece selado para qualquer análise econômica.
- Replicação prospectiva futura continua necessária.

## Limites observados

- Nenhum retorno, carry, PnL, correlação ou regressão foi calculado.
- Nenhuma média/distribuição de preço ou funding foi produzida.
- Funding foi lido apenas para schema, parseabilidade numérica e timestamps.
- Nenhum gap foi preenchido e nenhum raw foi corrigido.
- D1 não ativa H01 e não inicia protocolo experimental.
