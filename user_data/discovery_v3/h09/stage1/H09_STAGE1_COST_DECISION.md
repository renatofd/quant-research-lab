# H09 Stage 1 — Dados, orçamento e decisão

**Decisão:** `REJECTED_BEFORE_IMPLEMENTATION_COST_EXCEEDS_EXPECTED_INFORMATION`

Binance publica `aggTrades` com buyer-maker, permitindo signed aggressive flow.
Entretanto, uma campanha válida exigiria:

- granularidade de trade e sequência;
- quotes/book para entrada, spread, depth e slippage;
- vários ativos e regimes;
- resposta em segundos/subsegundos;
- relógio de exchange e testes de latência;
- holdout prospectivo.

O laboratório não possui histórico de quotes/book. Agregar trades em candles de
5 minutos perde a ordem dos eventos e confunde fluxo informativo com o retorno que
ele já causou. O campo taker-buy dos klines foi usado como componente no V2-H02, mas
não é substituto de uma campanha OFI executável.

O download de dois anos de aggTrades para dez ativos é tecnicamente público, porém
teria alto custo de armazenamento, QA e processamento sem resolver o dado decisivo
de execução. H04 mostrou que até liderança estatística cross-exchange a 5 minutos
deixa apenas 0,37 bp bruto, muito abaixo de 15 bp. A probabilidade racional de uma
triagem 5m de CVD alterar a conclusão é inferior ao custo científico.

Pela regra explícita de orçamento, H09 é descartada antes de implementação. Não é
alegação de que order flow nunca contém informação; é decisão de que o experimento
executável atual não pode demonstrar vantagem líquida. Reabertura exige dataset
conjunto trade+book point-in-time e orçamento novo.
