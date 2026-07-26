# PH4-A09 — Persistência Preditiva de Inovação de Volume OHLCV

**Status:** protocolo científico pré-registrado. Nenhum OHLCV foi lido ou calculado antes de seu congelamento.

## 1. Mandato e limites

PH4-A09 testa uma única hipótese: se uma inovação contínua de volume observada em `t` contém informação incremental e replicável sobre atividade e risco futuros de uma hora, além da persistência de volume, risco contemporâneo, movimento comum de mercado, par, bloco e sazonalidade horária.

Volume OHLCV é somente proxy de atividade/atenção. O estudo não identifica fluxo institucional, lado agressor/passivo, liquidez real, spread, profundidade, impacto causal ou custo de execução. Não cria estratégia, entrada, ordem, threshold ou parâmetro de trading.

As famílias A01, A02, A03, A05, A07, A08, Trend, Pullback, N-of-M, Ensemble e MeanReversion permanecem encerradas e não são reabertas.

## 2. Hipóteses

### H1-A09

A inovação própria de volume `X_t` acrescenta previsão cronológica fora da amostra interna para atividade futura e, para relevância operacional, também para risco futuro. O ganho deve ser material, estatisticamente favorável, replicável entre pares e blocos, superar controles negativos e não depender de concentração.

### H0-A09

`X_t` não acrescenta ganho preditivo material e replicável além do baseline, ou o aparente efeito não supera placebos, especificidade cross-asset, reverse-time, multiplicidade ou gates de robustez.

## 3. Dados congelados

- Binance spot OHLCV 5 minutos já existente; nenhum download.
- Dez pares: `BTC/USDT`, `ETH/USDT`, `SOL/USDT`, `BNB/USDT`, `XRP/USDT`, `ADA/USDT`, `DOGE/USDT`, `LINK/USDT`, `AVAX/USDT` e `LTC/USDT`.
- Exatamente os cinco blocos de `user_data/lab/ph3_c03r_windows.json`.
- Somente timestamps completos e comuns aos dez pares dentro de cada bloco.
- Nenhuma amostra pode cruzar um limite de bloco.
- Todos os dados são development-consumed; não são holdout confirmatório.

## 4. Definições fixas

Para cada par e timestamp elegível:

- `L_t = log1p(volume_t)`;
- `X_t = L_t - L_{t-1}`;
- `Y_activity = mean(log1p(volume))` nos 12 candles `t+1 ... t+12`;
- `Y_risk = sum(abs(r))` nos 12 retornos close-to-close `t+1 ... t+12`;
- `CurrentRisk = sum(abs(r))` nos 12 retornos `t-11 ... t`;
- `MarketActivity_t = mean(X_t)` equal-weight dos outros nove ativos no mesmo timestamp;
- `MarketRisk_t = mean(abs(r_t))` equal-weight dos outros nove ativos;
- `HourOfWeek` é categoria UTC fixa de `0` a `167`.

O único horizonte futuro e lookback de risco é 12 candles, equivalentes a 60 minutos. Não haverá outro horizonte, janela, lag, threshold, quantil, evento extremo, z-score, top-k ou corte.

Volume usa exclusivamente a coluna OHLCV existente e a transformação `log1p(volume)`. Níveis brutos de volume não são comparados entre pares.

## 5. Unidade e amostragem

- Unidade científica: par × bloco, máximo de 50 unidades.
- Candles dentro de uma unidade não são independentes para a decisão agregada.
- A construção usa somente candles completos, OHLCV válido, timestamps sincronizados e labels totalmente contidos no bloco.
- Cada unidade recebe split cronológico fixo: 60% treino e 40% avaliação.
- Os 12 candles imediatamente anteriores à primeira observação de avaliação formam embargo; nenhuma observação de treino cujo label alcance esse embargo ou a avaliação é admitida.
- Modelos são estimados apenas no treino e congelados antes da avaliação.

## 6. Modelos preditivos

### 6.1 Activity baseline

`Y_activity ~ intercept + L_{t-1} + CurrentRisk + MarketActivity_t + MarketRisk_t + HourOfWeek`

### 6.2 Activity full

Baseline Activity mais `X_t`.

### 6.3 Risk baseline

`Y_risk ~ intercept + CurrentRisk + L_{t-1} + MarketActivity_t + MarketRisk_t + HourOfWeek`

### 6.4 Risk full

Baseline Risk mais `X_t`.

`HourOfWeek` é codificado por dummies categóricas fixas, com uma categoria de referência determinística. Não há regularização selecionável, feature selection ou retuning.

## 7. Estimandos e métricas

### P1 primário — atividade

- beta de `X_t` no treino;
- SE, p-value bilateral e IC95 analítico do beta de treino;
- correlação parcial de `X_t` com `Y_activity` no painel de avaliação, controlando o baseline;
- MSE e MAE OOS do baseline e full;
- melhoria percentual `1 - loss_full / loss_baseline` para MSE e MAE;
- R² baseline, full e incremental.

### P2 — relevância econômica de risco

As mesmas métricas para `Y_risk`. Previsão de atividade não é vantagem negociável. Justificativa para experimento operacional exige que P1 e P2 passem integralmente seus gates.

As métricas são calculadas por unidade, agregadas com peso igual entre unidades, e reportadas também equal-weight por par e bloco.

## 8. Inferência

- 1.000 réplicas determinísticas.
- Seed fixa `2026071409`.
- Reamostrar dias UTC completos com reposição dentro da avaliação de cada par/bloco.
- Preservar todos os eventos pertencentes a cada dia sorteado.
- Recalcular métricas por unidade e agregar as unidades informativas com peso igual.
- Nunca reamostrar candles individuais.
- Coeficientes preditivos permanecem congelados do treino em todas as réplicas.
- IC95 percentil.
- Para hipóteses unilaterais positivas: `p = (1 + count(estimando <= 0)) / (1 + 1000)`.
- Holm na família decisória predefinida, sem escolher o menor p-value.

## 9. Controles negativos

1. **Circular shift:** deslocar `X_t` deterministicamente por metade de cada série de treino e avaliação dentro de par/bloco, ajustar o modelo placebo no treino e avaliar com alinhamento deslocado.
2. **Permutação de dias UTC:** permutar deterministicamente blocos diários completos de `X_t` dentro do treino e da avaliação, usando seed fixa e preservando ordem intradia.
3. **Pseudo-volume cross-asset:** substituir `X_t` pela inovação contemporânea equal-weight dos outros nove ativos, mantendo os controles; o `X_t` próprio deve produzir menor perda que esse modelo.
4. **Reverse-time:** inverter o alinhamento temporal para testar se `X` futuro explica respostas passadas; o modelo real deve superar essa falsificação.
5. **Baseline sem `X_t`:** comparador central de ganho incremental.

Nenhum controle vencedor será promovido. Os contrastes de superioridade são reduções percentuais de perda do modelo real em relação ao respectivo controle, sempre na mesma avaliação.

## 10. Multiplicidade

A família decisória Holm contém, para P1 e P2:

- P1 melhoria MSE;
- P1 melhoria MAE;
- P2 melhoria MSE;
- P2 melhoria MAE;
- superioridade P1 e P2 contra circular shift;
- superioridade P1 e P2 contra permutação diária;
- superioridade P1 e P2 contra pseudo-volume cross-asset;
- superioridade P1 e P2 contra reverse-time.

Todos os p-values relevantes ao gate devem permanecer abaixo de `0,05` após Holm. Betas e correlações são reportados com incerteza, mas não substituem os gates de perda.

## 11. Robustez e concentração

- P1 deve melhorar MSE e MAE em pelo menos 7/10 pares e 4/5 blocos.
- P2 deve satisfazer o mesmo para relevância operacional.
- Reportar estabilidade do sinal do beta e das melhorias OOS por unidade, par e bloco.
- Nenhum par, bloco ou dia UTC pode responder por mais de 30% da melhoria positiva agregada.
- Contribuições são calculadas por redução positiva de erro por observação, normalizada para peso igual das unidades.

## 12. Integridade e amostra

Antes da interpretação:

- hashes dos dez Feather e deste protocolo;
- cobertura e sincronização exata dos timestamps;
- timezone UTC, ordenação, duplicatas e gaps de 5 minutos;
- OHLCV finito, preços positivos, relações high/low válidas e volume não negativo;
- eventos descartados e motivos;
- labels contidos no bloco e ausência de lookahead;
- embargo de 12 candles comprovado;
- amostra suficiente para estimar o desenho com dummies fixas e avaliar cada unidade;
- pelo menos 8 pares, 4 blocos e 30 eventos de avaliação por unidade informativa.

Falhas técnicas rotineiras de montagem devem ser corrigidas sem mudar o desenho. Inconclusão é reservada a impedimento material de dados, amostra ou integridade.

## 13. Critérios de decisão

### VOLUME-ACTIVITY PROXY CONFIRMED

P1 é confirmado somente se todos ocorrerem:

1. integridade suficiente;
2. melhorias P1 de MSE e MAE iguais ou superiores a 5%;
3. IC95 de ambas inteiramente acima de zero;
4. p-values correspondentes após Holm abaixo de 0,05;
5. beta `X_t` positivo com IC95 inteiramente acima de zero;
6. melhorias positivas em pelo menos 7/10 pares e 4/5 blocos;
7. o modelo real supera circular, permutação diária, pseudo-volume e reverse-time após Holm;
8. concentração máxima por par, bloco e dia não excede 30%.

### RISK OPERATIONAL EXPERIMENT JUSTIFIED

Somente se P1 passar e P2 cumprir os mesmos gates: melhorias MSE e MAE de pelo menos 5%, IC95 positivo, Holm, beta positivo, 7/10 pares, 4/5 blocos, todos os controles e concentração máxima de 30%.

### Rejeição

Com integridade válida, A09 é rejeitada se P1 falhar qualquer gate econômico, estatístico ou de robustez central. Efeito pequeno ou negativo não é inconclusivo e proíbe novos horizontes, thresholds ou subgrupos.

### Inconclusão

Somente se dados, amostra ou integridade impedirem materialmente o teste após correções técnicas rotineiras. Não usar inconclusão para efeito pequeno, negativo ou não significativo.

## 14. Decisões finais permitidas

- `VOLUME-ACTIVITY PROXY CONFIRMED — RISK OPERATIONAL EXPERIMENT JUSTIFIED`
- `VOLUME-ACTIVITY PROXY CONFIRMED — NO OPERATIONAL BOT JUSTIFIED`
- `OHLCV VOLUME-PERSISTENCE HYPOTHESIS REJECTED IN PRIMARY SCOPE`
- `INCONCLUSIVE OHLCV VOLUME-PERSISTENCE AUDIT`

## 15. Proibições pós-resultado

- Não testar outro horizonte, janela, lag, transformação, threshold, quantil, par, sessão, regime ou subgrupo.
- Não converter o achado em estratégia, filtro, score, sizing ou bot.
- Não inferir fluxo institucional, agressor/passivo, liquidez real ou causalidade.
- Não iniciar A11 ou qualquer outra hipótese nesta campanha.

## 16. Artefatos previstos

- `user_data/discovery/reports/ph4_a09_volume_persistence_report.md`
- `user_data/discovery/reports/ph4_a09_volume_persistence_report.html`
- `user_data/discovery/reports/ph4_a09_volume_persistence_report.json`
- `user_data/discovery/reports/ph4_a09_volume_persistence_matrix.csv`
- `user_data/discovery/reports/ph4_a09_volume_persistence_bootstrap.csv`

## 17. Auditoria de congelamento

Este arquivo deve ser hasheado antes da primeira leitura ou cálculo de OHLCV. Depois do primeiro cálculo, seu conteúdo não pode ser alterado. Os dados atuais são development-consumed; mesmo resultado positivo não é confirmação independente.
