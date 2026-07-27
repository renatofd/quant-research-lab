# H07 Stage 0 — ETF Flows

**Decisão:** `STAGE0_PASS` — 2026-07-24

Mecanismo: creations/redemptions de ETFs spot geram demanda de hedge e execução nos
mercados subjacentes; quando o fluxo excede profundidade agregada, o impacto pode
persistir entre venues. O teste causal deve usar apenas fluxo conhecido no momento
da decisão e prever retorno posterior à publicação, não explicar o mesmo dia.

Literatura recente modela impacto cross-venue e relata efeito permanente/momentum,
mas usa painel derivado de Farside, não uma fonte oficial única:
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6567058

O mecanismo é forte; a dificuldade é o relógio informacional do dado.
