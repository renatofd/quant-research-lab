# DISCOVERY V2 — RESEARCH CATALOG

## Charter

Discovery V2 é um programa científico novo para investigar mecanismos econômicos que dependem de dados ausentes no laboratório atual. O projeto anterior permanece **ARCHIVED_FINAL**: nenhuma hipótese baseada somente em OHLCV justificou bot, e nenhuma família encerrada pode ser reaberta por renomeação, parâmetros ou indicadores.

Este catálogo é uma agenda, não evidência. Nenhuma hipótese V2 foi testada, nenhuma está ativa e nenhum bot está autorizado. A escala de prioridade é `VEI / custo científico`; ela mede valor esperado de informação por custo, não probabilidade de sucesso.

## Inventário atual

- Disponível: Binance spot OHLCV 5m em Feather para ADA, AVAX, BNB, BTC, DOGE, ETH, LINK, LTC, SOL e XRP contra USDT.
- Indisponível: funding, basis, perp prices, mark/index, open interest, liquidações, maker/taker, livro L2/L3, multi-exchange, ETF flows, on-chain, opções e macro point-in-time.
- Disponibilidade local das 15 hipóteses: **NÃO**.
- Estado: **PAUSED_AT_EXTERNAL_DATA_GATE**.

## Ranking vinculante

| Ordem | ID | Hipótese | VEI | Custo | Prioridade | Overfitting | Refutação | Estado |
|---:|---|---|---:|---:|---:|---|---|---|
| 1 | V2-H01 | Carry e convergência de funding/basis | 5 | 2 | 2,50 | Baixo-médio | Fácil | SELECTED_PENDING_DATA |
| 2 | V2-H02 | Funding extremo + OI como crowding | 5 | 3 | 1,67 | Médio | Média | CATALOGUED_NOT_STARTED |
| 3 | V2-H03 | Liderança spot–perp | 5 | 3 | 1,67 | Médio | Média | CATALOGUED_NOT_STARTED |
| 4 | V2-H04 | Fluxos de ETF spot | 4 | 3 | 1,33 | Médio-alto | Média | CATALOGUED_NOT_STARTED |
| 5 | V2-H05 | Surpresas macro | 4 | 3 | 1,33 | Médio | Média | CATALOGUED_NOT_STARTED |
| 6 | V2-H06 | Dispersão de funding/carry | 4 | 3 | 1,33 | Médio-alto | Média | CATALOGUED_NOT_STARTED |
| 7 | V2-H07 | Order-flow imbalance ajustado por depth | 5 | 4 | 1,25 | Médio | Média-difícil | CATALOGUED_NOT_STARTED |
| 8 | V2-H08 | Cascatas de liquidação | 4 | 4 | 1,00 | Médio-alto | Média | CATALOGUED_NOT_STARTED |
| 9 | V2-H09 | Prêmio de variância e skew em opções | 5 | 5 | 1,00 | Médio | Difícil | CATALOGUED_NOT_STARTED |
| 10 | V2-H10 | Resiliência e retirada de liquidez | 4 | 5 | 0,80 | Médio | Difícil | CATALOGUED_NOT_STARTED |
| 11 | V2-H11 | Fluxos on-chain para exchanges | 4 | 5 | 0,80 | Alto | Difícil | CATALOGUED_NOT_STARTED |
| 12 | V2-H14 | Descoberta de preço cross-exchange | 4 | 5 | 0,80 | Médio | Difícil | CATALOGUED_NOT_STARTED |
| 13 | V2-H12 | Stablecoin issuance/redemption | 3 | 4 | 0,75 | Alto | Difícil | CATALOGUED_NOT_STARTED |
| 14 | V2-H13 | CME/offshore basis | 3 | 4 | 0,75 | Médio-alto | Difícil | CATALOGUED_NOT_STARTED |
| 15 | V2-H15 | Arbitragem CEX–DEX executável | 3 | 5 | 0,60 | Alto | Difícil | CATALOGUED_NOT_STARTED |

## Fichas científicas

### V2-H01 — Carry e convergência de funding/basis em perpétuos

- **Pergunta:** funding/basis ex ante prevê retorno líquido de uma posição delta-neutral spot–perp ou convergência capturável após fees, slippage, borrow, margem e liquidação?
- **Mecanismo:** funding transfere renda entre lados e ancora o perp ao índice; limites de capital, arbitragem e margem podem sustentar basis e carry.
- **Literatura:** He, Manela, Ross & von Wachter, [Fundamentals of Perpetual Futures](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4301150), motivação acadêmica, não evidência local.
- **Dados:** spot/perp sincronizados, mark/index, premium/basis, funding events, specs, fees, borrow/margin; ≥8 ativos e ≥24 meses.
- **Avaliação:** VEI 5; custo 2; prioridade 2,50; generalização alta se replicada; overfitting baixo-médio; expectativa qualitativa alta; refutação fácil.
- **Experimento mínimo conceitual:** contraste pré-registrado de carry delta-neutral ex ante versus zero, líquido de todos os custos e replicado por ativo/período.
- **Estado:** `SELECTED_PENDING_DATA`; disponibilidade local **NÃO**; primeiro candidato apenas após gate de dados.

### V2-H02 — Funding extremo + crescimento de open interest

- **Pergunta:** funding e OI crescentes identificam crowding que antecede deleveraging assimétrico líquido de custos?
- **Mecanismo:** posições alavancadas lotadas elevam funding/OI e aumentam vulnerabilidade a unwind.
- **Literatura:** Cheng et al., [Liquidation, Leverage and Optimal Margin in Bitcoin Futures Markets](https://arxiv.org/abs/2102.04591), preprint; motivação, não evidência local.
- **Dados:** H01 + OI point-in-time, taker flow e, idealmente, liquidações.
- **Avaliação:** VEI 5; custo 3; prioridade 1,67; generalização média-alta; overfitting médio; expectativa alta; refutação média.
- **Experimento mínimo conceitual:** comparar períodos de crowding definidos ex ante com baseline pareado, sem selecionar extremos após outcomes.
- **Estado:** `CATALOGUED_NOT_STARTED`; disponibilidade local **NÃO**.

### V2-H03 — Liderança spot–perp e descoberta de preço

- **Pergunta:** choques em um venue antecipam convergência do outro além de common factor e microstructure noise?
- **Mecanismo:** o mercado com maior informação/liquidez incorpora choques primeiro.
- **Literatura:** Dimpfl & Peter, [Nothing but noise?](https://doi.org/10.1016/j.finmar.2020.100584), artigo acadêmico; motivação, não evidência local.
- **Dados:** trades/quotes spot e perp subsegundo ou 1s, spreads, depth e clocks auditáveis.
- **Avaliação:** VEI 5; custo 3; prioridade 1,67; generalização média-alta; overfitting médio; expectativa alta; refutação média.
- **Experimento mínimo conceitual:** lead-lag pré-fixado com falsificações de tempo e pseudo-líderes em séries sincronizadas.
- **Estado:** `CATALOGUED_NOT_STARTED`; disponibilidade local **NÃO**.

### V2-H04 — Fluxos de ETF spot

- **Pergunta:** fluxos point-in-time de ETF antecipam impacto persistente em BTC após controlar anúncio, mercado e custos?
- **Mecanismo:** criação/resgate gera demanda/oferta física e arbitragem em mercados fragmentados.
- **Literatura:** literatura de fluxos institucionais deve apenas motivar; não há evidência local nem dataset registrado.
- **Dados:** ETF flows point-in-time, calendário de publicação, AUM, feriados e BTC spot/perp.
- **Avaliação:** VEI 4; custo 3; prioridade 1,33; generalização média; overfitting médio-alto; expectativa média-alta; refutação média.
- **Experimento mínimo conceitual:** event study preregistrado por timestamp de disponibilidade, contra dias placebo e surprises de fluxo.
- **Estado:** `CATALOGUED_NOT_STARTED`; disponibilidade local **NÃO**.

### V2-H05 — Surpresas macro e risk-on/risk-off

- **Pergunta:** surpresas macro point-in-time explicam resposta cripto incremental e economicamente material?
- **Mecanismo:** notícias alteram taxas de desconto e apetite a risco.
- **Literatura:** [Crypto macro news](https://papers.ssrn.com/sol3/Delivery.cfm/6447644.pdf?abstractid=6447644&mirid=1) e [FRED/ALFRED](https://fred.stlouisfed.org/docs/api/fred/alfred.html); motivação e fonte de vintages, não evidência local.
- **Dados:** releases e surprises point-in-time, yields/equities/USD e trades/quotes cripto intraday.
- **Avaliação:** VEI 4; custo 3; prioridade 1,33; generalização média-alta; overfitting médio; expectativa média-alta; refutação média.
- **Experimento mínimo conceitual:** event study com janela fixa, consenso vintage e falsos eventos, sem dados revisados.
- **Estado:** `CATALOGUED_NOT_STARTED`; disponibilidade local **NÃO**.

### V2-H06 — Dispersão cross-sectional de funding/carry

- **Pergunta:** dispersão de funding/basis prevê prêmio relativo líquido e replicável, distinto de momentum OHLCV?
- **Mecanismo:** demanda alavancada e custos de short heterogêneos geram carry relativo.
- **Literatura:** He et al., [Fundamentals of Perpetual Futures](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4301150); motivação, não evidência local.
- **Dados:** funding, basis, spot/perp, borrow, fees e capacidade short em painel amplo.
- **Avaliação:** VEI 4; custo 3; prioridade 1,33; generalização média; overfitting médio-alto; expectativa média; refutação média.
- **Experimento mínimo conceitual:** portfólios de carry definidos ex ante e delta-neutral, com custos e capacidade, contra equal-weight.
- **Estado:** `CATALOGUED_NOT_STARTED`; disponibilidade local **NÃO**.

### V2-H07 — Order-flow imbalance ajustado por depth

- **Pergunta:** fluxo agressor relativo à capacidade de absorção prevê impacto incremental líquido?
- **Mecanismo:** agressão move preço quando excede depth disponível; fluxo bruto sem depth é incompleto.
- **Literatura:** Anastasopoulos et al., [Order flow and cryptocurrency returns](https://www.sciencedirect.com/science/article/pii/S1386418126000029); URL fornecida, DOI não assumido.
- **Dados:** trades assinados e L2 reconstruível, sequence IDs, gaps, latency e fees.
- **Avaliação:** VEI 5; custo 4; prioridade 1,25; generalização alta se multiativo; overfitting médio; expectativa alta; refutação média-difícil.
- **Experimento mínimo conceitual:** previsão OOS do impacto pelo imbalance/depth contra fluxo bruto e shifts de sequência.
- **Estado:** `CATALOGUED_NOT_STARTED`; disponibilidade local **NÃO**.

### V2-H08 — Cascatas de liquidação

- **Pergunta:** forced flow produz continuação ou reversão líquida replicável após custos e capacidade?
- **Mecanismo:** liquidações consomem liquidez, amplificam movimento e podem gerar overshoot.
- **Literatura:** Cheng et al., [Liquidation, Leverage and Optimal Margin](https://arxiv.org/abs/2102.04591), preprint.
- **Dados:** liquidações com lado/quantidade/timestamp, OI, mark/index, trades, livro e regras de margem.
- **Avaliação:** VEI 4; custo 4; prioridade 1,00; generalização média; overfitting médio-alto; expectativa média-alta; refutação média.
- **Experimento mínimo conceitual:** event study de eventos forçados pré-definidos versus choques de preço sem liquidação.
- **Estado:** `CATALOGUED_NOT_STARTED`; disponibilidade local **NÃO**.

### V2-H09 — Prêmio de variância e skew em opções

- **Pergunta:** momentos implícitos remuneram risco de convexidade de forma líquida e estável?
- **Mecanismo:** demanda por proteção pode remunerar vendedores de variância/skew.
- **Literatura:** Alexander & Imeraj, [The Bitcoin VIX and its Variance Risk Premium](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3383734), working paper.
- **Dados:** cadeia point-in-time BTC/ETH, bid/ask, trades, IV surface, futures/spot, rates e expiries.
- **Avaliação:** VEI 5; custo 5; prioridade 1,00; generalização média; overfitting médio; expectativa alta; refutação difícil.
- **Experimento mínimo conceitual:** diferença preregistrada entre variância implícita e realizada com P&L executável e custos.
- **Estado:** `CATALOGUED_NOT_STARTED`; disponibilidade local **NÃO**.

### V2-H10 — Resiliência do livro e retirada de liquidez

- **Pergunta:** retirada/cancelamento de depth antecede impacto e adverse selection incremental?
- **Mecanismo:** menor resiliência reduz absorção e amplifica choques.
- **Literatura:** microestrutura é motivação externa; não há evidência local nem livro histórico.
- **Dados:** L2/L3 incremental, cancelamentos, trades, sequence IDs e latência.
- **Avaliação:** VEI 4; custo 5; prioridade 0,80; generalização média-alta; overfitting médio; expectativa média-alta; refutação difícil.
- **Experimento mínimo conceitual:** contraste de impacto após retirada de depth contra estados pareados de volume/preço.
- **Estado:** `CATALOGUED_NOT_STARTED`; disponibilidade local **NÃO**.

### V2-H11 — Fluxos on-chain para exchanges

- **Pergunta:** depósitos de ativos ou entradas de stablecoins antecipam oferta/demanda líquida?
- **Mecanismo:** transferências podem preceder intenção de vender ou capital disponível para compra.
- **Literatura:** Chi, Chu & Hao, [On-chain flows](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4630115); working paper, labels são risco central.
- **Dados:** blockchain, labels versionados point-in-time, exchange addresses, bridge/mint/burn e preços.
- **Avaliação:** VEI 4; custo 5; prioridade 0,80; generalização média; overfitting alto; expectativa média; refutação difícil.
- **Experimento mínimo conceitual:** eventos definidos com labels vintage e controles de relabeling/endogeneidade.
- **Estado:** `CATALOGUED_NOT_STARTED`; disponibilidade local **NÃO**.

### V2-H14 — Descoberta de preço cross-exchange

- **Pergunta:** algum venue lidera de modo estável e economicamente superior ao ruído de microestrutura?
- **Mecanismo:** fragmentação cria velocidades distintas de incorporação da informação.
- **Literatura:** Dimpfl & Peter, [Price discovery across cryptocurrency exchanges](https://doi.org/10.1016/j.finmar.2020.100584).
- **Dados:** trades/quotes/depth de ≥3 venues, fees, latency e clock audit.
- **Avaliação:** VEI 4; custo 5; prioridade 0,80; generalização alta se replicada; overfitting médio; expectativa média-alta; refutação difícil.
- **Experimento mínimo conceitual:** liderança comum em múltiplos venues contra clock shifts e pseudo-líderes.
- **Estado:** `CATALOGUED_NOT_STARTED`; disponibilidade local **NÃO**.

### V2-H12 — Stablecoin issuance/redemption

- **Pergunta:** mint/burn altera liquidez e retornos futuros além de resposta endógena à demanda?
- **Mecanismo:** emissão/resgate muda capacidade de settlement e capital disponível.
- **Literatura:** Ante, Fiedler & Strehle, [Stablecoin issuances](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3626969), working paper.
- **Dados:** mint/burn, treasury/exchange flows, supply point-in-time e preços multi-venue.
- **Avaliação:** VEI 3; custo 4; prioridade 0,75; generalização média; overfitting alto; expectativa média; refutação difícil.
- **Experimento mínimo conceitual:** surpresa de emissão point-in-time contra calendário/placebos e controles de demanda.
- **Estado:** `CATALOGUED_NOT_STARTED`; disponibilidade local **NÃO**.

### V2-H13 — CME/offshore basis e segmentação

- **Pergunta:** basis e liderança entre CME e offshore revelam segmentação institucional capturável?
- **Mecanismo:** capital, horário e regulação separam investidores e atrasam convergência.
- **Literatura:** Dimpfl & Peter e Liu & Tsyvinski, [Risks and Returns of Cryptocurrency](https://www.nber.org/papers/w24877), motivação ampla.
- **Dados:** CME trades/quotes/OI, offshore futures/perp, spot, horários e custos.
- **Avaliação:** VEI 3; custo 4; prioridade 0,75; generalização média; overfitting médio-alto; expectativa média; refutação difícil.
- **Experimento mínimo conceitual:** transmissão preregistrada em janelas comuns e de fechamento, com clocks e custos.
- **Estado:** `CATALOGUED_NOT_STARTED`; disponibilidade local **NÃO**.

### V2-H15 — Arbitragem CEX–DEX executável

- **Pergunta:** desvios CEX–DEX sobrevivem a gas, MEV, depth, inventário e latência de transferência?
- **Mecanismo:** segmentação de inventário, blocos e curvas AMM pode gerar desvio temporário.
- **Literatura:** literatura de arbitragem fragmentada é motivação; não há evidência local CEX–DEX.
- **Dados:** mempool/blocos, pools/reserves, gas, MEV, CEX depth, bridge/transfer latency e inventário.
- **Avaliação:** VEI 3; custo 5; prioridade 0,60; generalização baixa-média; overfitting alto; expectativa média; refutação difícil.
- **Experimento mínimo conceitual:** replay executável simultâneo com todos os custos e restrições de inventário.
- **Estado:** `CATALOGUED_NOT_STARTED`; disponibilidade local **NÃO**.

## Descartes pré-implementação

Não são hipóteses executáveis: spreads cross-exchange por candles/last price; liquidity grabs por wick; fluxo institucional por volume OHLCV; sentimento black-box; macro revisado ex post; labels on-chain atuais aplicados retroativamente; arbitragem sem depth/custos/latência/borrow/transfer; e qualquer reformulação de Trend, RSI, EMA, MACD, Bollinger, parâmetros ou Hyperopt.

## Primeira decisão

V2-H01 é a primeira candidata científica, mas permanece **SELECTED_PENDING_DATA**, não ativa e não testada. Não existe contrato de dados aceito nem protocolo experimental. A única próxima ação autorizável é uma decisão humana separada sobre aquisição e QA de dados externos.

## Referência operacional de dados

Para eventual avaliação de disponibilidade de derivados, a documentação oficial indicada é [Binance USDⓈ-M Futures Market Data](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data). Este catálogo não consultou endpoints nem autorizou download.
