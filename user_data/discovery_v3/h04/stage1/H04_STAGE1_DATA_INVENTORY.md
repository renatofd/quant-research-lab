# Discovery V3 — H04 Stage 1

## Inventário de dados

**Decisão:** `STAGE1_PASS_FOR_LOW_COST_SCREEN`  
**Data:** 2026-07-24

## Binance

O acervo oficial e imutável do Discovery V2 contém klines USD-M de 5 minutos para
dez ativos entre 2024-07-01 e 2026-06-30, com cobertura de 100%, checksums oficiais
e QA. Será reutilizado somente por referência e classificado como desenvolvimento.

## Bybit

O endpoint oficial público `GET /v5/market/kline`:

- cobre contratos USDT (`category=linear`);
- aceita intervalo `5`;
- recebe `start` e `end` em milissegundos;
- retorna até 1.000 candles em ordem reversa;
- não exige credencial;
- não fornece checksum oficial.

Fonte: https://bybit-exchange.github.io/docs/v5/market/kline

O endpoint foi verificado mecanicamente para BTCUSDT em julho de 2024. Ele permite
adquirir o mesmo painel e período. Cada resposta raw deverá ser preservada comprimida
com URL, tempo, SHA-256 local, retCode e intervalo coberto.

## Contrato

- ativos: os mesmos dez da H02;
- venues: Binance USD-M e Bybit linear;
- moeda: USDT;
- frequência: 5 minutos;
- desenvolvimento: 2024-07-01 a 2026-06-30;
- holdout: 2026-07-01 a 2026-07-23, selado antes de outcomes;
- dados Binance: referência read-only;
- dados Bybit: aquisição oficial API e cache imutável.

## Limitações

Candles não observam latência subsegundo, bid-ask ou fila. Portanto:

- ausência de efeito a 5m rejeita H04 para execução não-HFT;
- presença de efeito não confirma vantagem e exige trades/order book;
- relógios, duplicatas, lacunas e candle ainda aberto devem reprovar QA;
- o holdout curto pode refutar, mas não confirmar sozinho.

## Gates Stage 2

- respostas oficiais com `retCode=0`;
- cobertura e sincronização Binance/Bybit ≥99,9% por ativo;
- timestamps únicos, crescentes, UTC e múltiplos de 5 minutos;
- nenhum candle incompleto;
- hashes/proveniência de 100% das respostas;
- holdout selado antes de retornos, correlações ou regressões;
- nenhuma imputação.

## Decisão

`STAGE1_PASS_FOR_LOW_COST_SCREEN`. Dados tick-level são deliberadamente adiados.
