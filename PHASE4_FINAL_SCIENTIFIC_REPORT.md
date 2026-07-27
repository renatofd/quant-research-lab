# PHASE4 FINAL SCIENTIFIC REPORT

## Decisão executiva

**Fase 4: ENCERRADA.** Não existe hipótese ativa.

**Não existe evidência científica suficiente para justificar um bot operacional.**

## Pergunta central

O programa investigou se alguma ineficiência econômica pré-especificada, observável com o OHLCV disponível, produzia informação incremental, robusta entre ativos e períodos e economicamente útil após custos. A resposta, no universo e período testados, foi negativa.

## Desenho do programa

- Dados: Binance spot, OHLCV 5m, dez pares contra USDT.
- Validação: blocos temporais, unidades por ativo/bloco, splits cronológicos internos, bootstrap por unidades temporais, correção Holm e controles negativos.
- Disciplina: uma hipótese econômica por campanha, preregistro, critérios de sucesso e rejeição fixos, sem retuning pós-resultado.
- Interpretação: associação descritiva, incremento preditivo e utilidade econômica líquida foram tratados como níveis distintos de evidência.
- Limite decisório: todos os dados são `development-consumed`; o OOS foi interno e não constitui holdout prospectivo.

## Resultado por família

As famílias operacionais Trend/score, Pullback, N-of-M, ensembles e MeanReversion já haviam sido encerradas por falta de generalização, robustez ou vantagem líquida. A Fase 4 não as reabriu; testou mecanismos econômicos brutos e previsões de risco/atividade sem transformar resultados em estratégia.

| ID | Objeto | Resultado atual | Síntese |
|---|---|---|---|
| A01 | BTC lead-lag | Rejeitada | Beta descritivo não se converteu em retorno líquido nem especificidade robusta. |
| A02 | Persistência de volatilidade | Rejeitada | Informação de risco existiu, mas falhou o gate de concentração. |
| A03 | Assimetria/jumps assinados | Rejeitada | Incremento preditivo, multiplicidade e concentração falharam. |
| A04 | Co-jumps/contágio | Inconclusiva e encerrada | Dados/identificação não sustentaram unidades suficientes; não foi convertida em rejeição falsa. |
| A05 | Dispersão cross-sectional | Rejeitada | Resultado concentrado além do limite pré-registrado. |
| A06 | Reversão cross-sectional distinta | Encerrada/deferida | Não era independentemente identificável sem reciclar famílias rejeitadas. |
| A07 | Compressão seguida de expansão | Rejeitada | Gates de beta, Holm e robustez falharam. |
| A08 | Iliquidez/impacto via OHLCV | Rejeitada | Proxy não demonstrou ganho incremental robusto; OHLCV não identifica liquidez causal. |
| A09 | Persistência de volume | Rejeitada | Ganho de atividade foi excessivamente concentrado; ganho de risco ficou muito abaixo do mínimo. |
| A10 | Liquidity grabs por candles | Encerrada/deferida | Identificação inadequada com OHLCV e sobreposição com breakout já rejeitado. |
| A11 | Calendário/sessões/weekend | Rejeitada | Nenhum dos 11 contrastes produziu retorno líquido ou ganho preditivo suficiente e replicável. |

B12–B26 não foram testadas. Dependem de funding, basis, open interest, liquidações, trades, livro, multi-exchange, on-chain, macro, opções ou eventos/sentimento que não existem no laboratório atual. São bloqueios de dados, não resultados negativos, e não autorizam aquisição automática.

## Evidência central A09 e A11

A09 preservou uma descoberta descritiva: P1 de atividade melhorou MSE em 14,0669% e MAE em 5,4506%. Porém, 74,2851% da melhoria positiva concentrou-se no bloco 1, 69,1177% em 2025-10-10 e 32,1426% em AVAX. Para risco, os ganhos foram apenas 0,6836% em MSE e 0,6634% em MAE, abaixo do gate de 5%. A integridade foi válida, portanto a conclusão correta é rejeição, não inconclusão.

A11 teve integridade válida, hash de protocolo `5FF6E981A6AF7D88C09C37398DF2C55566F97C8D3305745E74F4EF7C135D157A`, 50 unidades, 10 pares, 5 blocos, 11 contrastes e 1.000 réplicas por contraste. Todos os retornos líquidos médios e medianos a custo de 0,30% foram negativos; nenhum ganho de MSE/MAE atingiu 5%; nenhum contraste replicou em 7/10 pares e 4/5 blocos. Uma única semana UTC completa por unidade tornou alguns ICs bootstrap degenerados, mas isso não resgata a hipótese porque os gates econômicos determinísticos falharam em todos os contrastes.

## Validade e limitações

1. As conclusões são válidas para o universo, cobertura temporal, timeframe, custos e definições pré-registradas; não provam ausência universal de ineficiências em cripto.
2. O dataset inteiro foi consumido em desenvolvimento. Não há confirmação prospectiva independente.
3. OHLCV não mede funding, alavancagem, liquidações, lado agressor, profundidade, fragmentação, fluxos on-chain, opções ou eventos point-in-time.
4. Efeitos incrementais positivos observados em A02, A05 e A09 foram preservados como conhecimento, mas concentração ou falta de utilidade econômica impediu promoção.
5. A04 permaneceu inconclusiva por insuficiência material; não foi indevidamente classificada como rejeitada.

## Critérios de parada satisfeitos

- Todas as hipóteses OHLCV executáveis foram rejeitadas ou encerradas.
- As hipóteses restantes exigem dados indisponíveis.
- Não há hipótese com vantagem líquida, robustez, replicação e controles suficientes para experimento operacional.
- Mais variações OHLCV equivaleriam a multiplicidade, retuning ou reciclagem de ideias.
- A expectativa racional de sucesso de novas variações no espaço consumido é inferior a 5%.

## Conclusão binária

**Não existe evidência científica suficiente para justificar um bot operacional.**

Nenhum componente, arquitetura ou bot é promovido. A pesquisa da Fase 4 está encerrada.
