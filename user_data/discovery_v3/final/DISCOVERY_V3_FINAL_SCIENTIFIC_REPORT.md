# Discovery V3 — Relatório científico final

**Encerramento:** 2026-07-24  
**Status:** `CONCLUDED_NO_ROBUST_EDGE`  
**Bot autorizado:** não

## Pergunta final

Foi descoberta vantagem econômica real, estatisticamente defensável, replicável e
operacionalmente viável que justifique um bot?

**Não.**

## Resultado por hipótese

| ID | Hipótese | Decisão | Evidência decisiva |
|---|---|---|---|
| H01 | Liquidation Cascades | REJECTED | Continuação falhou magnitude, 5/6 ativos e 3/4 blocos; holdout não aberto |
| H02 | Spot × Perp Divergence | REJECTED | Convergência 1,23 bp bruto versus 30 bp de custo; 0/10 ativos e 0/4 blocos líquidos |
| H03 | Extreme Funding | REJECTED Stage 0 | Baseline V2 pré-registrado já foi negativo em desenvolvimento e ~zero em holdout; sem mecanismo incremental |
| H04 | Cross-Exchange Leadership | REJECTED | Liderança estatística, mas 0,37 bp bruto versus 15 bp; 0/10 ativos e 0/4 blocos líquidos |
| H05 | Liquidity Regimes | BLOCKED | Falta livro point-in-time sequenciado; proxy OHLCV A08 é proibido |
| H06 | On-chain Flows | BLOCKED | Faltam labels de exchange versionados por data de conhecimento |
| H07 | ETF Flows | BLOCKED | Falta painel oficial/auditado de flows com vintages e release timestamps |
| H08 | Options Market | BLOCKED | Falta superfície histórica point-in-time com bid/ask e OI |
| H09 | Order Flow / CVD | REJECTED por orçamento | Trade archive sem book não resolve execução; custo excede informação esperada |
| H10 | Cross-Asset Relative Strength | REJECTED Stage 0 | Reabriria a conclusão OHLCV/momentum definitiva sem dado econômico novo |

## O que foi aprendido

### Significância não é vantagem

H02 e H04 apresentaram relações estatísticas fortes. Ambas falharam por uma ordem de
grandeza econômica: o mercado transmitiu informação, mas o resíduo capturável ficou
muito abaixo dos custos. Isso é evidência contra bot, não resultado “quase bom”.

### Dados de preço conseguem refutar, mas não confirmar microestrutura

Candles sincronizados foram suficientes para mostrar que convergência e liderança em
5 minutos não pagam execução taker conservadora. Eles não medem spread, depth, fila,
latência ou fill. Repetir análises com mais thresholds não corrige esse limite.

### Proxy não substitui mecanismo

Volume/range não substituem liquidez de livro; AUM não substitui ETF flow; chain
bruta não substitui labels point-in-time; trades de opções não substituem superfície
executável; taker volume agregado não substitui order flow sequenciado.

### Holdouts foram preservados quando o desenvolvimento já refutou

H01, H02 e H04 foram encerradas antes de abrir seus novos holdouts. Isso conserva
evidência futura e evita gastar independência estatística em efeitos economicamente
mortos.

## Decisão de parada

Todas as hipóteses executáveis no contrato atual foram encerradas. As restantes
dependem de dados causalmente indispensáveis que não existem no laboratório.
Continuar com os mesmos dados exigiria proxies já rejeitados, seleção pós-outcome ou
infraestrutura cara sem valor esperado suficiente.

## Decisão formal

**Não existe evidência científica suficiente para justificar um bot operacional.**

O desenvolvimento de estratégia, regras de entrada, sizing, execução ou bot permanece
proibido. O Discovery V3 está encerrado.
