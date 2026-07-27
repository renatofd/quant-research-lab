# DISCOVERY V2 — V2-H01 D0 SCIENTIFIC DECISION

## Decisão vinculante

`D0_SCIENTIFIC_DECISION = CONDITIONAL_PASS_FOR_D1_ACQUISITION_ONLY`

Esta decisão foi emitida pelo Diretor Científico. Ela não converte o resultado mecânico em `PASS`, não altera os artefatos D0 e não autoriza D1.

## Estado

- Resultado mecânico D0: **D0_MECHANICAL_INCONCLUSIVE**
- Decisão científica D0: **CONDITIONAL_PASS_FOR_D1_ACQUISITION_ONLY**
- Programa: **PAUSED_PENDING_D1_AUTHORIZATION**
- V2-H01: **SELECTED_PENDING_DATA**
- Hipótese ativa: **não**
- Hipótese testada: **não**
- D1 autorizado: **não**
- Bot autorizado: **não**
- Projeto anterior: **ARCHIVED_FINAL**
- Próxima ação: **HUMAN_AUTHORIZATION_FOR_H01_D1_DATASET_CONTENT_AND_STRUCTURAL_QA**

## Evidência D0 vinculante

- 1.440/1.440 objetos presentes.
- 1.440/1.440 checksums presentes.
- 10/10 ativos completos nas seis famílias por 24 meses.
- Zero ausências, ambiguidades ou falhas de consulta.
- 321.304.758 bytes de conteúdo declarados e não baixados.
- 1.500 requests de metadados/checksum, todos HTTP 200.
- Zero bytes de conteúdo ZIP/CSV de mercado baixados.
- Contract specifications: `CURRENT_ONLY`.
- Fee schedules: `CURRENT_ONLY`.
- Borrow/margin histórico: `NOT_FOUND`.
- Nenhum outcome inspecionado; holdout não consumido.

## Distinção obrigatória

O resultado mecânico permanece **INCONCLUSIVE** porque o item 7 do gate não foi documentalmente resolvido por uma rota histórica point-in-time. A interpretação científica vinculante permite somente solicitar D1 sob um contrato de desenho que resolva o tratamento de custos antes de qualquer outcome.

Essa interpretação:

- não confirma H01;
- não ativa ou testa H01;
- não autoriza D1;
- não autoriza protocolo experimental;
- não autoriza bot;
- não modifica o relatório ou manifest D0.

## Resolução pré-outcome do gap de custos

O futuro desenho de H01 fica restrito, antes de qualquer inspeção, à forma economicamente mais limpa:

1. cash-and-carry unilateral totalmente financiado;
2. long spot + short USD-M perpetual;
3. somente o lado que recebe carry positivo;
4. reverse carry, short spot, borrow e funding negativo fora do escopo primário;
5. nenhum custo de borrow necessário no escopo primário;
6. retornos avaliados por unidade de notional, sem exigir tick/lot histórico para descoberta econômica;
7. restrições operacionais correntes reservadas a gate posterior, apenas se houver evidência;
8. custos de trading/slippage deduzidos por um único envelope fixo conservador, definido e congelado antes de outcomes;
9. envelope proibido de ajuste ao resultado, otimização ou grid;
10. ausência de fee history real mantida como limitação e tratada por upper bound conservador, nunca por imputação favorável.

A restrição reduz graus de liberdade e foi definida sem outcomes, pois D0 inspecionou somente manifests e checksums.

## Razão vinculante

- Os critérios D0 1–6 e 8 passaram integralmente.
- O item 7 admitia rota oficial capaz de sustentar envelope conservador auditável.
- `CURRENT_ONLY` não reconstrói custos históricos reais, mas permite definir previamente um limite conservador uniforme.
- Borrow/margin histórico deixa de ser requisito no cash-and-carry unilateral totalmente financiado.
- O gap não descarta H01 e não autoriza experimento; permite somente solicitar aquisição e QA estrutural em D1.

## Escopo autorizável de D1

Somente após nova autorização humana explícita:

- baixar os 1.440 ZIPs oficiais manifestados, total declarado de 321.304.758 bytes;
- validar os 1.440 checksums;
- preservar raw imutável e proveniência;
- extrair e ingerir em área isolada;
- executar somente QA estrutural de schema, timestamps, duplicatas, gaps, continuidade e sincronização;
- não calcular retornos, carry, regressões ou qualquer outcome;
- não ativar H01;
- não escrever protocolo experimental se o QA falhar.

## Próxima ação exata

`HUMAN_AUTHORIZATION_FOR_H01_D1_DATASET_CONTENT_AND_STRUCTURAL_QA`

Até essa autorização, Discovery V2 permanece `PAUSED_PENDING_D1_AUTHORIZATION`, H01 permanece `SELECTED_PENDING_DATA` e D1 permanece não autorizado.
