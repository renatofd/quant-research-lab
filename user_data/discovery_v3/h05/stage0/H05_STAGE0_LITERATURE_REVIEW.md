# H05 Stage 0 — Liquidity Regimes

**Decisão:** `STAGE0_PASS` — 2026-07-24

Mecanismo: profundidade, spread e reposição do livro determinam quanto fluxo se
converte em impacto permanente ou temporário. Em baixa liquidez, a mesma ordem
produz maior deslocamento, risco de adverse selection e custo. A hipótese
falsificável mais econômica é que choque de fluxo condicionado a baixa profundidade
tem impacto futuro maior e replicável que o mesmo choque em alta profundidade.

Literatura de limit order books identifica regimes de “liquidity cushion” e campo
fragmentado, e estudos cripto ligam livro, impacto e qualidade de mercado:

- https://arxiv.org/abs/2106.11691
- https://arxiv.org/abs/2303.10043
- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4218907

OHLCV, volume ou range não podem substituir profundidade/spread: a hipótese A08 do
projeto anterior rejeitou definitivamente proxy OHLCV de iliquidez. H05 passa apenas
ao inventário do dado de livro, sem código.
