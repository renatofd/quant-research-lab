# PHASE4_RESEARCH_ROADMAP.md

# Fase 4 — Economic Hypothesis Discovery

## Título e mandato

A Fase 4 muda o objeto de pesquisa. O laboratório não está mais procurando uma estratégia, um indicador ou uma combinação de filtros. O mandato agora é descobrir quais ineficiências econômicas merecem investigação científica futura.

O papel desta fase é formular hipóteses econômicas falsificáveis, definir dados necessários, separar o que pode ser testado com o inventário atual do que exige nova aquisição de dados, e impedir que resultados encerrados sejam reembalados com outro nome.

Este documento não autoriza implementação, backtest, Hyperopt, plugin, robô, indicador ou campanha. Ele é uma agenda científica.

## Estado herdado e fronteira científica

Os gates finais de Fase 3 prevalecem sobre `RESEARCH_HANDBOOK.md` e `CURRENT_STATE.md`, que estão historicamente defasados para decisões atuais.

Estado vinculante:

- PH3-GATE02: `STOP ALL EXISTING FAMILIES — SCIENTIFIC RESET`.
- PH3-RST-GATE01: `STOP RAW SIGNAL SEARCH — NO ARCHITECTURE JUSTIFIED`.
- Trend/Score/Pullback/MeanReversion, ensembles e variações permanecem encerrados.
- RST01, trend absoluto em 2h, não detectou sinal líquido econômico.
- RST02, mean reversion absoluto em 2h, teve pequena melhora relativa versus unconditional, mas permaneceu líquido negativo.
- RST03, expansão direcional de volatilidade condicionada a momentum, teve efeito incremental positivo versus momentum-only, mas permaneceu líquido negativo.
- RST04, relative strength top-2 em 2h, não superou equal-weight nem placebo.

Nuance importante: RST02 e RST03 preservam conhecimento estatístico. Eles não autorizam ajuste de thresholds, combinação de sinais, mudança de horizonte ou criação de uma nova arquitetura.

A fronteira científica atual é esta:

- O que está encerrado: arquiteturas de estratégia existentes e sinais brutos simples testados em OHLCV 5m no universo atual.
- O que permanece aberto: hipóteses econômicas novas, com mecanismo claro, unidade inferencial adequada e, quando necessário, novos dados.
- O que não pode ser feito agora: reabrir famílias antigas, renomear indicadores como mecanismos econômicos, ou procurar o “menos ruim” nos mesmos blocos consumidos.

## Inventário de dados e capacidades

### Dados confirmados

O laboratório possui:

- OHLCV spot Binance.
- Timeframe 5m.
- Formato Feather.
- 10 pares contra USDT: BTC, ETH, SOL, BNB, XRP, ADA, DOGE, LINK, AVAX e LTC.
- Cobertura histórica já consumida em desenvolvimento.
- Nenhum holdout virgem.

O laboratório não possui:

- Funding.
- Basis.
- Open interest.
- Liquidações.
- Trades agressor/passivo.
- Livro de ofertas.
- Dados multi-exchange.
- Opções.
- Dados on-chain.
- Stablecoin issuance/flows.
- Macro surprises.
- Token unlocks.
- Sentimento.

### Capacidades reutilizáveis em nível conceitual

Podem ser reaproveitadas conceitualmente, sem priorizar estratégia/plugin/backtest:

- ExperimentManager, ExperimentDatabase e ResearchSession, apenas para rastreabilidade experimental.
- robustness_analyzer, neighborhood_explorer e walk_forward_analyzer, apenas se a hipótese tiver desenho compatível.
- ranking_engine, result_parser, comparison_report e html_dashboard, apenas como infraestrutura de relatório.
- market_regime_profiler e market_eligibility_research, se o regime for variável econômica pré-especificada.
- domain_decomposition_research, para segmentação por ativo ou grupo quando a hipótese justificar.
- signal_opportunity_analyzer e filter_information_value_analyzer, somente quando a hipótese e os dados forem compatíveis.
- dataset_builder/exportação e auditorias de hashes/cobertura, para QA e reprodutibilidade.

Não são reutilização prioritária nesta fase:

- Módulos de estratégia.
- Plugins de estratégia.
- Backtest operacional.
- Geradores de parâmetros.
- Hyperopt.

## Taxonomia do espaço de hipóteses

A Fase 4 organiza hipóteses por mecanismo econômico, não por indicador.

### Grupo A — Testáveis com OHLCV atual, com limitações

Estas hipóteses podem ser estudadas com os dados atuais apenas como associação estatística em OHLCV. Elas não suportam causalidade forte, microestrutura real ou identificação de fluxo institucional.

1. Liderança BTC e transmissão defasada para altcoins.
2. Persistência de volatilidade como previsão de risco, não direção.
3. Assimetria de volatilidade e jumps positivos versus negativos.
4. Co-jumps, contágio e propagação cross-asset.
5. Dispersão cross-sectional como estado de mercado.
6. Reversão cross-sectional em horizonte economicamente distinto dos testes encerrados.
7. Compressão de volatilidade seguida de expansão, como previsão de magnitude.
8. Iliquidez/preço-impacto aproximado por OHLCV.
9. Volume anormal e persistência de fluxo como proxy fraco.
10. Falsos rompimentos/liquidity grabs, hipótese fraca com candles.
11. Sazonalidade/session/weekend, prioridade baixa.

### Grupo B — Maior clareza econômica, exigem novos dados

Estas hipóteses possuem mecanismo econômico mais limpo, mas não podem ser testadas corretamente com o inventário atual.

12. Funding/basis como prêmio de carry e crowding.
13. Mudanças de open interest + funding como acúmulo de alavancagem.
14. Cascatas de liquidação e overshoot/reversão pós-forced-flow.
15. Liderança spot versus perp e descoberta de preço.
16. Desequilíbrio de order flow agressor/passivo.
17. Desequilíbrio/profundidade do livro e retirada de liquidez.
18. Fragmentação entre exchanges e limites à arbitragem.
19. Dispersão de funding/carry cross-sectional.
20. Fluxos de stablecoins para exchanges.
21. Fluxos on-chain de entrada/saída de exchanges.
22. Macro announcements e surpresas.
23. Variance/jump/skew risk premia de opções.
24. Choques de oferta por token unlock/vesting.
25. Listings/delistings/regulatory events.
26. Atenção/sentimento.

### Grupo C — Descartes imediatos

Descartados nesta fase:

- Reembalar EMA/ATR/RSI/Bollinger ou filtros antigos como hipótese econômica.
- Reabrir Trend/Score/Pullback/MeanReversion/ensembles.
- Repetir RST01-RST04 mudando horizontes, thresholds ou top-k nos dados consumidos.
- “Volume institucional” inferido apenas de OHLCV.
- Calendar/session/weekend como primeira prioridade.
- DEX/MEV se o escopo operacional continuar Binance spot/Freqtrade.
- ML/sentimento sem hipótese econômica, proveniência e holdout prospectivo.

## Fichas individuais

### A01 — Liderança BTC e transmissão defasada para altcoins

- Formulação falsificável: movimentos de BTC precedem retornos ou risco de altcoins em janelas futuras, além do retorno simultâneo comum do mercado.
- Fundamento econômico: BTC pode funcionar como ativo âncora de atenção, liquidez e beta de mercado.
- Literatura: fatores comuns e riscos em cripto são discutidos por Liu, Tsyvinski e Wu; price discovery é motivado por Alexander, Heck e Kaeck. Evidência acadêmica não prova efeito no nosso universo.
- Por que poderia existir em cripto: BTC concentra liquidez, notícia e referência de preço.
- Dados necessários: OHLCV sincronizado por par; idealmente dados de derivativos para separar spot/perp.
- Dados atuais: sim, parcialmente.
- Módulos reutilizáveis: dataset/auditorias, domain_decomposition_research, market_regime_profiler.
- Capacidade nova necessária: protocolo de lead-lag cross-asset em nível de evento/tempo, conceitual.
- Protocolo científico: pré-registrar direção BTC para altcoins, comparar contra altcoin equal-weight e placebo por circular shift temporal dentro de bloco.
- Resultado/contraste principal: retorno ou risco futuro de altcoins condicionado ao movimento anterior de BTC versus baseline simultâneo/incondicional.
- Controles/placebos: shift temporal, permutação de labels por bloco, controle de mercado equal-weight.
- Risco de overfitting: médio, especialmente por múltiplos lags.
- Custo computacional: baixo.
- Potencial de generalização: médio, se replicar em múltiplos ativos e blocos.
- Dificuldade experimental: média.
- Prioridade científica: P0.
- Dependências: holdout prospectivo antes de qualquer interpretação operacional.
- Condição objetiva de rejeição: efeito não supera baseline/placebo ou concentra em poucos ativos/blocos.

### A02 — Persistência de volatilidade como previsão de risco

- Formulação falsificável: estados de alta volatilidade passada predizem maior magnitude futura de retorno, independentemente da direção.
- Fundamento econômico: clustering de volatilidade e persistência de incerteza.
- Literatura: Zhang e Zhao discutem good/bad volatility e signed jumps; risco e fatores em cripto aparecem em Liu, Tsyvinski e Wu.
- Por que poderia existir em cripto: negociação contínua, alavancagem e fluxo global podem manter regimes de risco.
- Dados necessários: OHLCV; idealmente realized volatility intrabar/trades para melhor medição.
- Dados atuais: sim.
- Módulos reutilizáveis: market_regime_profiler, market_eligibility_research, robustness_analyzer.
- Capacidade nova necessária: estudo de magnitude/risk forecasting, não retorno direcional.
- Protocolo científico: prever valor absoluto ou variância futura, comparar contra baseline de volatilidade incondicional e placebo temporal.
- Resultado/contraste principal: erro/ordenação de risco futuro, não lucro.
- Controles/placebos: circular shift, bloco temporal, comparação com volatilidade incondicional.
- Risco de overfitting: baixo a médio.
- Custo computacional: baixo.
- Potencial de generalização: alto para risco, baixo para direção.
- Dificuldade experimental: baixa.
- Prioridade científica: P0.
- Dependências: definir gate de utilidade como previsão de risco, não estratégia.
- Condição objetiva de rejeição: não melhora previsão de magnitude fora de bloco versus baseline simples.

### A03 — Assimetria de volatilidade e jumps positivos versus negativos

- Formulação falsificável: volatilidade/jumps positivos e negativos têm efeitos futuros diferentes sobre risco e retorno.
- Fundamento econômico: choques bons e ruins podem carregar informação distinta sobre liquidez, desalavancagem e atenção.
- Literatura: Zhang e Zhao tratam good/bad volatility e signed jumps; evidência deve ser vista como working paper/preprint quando aplicável.
- Por que poderia existir em cripto: quedas podem envolver liquidações; altas podem envolver squeeze ou entrada de fluxo.
- Dados necessários: OHLCV; melhor com trades/liquidações.
- Dados atuais: parcial.
- Módulos reutilizáveis: market_regime_profiler, dataset_builder/auditorias.
- Capacidade nova necessária: decomposição direcional de jumps em OHLCV, conceitual.
- Protocolo científico: classificar eventos por sinal e magnitude do jump passado, medir risco/retorno futuro contra eventos neutros.
- Resultado/contraste principal: diferença entre pós-jump positivo, pós-jump negativo e baseline.
- Controles/placebos: permutação de sinais, blocos, controle de volatilidade total.
- Risco de overfitting: médio.
- Custo computacional: baixo.
- Potencial de generalização: médio.
- Dificuldade experimental: média.
- Prioridade científica: P1.
- Dependências: cuidado para não confundir com RST03; foco é assimetria de risco/jump.
- Condição objetiva de rejeição: efeitos simétricos ou não replicáveis por bloco/ativo.

### A04 — Co-jumps, contágio e propagação cross-asset

- Formulação falsificável: eventos extremos simultâneos em subconjunto de ativos predizem risco futuro elevado ou propagação para ativos ainda não afetados.
- Fundamento econômico: contágio, liquidez comum e desalavancagem de carteiras.
- Literatura: high-frequency macro news and crypto co-jumps motiva co-movimentos; fatores comuns em cripto também aparecem em Liu, Tsyvinski e Wu.
- Por que poderia existir em cripto: mercado 24/7 com traders alavancados e portfólios multiativo.
- Dados necessários: OHLCV sincronizado; idealmente liquidações/open interest.
- Dados atuais: sim, parcialmente.
- Módulos reutilizáveis: domain_decomposition_research, market_regime_profiler.
- Capacidade nova necessária: estudo de eventos co-jump e propagação temporal.
- Protocolo científico: identificar co-jumps usando apenas passado/simultâneo, medir propagação futura para não-jumpers versus placebo.
- Resultado/contraste principal: aumento de magnitude futura ou probabilidade de jump em ativos não afetados.
- Controles/placebos: permutar ativos por timestamp, shift temporal por bloco.
- Risco de overfitting: médio.
- Custo computacional: baixo.
- Potencial de generalização: médio a alto.
- Dificuldade experimental: média.
- Prioridade científica: P0.
- Dependências: holdout para validação.
- Condição objetiva de rejeição: sem propagação além da co-movimentação simultânea.

### A05 — Dispersão cross-sectional como estado de mercado

- Formulação falsificável: alta dispersão entre retornos dos 10 pares identifica estados futuros de risco/instabilidade diferentes de baixa dispersão.
- Fundamento econômico: dispersão pode indicar rotação, desalinhamento de liquidez ou fragmentação de atenção.
- Literatura: fatores comuns em cripto e cross-sectional risk podem ser motivados por Liu, Tsyvinski e Wu.
- Por que poderia existir em cripto: narrativas setoriais e liquidez desigual entre altcoins.
- Dados necessários: OHLCV sincronizado; melhor com volume/liquidez real.
- Dados atuais: sim.
- Módulos reutilizáveis: domain_decomposition_research, market_regime_profiler.
- Capacidade nova necessária: estudo de estado de dispersão, não seleção top-k.
- Protocolo científico: condicionar risco/magnitude futura do universo ao estado de dispersão anterior.
- Resultado/contraste principal: risco futuro do universo ou estabilidade cross-asset versus dispersão incondicional.
- Controles/placebos: permutação temporal, equal-weight baseline.
- Risco de overfitting: baixo a médio.
- Custo computacional: baixo.
- Potencial de generalização: médio.
- Dificuldade experimental: baixa.
- Prioridade científica: P0.
- Dependências: não confundir com RST04 top-2; aqui o alvo é estado de mercado.
- Condição objetiva de rejeição: dispersão não prediz risco/magnitude fora da amostra.

### A06 — Reversão cross-sectional em horizonte economicamente distinto

- Formulação falsificável: ativos que ficaram relativamente para trás versus o universo revertem em janelas futuras quando a unidade econômica é cross-sectional, não mean reversion time-series.
- Fundamento econômico: rotação relativa, overshooting de curto prazo e recomposição de beta.
- Literatura: Dobrynskaya discute momentum e reversal em criptomoedas; status pode incluir working paper e resultados conflitantes.
- Por que poderia existir em cripto: rotação entre majors e altcoins, efeitos de atenção e liquidez.
- Dados necessários: OHLCV sincronizado; idealmente custos/slippage mais realistas.
- Dados atuais: parcial.
- Módulos reutilizáveis: domain_decomposition_research, ranking/reporting.
- Capacidade nova necessária: estudo cross-sectional contrarian com hipótese separada.
- Protocolo científico: comparar bottom relative performers contra equal-weight e placebo, sem reutilizar RST02/RST04.
- Resultado/contraste principal: retorno líquido relativo de laggards versus universo.
- Controles/placebos: rank permutation, equal-weight, bloqueio temporal.
- Risco de overfitting: alto, devido à proximidade com testes encerrados.
- Custo computacional: baixo.
- Potencial de generalização: médio-baixo.
- Dificuldade experimental: média.
- Prioridade científica: P2.
- Dependências: só deve avançar após gate e preregistro rígido; não reabre MeanReversionStrategy.
- Condição objetiva de rejeição: efeito líquido não positivo ou não supera equal-weight/placebo.

### A07 — Compressão de volatilidade seguida de expansão

- Formulação falsificável: compressão passada de volatilidade prediz aumento futuro de magnitude, sem necessariamente prever direção.
- Fundamento econômico: acumulação de energia de preço, transição de regime e atenção latente.
- Literatura: volatilidade/jump risk é discutida por Zhang e Zhao; literatura de seasonality e risk factors não prova esse mecanismo.
- Por que poderia existir em cripto: regimes de baixa liquidez podem preceder repricing rápido.
- Dados necessários: OHLCV; melhor com livro/trades.
- Dados atuais: sim, com limitação.
- Módulos reutilizáveis: market_regime_profiler, robustness_analyzer.
- Capacidade nova necessária: protocolo de previsão de magnitude pós-compressão.
- Protocolo científico: identificar compressão com dados passados, medir distribuição da magnitude futura versus baseline.
- Resultado/contraste principal: magnitude futura, não retorno direcional.
- Controles/placebos: shift temporal, controle de volatilidade média por bloco.
- Risco de overfitting: médio.
- Custo computacional: baixo.
- Potencial de generalização: médio.
- Dificuldade experimental: média.
- Prioridade científica: P1.
- Dependências: deve evitar virar Bollinger/ATR operacional.
- Condição objetiva de rejeição: compressão não melhora previsão de magnitude futura.

### A08 — Iliquidez/preço-impacto aproximado por OHLCV

- Formulação falsificável: proxies simples de impacto/iliquidez baseados em candle e volume predizem pior eficiência, maior risco ou reversão de micro preço.
- Fundamento econômico: menor liquidez aumenta impacto e ruído.
- Literatura: price discovery e limit orders em Bitcoin são discutidos por Alexander, Heck e Kaeck; OHLCV é proxy fraco para microestrutura.
- Por que poderia existir em cripto: liquidez fragmentada e profundidade variável.
- Dados necessários: OHLCV para proxy; livro/trades para teste correto.
- Dados atuais: parcial.
- Módulos reutilizáveis: market_eligibility_research, domain_decomposition_research.
- Capacidade nova necessária: QA de proxy de iliquidez e validação contra dados microestruturais no futuro.
- Protocolo científico: testar se estados de baixa liquidez proxy predizem risco/custo, não edge direcional.
- Resultado/contraste principal: aumento de risco, spread proxy ou slippage esperado.
- Controles/placebos: controle por volatilidade, volume e par.
- Risco de overfitting: alto com OHLCV.
- Custo computacional: baixo.
- Potencial de generalização: médio se confirmado com livro.
- Dificuldade experimental: média.
- Prioridade científica: P2.
- Dependências: não chamar proxy de liquidez institucional.
- Condição objetiva de rejeição: proxy não prediz custo/risco ou não replica com dados de livro.

### A09 — Volume anormal e persistência de fluxo como proxy

- Formulação falsificável: volume anormal passado prediz persistência de atividade ou risco futuro, sem inferir identidade institucional.
- Fundamento econômico: chegada de informação e atenção pode elevar volume por algum tempo.
- Literatura: wash trading em Cong et al. alerta que volume cripto pode ser contaminado; usar como proxy exige ceticismo.
- Por que poderia existir em cripto: atenção social, eventos e liquidez concentrada.
- Dados necessários: OHLCV; idealmente trades/aggressor side.
- Dados atuais: parcial.
- Módulos reutilizáveis: filter_information_value_analyzer apenas se compatível, market_regime_profiler.
- Capacidade nova necessária: protocolo de volume como proxy de atividade, não fluxo institucional.
- Protocolo científico: testar persistência de volume/volatilidade e impacto em custos futuros.
- Resultado/contraste principal: risco/atividade futura, não retorno direcional.
- Controles/placebos: controle por volatilidade, par e bloco.
- Risco de overfitting: alto.
- Custo computacional: baixo.
- Potencial de generalização: baixo-médio.
- Dificuldade experimental: baixa.
- Prioridade científica: P2.
- Dependências: não inferir institucional com OHLCV.
- Condição objetiva de rejeição: volume não melhora previsão de atividade/risco após controles.

### A10 — Falsos rompimentos/liquidity grabs com candles

- Formulação falsificável: candles que excedem extremos recentes e retornam ao range carregam informação sobre risco ou reversão futura.
- Fundamento econômico: busca por liquidez e stop runs, mas identificação real exige livro/fluxo.
- Literatura: price discovery e limit orders motivam microestrutura, mas candles não identificam liquidity grabs plenamente.
- Por que poderia existir em cripto: alavancagem, stops e baixa profundidade em altcoins.
- Dados necessários: OHLCV para proxy fraco; livro/trades para evidência forte.
- Dados atuais: parcial fraco.
- Módulos reutilizáveis: market_regime_profiler, signal_opportunity_analyzer apenas se hipótese for compatível.
- Capacidade nova necessária: estudo de evento candle-only com linguagem de proxy.
- Protocolo científico: medir comportamento futuro após rompimento revertido versus rompimento sustentado.
- Resultado/contraste principal: risco/reversão pós-evento.
- Controles/placebos: controle por volatilidade e tamanho do candle, shift temporal.
- Risco de overfitting: alto.
- Custo computacional: baixo.
- Potencial de generalização: baixo sem microestrutura.
- Dificuldade experimental: média.
- Prioridade científica: P3.
- Dependências: não usar como primeira hipótese.
- Condição objetiva de rejeição: sem efeito replicável ou dependente de poucos eventos.

### A11 — Sazonalidade/session/weekend

- Formulação falsificável: blocos de tempo apresentam diferença replicável de risco/retorno líquido.
- Fundamento econômico: variação de participantes, liquidez e calendário global.
- Literatura: estudo recente sobre seasonality em criptomoedas sugere cautela; evidência pode ser fraca e instável.
- Por que poderia existir em cripto: 24/7, fins de semana e sobreposição de sessões.
- Dados necessários: OHLCV; melhor com liquidez/spread.
- Dados atuais: sim.
- Módulos reutilizáveis: market_eligibility_research.
- Capacidade nova necessária: nenhum módulo prioritário; apenas gate específico se autorizado.
- Protocolo científico: comparar blocos temporais pré-especificados com ajuste de múltiplos testes.
- Resultado/contraste principal: retorno líquido/risco por sessão versus baseline.
- Controles/placebos: permutação de labels temporais por bloco.
- Risco de overfitting: alto.
- Custo computacional: baixo.
- Potencial de generalização: baixo.
- Dificuldade experimental: baixa.
- Prioridade científica: P3.
- Dependências: não primeira prioridade.
- Condição objetiva de rejeição: efeito instável ou eliminado por custos/múltiplos testes.

### B12 — Funding/basis como prêmio de carry e crowding

- Formulação falsificável: funding/basis extremos predizem retornos futuros, carry ou reversão de crowding.
- Fundamento econômico: compensação por carregar posição e desequilíbrio entre perp/futuro e spot.
- Literatura: Chi et al. discutem risk factors/basis em crypto futures; Makarov e Schoar tratam arbitragem e fricções em mercados cripto.
- Por que poderia existir em cripto: perps dominam volume, alavancagem e crowding.
- Dados necessários: funding, perp prices, spot prices, futures basis.
- Dados atuais: não.
- Módulos reutilizáveis: ExperimentDatabase/ResearchSession para rastreabilidade; comparison_report.
- Capacidade nova necessária: ingestão e QA conceitual de derivativos.
- Protocolo científico: estudar carry/basis pré-especificado versus spot returns e custo de funding.
- Resultado/contraste principal: retorno líquido/carry ajustado a risco versus baseline.
- Controles/placebos: exchange/pair fixed effects, shift temporal, controle de mercado.
- Risco de overfitting: médio.
- Custo computacional: médio.
- Potencial de generalização: alto.
- Dificuldade experimental: média-alta.
- Prioridade científica: P0 para dados novos.
- Dependências: fonte confiável de funding/basis.
- Condição objetiva de rejeição: funding/basis não prediz retorno/carry fora da amostra.

### B13 — Open interest + funding como acúmulo de alavancagem

- Formulação falsificável: aumento de open interest junto a funding extremo identifica crowding e risco futuro de unwind.
- Fundamento econômico: posições alavancadas acumuladas podem amplificar movimentos.
- Literatura: risk factors/basis em crypto futures e arbitrage limits motivam a hipótese; evidência depende de fonte.
- Por que poderia existir em cripto: perps com funding e OI transparentes.
- Dados necessários: open interest, funding, perp/spot OHLCV.
- Dados atuais: não.
- Módulos reutilizáveis: market_regime_profiler em nível conceitual.
- Capacidade nova necessária: dataset de derivativos e QA de timestamps/exchanges.
- Protocolo científico: condicionar eventos de funding+OI a risco futuro e drawdown de mercado.
- Resultado/contraste principal: risco/reversão pós-crowding versus baseline.
- Controles/placebos: pares, bloco temporal, shift de OI, controle de volatilidade.
- Risco de overfitting: médio.
- Custo computacional: médio.
- Potencial de generalização: alto.
- Dificuldade experimental: alta.
- Prioridade científica: P0.
- Dependências: aquisição de OI limpo.
- Condição objetiva de rejeição: sem relação replicável entre crowding proxy e risco futuro.

### B14 — Cascatas de liquidação e overshoot pós-forced-flow

- Formulação falsificável: clusters de liquidações predizem overshoot, risco elevado ou reversão posterior.
- Fundamento econômico: forced selling/buying temporário e desalavancagem.
- Literatura: literatura de limites à arbitragem e microestrutura cripto motiva, mas dados de liquidação são necessários.
- Por que poderia existir em cripto: alavancagem alta e liquidações automáticas em perps.
- Dados necessários: liquidações por símbolo/exchange, perp/spot OHLCV, funding/OI.
- Dados atuais: não.
- Módulos reutilizáveis: event-study reporting, robustness/walk-forward conceituais.
- Capacidade nova necessária: estudo de eventos de liquidação.
- Protocolo científico: event study de janelas pós-liquidação, separando direção e tamanho.
- Resultado/contraste principal: retorno/risk pós-evento versus placebo de eventos aleatórios.
- Controles/placebos: eventos aleatórios pareados por volatilidade, exchange e horário.
- Risco de overfitting: médio.
- Custo computacional: médio.
- Potencial de generalização: alto.
- Dificuldade experimental: alta.
- Prioridade científica: P0.
- Dependências: dados de liquidação confiáveis.
- Condição objetiva de rejeição: eventos não superam placebo pareado.

### B15 — Liderança spot versus perp e descoberta de preço

- Formulação falsificável: spot ou perp lidera o outro em determinados regimes, gerando informação de price discovery.
- Fundamento econômico: mercado dominante incorpora informação primeiro; arbitragem corrige defasagem.
- Literatura: Alexander, Heck e Kaeck estudam price discovery e limit orders; Makarov e Schoar tratam arbitragem em cripto.
- Por que poderia existir em cripto: perps podem concentrar especulação; spot pode ancorar fluxo real.
- Dados necessários: spot e perp sincronizados, trades/livro idealmente.
- Dados atuais: não, apenas spot.
- Módulos reutilizáveis: domain_decomposition_research conceitualmente.
- Capacidade nova necessária: sincronização multi-mercado spot/perp.
- Protocolo científico: testar lead-lag entre spot/perp por ativo, com placebo temporal.
- Resultado/contraste principal: informação incremental de um mercado para o outro.
- Controles/placebos: shift temporal, controle por volatilidade e funding.
- Risco de overfitting: médio.
- Custo computacional: médio.
- Potencial de generalização: alto.
- Dificuldade experimental: alta.
- Prioridade científica: P0.
- Dependências: dados spot/perp consistentes.
- Condição objetiva de rejeição: sem liderança replicável após custos/latência.

### B16 — Desequilíbrio de order flow agressor/passivo

- Formulação falsificável: imbalance de trades agressivos prediz pressão de curto prazo ou reversão.
- Fundamento econômico: fluxo agressor revela demanda imediata.
- Literatura: microestrutura e price discovery motivam; evidência candle-only é insuficiente.
- Por que poderia existir em cripto: dados de trades podem indicar pressão real melhor que volume agregado.
- Dados necessários: trades com side/aggressor ou reconstrução confiável.
- Dados atuais: não.
- Módulos reutilizáveis: dataset_builder conceitual.
- Capacidade nova necessária: ingestão de trades e classificação agressor/passivo.
- Protocolo científico: associar imbalance passado a retorno/risk futuro, com controle de volume e volatilidade.
- Resultado/contraste principal: efeito incremental do imbalance versus volume OHLCV.
- Controles/placebos: permutação de signs, shift temporal.
- Risco de overfitting: médio.
- Custo computacional: alto.
- Potencial de generalização: alto se dados forem bons.
- Dificuldade experimental: alta.
- Prioridade científica: P1.
- Dependências: fonte de trades confiável.
- Condição objetiva de rejeição: imbalance não supera volume/volatilidade após controles.

### B17 — Livro de ofertas, profundidade e retirada de liquidez

- Formulação falsificável: desequilíbrio ou queda de profundidade no livro prediz movimentos, risco ou slippage.
- Fundamento econômico: liquidez disponível determina impacto e fragilidade.
- Literatura: price discovery via limit orders em Bitcoin é diretamente relevante.
- Por que poderia existir em cripto: profundidade varia muito por ativo e regime.
- Dados necessários: snapshots/order book depth.
- Dados atuais: não.
- Módulos reutilizáveis: market_eligibility_research conceitual.
- Capacidade nova necessária: infraestrutura conceitual de livro, QA de snapshots, métricas de profundidade.
- Protocolo científico: testar se retirada de liquidez precede jumps/risco.
- Resultado/contraste principal: risco/slippage futuro versus baseline de profundidade normal.
- Controles/placebos: horários, volume, volatilidade, permutação temporal.
- Risco de overfitting: médio.
- Custo computacional: alto.
- Potencial de generalização: alto.
- Dificuldade experimental: alta.
- Prioridade científica: P1.
- Dependências: dados de livro e armazenamento.
- Condição objetiva de rejeição: profundidade não prediz risco/custo fora da amostra.

### B18 — Fragmentação entre exchanges e limites à arbitragem

- Formulação falsificável: spreads entre exchanges ou atraso de convergência predizem retorno de convergência ou risco.
- Fundamento econômico: limites à arbitragem e fricções de capital.
- Literatura: Makarov e Schoar são referência central para trading e arbitrage em crypto markets.
- Por que poderia existir em cripto: exchanges fragmentadas, custos de transferência e risco operacional.
- Dados necessários: multi-exchange spot/perp preços, fees, disponibilidade.
- Dados atuais: não.
- Módulos reutilizáveis: ExperimentDatabase/QA conceitual.
- Capacidade nova necessária: dataset multi-exchange sincronizado.
- Protocolo científico: medir gaps e convergência, com custos e latência realistas.
- Resultado/contraste principal: convergência líquida versus custo/fricção.
- Controles/placebos: exchange pairs aleatórios, blocos, ativos.
- Risco de overfitting: médio.
- Custo computacional: alto.
- Potencial de generalização: alto.
- Dificuldade experimental: alta.
- Prioridade científica: P1.
- Dependências: dados multi-exchange e custos.
- Condição objetiva de rejeição: gaps não são exploráveis líquidos ou não replicam.

### B19 — Dispersão de funding/carry cross-sectional

- Formulação falsificável: ativos com funding/carry relativo extremo apresentam retorno/carry futuro diferente do universo.
- Fundamento econômico: prêmio de risco, crowding e custo de alavancagem.
- Literatura: Chi et al. e fatores comuns em cripto motivam.
- Por que poderia existir em cripto: perps tornam carry observável por ativo.
- Dados necessários: funding/carry por ativo.
- Dados atuais: não.
- Módulos reutilizáveis: domain_decomposition_research conceitual.
- Capacidade nova necessária: painel cross-sectional de funding/carry.
- Protocolo científico: rankear funding relativo e medir retorno/carry futuro versus equal-weight.
- Resultado/contraste principal: prêmio de carry líquido e robustez cross-asset.
- Controles/placebos: rank permutation, controle de beta BTC.
- Risco de overfitting: médio.
- Custo computacional: médio.
- Potencial de generalização: alto.
- Dificuldade experimental: média-alta.
- Prioridade científica: P1.
- Dependências: funding histórico limpo.
- Condição objetiva de rejeição: rank de funding não prediz carry/retorno líquido.

### B20 — Fluxos de stablecoins para exchanges

- Formulação falsificável: fluxos líquidos de stablecoins para exchanges predizem liquidez, pressão compradora ou volatilidade futura.
- Fundamento econômico: stablecoins são capital pronto para negociação.
- Literatura: Lyons e Viswanath-Natraj tratam estabilidade de stablecoins; fluxos on-chain e retornos/volatilidade aparecem em literatura recente como preprint.
- Por que poderia existir em cripto: entrada de USDT/USDC em exchanges pode preceder atividade.
- Dados necessários: on-chain labeled exchange flows, stablecoin supply/flows.
- Dados atuais: não.
- Módulos reutilizáveis: market_regime_profiler conceitual.
- Capacidade nova necessária: ingestão on-chain/stablecoin com proveniência.
- Protocolo científico: event study de fluxos para exchanges versus retorno/risco futuro.
- Resultado/contraste principal: mudança de liquidez/risco após fluxo.
- Controles/placebos: fluxo placebo, blocos, controle de BTC.
- Risco de overfitting: alto.
- Custo computacional: alto.
- Potencial de generalização: médio-alto.
- Dificuldade experimental: alta.
- Prioridade científica: P2.
- Dependências: dados rotulados confiáveis.
- Condição objetiva de rejeição: fluxos não superam baseline de mercado.

### B21 — Fluxos on-chain de entrada/saída de exchanges

- Formulação falsificável: entradas/saídas on-chain de exchanges predizem venda, acumulação ou volatilidade.
- Fundamento econômico: transferência para exchange pode sinalizar intenção de negociar; retirada pode sinalizar custódia.
- Literatura: on-chain flows and returns/volatility aparece em preprint recente; evidência deve ser tratada como não consensual.
- Por que poderia existir em cripto: blockchains tornam parte do fluxo observável.
- Dados necessários: labels de endereços, flows por ativo/exchange.
- Dados atuais: não.
- Módulos reutilizáveis: event/reporting conceitual.
- Capacidade nova necessária: pipeline on-chain e QA de labels.
- Protocolo científico: estudar flows pré-especificados versus risco/retorno futuro.
- Resultado/contraste principal: efeito incremental de flow versus OHLCV.
- Controles/placebos: exchange labels alternativos, lag placebo, controle de volume.
- Risco de overfitting: alto.
- Custo computacional: alto.
- Potencial de generalização: médio.
- Dificuldade experimental: alta.
- Prioridade científica: P2.
- Dependências: fonte on-chain.
- Condição objetiva de rejeição: fluxo não adiciona informação fora da amostra.

### B22 — Macro announcements e surpresas

- Formulação falsificável: anúncios macro e surpresas geram co-jumps ou mudança de regime em crypto.
- Fundamento econômico: cripto pode carregar beta a liquidez global e risco macro.
- Literatura: high-frequency macro news and crypto co-jumps é relevante; evidência pode variar por período.
- Por que poderia existir em cripto: BTC/ETH são negociados por participantes sensíveis a liquidez global.
- Dados necessários: calendário macro, surpresa versus consenso, timestamps precisos.
- Dados atuais: não.
- Módulos reutilizáveis: event-study reporting conceitual.
- Capacidade nova necessária: dataset de eventos macro e surpresas.
- Protocolo científico: event study em janelas pré-especificadas ao redor de anúncios.
- Resultado/contraste principal: co-jump/volatilidade/retorno pós-surpresa versus dias controle.
- Controles/placebos: eventos falsos, horários pareados, controle de sessão.
- Risco de overfitting: médio.
- Custo computacional: médio.
- Potencial de generalização: médio.
- Dificuldade experimental: média-alta.
- Prioridade científica: P2.
- Dependências: dados de surpresa confiáveis.
- Condição objetiva de rejeição: eventos não alteram distribuição versus controles.

### B23 — Variance/jump/skew risk premia de opções

- Formulação falsificável: medidas implícitas de risco em opções predizem retorno, volatilidade realizada ou compensação de risco.
- Fundamento econômico: opções precificam demanda por convexidade, jumps e assimetria.
- Literatura: option-implied crypto risk premia aparece em working paper; tratar como motivação, não consenso.
- Por que poderia existir em cripto: mercado de opções BTC/ETH concentra hedging e especulação institucional.
- Dados necessários: opções, IV surface, maturities, forwards.
- Dados atuais: não.
- Módulos reutilizáveis: reporting/robustness conceitual.
- Capacidade nova necessária: ingestão e normalização de opções.
- Protocolo científico: relacionar premia implícitos a retornos/volatilidade futuros.
- Resultado/contraste principal: prêmio de risco versus realized outcomes.
- Controles/placebos: maturidade, moneyness, regime, shift temporal.
- Risco de overfitting: alto.
- Custo computacional: alto.
- Potencial de generalização: médio-alto para BTC/ETH.
- Dificuldade experimental: alta.
- Prioridade científica: P2.
- Dependências: dados de opções.
- Condição objetiva de rejeição: variáveis implícitas não predizem outcomes fora da amostra.

### B24 — Choques de oferta por token unlock/vesting

- Formulação falsificável: eventos de unlock/vesting alteram retorno, volume ou risco por pressão de oferta.
- Fundamento econômico: aumento conhecido de free float pode gerar venda antecipada ou pós-evento.
- Literatura: não há consenso único; deve ser tratado como event-driven hypothesis.
- Por que poderia existir em cripto: cronogramas de vesting são relevantes para altcoins.
- Dados necessários: calendário de unlocks, supply, free float, eventos por token.
- Dados atuais: não.
- Módulos reutilizáveis: event reporting conceitual.
- Capacidade nova necessária: dataset de eventos de oferta.
- Protocolo científico: event study pré/pós unlock com controles por mercado.
- Resultado/contraste principal: abnormal return/volume/risk versus controle.
- Controles/placebos: eventos falsos, pares sem evento, controle de beta.
- Risco de overfitting: alto.
- Custo computacional: médio.
- Potencial de generalização: médio.
- Dificuldade experimental: média-alta.
- Prioridade científica: P2.
- Dependências: fonte confiável de unlocks.
- Condição objetiva de rejeição: sem abnormal behavior replicável por evento.

### B25 — Listings, delistings e eventos regulatórios

- Formulação falsificável: eventos discretos de mercado/regulação geram retorno/risco anormal.
- Fundamento econômico: mudança de acesso, liquidez, restrição ou demanda.
- Literatura: event studies são aplicáveis; evidência específica depende do evento.
- Por que poderia existir em cripto: listings em exchanges e decisões regulatórias afetam liquidez/acesso.
- Dados necessários: calendário de eventos, timestamps, classificação de surpresa.
- Dados atuais: não.
- Módulos reutilizáveis: event reporting conceitual.
- Capacidade nova necessária: curadoria de eventos e classificação ex ante.
- Protocolo científico: event study com controles pareados e preregistro do evento.
- Resultado/contraste principal: abnormal return/volume/risk.
- Controles/placebos: datas falsas, ativos controle.
- Risco de overfitting: alto.
- Custo computacional: médio.
- Potencial de generalização: baixo-médio.
- Dificuldade experimental: média.
- Prioridade científica: P3.
- Dependências: dataset de eventos.
- Condição objetiva de rejeição: efeitos idiossincráticos sem replicação.

### B26 — Atenção e sentimento

- Formulação falsificável: medidas ex ante de atenção/sentimento predizem atividade, risco ou retorno futuro.
- Fundamento econômico: cripto é sensível a atenção, narrativas e coordenação social.
- Literatura: evidência de sentimento em ativos digitais é contestada; risco de data leakage é alto.
- Por que poderia existir em cripto: varejo, redes sociais e narrativas movem liquidez.
- Dados necessários: notícias, social, search trends, timestamps e proveniência.
- Dados atuais: não.
- Módulos reutilizáveis: nenhum prioritário além de reporting.
- Capacidade nova necessária: pipeline de texto/atenção com controle de leakage.
- Protocolo científico: eventos/scores pré-publicação versus outcomes futuros, com holdout prospectivo.
- Resultado/contraste principal: informação incremental após controlar mercado/volume.
- Controles/placebos: timestamps embaralhados, fontes atrasadas, controle de múltiplos testes.
- Risco de overfitting: muito alto.
- Custo computacional: alto.
- Potencial de generalização: baixo-médio.
- Dificuldade experimental: alta.
- Prioridade científica: P3.
- Dependências: proveniência e holdout prospectivo.
- Condição objetiva de rejeição: efeito desaparece sob controle de leakage/holdout.

## Matrizes de classificação

### 1. Prioridade científica

| ID | Hipótese | Prioridade | Justificativa |
|---|---|---|---|
| A01 | Liderança BTC | P0 | Baixo custo, mecanismo plausível, dados parciais disponíveis. |
| A02 | Persistência de volatilidade | P0 | Alto valor como previsão de risco; não reabre sinal direcional. |
| A04 | Co-jumps/contágio | P0 | Mecanismo de mercado claro e testável com OHLCV. |
| A05 | Dispersão como estado | P0 | Estado de mercado, não top-k; baixo custo. |
| B12 | Funding/basis | P0 | Forte mecanismo econômico, exige novos dados. |
| B13 | OI + funding | P0 | Crowd leverage é mecanismo cripto central. |
| B14 | Liquidações | P0 | Forced-flow é hipótese econômica limpa. |
| B15 | Spot versus perp | P0 | Price discovery é central, mas exige novos dados. |
| A03 | Vol/jumps assimétricos | P1 | Promissora, mas parcialmente limitada por OHLCV. |
| A07 | Compressão → magnitude | P1 | Testa risco/magnitude, não direção. |
| B16 | Order flow | P1 | Alto valor, custo alto. |
| B17 | Livro/profundidade | P1 | Mecanismo limpo, dados caros. |
| B18 | Multi-exchange arbitragem | P1 | Forte fundamento, escopo maior. |
| B19 | Funding cross-sectional | P1 | Promissora após funding básico. |
| A06 | Reversão cross-sectional | P2 | Próxima demais de hipóteses encerradas; só com preregistro rígido. |
| A08 | Iliquidez OHLCV | P2 | Proxy fraco; útil apenas como diagnóstico. |
| A09 | Volume proxy | P2 | Contaminado por wash trading e proxy fraco. |
| B20 | Stablecoin flows | P2 | Econômica, mas dados/proveniência difíceis. |
| B21 | On-chain exchange flows | P2 | Potencial médio, risco de labels. |
| B22 | Macro surprises | P2 | Evento claro, mas depende de dados externos. |
| B23 | Opções | P2 | Forte para BTC/ETH, complexidade alta. |
| B24 | Unlocks | P2 | Event-driven plausível, coverage limitada. |
| A10 | Liquidity grabs candle-only | P3 | Identificação fraca com candles. |
| A11 | Seasonality | P3 | Baixa prioridade e risco de mineração. |
| B25 | Listings/regulatório | P3 | Idiossincrático e dependente de evento. |
| B26 | Sentimento | P3 | Alto risco de leakage/mineração. |

### 2. Potencial de generalização

| Classe | Hipóteses | Justificativa |
|---|---|---|
| Alto | A02, A04, B12, B13, B14, B15, B16, B17, B18, B19 | Mecanismos ligados a risco, alavancagem, liquidez ou arbitragem. |
| Médio | A01, A03, A05, A07, B20, B21, B22, B23, B24 | Plausíveis, mas dependem de regime, dados ou universo. |
| Baixo | A06, A08, A09, A10, A11, B25, B26 | Maior risco de mineração, proxy fraco ou eventos idiossincráticos. |

### 3. Dificuldade experimental

| Dificuldade | Hipóteses | Motivo |
|---|---|---|
| Baixa | A02, A05, A09, A11 | Usam OHLCV e protocolos simples. |
| Média | A01, A03, A04, A06, A07, A08, A10, B12, B19, B22, B24, B25 | Exigem controles mais cuidadosos ou novos painéis moderados. |
| Alta | B13, B14, B15, B16, B17, B18, B20, B21, B23, B26 | Exigem dados novos, QA pesado ou risco alto de leakage. |

### 4. Cobertura por dados atuais

| Cobertura | Hipóteses | Observação |
|---|---|---|
| Sim | A01, A02, A04, A05, A07, A11 | Testáveis agora como associação OHLCV, sem holdout virgem. |
| Parcial | A03, A06, A08, A09, A10 | Testáveis como proxy fraco ou com alto risco de identificação. |
| Não | B12, B13, B14, B15, B16, B17, B18, B19, B20, B21, B22, B23, B24, B25, B26 | Exigem aquisição/curadoria de dados externos. |

### 5. Descarte imediato/deferimento

| Categoria | Itens | Decisão |
|---|---|---|
| Descarte imediato | Reembalar EMA/ATR/RSI/Bollinger, reabrir Trend/Pullback/MeanReversion/ensembles, repetir RST01-RST04 com novos horizontes/thresholds/top-k | Proibido. |
| Deferir | A10, A11, B25, B26 | Só após hipóteses P0/P1 ou dados/proveniência melhores. |
| Pode planejar sem executar | A01, A02, A04, A05 | Track A, baixo custo, exige governança/holdout primeiro. |
| Requer aquisição | B12, B13, B14, B15 | Track B prioritário se houver orçamento/dados. |

## Ordem recomendada

### Track A — Baixo custo com dados atuais

Ordem recomendada:

1. Governança e holdout prospectivo antes de qualquer novo teste.
2. A01 — liderança BTC e transmissão defasada.
3. A02 — persistência de volatilidade como risco.
4. A04 — co-jumps/contágio.
5. A05 — dispersão como estado de mercado.
6. A03/A07 apenas se os quatro primeiros produzirem conhecimento estrutural, não edge operacional.

Motivo: maximiza conhecimento por custo sem fingir que OHLCV mede microestrutura.

### Track B — Maior valor econômico com aquisição de dados

Ordem recomendada:

1. B12 — funding/basis.
2. B13 — open interest + funding.
3. B14 — liquidações.
4. B15 — spot versus perp.
5. B16/B17 — trades/livro.
6. B18/B19 — multi-exchange e carry cross-sectional.

Motivo: derivativos e microestrutura têm mecanismo econômico mais direto que candles.

### Track C — Condicionado a disponibilidade/licenciamento

Ordem recomendada:

1. B22 — macro surprises.
2. B20/B21 — stablecoins/on-chain.
3. B23 — opções.
4. B24/B25 — eventos de oferta/listings/regulação.
5. B26 — atenção/sentimento apenas com proveniência forte e holdout.

## Hipóteses testáveis agora

Testáveis com OHLCV atual, sem iniciar execução:

- A01 — liderança BTC.
- A02 — persistência de volatilidade.
- A04 — co-jumps/contágio.
- A05 — dispersão como estado.
- A03 — assimetria de volatilidade/jumps, com limitações.
- A07 — compressão seguida de expansão de magnitude.
- A06/A08/A09/A10/A11 apenas como baixa prioridade ou proxy fraco.

Todas exigem:

- Preregistro antes de qualquer cálculo.
- Separação development versus holdout.
- Controle de múltiplos testes.
- Gate que permita STOP sem ramificar.

## Hipóteses que exigem novos dados

Exigem novos dados antes de qualquer teste:

- B12 funding/basis.
- B13 open interest + funding.
- B14 liquidações.
- B15 spot versus perp.
- B16 trades agressor/passivo.
- B17 livro/profundidade.
- B18 multi-exchange.
- B19 funding cross-sectional.
- B20 stablecoin flows.
- B21 on-chain flows.
- B22 macro surprises.
- B23 opções.
- B24 unlocks.
- B25 listings/regulatory events.
- B26 sentimento/atenção.

Nenhuma dessas deve ser simulada com OHLCV como se os dados existissem.

## Descartes imediatos

Não devem entrar na Fase 4:

- Qualquer nova estratégia baseada em EMA/ATR/RSI/Bollinger.
- Qualquer reabertura de Trend/Score/Pullback/MeanReversion/ensembles.
- Qualquer “nova” hipótese que seja RST01-RST04 com outro horizonte, threshold ou top-k nos mesmos dados consumidos.
- Qualquer inferência de fluxo institucional baseada apenas em OHLCV.
- Qualquer ML/sentimento sem hipótese econômica, proveniência e holdout prospectivo.
- Qualquer DEX/MEV enquanto o escopo operacional continuar Binance spot/Freqtrade.

## Protocolo transversal da Fase 4

Regras obrigatórias:

- Uma hipótese por estudo.
- Preregistro imutável antes de cálculo.
- Ledger de hipóteses para impedir reciclagem retrospectiva.
- Separação explícita de dados development e holdout prospectivo.
- Nenhum uso de holdout para formular hipótese.
- Controle de múltiplos testes entre famílias.
- Unidade inferencial coerente: tempo, ativo, exchange ou evento, conforme mecanismo.
- Custos e capacidade incluídos sempre que houver interpretação econômica.
- Replicação temporal e cross-asset antes de qualquer conclusão forte.
- STOP é resultado válido.
- Associação não será tratada como causalidade.
- Literatura motiva hipóteses, mas não prova que funcionam no universo do laboratório.
- Nenhum achado estatístico relativo vira regra operacional sem positividade líquida, estabilidade, controle/placebo e holdout.

Critérios gerais de STOP:

- Efeito líquido não positivo.
- CI de média ou efeito cruza zero.
- Falha de consistência entre blocos/ativos.
- Dependência de poucos eventos/ativos.
- Efeito não supera placebo/controle.
- Resultado depende de variação paramétrica pós-hoc.
- Dados insuficientes ou proxy inadequado para o mecanismo.

## Cronograma

### Semana 0 — Governança

- Congelar estado PH3.
- Criar ledger de hipóteses.
- Definir política de holdout prospectivo.
- Definir quais dados atuais são apenas development-consumed.

Tempo de Codex: baixo. Tempo de calendário: depende de formação/reserva de holdout.

### Semanas 1-2 — QA e desenho dos estudos baratos

- Especificar preregistros de A01, A02, A04 e A05.
- Auditar cobertura e hashes sem executar hipóteses.
- Definir unidade inferencial e critérios de STOP.

Tempo de Codex: médio. Tempo de calendário: curto, sem promessa de execução.

### Semanas 3-4 — Estudos OHLCV de baixo custo, se autorizados

- Executar no máximo uma hipótese por vez.
- Finalizar cada estudo com gate próprio.
- Não ramificar após resultado fraco.

Tempo de Codex: médio. Tempo de calendário: depende de autorização.

### Semanas 4-8 — Aquisição/QA de derivativos e microestrutura

- Avaliar fontes de funding, basis, OI e liquidações.
- Definir QA, timestamps, cobertura, custos e licença.
- Não executar pesquisa antes de validação de dados.

Tempo de Codex: médio. Tempo de calendário: médio.

### Semanas 8-12 — Estudos com derivativos/microestrutura

- Prioridade B12-B15.
- Replicação temporal e cross-asset.
- Gate de utilidade econômica.

Tempo de Codex: médio-alto. Tempo de calendário: depende dos dados.

### Após 12 semanas — Replicação e gates

- Reavaliar apenas hipóteses que passarem gates.
- Reservar holdout futuro.
- Encerrar famílias que falharem.

Não há promessa de bot em nenhuma etapa.

## Critérios de entrada e saída da Fase 4

### Entrada

Uma hipótese entra em Fase 4 se:

- Tem mecanismo econômico explícito.
- É falsificável.
- Define dados necessários.
- Define unidade inferencial.
- Define comparador e placebo.
- Define condição objetiva de rejeição.
- Não reabre família encerrada.

### Saída

Uma hipótese sai como rejeitada se:

- Falha economicamente após custos.
- Não supera controle/placebo.
- Não replica por bloco/ativo.
- Exige proxy que não mede o mecanismo.
- Depende de ajuste retrospectivo.

Uma hipótese sai como candidata a futura pesquisa se:

- Produz evidência líquida positiva.
- Tem CI favorável.
- Replica temporal e cross-asset.
- Supera controle/placebo.
- Não depende de concentração.
- Ainda requer holdout prospectivo antes de arquitetura.

Mesmo uma hipótese candidata não autoriza estratégia.

## Bibliografia

Estas referências motivam mecanismos. Elas não provam que qualquer hipótese funcionará no universo, período ou infraestrutura deste laboratório.

- Liu & Tsyvinski, “Risks and Returns of Cryptocurrency”, RFS/NBER: https://www.nber.org/papers/w24877
- Liu, Tsyvinski & Wu, “Common Risk Factors in Cryptocurrency”, Journal of Finance/NBER: https://www.nber.org/papers/w25882
- Makarov & Schoar, “Trading and Arbitrage in Cryptocurrency Markets”: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3171204
- Cong et al., “Crypto Wash Trading”, Management Science/NBER: https://www.nber.org/papers/w30783
- Lyons & Viswanath-Natraj, “What Keeps Stablecoins Stable?”: https://www.nber.org/papers/w27136
- Dobrynskaya, “Cryptocurrency Momentum and Reversal”: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3913263
- Chi et al., risk factors/basis in crypto futures: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4657014
- Alexander, Heck & Kaeck, “Price Discovery in Bitcoin: The Role of Limit Orders”: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4150979
- “Revisiting seasonality in cryptocurrencies”: https://doi.org/10.1016/j.frl.2024.105429
- “High-frequency macro news and crypto co-jumps”: https://doi.org/10.1007/s10479-021-04353-0
- Zhang & Zhao, good/bad volatility and signed jumps: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3910202
- “On-chain flows and returns/volatility”: https://arxiv.org/abs/2411.06327
- “Option-implied crypto risk premia”: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6410838

Status da literatura:

- NBER/Journal of Finance/RFS/Management Science indicam pesquisa acadêmica forte, mas ainda não substituem validação local.
- SSRN e arXiv podem incluir working papers/preprints; tratar como motivação, não consenso.
- Resultados em cripto frequentemente são dependentes de período, exchange, custos e qualidade de dados.

## Decisão executiva final

O que merece existir como hipótese:

- Track A P0: liderança BTC, persistência de volatilidade como risco, co-jumps/contágio e dispersão como estado de mercado.
- Track B P0: funding/basis, OI+funding, liquidações e spot-versus-perp price discovery, desde que novos dados confiáveis sejam adquiridos e auditados.

O que não merece existir agora:

- Qualquer nova estratégia operacional.
- Qualquer reabertura de famílias encerradas.
- Qualquer variação paramétrica de RST01-RST04 nos dados consumidos.
- Qualquer inferência microestrutural forte a partir de OHLCV.

Decisão: Fase 4 pode existir apenas como programa de descoberta de hipóteses econômicas. Ela não autoriza implementação, backtest, robô funcional, dry-run, capital real ou criação de plugin.

## Auditoria deste documento

- Arquivo criado/modificado: `PHASE4_RESEARCH_ROADMAP.md`.
- Backtests executados: nenhum.
- Análises estatísticas executadas: nenhuma.
- Downloads executados: nenhum.
- Código criado/modificado: nenhum.
- Estratégias, plugins, indicadores, configs, dados, SQLite, módulos e relatórios existentes alterados: nenhum.
