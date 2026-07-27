# H09 Stage 0 — Order Flow / CVD

**Decisão:** `STAGE0_PASS_TO_COST_AUDIT` — 2026-07-24

Mecanismo: fluxo agressor pode carregar informação privada ou demanda urgente.
Quando market makers não conseguem absorvê-lo sem adverse selection, o impacto
persiste; quando é apenas demanda por imediatismo, reverte. O teste correto exige
sequência de trades, lado agressor e preço executável posterior.

A literatura sustenta relação entre imbalance e impacto, mas alerta que volume
agregado é mais ruidoso que eventos de livro:

- https://arxiv.org/abs/1011.6402
- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6938742
- https://www.sciencedirect.com/science/article/pii/S1386418126000029
- https://arxiv.org/abs/2607.09426

CVD acumulado sem janela econômica seria um indicador ajustável. A hipótese
admissível é somente signed aggressive flow em tempo nativo → retorno futuro,
condicional ao impacto contemporâneo.
