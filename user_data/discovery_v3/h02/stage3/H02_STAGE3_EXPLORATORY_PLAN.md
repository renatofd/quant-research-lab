# Discovery V3 — H02 Stage 3

## Plano exploratório congelado antes de outcomes

**Hipótese:** H02 — Divergência Spot × Perp  
**Data de congelamento:** 2026-07-24  
**Dados autorizados:** somente desenvolvimento V2, 2024-07-01 a 2026-06-30  
**Holdout H02:** 2026-07-01 a 2026-07-23, `SEALED_UNOPENED`  

## Pergunta

Quando o perpétuo USD-M da Binance está caro em relação ao spot USDT do mesmo
ativo, a diferença comprime nos 30 minutos seguintes em magnitude suficiente para
uma posição long spot/short perp cobrir um envelope conservador de execução de duas
pernas?

O teste é de convergência relativa e delta-neutral. Não prevê a direção do ativo.

## Unidade e alinhamento

- painel fixo de 10 ativos da Stage 1;
- grade não sobreposta de 30 minutos, fixada em `HH:00` e `HH:30` UTC;
- candle identificado por seu open time;
- sinal observado no close do candle de 5 minutos iniciado em `t`;
- entrada simulada no open do candle `t+5m`;
- saída no open do candle `t+35m`;
- holding fixo de 30 minutos;
- nenhum outro horizonte será calculado.

Esse alinhamento impede usar o mesmo preço no sinal e na entrada.

## Variáveis congeladas

Base observada:

`b_t = log(perp_close_t / spot_close_t)`.

Universo elegível primário: somente `b_t > 0`, porque long spot/short perp não exige
short do ativo à vista.

Intensidade: percentil de `b_t` dentro de cada ativo no desenvolvimento. A análise
econômica primária usa exclusivamente o decil superior, fixado antes dos outcomes.
Os cinco quintis serão usados apenas para verificar monotonicidade, sem selecionar
um cutoff alternativo.

Retorno bruto de convergência:

`y_t = log(spot_open_t+35 / spot_open_t+5) - log(perp_open_t+35 / perp_open_t+5)`.

Funding realizado dentro do holding será incorporado com o sinal econômico da perna
short perp. Não haverá estimativa ou antecipação de funding.

Envelope conservador fixo:

- 30 pontos-base por roundtrip completo das duas pernas;
- inclui taxas mínimas conservadoras, spread/slippage agregado e pequena reserva;
- nenhum custo alternativo será usado para alterar a decisão;
- resultados brutos também serão reportados para diagnóstico.

Resultado líquido exploratório: `y_t + funding_t - 0,003`.

## Estatística

1. média, mediana e concentração do retorno bruto e líquido no decil superior;
2. regressão `y_t` sobre `b_t`, controlando retorno spot e perp no candle do sinal;
3. coeficiente, erro padrão, R² incremental e IC95%;
4. bootstrap por dias UTC, 1.000 réplicas, seed `20260724`;
5. decomposição por ativo;
6. quatro blocos temporais fixos de seis meses;
7. quintis de base para monotonicidade;
8. resultado separado para divergência negativa apenas como diagnóstico não
   promocional, sem gate e sem possibilidade de substituir o primário.

## Controles negativos

- circular shift do sinal em +7 dias;
- reverse time da série de sinal dentro de cada ativo;
- desalinhamento artificial do spot em +5 minutos;
- pseudo-divergência mark/index.

Os controles usarão o mesmo horizonte, grade e amostra elegível. Nenhum placebo
poderá substituir ou redefinir o teste principal.

## Gate único para Stage 4

H02 avança somente se **todos** os itens forem satisfeitos:

1. média líquida do decil superior maior que zero;
2. limite inferior do IC95% bootstrap da média líquida maior que zero;
3. média bruta do decil superior pelo menos 0,30%;
4. coeficiente de convergência positivo, IC95% inteiramente acima de zero e
   R² incremental pelo menos `0,0001`;
5. média líquida positiva em pelo menos 7 dos 10 ativos;
6. média líquida positiva em todos os 4 blocos de seis meses;
7. média bruta não decrescente nos cinco quintis;
8. nenhum controle negativo reproduz simultaneamente sinal, magnitude e
   significância;
9. nenhum ativo responde por mais de 35% do PnL bruto positivo.

Falha em qualquer item rejeita H02 na Stage 3. Não haverá ajuste de horizonte,
percentil, custo, universo ou direção. Resultado positivo no diagnóstico de base
negativa não resgata o primário.

## Artefatos esperados

- `H02_STAGE3_RESULTS.json`;
- `H02_STAGE3_RESULTS.md`;
- `H02_STAGE3_ASSET_MATRIX.csv`;
- `H02_STAGE3_BLOCK_MATRIX.csv`;
- `H02_STAGE3_QUINTILE_MATRIX.csv`;
- `H02_STAGE3_CONTROL_MATRIX.csv`;
- `H02_STAGE3_FINAL_DECISION.json`;
- `H02_STAGE3_FINAL_DECISION.md`.

## Proibições

- não abrir o holdout H02;
- não pesquisar lags, horizontes ou thresholds;
- não criar estratégia ou sinal operacional;
- não executar backtest;
- não promover resultado apenas estatístico;
- não reabrir a regra de carry/funding rejeitada no Discovery V2.
