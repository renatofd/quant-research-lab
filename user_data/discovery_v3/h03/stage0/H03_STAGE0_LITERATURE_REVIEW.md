# Discovery V3 — H03 Stage 0

## Extreme Funding: revisão de mecanismo, novidade e decisão

**Data:** 2026-07-24  
**Decisão:** `REJECTED_AT_STAGE0_NO_NOVEL_INCREMENTAL_MECHANISM`  

## Mecanismo proposto

A narrativa candidata é contrária: funding muito positivo representaria longs
alavancados e vulneráveis a desalavancagem; funding muito negativo representaria
shorts vulneráveis a squeeze. Se funding fosse uma medida limpa de posicionamento,
seu extremo poderia anteceder retorno na direção oposta.

O problema causal é que funding não mede posição ou fragilidade diretamente. Ele é
uma regra de transferência desenhada a partir do prêmio do perpétuo, podendo refletir
demanda informada, momentum, custo de capital e basis de equilíbrio. Funding extremo
pode preceder continuação, reversão ou nenhum efeito, sem contradição com o desenho
do contrato.

## Literatura

- He, Manela, Ross e von Wachter demonstram que funding é o mecanismo que incentiva
  alinhamento spot-perp, mas perpétuos não têm convergência obrigatória. O resultado
  sustenta pricing/carry, não a alegação de retorno direcional contrário.
  https://arxiv.org/abs/2212.06888
- Zhang modela funding como feedback endógeno entre arbitradores restritos e
  especuladores de momentum. A teoria prevê mean reversion da **base**, não
  necessariamente reversão do ativo.
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6185958
- Schmeling, Schrimpf e Todorov ligam carry a demanda alavancada e limites à
  arbitragem, mas documentam riscos relevantes e não estabelecem funding extremo
  como sinal direcional universal.
  https://www.bis.org/publ/work1087.pdf
- Evidência pública recente de seis ativos e três venues encontra sinal contrário
  apenas em parte do painel, com a cauda negativa essencialmente sem previsão. É
  evidência observacional secundária, não confirmação, mas reforça heterogeneidade.
  https://markettrace.ai/blog/funding-rate-extremes

## Evidência experimental já existente

O Discovery V2-H02 pré-registrou, antes de outcomes:

- funding positivo no quartil superior por ativo;
- entrada short perp após o evento;
- saída no funding seguinte;
- custo fixo de 0,20%;
- desenvolvimento 2024-07 a 2025-12;
- holdout 2026-01 a 2026-06;
- bootstrap, Holm, replicação entre ativos e períodos.

O subconjunto “funding-only” foi o baseline obrigatório. A partir dos resultados
registrados:

- desenvolvimento: média aproximada do baseline `−0,1612%`;
- holdout: média aproximada do baseline `+0,0053%`;
- o componente adicional de crowding teve valor incremental negativo;
- a hipótese composta falhou desenvolvimento e holdout, replicação cross-asset e
  temporal.

Os valores do baseline são obtidos pela identidade registrada:
`média crowding − incremental crowding-vs-baseline`.

Portanto, a parte economicamente operacional da narrativa de funding positivo
extremo já recebeu teste fora da amostra e não sobreviveu.

## Por que não testar apenas funding negativo

Selecionar agora somente a cauda negativa seria uma mudança de direção após conhecer
a falha da cauda positiva. Não existe evidência acadêmica robusta e cross-asset que
eleve essa meia-hipótese acima do orçamento científico, e funding negativo exige
distinguir pressão informada, hedge, basis e risco de squeeze. Sem uma variável nova
de posição/fragilidade, seria apenas nova seleção no mesmo dado.

## Decisão formal

`REJECTED_AT_STAGE0_NO_NOVEL_INCREMENTAL_MECHANISM`.

H03 não avança a inventário, aquisição ou implementação. Não se reabre alterando
quantil, horizonte, direção, custo ou universo. Uma hipótese futura exigiria dados
materialmente novos de posição, margem ou liquidação e um mecanismo incremental
pré-registrado; isso pertenceria a outra geração de pesquisa.
