# H06 Stage 1 — Inventário e bloqueio

**Decisão:** `BLOCKED_DATA_POINT_IN_TIME_LABELS_REQUIRED`

Blockchain pública fornece transações, mas a variável econômica “exchange inflow”
depende de clusters de endereços. O laboratório não possui:

- labels de exchange versionados por data de conhecimento;
- histórico de mudanças dos clusters;
- fluxos intraday BTC, ETH e stablecoin com provenance;
- proteção contra uso retrospectivo de endereços descobertos depois.

Um nó próprio ainda não resolve entity resolution. Provedores comerciais oferecem
labels, mas exigem credencial/gasto e autorização externa. Scraping de dashboards
sem release timestamp não é auditável. H06 permanece bloqueada; não se baixa chain
bruta sem o contrato de labels.
