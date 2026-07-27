# H06 Stage 0 — On-chain Flows

**Decisão:** `STAGE0_PASS` — 2026-07-24

Mecanismo: transferências para exchanges podem representar oferta vendável; saídas
podem retirar inventário líquido. Fluxos de stablecoins para exchanges podem medir
capacidade de compra. A hipótese exige endereço de exchange conhecido no instante da
previsão, direção da transferência e timestamp causal.

A literatura encontra efeitos heterogêneos: USDT inflow pode prever BTC/ETH, ETH
inflow pode prever ETH negativamente e BTC inflow pode não prever BTC. Outro estudo
separa transações peer-to-peer e exchange-related.

- https://arxiv.org/abs/2411.06327
- https://doi.org/10.1016/j.jimonfin.2025.103415

Essa heterogeneidade torna o teste valioso, mas impede usar contagem bruta de
transações como substituto.
