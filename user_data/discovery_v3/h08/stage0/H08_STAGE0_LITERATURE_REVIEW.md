# H08 Stage 0 — Options Market

**Decisão:** `STAGE0_PASS` — 2026-07-24

Mecanismo selecionado: variance risk premium. Dealers/investidores transferem risco
de cauda via opções; volatilidade implícita e skew podem exceder a volatilidade
realizada esperada como compensação, com assimetria após demanda extrema de puts ou
calls. Isso é economicamente distinto de indicadores técnicos.

Deribit oferece API pública de trades históricos e índices de volatilidade, mas a
própria documentação limita histórico de mark price a subconjunto de opções:
https://docs.deribit.com/

A hipótese é plausível e falsificável, mas requer superfície point-in-time e preços
executáveis, não apenas trades esparsos.
