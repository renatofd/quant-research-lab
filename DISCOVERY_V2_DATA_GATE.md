# DISCOVERY V2 — EXTERNAL DATA GATE

## Decisão

**PAUSED_AT_EXTERNAL_DATA_GATE**

Nenhuma hipótese V2 está ativa ou executável. Este documento não autoriza download, compra, consulta de endpoint, protocolo experimental ou análise.

## Evidência do inventário local

A auditoria documental encontrou exatamente dez arquivos de mercado em `user_data/data/binance`, todos spot OHLCV 5m em Feather:

- `ADA_USDT-5m.feather`
- `AVAX_USDT-5m.feather`
- `BNB_USDT-5m.feather`
- `BTC_USDT-5m.feather`
- `DOGE_USDT-5m.feather`
- `ETH_USDT-5m.feather`
- `LINK_USDT-5m.feather`
- `LTC_USDT-5m.feather`
- `SOL_USDT-5m.feather`
- `XRP_USDT-5m.feather`

`user_data/config.json` identifica exchange `binance`, trading mode `spot` e a mesma whitelist de dez pares. Não foi identificado dataset local de derivados, microestrutura, outras exchanges, ETF, on-chain, opções ou macro point-in-time.

## Gap por família

| Família V2 | Hipóteses | Gap impeditivo |
|---|---|---|
| Funding, basis e OI | H01, H02, H06, H13 | Perp/futures, mark/index, funding, basis, OI, specs, fees, borrow/margin |
| Price discovery spot–perp/multi-exchange | H03, H14 | Trades/quotes/depth sincronizados, clocks e múltiplos venues |
| ETF e macro | H04, H05 | Eventos e valores point-in-time, calendário de publicação, mercados de controle |
| Order flow e livro | H07, H10 | Trades assinados, L2/L3, sequence IDs, latência e reconstrução de gaps |
| Liquidações | H08 | Eventos de liquidação, OI, mark/index, margem, trades e livro |
| Opções | H09 | Cadeias point-in-time, bid/ask, IV surface, rates e expiries |
| On-chain e stablecoins | H11, H12 | Blockchain, labels versionados, mint/burn, exchange/treasury flows |
| CEX–DEX | H15 | Blocos/mempool, pools, gas, MEV, depth CEX, bridges e inventário |

OHLCV existente não é substituto válido para esses contratos de dados.

## Dataset mínimo para destravar V2-H01

1. Binance spot e USD-M perpetual para os mesmos dez ativos.
2. Granularidade preferencial de 1m e mínima de 5m.
3. Mark price, index price, premium/basis e funding events.
4. Cobertura contínua mínima de 24 meses, em UTC.
5. Contract specifications e fee schedules versionados no tempo.
6. Custos de borrow/margin quando aplicáveis.
7. Hashes, proveniência, timestamps de aquisição e inventário imutável.
8. Holdout temporal prospectivo reservado antes da inspeção de outcomes.
9. Pelo menos oito ativos com interseção temporal válida.
10. Nenhum endpoint de retenção curta tratado como histórico completo.

Open interest e liquidações não são requisitos de H01; pertencem a H02 e H08 e não devem ampliar a aquisição mínima de H01.

## Gate de QA antes de qualquer protocolo

O dataset só pode ser aceito se todos os itens abaixo forem auditados e aprovados:

- cobertura individual e comum;
- sincronização spot/perp, funding, mark e index;
- unicidade e ordenação de timestamps;
- gaps, interrupções e política explícita de missing data;
- timezone UTC e timestamps de evento economicamente corretos;
- survivorship, listings, delistings e símbolos/contratos;
- mudanças de especificação, tick/lot size e settlement;
- funding schedule e eventos ausentes/duplicados;
- fees point-in-time, borrow/margin e premissas de capacidade;
- proveniência, licença, retenção e integridade por hash;
- separação irrevogável entre development e holdout prospectivo;
- confirmação de que nenhuma inspeção de outcome ocorreu no holdout.

Falha em qualquer item material mantém o programa pausado. O gate não pode ser contornado com candles spot, preenchimento silencioso ou dados revisados sem vintage.

## Retenção e proveniência

Antes de aquisição, um contrato de dados deverá definir fonte oficial, endpoints, limites de retenção, frequência de captura, versionamento, licença, política de correção e reconstrução. A documentação oficial indicada para eventual avaliação é [Binance USDⓈ-M Futures Market Data](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data); ela não foi consultada nem executada nesta fase documental.

## Próxima ação permitida

`HUMAN_DECISION_ON_DATA_ACQUISITION_ONLY`

Uma autorização humana separada é necessária antes de qualquer download, custo externo ou implementação. Até então, V2-H01 permanece `SELECTED_PENDING_DATA`, não ativa e não testada.
