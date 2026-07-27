# Discovery V3 — H04 Stage 3

## Plano congelado

**Data:** 2026-07-24  
**Desenvolvimento:** 2024-07-01 a 2026-06-30  
**Holdout:** 2026-07-01 a 2026-07-23, `SEALED_UNOPENED`

## Teste único

- líder fixo: Binance USD-M;
- seguidora fixa: Bybit linear;
- horizonte fixo: um candle de 5 minutos;
- sinal: retorno close/open da Binance no candle `t`;
- controle: retorno close/open contemporâneo da Bybit em `t`;
- outcome: retorno open-to-open da Bybit de `t+5m` a `t+10m`;
- amostra econômica: decil superior de `abs(retorno Binance_t)` dentro de cada
  ativo, sem testar outro corte;
- retorno alinhado: `sign(retorno Binance_t) × retorno Bybit_t+1`;
- custo roundtrip fixo de uma perna: 0,15%;
- resultado líquido: retorno alinhado menos 0,15%.

## Estatística

- regressão do retorno Bybit seguinte no retorno Binance e retorno Bybit
  contemporâneo;
- coeficiente, erro padrão, p-value normal, IC95% bootstrap e R² incremental;
- bootstrap por dias UTC, 1.000 réplicas, seed `20260724`;
- dez ativos e quatro blocos semestrais;
- concentração de PnL por ativo.

## Controles

- líder invertido: Bybit `t` → Binance `t+1`;
- sinal Binance circularmente deslocado +7 dias;
- sinal Binance em reverse time;
- sinal Binance defasado artificialmente −5 minutos.

## Gate

Avança somente se todos:

1. média líquida do decil superior >0 e IC95% inferior >0;
2. média bruta ≥0,15%;
3. coeficiente Binance positivo com IC95% inferior >0;
4. R² incremental ≥0,0001;
5. pelo menos 7/10 ativos líquidos positivos;
6. 4/4 blocos líquidos positivos;
7. líder invertido não iguala/supera o coeficiente Binance;
8. nenhum placebo reproduz magnitude e significância;
9. nenhum ativo concentra >35% do PnL bruto positivo.

Falha em qualquer gate rejeita H04 em escala não-HFT. Não serão testados outros
lags, horizontes, custos, thresholds, líderes ou seguidores. O holdout não será
aberto na Stage 3.
