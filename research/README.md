# Índice de Pesquisa

Este diretório é a porta de entrada para a trilha científica. Os artefatos
permanecem em seus locais originais para preservar caminhos, hashes e
reprodutibilidade.

## Evolução do programa

| Geração | Pergunta | Fonte principal | Estado |
|---|---|---|---|
| Fases 1–3 | Estratégias e componentes generalizam? | [`RESEARCH_HANDBOOK.md`](../RESEARCH_HANDBOOK.md) | Encerrada |
| Fase 4 | Existe mecanismo econômico em OHLCV? | [`PHASE4_FINAL_SCIENTIFIC_REPORT.md`](../PHASE4_FINAL_SCIENTIFIC_REPORT.md) | Encerrada sem edge |
| Discovery V2 | Dados de derivativos justificam H01/H02? | [`DISCOVERY_V2_SCIENTIFIC_LEDGER.md`](../DISCOVERY_V2_SCIENTIFIC_LEDGER.md) | Encerrada |
| Discovery V3 | Algum mecanismo novo é robusto e executável? | [`DISCOVERY_V3_FINAL_SCIENTIFIC_REPORT.md`](../user_data/discovery_v3/final/DISCOVERY_V3_FINAL_SCIENTIFIC_REPORT.md) | Encerrada sem edge |

## Fontes canônicas atuais

- [Charter do Discovery V3](../user_data/discovery_v3/governance/DISCOVERY_V3_CHARTER.md)
- [Ledger definitivo](../user_data/discovery_v3/governance/SCIENTIFIC_LEDGER.md)
- [Inventário de hipóteses](../user_data/discovery_v3/final/FINAL_HYPOTHESIS_INVENTORY.md)
- [Inventário de dados](../user_data/discovery_v3/final/FINAL_DATA_INVENTORY.md)
- [Árvore de decisão](../user_data/discovery_v3/final/FINAL_DECISION_TREE.md)
- [Recomendações objetivas](../user_data/discovery_v3/final/OBJECTIVE_RECOMMENDATIONS.md)

## Como ler uma hipótese

1. Stage 0: fundamento e literatura.
2. Stage 1: disponibilidade, provenance e custo.
3. Stage 2: aquisição e QA sem outcomes.
4. Stage 3: análise congelada com controles.
5. Decisão: `CONFIRMED`, `REJECTED`, `BLOCKED` ou falha experimental.

Não comece pelo maior coeficiente. Comece pela pergunta, pelos gates e pelo
estimando.

## Dados

O Git não contém o data lake local. Relatórios e manifests identificam fonte,
período, cobertura e hashes. A ausência dos blobs no repositório não altera as
decisões já registradas; evita um histórico Git de vários gigabytes.
