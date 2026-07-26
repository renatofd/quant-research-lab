# PH4-A08 — Valor Preditivo Incremental de Proxies OHLCV de Iliquidez

**Status:** protocolo científico pré-registrado. Nenhum dado foi analisado e nenhum resultado foi observado nesta etapa.

## 1. Mandato e fronteira de identificação

PH4-A08 testa se um proxy de impacto preço-volume construído exclusivamente com OHLCV contém informação incremental sobre risco futuro. O objeto é **previsão de risco**, não previsão direcional, regra de entrada, filtro, estratégia, sizing ou execução.

OHLCV não observa spread, profundidade, fila, lado agressor/passivo, slippage realizado ou impacto de uma ordem identificada. Portanto:

- o estudo pode sustentar apenas “o proxy OHLCV acrescenta previsão de risco”;
- não pode sustentar “a liquidez real causou o resultado”;
- não pode validar custo de execução nem transformar o proxy em indicador operacional;
- qualquer confirmação do mecanismo microestrutural exigiria posteriormente trades ou livro de ofertas, fora deste protocolo.

## 2. Pergunta científica

Depois de controlar a volatilidade passada e o volume nocional passado, uma medida contínua de movimento de preço por unidade de volume prevê a volatilidade realizada futura de maneira incremental, estável e replicável entre ativos e blocos temporais?

## 3. Fundamento econômico

Quando menor capacidade de negociação absorve uma mesma chegada de informação, uma quantidade de volume tende a acompanhar movimento de preço maior. Se esse estado persiste por fricção de inventário, atenção ou provisão lenta de liquidez, uma razão preço-volume elevada pode anteceder maior risco de preço.

Esse mecanismo é plausível, mas OHLCV oferece somente uma aproximação reduzida. A razão também pode aumentar por volatilidade elevada, volume contaminado, composição de participantes ou movimentos comuns do mercado. Por isso, volatilidade e volume entram separadamente no baseline, e o teste é incremental.

## 4. Hipóteses

### H1-A08

O proxy Amihud-OHLCV passado possui coeficiente positivo e melhora materialmente a previsão cronológica fora da amostra interna da volatilidade realizada futura, além de volatilidade e volume passados. O efeito supera placebos temporais e de pareamento preço-volume, replica entre pares e blocos e não depende de concentração excessiva.

### H0-A08

O proxy não adiciona informação estável além de volatilidade e volume: seu coeficiente é não positivo ou incerto, a redução de erro é economicamente desprezível, o modelo não supera os controles negativos, ou o efeito não replica.

## 5. Dados congelados

- Fonte: arquivos Feather OHLCV spot Binance já existentes.
- Timeframe: 5 minutos.
- Universo: `BTC/USDT`, `ETH/USDT`, `SOL/USDT`, `BNB/USDT`, `XRP/USDT`, `ADA/USDT`, `DOGE/USDT`, `LINK/USDT`, `AVAX/USDT` e `LTC/USDT`.
- Blocos: as cinco janelas não sobrepostas congeladas em `user_data/lab/ph3_c03r_windows.json`.
- Todos os blocos são development-consumed; nenhum é holdout virgem.
- Não usar funding, trades, livro, spread, open interest, liquidações, dados on-chain ou qualquer fonte externa.
- Nenhuma amostra pode cruzar limite de bloco.

## 6. Definições OHLCV

Para o candle `i`:

- retorno logarítmico: `r_i = log(close_i / close_i-1)`;
- volume nocional aproximado em USDT: `q_i = close_i * volume_i`;
- range logarítmico: `g_i = log(high_i / low_i)`.

`q_i` é aproximação obtida de volume-base multiplicado pelo fechamento; não é turnover econômico, volume agressor ou custo executável.

Uma observação exige `close > 0`, `high >= max(open, close, low)`, `low <= min(open, close, high)`, `volume > 0`, `q_i > 0` e valores finitos. Não inserir epsilon para esconder volume zero; eventos afetados são descartados e contabilizados.

## 7. Horizonte e amostragem

- Janela passada fixa: 24 retornos de 5 minutos, equivalentes a duas horas.
- Janela futura fixa: 24 retornos seguintes.
- Eventos espaçados a cada 24 candles para evitar sobreposição dos labels dentro de cada par/bloco.
- No evento encerrado em `t`, os preditores usam somente candles até `t`; o outcome usa exclusivamente `t+1` a `t+24`.
- Os primeiros 24 e últimos 24 candles de cada bloco são indisponíveis por desenho.
- Não haverá horizonte secundário, threshold, quantil, top-k, direção ou seleção de subgrupo.

## 8. Proxies pré-registrados

### 8.1 Proxy primário P1 — Amihud-OHLCV

`P1_t = mean(|r_i| / q_i)` para os 24 candles encerrados em `t`.

Justificativa: aproxima quanto movimento absoluto de preço acompanhou cada unidade de volume nocional. É a adaptação OHLCV da intuição de price impact de Amihud. Uma razão maior é coerente com menor capacidade aparente de absorção, mas não mede impacto causal de ordens.

O modelo utiliza `log(P1_t)`. Se `P1_t <= 0` ou não finito, o evento é inválido; não haverá constante calibrável.

### 8.2 Proxy secundário P2 — Range por volume nocional

`P2_t = mean(g_i / q_i)` para os mesmos 24 candles.

Justificativa: o range intrabar resume deslocamento máximo-mínimo observado; dividido pelo volume nocional, aproxima variação de preço por capacidade negociada. É mais sensível à trajetória intrabar e a extremos do candle que P1.

P2 é somente triangulação diagnóstica. Não pode substituir P1, escolher um “vencedor” nem resgatar a hipótese se P1 falhar. Seus testes formam família de multiplicidade separada.

### 8.3 Componentes de controle, não proxies candidatos

- `RV_past_t = sqrt(sum(r_i^2))` nos 24 retornos passados;
- `QV_past_t = sum(q_i)` nos 24 candles passados;
- para P2, `RANGE_past_t = mean(g_i)`.

Esses componentes impedem atribuir ao quociente algo explicado apenas por volatilidade, range ou volume isoladamente.

## 9. Outcome

Outcome único:

`Y_t = log(RV_future_t)`

onde `RV_future_t = sqrt(sum(r_j^2))` para `j = t+1 ... t+24`.

O estudo não usa lucro, trade, PF ou retorno direcional como outcome. Não aplica fees ou slippage porque nenhuma ordem é simulada. A utilidade econômica avaliada é redução material de erro de previsão de risco.

## 10. Avaliação cronológica

Cada unidade par/bloco é dividida cronologicamente na mediana dos eventos elegíveis:

- primeira metade: calibração;
- segunda metade: avaliação.

### 10.1 Baseline primário

Calibrar na primeira metade:

`Y_t = alpha + b1*log(RV_past_t) + b2*log(QV_past_t)`

### 10.2 Modelo completo P1

`Y_t = alpha + b1*log(RV_past_t) + b2*log(QV_past_t) + beta1*log(P1_t)`

### 10.3 Modelo diagnóstico P2

Baseline P2:

`Y_t = alpha + b1*log(RV_past_t) + b2*log(QV_past_t) + b3*log(RANGE_past_t)`

Completo P2: baseline P2 mais `beta2*log(P2_t)`.

Todos os coeficientes são congelados antes da avaliação. Nenhuma transformação, variável ou modelo pode ser escolhido com resultados da segunda metade.

Os coeficientes usados nas previsões de MSE são exclusivamente os calibrados na primeira metade. Separadamente, para medir a associação estrutural fora da calibração, `beta1_eval` e `beta2_eval` são reestimados por OLS controlado somente na metade de avaliação. Esses betas de avaliação nunca são usados para produzir as previsões avaliadas.

## 11. Estimandos e métricas

### Primários P1

1. `beta1_eval` controlado na metade de avaliação, esperado positivo;
2. melhora de MSE na avaliação: `1 - MSE_full_P1 / MSE_baseline`;
3. redução de perda do modelo real versus placebo circular;
4. redução de perda do modelo real versus placebo de pareamento preço-volume.

### Magnitude econômica

- melhora de MSE igual ou superior a `5%` no agregado equal-weight;
- MAE improvement, correlação parcial e `R²` incremental são diagnósticos, não gates alternativos.

O limiar de 5% é um critério de relevância de previsão, não parâmetro de trading. Um efeito estatisticamente positivo abaixo dele é classificado como economicamente insuficiente.

### Diagnósticos P2

Reportar `beta2`, melhora de MSE, MAE, correlação parcial e comparação com placebo. P2 não participa da decisão positiva de P1 além de verificar coerência descritiva.

## 12. Unidade inferencial e agregação

- Unidade primária: série de avaliação de um par em um bloco, total máximo de 50 unidades.
- Candles não são tratados como observações inferenciais independentes.
- Calcular resultados separadamente por par/bloco.
- Agregar unidades com peso igual; também reportar agregações equal-weight por par e por bloco.
- Nunca ponderar um bloco por possuir mais candles ou mais volume.

## 13. Bootstrap

- 1.000 réplicas determinísticas.
- Reamostrar dias UTC completos dentro da metade de avaliação de cada par/bloco.
- Preservar todos os eventos pertencentes ao dia selecionado.
- Recalcular métricas por unidade e agregar unidades com peso igual em cada réplica.
- Nunca reamostrar candles individuais.
- Em cada réplica, reestimar `beta1_eval` nas unidades reamostradas; os modelos de previsão permanecem com coeficientes congelados da calibração.
- IC95 percentil para `beta1_eval`, melhora de MSE e contrastes contra os dois placebos.
- Para cada hipótese unilateral positiva, p-value bootstrap determinístico: `(1 + número de réplicas com estimando <= 0) / (1 + 1.000)`.
- Seed e regra de reamostragem devem ser únicas, determinísticas e registradas antes da futura execução; não são opções de pesquisa.

## 14. Controles negativos e falsificações

### 14.1 Baseline volatilidade + volume

Demonstra se P1 acrescenta informação além de seus componentes econômicos principais.

### 14.2 Placebo circular temporal

Deslocar `log(P1_t)` por metade da série de avaliação dentro de cada par/bloco, mantendo baseline e outcomes fixos. Isso preserva distribuição e dependência aproximada, removendo o alinhamento temporal correto.

### 14.3 Placebo de pareamento preço-volume

Construir um pseudo-P1 associando a sequência de `|r|` à sequência de `q` deslocada deterministicamente por metade da janela de eventos dentro do mesmo par/bloco. Preserva as distribuições marginais de retorno e volume, mas rompe sua relação contemporânea.

### 14.4 Auditoria de componentes

Comparar baseline completo com versões apenas-volatilidade e apenas-volume de forma diagnóstica. Nenhuma versão pode ser selecionada após os resultados.

### 14.5 Falsificação de lookahead

Verificar por índices e timestamps que nenhum candle posterior a `t` participa de P1, P2 ou controles e que nenhum label cruza bloco. Falha implica desenho inválido, não resultado inconclusivo comum.

## 15. Correção de multiplicidade

Aplicar Holm, com testes unilaterais pré-especificados na direção econômica, à família decisória P1:

1. `beta1_eval > 0`;
2. melhora de MSE P1 `> 0`;
3. modelo P1 supera placebo circular;
4. modelo P1 supera placebo de pareamento.

Todos os quatro devem sobreviver Holm. A família diagnóstica P2 aplica Holm separadamente a beta, melhora de MSE e contraste circular. Diagnósticos por par formam uma terceira família separada e nunca alteram o N primário.

Não há seleção do menor p-value, proxy, par, bloco ou transformação.

## 16. Concentração e consistência

Reportar a contribuição para a redução positiva total de MSE por:

- par;
- bloco;
- dia UTC.

Também reportar sinal da melhora de MSE em cada uma das 50 unidades. Controles zero-variância ou unidades sem eventos suficientes ficam `NA`, nunca zero de qualidade.

## 17. Integridade e amostra mínima

Antes de qualquer interpretação:

- hashes dos dez arquivos lidos;
- cobertura, timezone UTC, ordenação e duplicatas;
- gaps de 5 minutos por par/bloco;
- OHLCV inválido e volume não positivo;
- eventos descartados e motivo;
- número de eventos de calibração e avaliação;
- no mínimo 30 eventos válidos em cada metade de cada par/bloco informativo;
- no mínimo 8 pares e 4 blocos com unidades informativas;
- prova de ausência de sobreposição de labels e lookahead.

Gaps não são preenchidos silenciosamente. Uma janela de 24 candles é inválida se contiver gap.

## 18. Critérios de sucesso

Decisão máxima:

`DEVELOPMENT OHLCV ILLIQUIDITY-PROXY RISK SIGNAL DETECTED — PROSPECTIVE HOLDOUT REQUIRED`

Somente se **todos** ocorrerem:

1. `beta1_eval` agregado é positivo com IC95 bootstrap inteiramente acima de zero;
2. melhora agregada de MSE é pelo menos `5%` e seu IC95 é inteiramente acima de zero;
3. P1 supera placebo circular com IC95 acima de zero;
4. P1 supera placebo de pareamento com IC95 acima de zero;
5. os quatro testes decisórios sobrevivem Holm;
6. melhora de MSE positiva em pelo menos 4/5 blocos;
7. melhora positiva em pelo menos 7/10 pares;
8. nenhum par, bloco ou dia UTC responde por mais de 30% da redução positiva total de MSE;
9. resultados permanecem após controlar separadamente volatilidade e volume;
10. integridade e amostra mínima passam.

Mesmo com sucesso, a única continuação autorizada é confirmação prospectiva da previsão de risco. Não há autorização para estratégia, filtro, sizing ou bot.

## 19. Critérios de rejeição definitiva no escopo OHLCV

Decisão:

`OHLCV ILLIQUIDITY-PROXY HYPOTHESIS REJECTED IN PRIMARY SCOPE`

Se dados e implementação forem válidos e ocorrer qualquer falha econômica central:

- `beta1_eval <= 0` ou IC95 inclui zero;
- melhora de MSE `<= 0` ou IC95 inclui zero;
- melhora agregada de MSE positiva, porém inferior a `5%`;
- P1 não supera um dos placebos;
- efeitos decisórios não sobrevivem Holm;
- menos de 4/5 blocos ou 7/10 pares apresentam melhora positiva.

Após rejeição, A08 é encerrada. Não testar outra janela, horizonte, proxy, transformação, threshold, combinação, par ou regime nos dados consumidos. P2 positivo não pode resgatar P1.

## 20. Critérios de inconclusão

Decisão:

`INCONCLUSIVE OHLCV ILLIQUIDITY-PROXY AUDIT`

Somente quando:

- integridade, amostra mínima ou cobertura impedem o contraste;
- volume-base e preço não permitem construir `q_i` de forma consistente;
- core estatístico/econômico passa, mas o efeito viola exclusivamente o gate de concentração;
- erro de implementação ou leakage invalida a execução.

Concentração isolada impede confirmação, mas não demonstra H0. Não autoriza mudar o limite ou selecionar subconjunto.

## 21. Resultados que autorizam continuar ou encerrar

| Resultado | Consequência científica |
|---|---|
| Todos os dez gates de sucesso passam | Continuar apenas para holdout prospectivo de previsão de risco. |
| Beta/MSE/efeito econômico/placebos/replicação falham | Encerrar definitivamente A08 no escopo OHLCV. |
| Apenas P2 é positivo | Encerrar A08; diagnóstico secundário não substitui P1. |
| Significância sem melhora MSE >=5% | Encerrar por insuficiência econômica. |
| Core passa, mas concentração excede 30% | Inconclusivo; não retunar nem promover. |
| Integridade ou amostra impedem teste | Inconclusivo por dados, sem interpretação econômica. |

## 22. Ameaças à validade

- `close * volume` aproxima volume nocional e pode divergir do quote volume real.
- Volume reportado pode conter wash trading ou mudança de composição.
- OHLCV agrega trajetórias intrabar e não mede spread ou profundidade.
- Relação preço-volume pode refletir volatilidade comum, apesar dos controles.
- O universo contém apenas dez pares Binance spot contra USDT.
- Os cinco blocos já foram consumidos em desenvolvimento, elevando risco de multiplicidade acumulada.
- Um resultado positivo seria associação preditiva, não causalidade econômica.

## 23. Proibições pós-resultado

- Não escolher P2 se P1 falhar.
- Não testar outro horizonte, janela, proxy, transformação ou outcome.
- Não condicionar por par, horário, regime, volatilidade ou sinal de retorno.
- Não converter P1 em filtro, indicador, score, sizing ou regra de execução.
- Não interpretar significância estatística como custo executável ou lucro.

## 24. Decisões finais pré-registradas

- `DEVELOPMENT OHLCV ILLIQUIDITY-PROXY RISK SIGNAL DETECTED — PROSPECTIVE HOLDOUT REQUIRED`
- `OHLCV ILLIQUIDITY-PROXY HYPOTHESIS REJECTED IN PRIMARY SCOPE`
- `INCONCLUSIVE OHLCV ILLIQUIDITY-PROXY AUDIT`

## 25. Veredito de testabilidade

**A08 é cientificamente testável com OHLCV somente no escopo limitado de previsão incremental de risco por proxy preço-volume.**

Ela **não** é testável com validade como medida de liquidez real, impacto causal ou custo de execução. O protocolo prossegue apenas porque essa limitação está incorporada à hipótese, ao baseline e às decisões. Nenhuma implementação ou execução é autorizada por este documento.

## 26. Auditoria de escopo desta etapa

- Arquivo criado: `PH4_A08_PROTOCOL.md`.
- Código escrito ou modificado: não.
- Estratégias, indicadores ou parâmetros alterados: não.
- Backtests, cálculos, downloads ou campanhas executados: não.
- Dados além de OHLCV autorizados: não.
