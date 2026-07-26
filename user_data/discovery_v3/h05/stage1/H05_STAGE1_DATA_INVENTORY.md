# H05 Stage 1 — Inventário e bloqueio

**Decisão:** `BLOCKED_DATA_ORDERBOOK_REQUIRED`

Necessário: snapshots point-in-time de bid/ask, múltiplos níveis, eventos de
cancelamento/reposição, trades agressivos, sequência e timestamp de exchange por pelo
menos duas janelas temporais e vários ativos.

O laboratório possui OHLCV e trades derivados, mas não histórico de livro. Binance e
Bybit oferecem WebSocket prospectivo; seus arquivos públicos históricos não fornecem
um livro reconstruível completo com sequência para o painel. Usar volume/range
reabriria A08, o que é proibido.

H05 fica bloqueada até coleta prospectiva oficial de book updates ou aquisição de
dataset histórico de livro com provenance. Não há experimento válido de baixo custo
com os dados atuais.
