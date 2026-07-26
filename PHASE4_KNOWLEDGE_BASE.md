# PHASE4 KNOWLEDGE BASE

## Estado

Fase 4 **ENCERRADA**, sem hipótese ativa e sem bot operacional justificado.

## Como ler a evidência

O laboratório separa três níveis que não podem ser confundidos:

1. **Sinal descritivo:** associação observada no conjunto disponível.
2. **Valor preditivo incremental:** melhora OOS interna sobre baseline e controles.
3. **Utilidade econômica líquida:** efeito após custos, replicável e não concentrado.

Somente o terceiro nível, acompanhado de robustez e holdout, poderia justificar um experimento operacional. Nenhuma hipótese chegou a esse nível.

## Fatos positivos duráveis

- A01 apresentou beta descritivo e consistência direcional parcial, mas não retorno líquido nem especificidade suficiente.
- A02 mostrou que volatilidade passada contém informação de risco, porém o benefício foi concentrado além do limite aceito.
- A05 mostrou informação incremental de dispersão sobre risco, novamente concentrada.
- A09 demonstrou persistência de atividade: MSE melhorou 14,0669% e MAE 5,4506%. Esse conhecimento é válido como previsão de atividade, mas a concentração extrema impede generalização.
- A09 mostrou ganho de risco pequeno, 0,6836% em MSE e 0,6634% em MAE; é informação mensurável, não material.
- Controles negativos, correção Holm e análise de concentração alteraram decisões que seriam otimistas se baseadas apenas em beta ou média agregada.

## Fatos negativos duráveis

- Nenhuma hipótese A01–A11 executável demonstrou simultaneamente vantagem líquida, robustez, replicação, controle de multiplicidade e ausência de concentração.
- BTC lead-lag não produziu especificidade econômica suficiente frente a pseudo-líderes e shifts.
- Proxies OHLCV de iliquidez não identificaram valor incremental robusto e não medem liquidez causal.
- Volume OHLCV não autorizou inferência de fluxo institucional, lado agressor ou liquidez.
- Calendário, dias e sessões não cobriram custo de 0,30% e não melhoraram MSE/MAE em pelo menos 5%.
- Ajustar horizontes, thresholds, indicadores ou subgrupos nos mesmos dados consumidos não constitui hipótese nova.
- As famílias Trend/score, Pullback, N-of-M, ensembles e MeanReversion permanecem encerradas.

## Conhecimento não estabelecido

- A04 não estabeleceu nem refutou propagação de co-jumps; ficou inconclusiva por insuficiência de identificação/amostra e foi encerrada pelo programa.
- Funding, basis, open interest, liquidações, order flow, livro, multi-exchange, on-chain, macro, opções e eventos não foram testados porque os dados não existem no laboratório.
- Não há holdout prospectivo virgem; nenhum efeito positivo pode ser chamado de confirmação independente.

## Fronteira de validade

As conclusões valem para Binance spot, OHLCV 5m, os dez pares, blocos históricos, custos e estimandos registrados. Não são prova universal de que mercados cripto não contêm previsibilidade. São evidência suficiente para encerrar a busca OHLCV atual e negar promoção operacional.
