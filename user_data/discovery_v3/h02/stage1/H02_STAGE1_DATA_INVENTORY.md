# Discovery V3 — H02 Stage 1

## Inventário de dados

**Hipótese:** H02 — Divergência Spot × Perp  
**Data da decisão:** 2026-07-24  
**Estado:** `STAGE1_PASS_WITH_HOLDOUT_CONSTRAINT`  
**Próxima etapa autorizada:** Stage 2 — aquisição incremental, QA e selagem  

## Contrato de dados exigido

O teste primário requer spot e perpétuo USD-M do mesmo ativo, na Binance, ambos
cotados em USDT e sincronizados. Mark, index, premium e funding são controles. Dados
de livro/trades são desejáveis para validação operacional, mas não são necessários
para uma refutação inicial do efeito bruto.

## Dados existentes reutilizáveis

O acervo imutável do Discovery V2 contém dados oficiais Binance para dez ativos:

`ADAUSDT, AVAXUSDT, BNBUSDT, BTCUSDT, DOGEUSDT, ETHUSDT, LINKUSDT, LTCUSDT,
SOLUSDT, XRPUSDT`.

| Família | Frequência | Período | Objetos | Cobertura |
|---|---:|---|---:|---:|
| Spot klines | 5 min | 2024-07-01 a 2026-06-30 | 240 | 100% |
| USD-M perp klines | 5 min | mesmo | 240 | 100% |
| Mark-price klines | 5 min | mesmo | 240 | 99,863% |
| Index-price klines | 5 min | mesmo | 240 | 99,863% |
| Premium-index klines | 5 min | mesmo | 240 | 99,863% |
| Funding rate | evento nativo | mesmo | 240 | sem gaps materiais |

Os 1.440 objetos têm checksum oficial válido e QA estrutural aprovado. A ausência
uniforme de mark/index/premium em 29/06/2026 é limitação oficial documentada, não
falha aleatória. O spot e o perpétuo, que formam o par primário de H02, têm cobertura
integral.

Proveniência:

- fonte: `https://data.binance.vision/`;
- inventário: `DISCOVERY_V2_H01_D1_INVENTORY.csv`;
- matriz QA: `DISCOVERY_V2_H01_D1_QA_MATRIX.csv`;
- acervo raw: `user_data/discovery_v2/h01/d1/raw`;
- 1.440 arquivos, 321.304.758 bytes;
- hash do inventário:
  `3725748f376e3086421bdeee48e96535772d7b37c367381764a8ade606f5f77c`;
- hash da matriz QA:
  `52644a7597032ce91376a9530dee0db19e44d21d679fe8478d8980eb22e2864e`.

O acervo será somente referenciado e lido. Nenhum arquivo V2 será copiado,
normalizado novamente ou alterado.

## Restrição de independência

O período 2024-07-01 a 2026-06-30 já teve outcomes econômicos abertos em estudos do
Discovery V2. Embora H02 seja um mecanismo diferente e tenha sido fixada antes de
qualquer análise específica de convergência, esse período não pode receber o rótulo
de holdout virgem de H02.

Decisão permanente:

- todo o acervo V2 é **desenvolvimento/exploração** para H02;
- nenhuma partição histórica interna desse acervo será chamada de holdout;
- uma eventual confirmação requer período novo, selado antes de outcomes de H02;
- resultado positivo somente no acervo V2 não autoriza promoção.

## Aquisição incremental necessária

Stage 2 deve adquirir, sem abrir preços economicamente:

- arquivos diários oficiais Binance de 2026-07-01 até o último dia completo
  disponível no momento da selagem;
- as mesmas seis famílias, dez ativos e frequência de 5 minutos;
- checksums oficiais, URLs, tamanho, timestamp de aquisição e hashes locais.

Esse período será o primeiro holdout H02. Como é curto, poderá refutar rapidamente,
mas talvez seja insuficiente para confirmar. Se necessário, a selagem deve continuar
prospectivamente sem alterar a hipótese.

## Fontes alternativas auditadas conceitualmente

- **Bybit/OKX:** úteis para replicação entre bolsas, porém não necessários antes de
  demonstrar efeito bruto na Binance; acrescentariam normalização e custo.
- **Coinbase:** não oferece o mesmo par perpétuo USDT no mesmo desenho contratual.
- **Deribit:** foco e contratos diferentes; melhor reservado a opções/H08.
- **Dados pagos de livro:** não autorizados nem necessários para Stage 3.

## Riscos do contrato atual

- candle close não é preço simultaneamente executável em duas pernas;
- 5 minutos podem ocultar convergência mais rápida;
- OHLCV não mede spread, depth nem latência;
- last price pode divergir de mark/index por microestrutura;
- fees e slippage precisam de envelope conservador.

Essas limitações tornam o dataset adequado para **refutação** e triagem, não para
confirmação operacional definitiva.

## Gates de Stage 2

1. checksum válido para 100% dos objetos adquiridos;
2. schemas e unidades temporais identificados;
3. spot e perp sincronizados em pelo menos 99,9% da grade por ativo;
4. controles mark/index/premium tratados pela política permanente de limitações
   documentadas, sem imputação;
5. funding ordenado e sem gaps materiais;
6. holdout H02 selado antes de cálculo de basis, retorno, convergência ou PnL;
7. hashes do acervo V2 referenciado e do novo acervo registrados;
8. nenhuma leitura de outcomes durante aquisição/QA.

## Decisão formal

`STAGE1_PASS_WITH_HOLDOUT_CONSTRAINT`.

O laboratório já possui o painel necessário para uma exploração de baixo custo.
Como o histórico foi aberto em projeto anterior, Stage 2 deve criar uma partição
temporal nova e selada. Não há justificativa para adquirir outra bolsa antes de
H02 sobreviver à triagem Binance.
