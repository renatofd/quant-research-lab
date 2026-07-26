# H07 Stage 1 — Inventário e bloqueio

**Decisão:** `BLOCKED_DATA_RELEASE_TIME_AND_OFFICIAL_FLOW_PANEL_REQUIRED`

Emissores publicam holdings/NAV e filings, mas o laboratório não possui painel
histórico consolidado de creations/redemptions com:

- valor e shares por fundo;
- timestamp real de publicação;
- revisões/correções;
- diferença entre fluxo e valorização do BTC;
- provenance arquivo a arquivo.

Séries agregadas gratuitas normalmente são derivadas e podem ser revisadas sem
histórico de vintages. Usá-las sem timestamp criaria look-ahead. A amostra oficial
fragmentada pode ser reconstruída, mas exige nova fonte externa e auditoria material.
H07 fica bloqueada até esse contrato existir; nenhum proxy por variação de AUM será
aceito.
