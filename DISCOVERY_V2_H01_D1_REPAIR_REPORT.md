# Discovery V2 — H01 D1 Repair Report

## Resultado

**RECOVERY_NOT_POSSIBLE_SAME_SOURCE_ENDPOINT**

O resultado permanece **D1_QA_MECHANICAL_FAIL**. O gate de cobertura continua em **99,9%** e a cobertura observada continua em **99,8630136986%**. D2 não foi executado.

## Origem exata da falha

A lacuna é um dia UTC completo e idêntico nos dez símbolos e nas três famílias afetadas:

| Família | Símbolos | Ausentes/ativo | Ausentes totais | Intervalo |
|---|---:|---:|---:|---|
| `usd_m_markPriceKlines_5m` | 10 | 288 | 2.880 | `2026-06-29T00:00:00Z` a `2026-06-29T23:55:00Z` |
| `usd_m_indexPriceKlines_5m` | 10 | 288 | 2.880 | `2026-06-29T00:00:00Z` a `2026-06-29T23:55:00Z` |
| `usd_m_premiumIndexKlines_5m` | 10 | 288 | 2.880 | `2026-06-29T00:00:00Z` a `2026-06-29T23:55:00Z` |

Os 288 timestamps ausentes são a grade de cinco minutos de `2026-06-29T00:00:00Z` até `2026-06-29T23:55:00Z`, inclusive. A lista explícita dos 288 timestamps está em `gap.missing_timestamps_utc` no relatório JSON.

Símbolos: `ADAUSDT`, `AVAXUSDT`, `BNBUSDT`, `BTCUSDT`, `DOGEUSDT`, `ETHUSDT`, `LINKUSDT`, `LTCUSDT`, `SOLUSDT`, `XRPUSDT`.

Não existe offset entre mark, index e premium: as três famílias perderam exatamente o mesmo conjunto de timestamps. Existe desalinhamento estrutural contra spot e perp, que contêm os 288 timestamps para todos os dez ativos.

## Investigação de recuperação oficial

Foram verificados os 30 caminhos diários exatos em `data.binance.vision` e seus 30 objetos `.CHECKSUM`:

- 30/30 ZIPs diários de 29/06/2026: **HTTP 404**;
- 30/30 checksums diários correspondentes: **HTTP 404**;
- controles adjacentes BTC de 28/06 e 30/06 nas três famílias: ZIP e checksum **HTTP 200**;
- 30/30 checksums mensais atuais: **HTTP 200** e idênticos aos SHA-256 dos arquivos D1 locais.

Logo, não existe arquivo diário oficial para o dia perdido nem versão mensal corrigida. Outra API, outro schema, agregação de 1m, interpolação ou preenchimento sintético violariam as restrições e não foram usados.

## Integridade e auditoria

- Os 30 arquivos raw afetados mantiveram os mesmos SHA-256 antes e depois.
- Os seis artefatos D1 originais mantiveram os mesmos SHA-256.
- Holdout: **SEALED**, hash inalterado.
- Somente a primeira coluna de timestamps foi utilizada; valores de preço/funding foram ignorados e não reportados.
- Nenhum outcome, retorno, carry, PnL, correlação ou regressão foi calculado.
- Nenhum dado foi preenchido, substituído ou modificado.
- Hipótese, protocolo e gate não foram alterados.
- D2 não foi executado.

## Decisão técnica

A recuperação legítima não é possível sob os requisitos de mesma fonte, endpoint, schema, período e checksum. O D1 permanece reprovado e a execução deve parar antes de D2.

Os detalhes por símbolo/família, URLs, códigos HTTP, hashes mensais, controles adjacentes e a lista completa dos timestamps constam em `DISCOVERY_V2_H01_D1_REPAIR_REPORT.json`.
