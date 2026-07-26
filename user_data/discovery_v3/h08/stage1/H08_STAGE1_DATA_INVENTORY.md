# H08 Stage 1 — Inventário e bloqueio

**Decisão:** `BLOCKED_DATA_HISTORICAL_OPTION_SURFACE_REQUIRED`

Necessário por timestamp: cadeia completa BTC/ETH, bid/ask, OI, volume, IV,
instrument metadata, forwards, expiries/strikes e índice subjacente. Trades públicos
da Deribit são recuperáveis, mas não reconstroem cotações não negociadas nem um preço
executável da superfície. Mark history oficial cobre apenas subconjunto.

Reconstruir IV de trades criaria viés de seleção; usar preço médio sem spread
superestimaria o prêmio. Dataset de quotes/snapshots histórico normalmente exige
provedor externo. H08 fica bloqueada até coleta prospectiva oficial ou dataset
auditado; não se implementa modelo de opções sobre dados incompletos.
