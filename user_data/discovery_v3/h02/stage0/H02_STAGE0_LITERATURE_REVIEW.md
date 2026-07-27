# Discovery V3 — H02 Stage 0

## Revisão de literatura e mecanismo econômico

**Hipótese:** H02 — Divergência Spot × Perp  
**Data da decisão:** 2026-07-24  
**Estado:** `STAGE0_PASS`  
**Próxima etapa autorizada:** Stage 1 — inventário de dados  

## Delimitação causal

H02 testa exclusivamente se uma divergência transitória entre o spot e o perpétuo do
mesmo ativo, na mesma bolsa e na mesma moeda de cotação, contém convergência
economicamente capturável por uma posição delta-neutral depois de custos, funding e
risco de execução.

H02 não testa:

- direção futura do ativo;
- qual mercado lidera a descoberta de preço;
- divergência entre bolsas;
- nível extremo de funding isoladamente;
- futuros com vencimento;
- qualquer indicador técnico.

Esses limites evitam sobreposição com H03 (funding extremo) e H04 (liderança
cross-exchange).

## Mecanismo econômico

Spot e perpétuo são economicamente ligados, mas não equivalentes. O funding cria
incentivo para aproximar o perpétuo do índice/spot, enquanto a arbitragem exige
capital em duas pernas, margem, disponibilidade para short, liquidez simultânea e
capacidade de sobreviver a uma ampliação temporária da base. Demanda alavancada,
segmentação, ausência de cross-margining e limites de capital podem afastar os preços
temporariamente.

Se a divergência exceder o componente de equilíbrio e as fricções, arbitradores
compram a perna barata e vendem a cara. O fluxo deve comprimir a divergência. A
vantagem, se existir, é a convergência relativa das duas pernas, não uma previsão da
direção do mercado.

Uma base positiva ou negativa, por si só, não é evidência de ineficiência. Ela pode
remunerar financiamento, conveniência, demanda por alavancagem, margem, risco de
liquidação e funding esperado. Como o perpétuo não vence, a convergência não é
garantida em uma data fixa.

## Evidência na literatura

1. He, Manela, Ross e von Wachter, *Fundamentals of Perpetual Futures*, derivam
   preços e bandas de não arbitragem para perpétuos. Mostram que não há convergência
   obrigatória como em futuros com vencimento, que custos ampliam a banda admissível
   e que desvios diminuíram com o amadurecimento do mercado. O trabalho oferece
   sustentação direta ao mecanismo, mas também alerta que uma diferença spot-perp
   observada pode estar dentro de um equilíbrio com fricções.
   Fonte: https://arxiv.org/abs/2212.06888

2. Schmeling, Schrimpf e Todorov, *Crypto Carry*, documentam que demanda
   alavancada e limites à arbitragem explicam parte relevante da base. Mostram risco
   de margem e liquidação no cash-and-carry, além de compressão da base quando o
   acesso a capital institucional melhora. A evidência reforça que a divergência tem
   fundamento econômico, mas não é um “lucro sem risco”.
   Fonte: https://www.bis.org/publ/work1087.pdf

3. Cosenza e Stalder, *Where is the Price of Bitcoin Determined?*, encontram
   descoberta de preço concentrada nos mercados spot e perpétuo de maior liquidez e
   menores custos. Isso implica ajuste rápido e risco de o efeito disponível em OHLCV
   agregado ser pequeno demais para execução.
   Fonte: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4983566

4. A literatura de price discovery encontra liderança dependente do mercado, do
   período e da infraestrutura. Essa heterogeneidade não valida H02, pois liderança
   informacional e convergência delta-neutral são perguntas distintas.

## Hipótese falsificável

**H02:** divergências spot-perp transitórias, medidas sem informação futura, são
seguidas por compressão relativa estável entre ativos e períodos, com magnitude bruta
suficiente para superar custos realistas das duas pernas, funding e risco de execução.

**H02 nula:** depois de controlar retorno contemporâneo, funding, custos e
microestrutura observável, a divergência não prevê compressão incremental
replicável ou a magnitude líquida é economicamente insuficiente.

## Falsificadores antecipados

H02 deve ser rejeitada antes de holdout se qualquer condição ocorrer:

- não houver relação monotônica entre divergência e compressão;
- o efeito for absorvido pelo funding ou pelo movimento contemporâneo;
- o sinal representar apenas preço assíncrono entre candles;
- a convergência existir em uma única direção, ativo ou subperíodo;
- o efeito bruto não exceder um piso conservador de custos das duas pernas;
- placebos temporais ou desalinhamentos artificiais reproduzirem o resultado;
- a vantagem depender de selecionar horizonte, threshold ou ativo depois dos dados.

## Dados conceitualmente necessários

- spot e perpétuo do mesmo ativo, bolsa e moeda de cotação;
- timestamps sincronizados e preço executável ou, no mínimo, OHLCV de alta
  frequência com limitações explicitadas;
- mark/index/premium para distinguir dislocação do último preço e erro de marcação;
- funding realizado e calendário de pagamentos;
- volume e, se disponível, bid-ask/depth para modelar executabilidade;
- taxas conservadoras para ambas as pernas;
- múltiplos ativos e blocos temporais;
- período de holdout selado antes de qualquer outcome de H02.

OHLCV pode refutar H02 se não houver efeito bruto; não pode, sozinho, confirmar
viabilidade operacional fina quando o efeito estiver próximo do spread e do
slippage. Uma eventual promoção exigirá dados de trades/book ou confirmação
prospectiva.

## Controles mínimos exigidos em etapas futuras

- circular shift da divergência;
- reverse time;
- defasagem artificial entre spot e perp;
- pseudo-divergência mark-index;
- retorno contemporâneo de cada perna;
- proximidade do pagamento de funding;
- replicação por ativo e por bloco temporal;
- bootstrap por dias;
- correção de Holm para a família confirmatória.

Nenhum lag, horizonte ou threshold está autorizado nesta etapa. Eles somente poderão
ser fixados em pré-registro antes de outcomes confirmatórios.

## Avaliação de orçamento científico

- **Custo esperado:** baixo a moderado, porque preços spot/perp, mark/index,
  premium e funding já existem no laboratório.
- **Informação esperada:** alta; o experimento pode distinguir rapidamente uma
  base de equilíbrio de uma dislocação convergente.
- **Risco de falso positivo:** alto se houver assincronia, seleção de horizonte ou
  custos incompletos; controlável com alinhamento, placebos e pré-registro.
- **Probabilidade qualitativa de alterar a conclusão atual:** moderada-baixa.
  Mercados líquidos ajustam rapidamente e a margem disponível pode ser menor que
  os custos, mas o mecanismo é mais direto que previsão direcional por OHLCV.
- **Valor esperado da informação por custo:** suficiente para Stage 1.

## Decisão formal

`STAGE0_PASS`.

O mecanismo é economicamente coerente, falsificável e sustentado por teoria e
evidência de limites à arbitragem. A literatura não prova uma vantagem atual,
replicável ou executável; portanto, não há confirmação nem autorização para
estratégia. Avança-se somente ao inventário de dados, mantendo H02 como única
hipótese ativa.
