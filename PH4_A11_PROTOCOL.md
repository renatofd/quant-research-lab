# PH4-A11 — Sazonalidade Calendárica OHLCV

**Status:** protocolo científico pré-registrado. Nenhum OHLCV A11 foi lido ou calculado antes deste congelamento.

## 1. Mandato

PH4-A11 é a última campanha OHLCV e testa uma única hipótese: se blocos temporais conhecidos ex ante — dias da semana, fim de semana e três sessões UTC grossas — acrescentam informação replicável sobre retorno líquido futuro de uma hora e risco futuro, além de controles contemporâneos.

A11 é auditoria econômica offline, não estratégia. Não cria sinais, ordens, filtros, thresholds ou parâmetros. Resultado apenas de risco não justifica bot; P1 retorno líquido é o gate operacional.

A01, A02, A03, A05, A07, A08 e A09 estão encerradas. A04 permanece inconclusiva e fechada; A06 e A10 permanecem encerradas/deferidas. Famílias Trend, Pullback, N-of-M, Ensemble e MeanReversion não são reabertas. Explorações históricas de Tuesday, Friday, NY, H14-H16 ou combinações não selecionam nenhum contraste desta campanha.

## 2. Pergunta e hipóteses

### H1-A11

Pelo menos um dos onze contrastes temporais fixos possui retorno futuro long-only líquido de custos positivo e melhoria preditiva material, replica entre pares e blocos, supera placebos e não é concentrado.

### H0-A11

Nenhum contraste satisfaz simultaneamente positividade líquida, materialidade preditiva, multiplicidade, placebos, replicação e concentração.

## 3. Dados congelados

- Binance spot OHLCV 5 minutos já existente; nenhum download.
- Dez pares: `BTC/USDT`, `ETH/USDT`, `SOL/USDT`, `BNB/USDT`, `XRP/USDT`, `ADA/USDT`, `DOGE/USDT`, `LINK/USDT`, `AVAX/USDT` e `LTC/USDT`.
- Exatamente os cinco blocos de `user_data/lab/ph3_c03r_windows.json`.
- Somente timestamps completos e sincronizados entre os dez pares.
- Nenhuma observação pode cruzar limite de bloco.
- Dados development-consumed; OOS é interno, não holdout prospectivo.

## 4. Observações e variáveis

Observações são não sobrepostas, ancoradas exclusivamente em `HH:00 UTC`.

Para cada par e observação em `t`:

- `Y_return = close[t+12] / close[t] - 1`;
- `Y_risk = sum(abs(log(close_i / close_i-1)))` para `i=t+1...t+12`;
- `PastReturn = close[t] / close[t-12] - 1`;
- `PastRisk = sum(abs(log(close_i / close_i-1)))` para `i=t-11...t`;
- `MarketPastReturn` é a média equal-weight de `PastReturn` dos outros nove ativos;
- `MarketPastRisk` é a média equal-weight de `PastRisk` dos outros nove ativos.

O único horizonte futuro e lookback é 12 candles, equivalentes a 60 minutos.

## 5. Contrastes fixos

Exatamente onze indicadores binários, sem combinação ou seleção:

1. `MONDAY` versus todos os demais dias;
2. `TUESDAY` versus todos os demais dias;
3. `WEDNESDAY` versus todos os demais dias;
4. `THURSDAY` versus todos os demais dias;
5. `FRIDAY` versus todos os demais dias;
6. `SATURDAY` versus todos os demais dias;
7. `SUNDAY` versus todos os demais dias;
8. `WEEKEND` (sábado e domingo) versus segunda a sexta;
9. `UTC_00_08` versus as outras sessões;
10. `UTC_08_16` versus as outras sessões;
11. `UTC_16_24` versus as outras sessões.

Sessões são intervalos UTC semiabertos. Não testar horas individuais, dia × sessão, DST, fuso alternativo, outro horizonte ou subgrupo.

## 6. Custos

- Diagnóstico fee-only: `0,20%` round-trip.
- Cenário decisório conservador: fee `0,10%` por lado mais slippage `0,05%` por lado, total `0,30%` round-trip.
- Retorno líquido condicional é retorno bruto da janela menos o custo round-trip fixo.
- Não modelar execução intrabar.

## 7. Split e modelos

Unidade científica: par × bloco, máximo de 50 unidades.

- Split cronológico fixo 60% treino e 40% avaliação.
- Como observações são horárias, o embargo de 12 candles exclui a última observação horária anterior à fronteira, garantindo que nenhum label de treino alcance a avaliação.
- Coeficientes são estimados no treino e congelados antes da avaliação.

Baseline Return:

`Y_return ~ intercept + PastReturn + PastRisk + MarketPastReturn + MarketPastRisk`

Para cada contraste, full Return é baseline mais o indicador binário.

Baseline Risk:

`Y_risk ~ intercept + PastRisk + abs(PastReturn) + MarketPastRisk + abs(MarketPastReturn)`

Para cada contraste, full Risk é baseline mais o indicador binário.

Sem regularização selecionável, feature selection, retuning ou escolha de contraste.

## 8. P1 — retorno decisório

Para cada contraste, unidade, par, bloco e agregado equal-weight:

- beta do indicador, SE, p-value e IC95;
- correlação parcial na avaliação;
- MSE e MAE baseline/full, melhorias percentuais e R² incremental;
- retorno bruto médio e mediano condicional e do complemento;
- efeito condicional menos complemento;
- retorno líquido médio e mediano sob custos de 0,20% e 0,30%;
- contagens condicional e complemento.

P1 é long-only e compatível com spot. Efeito negativo não pode ser reinterpretado como short.

## 9. P2 — risco diagnóstico

Para cada contraste, reportar beta, SE, p-value, IC95, correlação parcial, MSE/MAE baseline/full, melhorias percentuais e R² incremental para `Y_risk`. P2 não resgata falha P1 e não justifica bot isoladamente.

## 10. Inferência

- 1.000 réplicas determinísticas, seed `2026071411`.
- Reamostrar semanas UTC completas com reposição dentro da avaliação de cada par/bloco.
- Avaliações de borda que não formem semana UTC completa são reportadas no ponto observado, mas não entram no bootstrap semanal.
- Coeficientes preditivos permanecem congelados do treino.
- Métricas por unidade são agregadas com peso igual entre unidades.
- IC95 percentil.
- p-value unilateral é obtido pela distribuição bootstrap normalizada pelo seu erro-padrão; betas usam inferência OLS unilateral na direção positiva.
- Candles e horas não são unidades independentes da conclusão.

### Família Holm P1 única

Para cada um dos 11 contrastes:

1. retorno líquido médio conservador positivo;
2. efeito condicional menos complemento positivo;
3. beta positivo;
4. melhoria MSE positiva;
5. melhoria MAE positiva;
6. superioridade MSE contra circular shift;
7. superioridade MSE contra permutação semanal;
8. superioridade MSE contra reverse-time.

Todos os 88 testes pertencem à mesma família Holm P1.

### Família Holm P2 diagnóstica

Para cada contraste: beta, melhoria MSE, melhoria MAE e superioridade MSE contra os três placebos, total de 66 testes em família separada. P2 nunca altera a decisão se P1 falhar.

## 11. Controles negativos

Para cada contraste:

1. **Circular shift:** deslocar o indicador por exatamente 84 observações horárias dentro de treino e avaliação de cada par/bloco.
2. **Permutação semanal:** permutar deterministicamente os labels horários dentro de cada semana UTC completa, preservando retornos e usando seed fixa.
3. **Reverse-time:** inverter a ordem temporal dos labels dentro de treino e avaliação; o alinhamento real deve superar a falsificação.
4. **Baseline:** modelo sem label.

O modelo real deve superar os três placebos após Holm. Nenhum placebo vencedor será promovido.

## 12. Robustez e concentração

Para o mesmo contraste:

- retorno líquido médio conservador positivo em pelo menos 7/10 pares e 4/5 blocos;
- melhorias MSE e MAE positivas nas mesmas contagens;
- nenhum par, bloco ou semana UTC responde por mais de 30% da melhoria positiva de MSE;
- nenhum par, bloco ou semana responde por mais de 30% do retorno líquido positivo agregado;
- estabilidade do sinal do beta e do retorno líquido.

Resultados de contrastes diferentes nunca são somados para cumprir gates.

## 13. Integridade e amostra

Antes da interpretação:

- hash deste protocolo, das janelas e dos dez Feather;
- timezone UTC, cobertura, ordenação, duplicatas e gaps de 5 minutos;
- sincronização exata dos dez pares;
- OHLCV finito e relações de preço válidas;
- labels e lookbacks totalmente dentro do bloco;
- âncoras exclusivamente `HH:00 UTC` e observações não sobrepostas;
- embargo válido;
- pelo menos 30 observações de avaliação e uma semana UTC completa por unidade informativa;
- pelo menos 8 pares, 4 blocos e 40 unidades informativas.

Falha técnica solucionável deve ser corrigida sem mudar desenho. Inconclusão é reservada a impedimento material de dados, amostra ou integridade.

## 14. Confirmação

Decisão `OHLCV CALENDAR-SEASONALITY CONFIRMED — OPERATIONAL EXPERIMENT JUSTIFIED` somente se pelo menos um contraste satisfizer todos:

1. integridade suficiente;
2. retorno líquido médio e mediano sob custo 0,30% acima de zero;
3. IC95 do retorno líquido médio inteiramente acima de zero e Holm `p<0,05`;
4. efeito versus complemento e beta positivos, IC95 acima de zero e Holm `p<0,05`;
5. melhorias OOS de MSE e MAE de pelo menos 5%, IC95 acima de zero e Holm `p<0,05`;
6. pelo menos 7/10 pares e 4/5 blocos positivos simultaneamente para retorno líquido, MSE e MAE;
7. superioridade contra circular, permutação semanal e reverse-time após Holm;
8. concentração máxima de 30% por par, bloco e semana para melhoria e retorno líquido.

Se múltiplos passarem, todos são reportados sem ranking.

## 15. Rejeição e inconclusão

Com integridade válida, se nenhum contraste passar todos os gates P1, decisão exata:

`OHLCV CALENDAR-SEASONALITY HYPOTHESIS REJECTED IN PRIMARY SCOPE`

Efeito pequeno, bruto positivo mas líquido negativo, resultado apenas P2, falha Holm, placebo, concentração ou replicação é rejeição, não inconclusão.

Inconclusão é permitida apenas se dados, amostra ou integridade impedirem materialmente o teste:

`INCONCLUSIVE OHLCV CALENDAR-SEASONALITY AUDIT`

## 16. Proibições pós-resultado

- Não ramificar para horas, combinações, DST, thresholds, outros horizontes ou subgrupos.
- Não escolher o contraste menos ruim.
- Não transformar resultado em estratégia, filtro ou bot sem que todos os gates passem.
- Não iniciar hipótese posterior nesta campanha.

## 17. Artefatos previstos

- `user_data/discovery/reports/ph4_a11_calendar_seasonality_report.md`
- `user_data/discovery/reports/ph4_a11_calendar_seasonality_report.html`
- `user_data/discovery/reports/ph4_a11_calendar_seasonality_report.json`
- `user_data/discovery/reports/ph4_a11_calendar_seasonality_matrix.csv`
- `user_data/discovery/reports/ph4_a11_calendar_seasonality_bootstrap.csv`

## 18. Decisões finais exatas

- `OHLCV CALENDAR-SEASONALITY CONFIRMED — OPERATIONAL EXPERIMENT JUSTIFIED`
- `OHLCV CALENDAR-SEASONALITY HYPOTHESIS REJECTED IN PRIMARY SCOPE`
- `INCONCLUSIVE OHLCV CALENDAR-SEASONALITY AUDIT`

Este arquivo deve ser hasheado antes do primeiro cálculo A11 e não pode ser alterado depois.
