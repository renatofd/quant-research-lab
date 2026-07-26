# Decisões de Design

## DD-001 — Freqtrade como motor, laboratório como camada

O core upstream foi preservado para reutilizar dados, persistência e execução
sem reimplementar uma plataforma. A interpretação científica permanece fora do
motor.

## DD-002 — Uma hipótese por campanha

Cada instrumento responde a uma pergunta pré-registrada. Isso reduz
multiplicidade oculta e impede que um módulo vire busca genérica.

## DD-003 — QA antes de outcomes

Aquisição, cobertura, schema, timestamps e checksums são avaliados antes de
retornos ou PnL. Uma falha de dados não é convertida em resultado econômico.

## DD-004 — Estados de dados explícitos

O protocolo distingue:

- `PASS`;
- `PASS WITH DOCUMENTED DATASET LIMITATION`;
- `FAIL`.

A limitação intermediária exige fonte oficial, padrão uniforme, ausência de
alternativa legítima, impacto avaliado e rastreabilidade. Gaps seletivos,
dependentes do outcome ou sem provenance continuam bloqueando.

## DD-005 — Holdout selado

Holdouts são definidos antes da análise. Quando desenvolvimento falha em
magnitude ou economia, o holdout permanece fechado; independência estatística
não é consumida por curiosidade.

## DD-006 — Bootstrap por unidade temporal

Candles adjacentes não são independentes. O bootstrap usa dias ou blocos
compatíveis com o estimando, conforme protocolo.

## DD-007 — Holm e controles negativos

Comparações múltiplas recebem correção de Holm. Pseudo-líderes, shifts,
reverse-time, placebos ou baselines testam especificidade.

## DD-008 — Economia antes de operação

Coeficiente e p-value não promovem hipótese. O efeito deve sobreviver a custos,
replicar entre ativos/períodos e ser operacionalmente mensurável.

## DD-009 — Não mover artefatos históricos

Na preparação open source, índices foram adicionados em vez de mover relatórios
e scripts. Paths fazem parte de manifests, hashes e comandos registrados.

## DD-010 — Dados fora do Git

Dados brutos, bancos e logs são armazenados localmente ou em depósito de dados.
O Git mantém código, provenance, manifests selecionados e resultados agregados.

## DD-011 — GPL preservada

O pedido de licença MIT não foi aplicado. O repositório deriva do Freqtrade sob
GPLv3; substituir a licença raiz removeria obrigações do upstream que o
mantenedor não pode unilateralmente relicenciar.
