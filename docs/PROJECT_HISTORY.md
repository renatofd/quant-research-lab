# História do Projeto

## Origem

O projeto começou como uma customização do Freqtrade orientada a estratégias,
indicadores, Hyperopt e operação. Essa formulação inicial foi substituída quando
o laboratório passou a tratar generalização, robustez e falsificação como
objetivos principais.

## Fases 1 e 2 — infraestrutura e exploração

Foram construídos gerenciador de experimentos, banco, runner, ranking, geração
de parâmetros, plugins, relatórios, robustez, neighborhood e walk-forward.
Trend, Pullback, Mean Reversion, N-of-M e ensembles foram examinados. Picos
locais frequentemente falharam fora da amostra.

## Fase 3 — intervenções causais

O foco mudou de “qual parâmetro maximiza PF?” para “este componente acrescenta
valor?”. Filtros e componentes foram neutralizados um por vez, sem retuning. As
intervenções não produziram sobrevivência walk-forward confiável, e as famílias
operacionais foram encerradas.

## Fase 4 — hipóteses econômicas

Indicadores deixaram de ser o ponto de partida. O programa testou liderança,
persistência de risco, assimetria, co-jumps, dispersão, compressão, proxies de
iliquidez, volume e sazonalidade. Relações estatísticas existiram, mas nenhuma
produziu vantagem líquida robusta.

## Discovery V2

O projeto passou a investigar dados de derivativos, com aquisição e QA
formalizados. Uma limitação oficial uniforme do dataset motivou a distinção
metodológica entre `PASS`, `PASS WITH DOCUMENTED DATASET LIMITATION` e `FAIL`,
sem relaxar gates de forma casuística.

## Discovery V3

Uma nova geração partiu de mecanismos e disponibilidade de dados:

- cascatas de liquidação;
- divergência spot-perp;
- funding extremo;
- liderança cross-exchange;
- liquidez, on-chain, ETF, opções, order flow e força relativa.

H01, H02 e H04 chegaram à análise, mas seus efeitos brutos ficaram abaixo dos
custos ou falharam replicação. H03, H09 e H10 foram encerradas antes de gasto
inútil. H05–H08 foram bloqueadas pela ausência de dados causalmente adequados.

Em 2026-07-24, o Discovery V3 foi encerrado com zero hipóteses promovidas.

## Release 1.0.0

O projeto foi preparado para publicação como demonstração de método científico,
engenharia de pesquisa e disciplina de decisão. O resultado negativo permanece
o principal resultado.
