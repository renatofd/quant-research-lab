# DISCOVERY V2 — SCIENTIFIC LEDGER

## Estado do programa

- Programa: **Discovery V2**
- Projeto anterior: **ARCHIVED_FINAL**
- Status: **PAUSED_PENDING_D1_AUTHORIZATION**
- Motivo exato: **D1_AUTHORIZATION_REQUIRED**
- Hipóteses ativas: **nenhuma**
- Hipóteses testadas: **nenhuma**
- Bot autorizado: **não**
- D0 mecânico: **D0_MECHANICAL_INCONCLUSIVE**
- D0 científico: **CONDITIONAL_PASS_FOR_D1_ACQUISITION_ONLY**
- D1 autorizado: **não**
- Próxima ação autorizada: **HUMAN_AUTHORIZATION_FOR_H01_D1_DATASET_CONTENT_AND_STRUCTURAL_QA**

O encerramento científico anterior permanece vinculante: nenhuma hipótese baseada apenas em OHLCV justificou bot. Discovery V2 não reabre essas hipóteses.

## Ledger

| ID | Estado | Ativa | Testada | Disponível localmente | Observação |
|---|---|---:|---:|---:|---|
| V2-H01 | SELECTED_PENDING_DATA | Não | Não | NÃO | D0 científico condicional permite somente solicitar D1; D1 não autorizado e nenhum protocolo experimental ativo. |
| V2-H02 | CATALOGUED_NOT_STARTED | Não | Não | NÃO | Depende de funding, OI e fluxo/liq. |
| V2-H03 | CATALOGUED_NOT_STARTED | Não | Não | NÃO | Depende de spot/perp em alta frequência. |
| V2-H04 | CATALOGUED_NOT_STARTED | Não | Não | NÃO | Depende de ETF flows point-in-time. |
| V2-H05 | CATALOGUED_NOT_STARTED | Não | Não | NÃO | Depende de surprises macro point-in-time. |
| V2-H06 | CATALOGUED_NOT_STARTED | Não | Não | NÃO | Depende de funding/basis cross-sectional e borrow. |
| V2-H07 | CATALOGUED_NOT_STARTED | Não | Não | NÃO | Depende de trades assinados e L2. |
| V2-H08 | CATALOGUED_NOT_STARTED | Não | Não | NÃO | Depende de liquidações, OI e livro. |
| V2-H09 | CATALOGUED_NOT_STARTED | Não | Não | NÃO | Depende de opções point-in-time. |
| V2-H10 | CATALOGUED_NOT_STARTED | Não | Não | NÃO | Depende de L2/L3 incremental. |
| V2-H11 | CATALOGUED_NOT_STARTED | Não | Não | NÃO | Depende de on-chain e labels versionados. |
| V2-H12 | CATALOGUED_NOT_STARTED | Não | Não | NÃO | Depende de mint/burn e fluxos de stablecoins. |
| V2-H13 | CATALOGUED_NOT_STARTED | Não | Não | NÃO | Depende de CME e offshore sincronizados. |
| V2-H14 | CATALOGUED_NOT_STARTED | Não | Não | NÃO | Depende de pelo menos três venues. |
| V2-H15 | CATALOGUED_NOT_STARTED | Não | Não | NÃO | Depende de CEX/DEX, gas, MEV e inventário. |

## Regra de transição

Seleção não significa ativação. A decisão `CONDITIONAL_PASS_FOR_D1_ACQUISITION_ONLY` não altera o resultado mecânico `D0_MECHANICAL_INCONCLUSIVE`. V2-H01 só poderá avançar para aquisição e QA estrutural após nova autorização humana explícita; continuará não ativa e não testada durante D1. Nenhum protocolo experimental está autorizado.
