# PHASE4_FIRST_EXPERIMENT.md

# PHASE 4.1 — Seleção da Primeira Hipótese

## 1. Mandato e limites

Este documento seleciona uma única hipótese da Fase 4 e especifica um protocolo científico completo para investigação futura. Ele não implementa, não executa e não autoriza estratégia, robô, indicador, Hyperopt, plugin, backtest, download ou campanha.

Fontes vinculantes:

- `PHASE4_RESEARCH_ROADMAP.md`.
- `user_data/lab/ph3_rst_gate01_final_raw_signal_gate.md/json`.
- `user_data/lab/ph3_gate02_family_portfolio_decision.md/json`.

Os gates finais prevalecem sobre `CURRENT_STATE.md` e `RESEARCH_HANDBOOK.md` em caso de conflito.

Estado científico obrigatório:

- PH3-GATE02: `STOP ALL EXISTING FAMILIES — SCIENTIFIC RESET`.
- PH3-RST-GATE01: `STOP RAW SIGNAL SEARCH — NO ARCHITECTURE JUSTIFIED`.
- Trend/Score/Pullback/MeanReversion, ensembles e variações permanecem encerrados.
- RST01, RST02, RST03 e RST04 não detectaram sinal econômico líquido suficiente.
- RST02 e RST03 preservam achados relativos positivos, mas não autorizam retuning, composição ou reabertura de famílias.

Escopo desta etapa:

- Escolher uma hipótese.
- Definir protocolo falsificável.
- Definir controles, unidade inferencial e gates.
- Não executar nada.
- Criar/modificar somente `PHASE4_FIRST_EXPERIMENT.md`.

## 2. Matriz das 26 hipóteses

Legenda:

- Evidência local: evidência produzida pelo laboratório atual.
- Literatura: motivação externa; não conta como evidência local.
- Custo computacional: baixo, médio ou alto.
- Risco de falso positivo: risco de mineração, múltiplos testes, proxy fraco ou leakage.
- Risco de perder tempo: risco de a hipótese ser barata, mas pouco informativa, ou exigir dados que não existem.
- Experimento mínimo: teste científico de refutação, não estratégia nem backtest.

| ID | Pergunta científica | Evidência já possuída | Evidência faltante | Dados necessários | Custo | Risco falso positivo | Risco perder tempo | Experimento mínimo capaz de refutar |
|---|---|---|---|---|---|---|---|---|
| A01 | BTC lidera altcoins com defasagem curta, além do movimento comum contemporâneo? | Não há teste local direto; RST01/RST04 não testaram difusão BTC→alts. | Evidência de especificidade de BTC, controle de common factor e pseudo-líderes. | OHLCV 5m sincronizado dos 10 pares. | Baixo: dados já existem. | Médio: lead-lag pode surgir por autocorrelação/common movement. | Baixo: refutável rapidamente com dados atuais. | Testar inovação relativa de BTC em t contra resposta equal-weight das nove altcoins em t+1, com controles/placebos. |
| A02 | Volatilidade passada prevê risco/magnitude futura, sem direção? | RST03 mostrou que expansão de volatilidade tem informação incremental, mas não retorno líquido. | Validação como previsão de risco, não lucro. | OHLCV 5m. | Baixo: usa dados atuais. | Baixo-médio: risco de escolher métricas de volatilidade pós-hoc. | Médio: pode ser útil para risco, não necessariamente edge. | Testar previsão de magnitude futura contra baseline de volatilidade incondicional e placebo temporal. |
| A03 | Jumps/volatilidade positivos e negativos têm implicações futuras distintas? | RST03 não separou good/bad volatility; apenas expansão direcional condicionada a momentum. | Evidência de assimetria robusta por bloco/ativo. | OHLCV atual; idealmente trades/liquidações. | Baixo-médio: proxy candle-only. | Médio: muitos modos de definir jump. | Médio: OHLCV pode medir mal o mecanismo. | Pré-definir decomposição signed jump e rejeitar se efeitos positivos/negativos não diferirem de controles. |
| A04 | Co-jumps e contágio entre ativos predizem propagação ou risco futuro? | RST04 sincronizou cross-section, mas não estudou eventos de co-jump/propagação. | Evidência de propagação para ativos ainda não afetados. | OHLCV sincronizado; idealmente OI/liquidações. | Baixo-médio: eventos podem ser raros. | Médio: thresholds de evento podem minerar resultado. | Médio: precisa cuidado com raridade. | Identificar co-jumps pré-registrados e refutar se não houver propagação além de placebo por ativo/tempo. |
| A05 | Dispersão cross-sectional indica estado futuro de risco/instabilidade? | RST04 testou top-2 relativo, não dispersão como estado do universo. | Evidência de que dispersão prevê risco/magnitude futura. | OHLCV sincronizado. | Baixo. | Médio: múltiplas métricas de dispersão. | Baixo-médio: teste barato, mas não direcional. | Medir se dispersão passada prediz magnitude/risco futuro versus baseline e placebo. |
| A06 | Existe reversão cross-sectional em horizonte economicamente distinto? | RST02 rejeitou mean reversion time-series; RST04 rejeitou top-2 relative strength. | Evidência de reversão relativa que não seja reabertura de MeanReversionStrategy. | OHLCV sincronizado; holdout prospectivo. | Baixo. | Alto: muito próximo de hipóteses já encerradas. | Alto: fácil virar retuning de RST02/RST04. | Teste único de laggards versus equal-weight; rejeitar se retorno líquido ou especificidade falhar. |
| A07 | Compressão de volatilidade prediz expansão futura de magnitude? | RST03 testou alta volatilidade, não compressão prévia. | Evidência de magnitude futura, sem direção. | OHLCV atual. | Baixo. | Médio: definições de compressão são mineráveis. | Médio: útil para risco, não edge direcional. | Pré-definir compressão e rejeitar se magnitude futura não superar baseline/placebo. |
| A08 | Proxies OHLCV de iliquidez/impacto predizem risco ou custo futuro? | O laboratório tem OHLCV, mas não livro/spread. | Validação de proxy contra microestrutura real. | OHLCV parcial; idealmente livro/trades. | Baixo agora, alto para validação real. | Alto: proxy pode medir volatilidade, não liquidez. | Alto: risco de concluir com dado inadequado. | Refutar se proxy não melhora previsão de risco/custo após controlar volatilidade e volume. |
| A09 | Volume anormal prediz persistência de atividade ou risco? | Volume foi fraco/ambíguo em estudos anteriores; RST não validou fluxo. | Evidência de atividade futura, sem inferir institucional. | OHLCV; idealmente trades agressor/passivo. | Baixo. | Alto: wash trading/proxy contaminado. | Médio-alto: pode repetir conclusões fracas. | Testar persistência de volume/risco; rejeitar se não superar baseline de volatilidade e volume normal. |
| A10 | Falsos rompimentos/liquidity grabs são identificáveis por candles? | Nenhuma evidência local causal; candles não identificam livro. | Evidência microestrutural real. | OHLCV parcial; idealmente livro e trades. | Baixo como proxy, alto para evidência. | Alto: definição visual subjetiva. | Alto: hipótese fraca sem livro. | Evento candle-only pré-definido; rejeitar se não superar controle por volatilidade/tamanho do candle. |
| A11 | Sessão/weekday/weekend gera diferença líquida replicável? | Laboratório e literatura recente sugerem prioridade fraca. | Evidência robusta pós-custos e múltiplos testes. | OHLCV atual. | Baixo. | Alto: mineração de calendário. | Alto: provável baixo valor. | Teste pré-registrado de poucos blocos temporais; rejeitar se efeito não sobreviver Holm/placebo. |
| B12 | Funding/basis contém prêmio de carry ou crowding? | Nenhum dado local; literatura motiva fortemente. | Dataset de derivativos e validação local. | Funding, basis, perp/spot, custos. | Médio. | Médio: múltiplas exchanges/maturidades. | Médio: maior custo inicial, mas mecanismo forte. | Com dados novos, testar funding/basis extremo versus retorno/carry futuro e placebo temporal. |
| B13 | Open interest + funding identifica acúmulo de alavancagem? | Nenhum dado local. | OI limpo, funding e replicação. | OI, funding, perp/spot. | Médio-alto. | Médio: regimes e thresholds. | Médio: depende de qualidade de OI. | Rejeitar se crowding proxy não predizer risco/unwind fora da amostra. |
| B14 | Liquidações geram overshoot/reversão pós-forced-flow? | Nenhum dado local. | Dados de liquidação e event study. | Liquidações, perp/spot, OI/funding. | Médio-alto. | Médio: seleção de eventos. | Médio: mecanismo forte, dado externo. | Rejeitar se eventos de liquidação não superarem placebo pareado por volatilidade/horário. |
| B15 | Spot ou perp lidera price discovery? | Apenas spot atual; sem perp. | Dados spot/perp sincronizados. | Spot/perp OHLCV, idealmente trades/livro. | Médio-alto. | Médio: latência/sincronização. | Médio: forte mecanismo, mas QA pesada. | Rejeitar se liderança spot/perp não replicar por ativo/bloco após controles. |
| B16 | Order flow agressor/passivo prediz pressão futura? | Nenhum dado local. | Trades com side/aggressor. | Trades tick, agressor/passivo. | Alto. | Médio-alto: classificação pode errar. | Médio-alto: custo de dados alto. | Rejeitar se imbalance não supera volume/volatilidade como preditor. |
| B17 | Livro/profundidade prediz fragilidade, slippage ou jumps? | Nenhum dado local. | Order book com QA. | Snapshots depth/order book. | Alto. | Médio: muitos níveis/medidas. | Alto: armazenamento e QA. | Rejeitar se retirada/desequilíbrio de liquidez não prediz risco/custo. |
| B18 | Fragmentação entre exchanges gera limites à arbitragem? | Nenhum dado multi-exchange local. | Painel multi-exchange e custos. | Preços multi-exchange, fees, transfer constraints. | Alto. | Médio: fricções difíceis de modelar. | Médio-alto: escopo grande. | Rejeitar se gaps não convergem líquido de custos ou não replicam. |
| B19 | Dispersão de funding/carry cross-sectional prediz retorno/carry? | Nenhum dado local. | Funding por ativo e período. | Funding/carry cross-sectional. | Médio. | Médio: rank mining. | Médio: depende de dados B12. | Rejeitar se ranking de carry não superar equal-weight/placebo. |
| B20 | Stablecoin flows para exchanges predizem liquidez/pressão? | Nenhum dado local. | Labels on-chain e flows. | Stablecoin flows, exchange labels. | Alto. | Alto: labels e timing. | Alto: dados externos complexos. | Rejeitar se flows não adicionarem informação versus mercado/volume. |
| B21 | Entradas/saídas on-chain de exchanges predizem retorno/risco? | Nenhum dado local. | Labels confiáveis e causalidade temporal. | On-chain exchange flows. | Alto. | Alto: leakage e labels. | Alto: QA pesada. | Rejeitar se flows não superarem controles de volume/BTC. |
| B22 | Surpresas macro causam co-jumps ou regimes em cripto? | Nenhum calendário/surpresa local. | Dados de surpresa e timestamps precisos. | Macro calendar, consensus, surprises. | Médio. | Médio: poucos eventos e múltiplas janelas. | Médio: pode ser relevante só para BTC/ETH. | Rejeitar se eventos não alterarem distribuição versus placebo temporal. |
| B23 | Opções precificam variance/jump/skew risk premia úteis? | Nenhum dado de opções local. | IV surface e realized outcomes. | Opções BTC/ETH, IV, maturidades. | Alto. | Alto: muitas dimensões. | Alto: escopo complexo. | Rejeitar se premia implícitos não predizerem realized risk/returns fora da amostra. |
| B24 | Unlock/vesting cria pressão de oferta mensurável? | Nenhum calendário local. | Eventos confiáveis e controle de beta. | Token unlocks, supply/free float. | Médio. | Alto: eventos idiossincráticos. | Médio-alto: poucos ativos do universo atual. | Rejeitar se eventos não gerarem abnormal behavior replicável. |
| B25 | Listings/delistings/regulação geram efeitos anormais? | Nenhum dataset local. | Calendário de eventos e classificação de surpresa. | Eventos, timestamps, ativos controle. | Médio. | Alto: seleção retrospectiva. | Alto: idiossincrático. | Rejeitar se efeitos não replicarem com controles pareados. |
| B26 | Atenção/sentimento prediz atividade, risco ou retorno? | Nenhum dado local; alto risco reconhecido. | Proveniência, timestamps e holdout. | Notícias, social, search, timestamps. | Alto. | Muito alto: leakage/mineração. | Alto: grande escopo sem garantia. | Rejeitar se efeito desaparecer com timestamps honestos, controle de mercado e holdout. |

## 3. Comparação multicritério e shortlist

Critérios comparados:

1. Ganho esperado de conhecimento.
2. Risco de overfitting.
3. Reutilização de infraestrutura.
4. Necessidade de novos dados.
5. Potencial de vantagem econômica real se confirmada.

### Shortlist

| Hipótese | Conhecimento esperado | Overfitting | Reuso infraestrutura | Novos dados | Potencial econômico | Comentário |
|---|---|---|---|---|---|---|
| A01 BTC lead-lag | Alto | Médio | Alto | Não | Médio-alto | Testa difusão cross-asset, não coberta por RST01/RST04. |
| A02 persistência de volatilidade | Alto para risco | Baixo-médio | Alto | Não | Médio-baixo direcional | Provável generalização, mas não identifica vantagem direcional por si só. |
| A04 co-jumps/contágio | Alto | Médio | Médio-alto | Não | Médio | Valioso, mas depende de eventos e thresholds. |
| A05 dispersão como estado | Médio-alto | Médio | Alto | Não | Médio-baixo direcional | Estado de mercado útil, mas não vantagem direta. |
| B12 funding/basis | Alto | Médio | Médio | Sim | Alto | Mecanismo econômico forte, mas exige dataset novo e QA. |

### Discussão dos conflitos

A02 é provavelmente a hipótese mais simples e generalizável em termos de previsão de risco. O conflito é que previsão de risco não equivale a ineficiência econômica direcional. Ela pode ser útil para elegibilidade futura, mas não responde diretamente se existe informação explorável de preço.

B12 talvez tenha o mecanismo econômico mais forte entre as opções iniciais, porque funding/basis representam carry, crowding e fricções observáveis. O conflito é custo e dependência de dados novos. Escolhê-la primeiro atrasaria a Fase 4 em aquisição e QA antes de qualquer refutação barata.

A04 e A05 são cientificamente valiosas, mas seus resultados primários são estados de risco, contágio ou dispersão. Elas ajudam a mapear regimes, mas não prometem imediatamente uma ineficiência direcional líquida.

A01 fica no melhor ponto de compromisso: usa dados atuais, reaproveita sincronização e blocos já auditados, testa uma relação econômica diferente dos sinais brutos encerrados e pode ser refutada rapidamente. Seu risco de overfitting existe, mas é controlável porque a hipótese terá um único lag decisório, um líder pré-especificado e pseudo-líderes como placebo.

## 4. Decisão única

Hipótese selecionada: **A01 — Liderança BTC e transmissão defasada para altcoins**.

Título científico:

**PH4-A01 — BTC Lead-Lag and Delayed Altcoin Price Discovery**

Justificativa:

- A01 usa OHLCV sincronizado já disponível.
- A01 testa informação nova não coberta por RST01/RST04.
- A01 não reabre Trend: o objeto é difusão cross-asset defasada e especificidade de BTC, não persistência do próprio ativo.
- A01 pode ser refutada com um experimento mínimo barato.
- A02 fica como segunda opção científica porque é mais diretamente uma hipótese de risco do que uma ineficiência direcional/econômica.
- B12 fica como hipótese economicamente forte, mas posterior, porque exige novo dataset de derivativos e QA.
- A04 e A05 ficam na fila por tratarem primariamente risco/estado, não vantagem direcional direta.

Esta seleção não afirma que A01 funciona. Ela apenas define a primeira hipótese a testar.

## 5. Hipótese e hipótese nula

### Pergunta científica

Uma inovação relativa de retorno de BTC em um candle de 5 minutos prediz resposta, na mesma direção, do portfólio equal-weight das nove altcoins no candle imediatamente seguinte, além do movimento comum contemporâneo e com magnitude econômica líquida?

### Hipótese H1

Após remover o movimento contemporâneo mediano das nove altcoins, a inovação relativa de BTC em `t` contém informação positiva e monotônica sobre o retorno equal-weight das altcoins em `t+1`; o efeito é específico de BTC, supera placebos, replica entre blocos/ativos e sua magnitude líquida excede custos.

### Hipótese nula H0

A inovação relativa de BTC não prediz retorno futuro das altcoins além de autocorrelação/common factor; o efeito é zero, instável, indistinguível de pseudo-líderes/placebos ou economicamente menor que custos.

## 6. Protocolo completo

### Escopo e dados

- Exchange/dados: Binance spot.
- Timeframe: OHLCV 5m.
- Universo: os 10 pares atuais contra USDT.
- Líder pré-especificado: BTC.
- Painel de resposta: nove altcoins, ETH, SOL, BNB, XRP, ADA, DOGE, LINK, AVAX e LTC.
- Timestamps: usar somente timestamps comuns aos dez pares.
- Blocos: usar os cinco blocos históricos definidos na Fase 3.
- Status dos dados: todos development-consumed.
- Confirmação definitiva: exige holdout temporal prospectivo ainda intocado.
- Ação nesta etapa: nenhuma execução.

### Definições pré-registradas

Retorno de candle close-to-close:

`r_i,t = close_i,t / close_i,t-1 - 1`

Alt-market contemporâneo:

`A_t = mediana(r_alt1,t, ..., r_alt9,t)`

Inovação relativa de BTC:

`X_t = r_BTC,t - A_t`

Resposta primária:

`Y_t+1 = média_equal_weight(r_alt1,t+1, ..., r_alt9,t+1)`

Contraste contínuo primário:

Estimar o efeito monotônico de `X_t` sobre `Y_t+1`, controlando:

- `A_t`, movimento contemporâneo comum das altcoins.
- `Y_t`, retorno equal-weight das altcoins no candle atual, como own-lag alt-market.

Forma conceitual:

`Y_t+1 = alpha + beta * X_t + gamma * A_t + delta * Y_t + erro_t`

O estimando principal é `beta`.

Contraste econômico auxiliar:

Comparar média e mediana líquidas de `Y_t+1` quando `X_t > 0` contra o unconditional na mesma grade.

Auditorias de simetria:

- `X_t < 0` como auditoria de direção reversa.
- Reverse-time falsification.

Essas auditorias não são hipóteses adicionais e não podem ser usadas para selecionar outro sinal.

Restrições de desenho:

- Nenhum threshold de magnitude.
- Nenhum quantil.
- Nenhum top-k.
- Nenhuma seleção de lag.
- Único lag decisório: um candle de 5 minutos.
- Nenhum horizonte secundário nesta campanha.

### Amostragem e inferência

- Sincronização exata dos dez pares.
- Predictor usa apenas candle encerrado em `t`.
- Label usa `t+1`.
- Nenhuma amostra pode cruzar limite de bloco.
- Unidade primária por timestamp: portfólio equal-weight das nove altcoins.
- As nove altcoins não serão tratadas como nove observações independentes para o estimando primário.
- Estimar efeito separadamente em cada um dos cinco blocos.
- Incerteza: block bootstrap de dias UTC completos dentro de cada bloco.
- Agregação: blocos com peso igual, não por número de candles.
- Diagnóstico por ativo: secundário para consistência, não para inflar N.
- Se o lag primário falhar, não procurar outro lag.

### Prova formal de ausência de lookahead

Para cada timestamp `t`:

- `r_BTC,t` usa `close_BTC,t` e `close_BTC,t-1`.
- `A_t` usa retornos de altcoins encerrados em `t`.
- `X_t` usa apenas `r_BTC,t` e `A_t`.
- `Y_t` usa retornos de altcoins encerrados em `t`.
- `Y_t+1` é label futuro e não entra no predictor.

Logo, o predictor é mensurável no fechamento de `t`, enquanto o label começa somente depois de `t`.

## 7. Controles e placebos obrigatórios

1. Baseline unconditional na mesma grade.
2. Circular shift de `X_t` dentro de bloco, preservando dependência temporal e removendo alinhamento real.
3. Pseudo-líder leave-one-out: repetir conceitualmente o mesmo estimando com cada altcoin como líder e o restante como resposta.
4. BTC deve superar a distribuição dos nove pseudo-líderes para demonstrar especificidade.
5. Reverse-time falsification: retorno futuro das altcoins não pode “prever” inovação passada de BTC.
6. Controle explícito de `A_t`.
7. Controle de own-lag alt-market `Y_t`.
8. Concentração por ativo, dia e bloco.
9. Auditoria de gaps, duplicatas, timezone, cobertura e hashes.
10. Correção de multiplicidade: Holm sobre o conjunto decisório BTC versus pseudo-líderes/placebos.

## 8. Custos

Reutilizar exatamente os dois cenários fixos de RST01-RST04:

- Fee-only: 0,1% por lado quando não houver override oficial.
- Conservador: fee + 5 bps por lado de slippage.

O cenário conservador é decisório para utilidade econômica.

Custos são contraste econômico, não simulação de execução de ordens. Nenhuma estratégia ou ordem é definida por este protocolo.

## 9. Métricas

Métricas obrigatórias:

- N elegível.
- Amostras descartadas e motivo.
- Efeito contínuo `beta`.
- CI95 block-bootstrap do `beta`.
- Efeito condicional `X_t > 0` versus unconditional.
- Mean/median gross.
- Mean/median net nos dois cenários de custo.
- Hit rate líquido.
- Resultado por bloco.
- Resultado por ativo, apenas como diagnóstico de consistência.
- Concentração por ativo, dia e bloco.
- Comparação BTC versus pseudo-líderes.
- Placebo circular shift.
- Reverse-time falsification.
- Holm p-values.
- Sensibilidade fee-only versus conservador.
- Evidência de ausência de lookahead.

## 10. Critérios de sucesso e fracasso

### Sucesso de desenvolvimento

Todos os critérios abaixo são obrigatórios:

- Efeito contínuo positivo com CI95 inteiramente acima de zero.
- Efeito `X_t > 0` versus unconditional positivo com CI95 acima de zero.
- Média e mediana líquidas positivas no cenário conservador.
- Hit rate líquido acima de 52%.
- Direção positiva em pelo menos 4/5 blocos.
- Direção positiva em pelo menos 7/9 altcoins no diagnóstico secundário.
- BTC supera pseudo-líderes e circular shifts após Holm.
- Nenhuma concentração superior a 30% por ativo, dia ou bloco.
- Resultado não desaparece ao controlar `A_t` e own-lag.
- Amostra e qualidade de dados suficientes.
- Manipulação coerente e sem lookahead.

Mesmo se todos passarem, a decisão máxima será:

`DEVELOPMENT BTC LEAD-LAG SIGNAL DETECTED — PROSPECTIVE HOLDOUT REQUIRED`

Não haverá aceite final nem estratégia.

### Fracasso

Rejeitar no escopo primário se qualquer requisito econômico central falhar:

- Efeito contínuo `<= 0` ou CI cruza zero.
- Efeito condicional não supera unconditional/placebo.
- Média ou mediana líquida `<= 0` no cenário conservador.
- BTC não supera pseudo-líderes.
- Consistência entre blocos/ativos falha.
- Concentração material.
- Efeito explicado por common movement/autocorrelação.
- Integridade ou leakage invalida contraste.

Classificar como inconclusivo apenas se dados, amostra ou integridade impedirem o teste.

Proibido após falha:

- Testar outro lag.
- Criar threshold.
- Escolher subgrupo de ativos.
- Mudar custo.
- Transformar pseudo-líder vencedor em nova hipótese automática.

## 11. Experimento mínimo de refutação

O gate mínimo de A01 deve usar somente dados atuais e responder:

1. `beta` de `X_t` sobre `Y_t+1`, controlando `A_t` e `Y_t`, é positivo com CI95 acima de zero?
2. O contraste econômico `X_t > 0` produz média e mediana líquidas positivas no cenário conservador?
3. BTC supera circular shifts e pseudo-líderes após Holm?
4. O efeito replica em blocos e no diagnóstico por ativo?
5. A qualidade dos dados permite inferência sem lookahead?

Se `beta`, contraste econômico ou especificidade de BTC falhar, parar A01 sem robustness, neighborhood, walk-forward ou backtest.

Este gate não deve construir estratégia. Ele é apenas refutação científica barata.

## 12. Artefatos necessários futuros

Não criar agora. Nomes estáveis sugeridos para execução futura autorizada:

- `ph4_a01_preregistration.md`
- `ph4_a01_preregistration.json`
- `ph4_a01_frozen_design.json`
- `ph4_a01_data_manifest_hashes.json`
- `ph4_a01_execution_inventory.json`
- `ph4_a01_integrity_check.json`
- `ph4_a01_results.md`
- `ph4_a01_results.json`
- `ph4_a01_results.html`
- `ph4_a01_audit_decision.md`
- `ph4_a01_audit_decision.json`
- `ph4_a01_audit_decision.html`

## 13. Reutilização e capacidade nova

### Módulos existentes reutilizáveis

- ExperimentManager/ExperimentDatabase/ResearchSession: rastreabilidade de estudos e IDs, se uma execução formal for autorizada.
- dataset_builder/auditorias de cobertura e hash: manifest, integridade, cobertura e reprodutibilidade.
- domain_decomposition_research: consistência por ativo, apenas diagnóstico.
- robustness_analyzer: somente após gate mínimo e sem backtest.
- walk_forward_analyzer: somente após gate mínimo e sem backtest operacional.
- result_parser/comparison_report/html_dashboard: geração de artefatos.
- market_regime_profiler: apenas como diagnóstico posterior pré-especificado, não na primeira campanha.

### Módulos não prioritários

Não reutilizar nesta hipótese:

- Estratégias.
- Plugins.
- BacktestRunner operacional.
- ParameterGenerator.
- Hyperopt.
- Ranking de parâmetros.

### Capacidade nova realmente necessária

No máximo uma capacidade conceitual nova:

Um analisador offline isolado de lead-lag cross-asset com:

- sincronização dos dez pares;
- construção de `X_t`, `A_t`, `Y_t` e `Y_t+1`;
- regressão/contrastes;
- block bootstrap por dias UTC;
- pseudo-líderes;
- placebos;
- auditoria de integridade;
- exportação de artefatos.

Não implementar nesta etapa.

Se futuramente autorizado, preferir script efêmero auditável ao módulo permanente, salvo se o estudo precisar de repetibilidade formal.

## 14. Riscos metodológicos e ameaças à validade

Principais riscos:

- Common movement: BTC e altcoins podem se mover juntos no mesmo candle, sem difusão defasada.
- Autocorrelação do alt-market: resposta futura pode vir do próprio painel de altcoins.
- Latência e timestamp: candles 5m podem esconder liderança intrabar.
- Custos: um efeito estatisticamente positivo pode ser economicamente insuficiente.
- Multiplicidade: pseudo-líderes e placebos exigem Holm e disciplina de decisão.
- Dependência cross-asset: nove altcoins não são observações independentes.
- Dados development-consumed: qualquer detecção só seria desenvolvimento.
- Sem holdout virgem: não há confirmação definitiva.
- Reuso indevido: um pseudo-líder melhor que BTC não autoriza trocar líder pós-hoc.
- Escopo limitado: Binance spot 5m e 10 pares não provam ausência/presença universal.

Mitigações:

- Controle `A_t`.
- Controle own-lag `Y_t`.
- Unidades por timestamp/portfólio.
- Blocos com peso igual.
- Block bootstrap por dias.
- Pseudo-líderes pré-especificados.
- Placebo circular shift.
- Gate rígido de STOP.

## 15. Decisões finais pré-registradas

As únicas decisões permitidas para o estudo futuro PH4-A01 são:

1. `DEVELOPMENT BTC LEAD-LAG SIGNAL DETECTED — PROSPECTIVE HOLDOUT REQUIRED`
2. `BTC LEAD-LAG HYPOTHESIS REJECTED IN PRIMARY SCOPE`
3. `INCONCLUSIVE BTC LEAD-LAG AUDIT`

Interpretação:

- A primeira decisão não autoriza estratégia.
- A segunda encerra A01 no escopo primário.
- A terceira só é permitida por problema real de dados, amostra ou integridade.

## 16. Auditoria de escopo

Esta etapa:

- Criou/modificou somente `PHASE4_FIRST_EXPERIMENT.md`.
- Não escreveu ou modificou código.
- Não executou backtest.
- Não executou análise estatística.
- Não fez download.
- Não criou estratégia, indicador, parâmetro de estratégia, Hyperopt ou plugin.
- Não alterou roadmap, gates, docs gerais, config, dados, SQLite, módulos ou infraestrutura.
- Não reabriu Trend/Score/Pullback/MeanReversion/ensembles.
- Não variou RST01-RST04 retrospectivamente.

Decisão executiva desta etapa:

**Selecionar A01 como primeiro experimento científico da Fase 4, exclusivamente para futura refutação/qualificação, sem autorizar implementação ou execução agora.**
