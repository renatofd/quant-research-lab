# Auditoria Científica Independente do Encerramento

## Pergunta decisória

**A decisão de encerrar definitivamente o projeto é cientificamente correta?**

**Resposta:** não. A decisão operacional de não promover um bot é correta, mas o encerramento definitivo da pesquisa não é suportado pelo próprio mapa pré-registrado. Há três hipóteses registradas, distintas e executáveis com o OHLCV já disponível que não receberam estudo primário correspondente: `A08`, `A09` e `A11`.

## Escopo e integridade da auditoria

- Auditoria exclusivamente documental e read-only.
- Nenhum código, estratégia, indicador, configuração, SQLite, OHLCV ou relatório existente foi alterado.
- Nenhum backtest, cálculo de sinal, bootstrap, download ou nova campanha foi executado.
- Documentos finais lidos integralmente: `FINAL_REPORT.md`, `FINAL_RESEARCH_REPORT.md`, `HYPOTHESIS_LEDGER_FINAL.md`, `LESSONS_LEARNED.md` e `KNOWLEDGE_BASE_FINAL.md` em `user_data/discovery/reports`.
- Relatórios primários consultados: gates PH3, RST01-RST04, A01-A07 disponíveis, market eligibility, filter information value, signal opportunity, famílias Trend/Pullback/MeanReversion/N-of-M, ensembles e single-asset.

## Achados críticos

### 1. O gate C não foi atingido

O relatório final afirma que toda hipótese economicamente plausível remanescente exige dados ausentes. Isso contradiz o pré-registro da Fase 4:

- `A08` foi definida como teste de **proxy OHLCV** de iliquidez/impacto sobre risco ou custo futuro; livro e trades eram desejáveis para validação microestrutural, não necessários para o teste limitado do proxy.
- `A09` foi definida como volume anormal passado predizendo atividade ou risco futuro, explicitamente sem inferir fluxo institucional. OHLCV era o dado mínimo declarado.
- `A11` foi definida como sazonalidade de retorno/risco em sessões, dias e fins de semana. OHLCV foi declarado disponível.

Não existem relatórios primários dedicados `PH4-A08`, `PH4-A09` ou `PH4-A11`. Logo, o estado terminal dessas três linhas não decorre de um teste direto da hipótese registrada.

### 2. Houve mudança de escopo na passagem do roadmap para o ledger

- `A08` mudou de “proxy OHLCV prediz risco/custo” para uma exigência de identificar spread, profundidade ou impacto realizado. A versão forte realmente exige microestrutura; a versão pré-registrada limitada continua testável.
- `A09` foi fechada por semelhança com o filtro de volume das estratégias. Isso é uma equivalência incorreta: um filtro de elegibilidade pergunta se volume seleciona melhores entradas de uma estratégia; `A09` pergunta se volume anormal prevê atividade/risco bruto, sem estratégia.
- `A11` foi rejeitada com base em filtros temporais condicionados a trades de estratégias já falhas. Esse estimando não equivale a testar sazonalidade incondicional de retornos ou risco do mercado.

### 3. O critério D de probabilidade inferior a 5% não é evidência independente

O valor final de `0%` resulta da ausência de hipóteses marcadas como acionáveis no registry. Ele não é uma probabilidade estimada a partir de dados, calibração histórica ou modelo de decisão. Como `A08`, `A09` e `A11` foram previamente marcadas como fechadas/bloqueadas, o zero é consequência da classificação, não validação autônoma do critério D. Portanto, não pode reforçar o gate C.

### 4. `A02` e `A05` foram rotuladas com força excessiva

- `A02`: beta `0,5918`, IC95 `[0,5528; 0,5981]`, melhora de MSE `0,3750`, 5/5 blocos e 10/10 pares positivos; falhou apenas concentração de `30,3708%` contra limite de `30%`.
- `A05`: beta `0,3652`, IC95 `[0,2924; 0,4258]`, melhora de MSE `0,1629`, 5/5 blocos e 10/10 universos leave-one-out positivos; falhou concentração de `30,3991%`.

Respeitar o limite pré-registrado impede declarar confirmação plena, mas não demonstra a nulidade. A classificação cientificamente adequada é **Inconclusiva**, com forte evidência de previsão de risco em desenvolvimento e sem autorização para inferir retorno direcional, lucro ou bot.

### 5. A base final não representa cobertura integral

`KNOWLEDGE_BASE_FINAL.md` contém 26 hipóteses, mas apenas 10 artefatos-fonte, 11 registros de evidência e uma decisão global. Isso é uma trilha de síntese, não prova de que cada hipótese recebeu um teste. Os artefatos importados cobrem os gates e A01-A07 selecionadas, porém não incluem estudo primário para `A08`, `A09` ou `A11`.

## Classificação obrigatória das 26 hipóteses

| ID | Classificação auditada | Fundamento |
|---|---|---|
| A01 | Rejeitada | Efeito econômico líquido negativo; contraste econômico sem IC positivo; BTC não superou pseudo-líderes/shift após Holm. |
| A02 | Inconclusiva | Forte previsão de risco, mas falhou marginalmente o gate de concentração e não possui holdout prospectivo. |
| A03 | Rejeitada | Melhora incremental de MSE com IC cruzando zero e concentração elevada. |
| A04 | Inconclusiva | Três de cinco blocos abaixo da amostra mínima de eventos. |
| A05 | Inconclusiva | Forte previsão de risco, mas falhou marginalmente concentração e não possui holdout prospectivo. |
| A06 | Duplicada | O contraste de laggards sobrepõe o bottom-2 diagnóstico de RST04 e a família de reversão já testada; novo horizonte seria retuning. |
| A07 | Rejeitada | O beta de compressão foi significativamente negativo, na direção oposta à hipótese de expansão. |
| A08 | Nunca testada | Não há estudo primário do proxy OHLCV incremental após controlar volatilidade/volume. |
| A09 | Nunca testada | Estudos existentes tratam volume como filtro de estratégia, não persistência bruta de atividade/risco. |
| A10 | Bloqueada por dados | Identificar liquidity grab/stop-run como mecanismo exige livro, trades agressor ou eventos de liquidação; candle-only mudaria o objeto. |
| A11 | Nunca testada | Market eligibility usa trades selecionados; não testa sazonalidade bruta de retorno/risco. |
| B12 | Bloqueada por dados | Funding, basis e perp ausentes. |
| B13 | Bloqueada por dados | Open interest e funding ausentes. |
| B14 | Bloqueada por dados | Eventos de liquidação, OI e perp ausentes. |
| B15 | Bloqueada por dados | Painel sincronizado spot-perp ausente. |
| B16 | Bloqueada por dados | Trades tick e lado agressor/passivo ausentes. |
| B17 | Bloqueada por dados | Livro, profundidade e spread ausentes. |
| B18 | Bloqueada por dados | Preços/custos sincronizados de múltiplas exchanges ausentes. |
| B19 | Bloqueada por dados | Painel cross-sectional de funding/carry ausente. |
| B20 | Bloqueada por dados | Fluxos de stablecoins e rótulos de exchange ausentes. |
| B21 | Bloqueada por dados | Fluxos on-chain e rótulos de endereços ausentes. |
| B22 | Bloqueada por dados | Calendário, consenso e surpresa macro timestampados ausentes. |
| B23 | Bloqueada por dados | Cadeias de opções, superfícies e forwards ausentes. |
| B24 | Bloqueada por dados | Calendário prospectivo de unlocks, vesting e free float ausente. |
| B25 | Bloqueada por dados | Eventos prospectivos e classificação de surpresa ausentes. |
| B26 | Bloqueada por dados | Sentimento/atenção com proveniência e timestamps sem leakage ausente. |

### Contagem auditada

- Confirmada: `0`
- Rejeitada: `3`
- Inconclusiva: `3`
- Nunca testada: `3`
- Duplicada: `1`
- Bloqueada por dados: `16`
- Total: `26`

## Hipóteses executáveis ainda não investigadas

### A08 — Proxy OHLCV de iliquidez/impacto

- Diferença: testa valor incremental de um proxy bruto sobre risco/custo aproximado; não é filtro de entrada nem afirma medir livro real.
- Dados necessários: retornos, volume e OHLCV já existentes.
- Limite: confirmação do mecanismo de liquidez real continuaria dependente de livro/trades.
- Executável no laboratório atual: **sim, apenas no escopo limitado de proxy**.

### A09 — Volume anormal e persistência de atividade/risco

- Diferença: estima persistência bruta de atividade/risco; não pergunta se o filtro de volume melhora TrendStrategy.
- Dados necessários: volume e OHLCV já existentes.
- Limite: não permite inferir fluxo institucional ou agressor/passivo.
- Executável no laboratório atual: **sim**.

### A11 — Sazonalidade bruta

- Diferença: mede retorno/risco do mercado por calendário na grade completa; market eligibility mede somente trades selecionados por estratégias.
- Dados necessários: timestamps UTC, retornos e OHLCV já existentes.
- Limite: os dados são development-consumed e qualquer resultado positivo exigiria confirmação prospectiva.
- Executável no laboratório atual: **sim**.

## Sobreposição e consistência metodológica

- A06 é adequadamente impedida pela regra antirreciclagem: o bottom-2 de RST04 já foi negativo e um novo horizonte seria seleção retrospectiva.
- A10 deve permanecer bloqueada; chamar um padrão de candle de “liquidity grab” sem microestrutura seria erro de identificação.
- B12-B26 representam mecanismos distintos, embora existam dependências (`B13/B19` dependem de `B12`); dependência não equivale a duplicação.
- Os critérios econômicos foram corretamente rigorosos para promoção operacional. O erro está em extrapolar “não promovível” para “hipótese rejeitada” e em substituir estimandos brutos por resultados condicionados a estratégias.

## Resultados positivos que não autorizam promoção

- A02 e A05 preservam informação de risco estatisticamente forte, mas não demonstram retorno líquido direcional.
- RST02 e RST03 preservaram efeitos incrementais relativos, porém permaneceram economicamente negativos após custos.
- LTC apresentou platô local (`354/381` vizinhos com PF > 1), mas nenhum resultado com mais de 100 trades, zero regiões robustas e nenhum holdout independente. Não é candidata operacional.
- Nenhuma família existente satisfaz simultaneamente PF robusto, expectativa positiva, Survival >=60%, estabilidade e holdout.

## Auditoria dos critérios de parada

| Critério | Situação auditada |
|---|---|
| A — 30 hipóteses testadas | **Não atingido:** 26 registradas e somente parte testada diretamente. |
| B — nenhuma hipótese economicamente fundamentada restante | **Não atingido:** A08, A09 e A11 permanecem distintas e falsificáveis. |
| C — restantes dependem de dados indisponíveis | **Não atingido:** A08/A09/A11 usam OHLCV atual no escopo registrado. |
| D — expectativa científica inferior a 5% | **Não demonstrado:** 0% deriva do registry sem hipóteses acionáveis, não de estimativa independente. |

## Limite da conclusão

Esta auditoria **não** encontrou estratégia robusta, não reabilita nenhuma família encerrada e não autoriza bot, Dry Run ou capital real. Ela conclui apenas que “nenhum bot foi demonstrado” é suportado, enquanto “toda pesquisa executável terminou” não é.

## DECISÃO B

Existe pelo menos uma hipótese executável ainda não investigada.

- `A08 — Proxy OHLCV de iliquidez/impacto`
- `A09 — Volume anormal e persistência de atividade/risco`
- `A11 — Sazonalidade bruta de retorno/risco`
