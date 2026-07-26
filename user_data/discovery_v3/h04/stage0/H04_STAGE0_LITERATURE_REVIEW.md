# Discovery V3 — H04 Stage 0

## Cross-Exchange Leadership

**Data:** 2026-07-24  
**Decisão:** `STAGE0_PASS`  

## Mecanismo econômico

Cripto é negociado simultaneamente em venues com liquidez, custos, clientela,
jurisdição e latência diferentes. Informação chega primeiro onde capital informado
consegue negociar com menor custo e maior profundidade. Arbitradores transmitem o
choque às demais venues, criando uma sequência líder → seguidora.

O efeito só constitui vantagem econômica se o retorno da venue líder, conhecido em
tempo causal, acrescentar previsão ao retorno contemporâneo da seguidora e o ajuste
remanescente superar custo e latência de execução. Information share sem retorno
capturável não autoriza bot.

## Literatura

- Makarov e Schoar documentam heterogeneidade de price discovery entre exchanges e
  perda de influência das venues segmentadas.
  https://www.aeaweb.org/articles?id=10.1257/pandp.20191020
- O artigo completo dos autores documenta arbitragem recorrente, mas limitada por
  fricções de capital e transferência.
  https://doi.org/10.1016/j.jfineco.2019.07.001
- Shestopaloff et al. estudam formação e cross-impact em escala inferior a um
  segundo com trades e order books de mercados líquidos.
  https://arxiv.org/abs/2108.09750
- Cosenza e Stalder encontram Binance spot/perp como fonte importante de price
  discovery e ligam liderança a custos e volume.
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4983566
- Evidência recente enfatiza assincronia e esparsidade, exigindo métodos próprios
  para alta frequência.
  https://doi.org/10.1016/j.jimonfin.2025.103415

## Hipótese falsificável

**H04:** retornos fechados da Binance USD-M antecipam, em escala fixa de 5 minutos,
o retorno imediatamente seguinte da Bybit linear do mesmo ativo, condicional ao
retorno contemporâneo da Bybit, com efeito replicável e economicamente superior ao
custo de uma perna.

**Nula:** não há informação incremental causal, ela é reproduzida por sincronização
incorreta/placebos, ou o efeito é menor que o custo.

Binance é fixada como líder antes dos outcomes por sua liquidez e pela literatura.
A direção não poderá ser invertida para resgatar o teste. Cinco minutos são um funil
de baixa frequência: falha rejeita utilidade não-HFT; sucesso apenas autoriza dados
tick-level.

## Orçamento

- custo de triagem 5m: moderado, com Binance já disponível e Bybit oficial pública;
- informação: alta, porque pode refutar utilidade em latência acessível;
- custo tick/subsegundo: alto e somente justificável após a triagem;
- risco de falso positivo: alto por candles sobrepostos e relógios; controlável com
  entrada no candle seguinte, placebos e alinhamento explícito.

## Decisão

`STAGE0_PASS` para inventário. Nenhuma estratégia ou vantagem foi confirmada.
