# DISCOVERY V2 ? V2-H01 D0 MANIFEST-ONLY REPORT

## Resultado mec?nico

**D0_MECHANICAL_INCONCLUSIVE**

Este r?tulo ? exclusivamente mec?nico. N?o ? decis?o cient?fica, n?o testa V2-H01 e n?o autoriza D1.

- Combina??es esperadas: **1.440**
- Objetos presentes: **1440**
- Objetos ausentes: **0**
- Ambiguidades: **0**
- Falhas de consulta: **0**
- Bytes declarados pelos manifests, sem download: **321304758**
- Objetos presentes com `.CHECKSUM`: **1440 / 1440 (100.0000%)**
- Ativos completos nas seis fam?lias: **ADAUSDT, AVAXUSDT, BNBUSDT, BTCUSDT, DOGEUSDT, ETHUSDT, LINKUSDT, LTCUSDT, SOLUSDT, XRPUSDT**
- Bytes de conte?do de mercado baixados: **0**
- D1 iniciado: **n?o**

## Escopo congelado

- Meses: 2024-07 a 2026-06, 24 meses completos.
- S?mbolos: ADAUSDT, AVAXUSDT, BNBUSDT, BTCUSDT, DOGEUSDT, ETHUSDT, LINKUSDT, LTCUSDT, SOLUSDT, XRPUSDT.
- Fam?lias: spot_klines_5m, usd_m_perp_klines_5m, usd_m_markPriceKlines_5m, usd_m_indexPriceKlines_5m, usd_m_premiumIndexKlines_5m, usd_m_fundingRate.
- Fonte: Binance Data Collection e backend oficial de listagem S3.

## Cobertura por fam?lia

| Fam?lia | Esperado | Presente | Ausente | Amb?guo | Consulta falhou | Checksum presente | Bytes declarados |
|---|---|---|---|---|---|---|---|
| spot_klines_5m | 240 | 240 | 0 | 0 | 0 | 240 | 93366295 |
| usd_m_perp_klines_5m | 240 | 240 | 0 | 0 | 0 | 240 | 88365788 |
| usd_m_markPriceKlines_5m | 240 | 240 | 0 | 0 | 0 | 240 | 46053489 |
| usd_m_indexPriceKlines_5m | 240 | 240 | 0 | 0 | 0 | 240 | 50519954 |
| usd_m_premiumIndexKlines_5m | 240 | 240 | 0 | 0 | 0 | 240 | 42786048 |
| usd_m_fundingRate | 240 | 240 | 0 | 0 | 0 | 240 | 213184 |

## Cobertura por ativo

| Ativo | Presente | Ausente | Amb?guo | Consulta falhou | 6 fam?lias ? 24 |
|---|---|---|---|---|---|
| ADAUSDT | 144 | 0 | 0 | 0 | SIM |
| AVAXUSDT | 144 | 0 | 0 | 0 | SIM |
| BNBUSDT | 144 | 0 | 0 | 0 | SIM |
| BTCUSDT | 144 | 0 | 0 | 0 | SIM |
| DOGEUSDT | 144 | 0 | 0 | 0 | SIM |
| ETHUSDT | 144 | 0 | 0 | 0 | SIM |
| LINKUSDT | 144 | 0 | 0 | 0 | SIM |
| LTCUSDT | 144 | 0 | 0 | 0 | SIM |
| SOLUSDT | 144 | 0 | 0 | 0 | SIM |
| XRPUSDT | 144 | 0 | 0 | 0 | SIM |

## Cobertura por m?s

| M?s | Presente | Ausente | Amb?guo | Consulta falhou |
|---|---|---|---|---|
| 2024-07 | 60 | 0 | 0 | 0 |
| 2024-08 | 60 | 0 | 0 | 0 |
| 2024-09 | 60 | 0 | 0 | 0 |
| 2024-10 | 60 | 0 | 0 | 0 |
| 2024-11 | 60 | 0 | 0 | 0 |
| 2024-12 | 60 | 0 | 0 | 0 |
| 2025-01 | 60 | 0 | 0 | 0 |
| 2025-02 | 60 | 0 | 0 | 0 |
| 2025-03 | 60 | 0 | 0 | 0 |
| 2025-04 | 60 | 0 | 0 | 0 |
| 2025-05 | 60 | 0 | 0 | 0 |
| 2025-06 | 60 | 0 | 0 | 0 |
| 2025-07 | 60 | 0 | 0 | 0 |
| 2025-08 | 60 | 0 | 0 | 0 |
| 2025-09 | 60 | 0 | 0 | 0 |
| 2025-10 | 60 | 0 | 0 | 0 |
| 2025-11 | 60 | 0 | 0 | 0 |
| 2025-12 | 60 | 0 | 0 | 0 |
| 2026-01 | 60 | 0 | 0 | 0 |
| 2026-02 | 60 | 0 | 0 | 0 |
| 2026-03 | 60 | 0 | 0 | 0 |
| 2026-04 | 60 | 0 | 0 | 0 |
| 2026-05 | 60 | 0 | 0 | 0 |
| 2026-06 | 60 | 0 | 0 | 0 |

## Crit?rios pr?-registrados

| Crit?rio | Resultado |
|---|---|
| at_least_8_assets_all_6_families_24_months | PASS |
| spot_and_perp_5m_present | PASS |
| mark_index_premium_and_funding_present | PASS |
| funding_present | PASS |
| at_least_99pct_present_objects_have_checksum | PASS |
| no_structural_listing_query_failure | PASS |
| defensible_versioned_operational_cost_route_resolved | FAIL |
| holdout_unconsumed_and_no_outcome_inspection | PASS |

## Rotas documentais de custos

| Requisito | Classifica??o | URL | Evid?ncia |
|---|---|---|---|
| contract_specifications_point_in_time | CURRENT_ONLY | https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Exchange-Information | Official current exchange-information documentation is known; no official versioned historical archive was established by this manifest-only audit. |
| fee_schedules_point_in_time | CURRENT_ONLY | https://www.binance.com/en/fee/trading | Official current fee information is known; no point-in-time versioned fee schedule was established by the official manifests. No private endpoint was queried. |
| borrow_margin_costs_point_in_time | NOT_FOUND | ? | No official versioned point-in-time route was established from the reviewed official manifests/catalog. No private endpoint or API-key route was queried. |

As rotas `CURRENT_ONLY` foram registradas como limita??o e n?o convertidas em hist?rico point-in-time. Nenhum endpoint privado ou autenticado foi consultado.

## Metadados de modifica??o e ETag

- `LastModified` m?nimo: 2024-08-08T08:49:03.000Z
- `LastModified` m?ximo: 2026-07-06T09:45:45.000Z
- Objetos com ETag: 1440
- ETags ?nicos: 1440
- Ocorr?ncias duplicadas de ETag: 0

A distribui??o mensal completa de `LastModified` est? no relat?rio JSON. ETag e LastModified s?o tratados apenas como metadados, n?o como evid?ncia de conte?do correto.

## Gaps e assimetrias

Nenhum gap ou assimetria no n?vel de manifest.

Todos os gaps est?o enumerados no CSV e no JSON. Nenhuma aus?ncia foi inferida quando a consulta falhou.

## Integridade e limites

- Nenhum ZIP ou CSV de mercado foi requisitado, baixado, aberto ou amostrado.
- Somente XML de listagem e texto `.CHECKSUM` foram transferidos.
- Nenhum pre?o, retorno, funding realizado ou outcome foi inspecionado.
- A presen?a no manifest n?o substitui QA candle/event-level de D1.
- Holdout permanece n?o consumido.
- V2-H01 permanece `SELECTED_PENDING_DATA`, n?o ativa e n?o testada.

## Pr?xima etapa

D1 **n?o foi iniciado**. Qualquer avan?o depende de revis?o humana do resultado D0 e nova autoriza??o expl?cita.
