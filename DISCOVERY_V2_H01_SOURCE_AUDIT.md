# DISCOVERY V2 — V2-H01 SOURCE AUDIT

## Estado vinculante

- Programa: **Discovery V2**
- Status: **PAUSED_AT_EXTERNAL_DATA_GATE**
- Hipótese: **V2-H01 — SELECTED_PENDING_DATA**
- Hipótese ativa: **não**
- Hipótese testada: **não**
- Protocolo experimental autorizado: **não**
- Bot autorizado: **não**
- Próxima ação autorizável: **HUMAN_AUTHORIZATION_FOR_H01_D0_MANIFEST_ONLY**

Este documento é uma auditoria de disponibilidade potencial baseada exclusivamente na documentação oficial já revisada pelo Diretor Científico. Nenhum arquivo, endpoint ou conteúdo de mercado foi consultado ou adquirido nesta etapa.

## Objetivo

Determinar quais fontes oficiais podem, em princípio, fornecer os componentes do dataset mínimo de V2-H01 e quais requisitos continuam não verificados ou sem fonte histórica adequada. O objetivo não é aceitar o dataset, formular protocolo experimental ou avaliar a hipótese.

**Disponibilidade potencial não significa dataset aceito.**

## Hipótese documentalmente selecionada

V2-H01 investiga carry e convergência de funding/basis em perpétuos. Seu mecanismo econômico é motivado pela transferência de renda via funding e pela convergência do perpetual ao índice, sob limites de arbitragem, capital e margem. A fundamentação indicada é He, Manela, Ross & von Wachter, [Fundamentals of Perpetual Futures](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4301150).

A referência acadêmica motiva a pergunta, mas não prova disponibilidade, qualidade ou cobertura dos dados necessários no universo do laboratório.

## Fontes oficiais auditadas documentalmente

### 1. Binance Public Data

Fonte: [binance/binance-public-data](https://github.com/binance/binance-public-data)

**O que prova documentalmente:**

- existe arquivo público oficial com dados spot e futures organizados em arquivos diários e mensais;
- há convenções para símbolos e intervalos, incluindo klines de 1m e 5m;
- existem checksums associados aos arquivos;
- a própria fonte admite substituição de arquivos quando problemas são descobertos.

**O que não prova:**

- cobertura contínua de 24 meses para cada série e cada um dos dez ativos;
- ausência de gaps, duplicatas, correções retrospectivas ou mudanças de schema;
- disponibilidade histórica completa de funding, especificações contratuais, fees e borrow/margin;
- adequação imediata para H01 sem inventário e QA.

**Conclusão:** candidato primário gratuito para dados brutos oficiais, com status **POTENCIAL**.

### 2. Scripts oficiais de futures

Fonte: [scripts Python do Binance Public Data](https://github.com/binance/binance-public-data/tree/master/python)

**O que prova documentalmente:**

- existem downloaders oficiais para USD-M klines, `indexPriceKlines`, `markPriceKlines` e `premiumIndexKlines`;
- os scripts contemplam intervalos temporais desde 2020 até o ano atual.

**O que não prova:**

- que todos os arquivos esperados existem para todos os dez símbolos e cada mês;
- que a cobertura de 24 meses é contínua e sincronizável entre todas as séries;
- que execução dos scripts produziria um dataset completo sem validação dos manifests;
- que funding, specs, fees e borrow/margin estejam resolvidos pelos mesmos scripts.

**Conclusão:** evidência de rota oficial para as séries primárias, ainda **POTENCIAL**.

### 3. Binance Derivatives API catalog

Fonte: [USDⓈ-M Futures REST Market Data](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data)

**O que prova documentalmente:**

- existem interfaces oficiais de mercado para funding, mark/index, premium/basis e séries relacionadas.

**O que não prova:**

- retenção histórica completa de 24 meses por endpoint;
- cobertura completa para cada símbolo;
- equivalência entre documentação de endpoint e arquivo histórico point-in-time;
- disponibilidade versionada de specs, fee schedules e custos de borrow/margin.

**Conclusão:** referência oficial de interfaces, mas **não** evidência suficiente de arquivo histórico. Endpoint com retenção curta não pode ser tratado como histórico completo.

### 4. Fundamentação econômica

Fonte: [Fundamentals of Perpetual Futures](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4301150)

**O que prova documentalmente:** existe fundamento acadêmico para estudar funding, basis, convergência e limites de arbitragem em perpetual futures.

**O que não prova:** que H01 funciona no universo selecionado, que o efeito é líquido de custos ou que os dados da Binance são suficientes.

## Matriz de requisitos de H01

| Requisito | Fonte candidata | Status | Evidência atual | Lacuna antes de D1 |
|---|---|---|---|---|
| Spot klines 1m/5m | Binance Public Data | POTENCIAL | Arquivo oficial diário/mensal e checksums documentados | Cobertura de 24 meses × 10 símbolos não verificada |
| USD-M perpetual klines 1m/5m | Public Data + scripts oficiais | POTENCIAL | Downloader e organização futures documentados | Presença, continuidade e sincronização não verificadas |
| Mark price klines | Scripts oficiais | POTENCIAL | `markPriceKlines` documentado | Matriz símbolo/mês e gaps não verificados |
| Index price klines | Scripts oficiais | POTENCIAL | `indexPriceKlines` documentado | Matriz símbolo/mês e gaps não verificados |
| Premium/basis klines | Scripts/API oficial | POTENCIAL | `premiumIndexKlines` e interfaces documentadas | Cobertura histórica e semântica point-in-time não verificadas |
| Funding events | Arquivo/API oficial potencial | NÃO VERIFICADO | Rota oficial parece existir | Cobertura contínua de 24 meses para os dez ativos não comprovada |
| Checksums | Binance Public Data | POTENCIAL | Checksums por arquivo documentados | Disponibilidade para cada arquivo esperado não verificada |
| Changelog/correções | Repositório e issues públicos | POTENCIAL | Substituição/correção de arquivos é documentada | Inventário de revisões por arquivo precisa ser preservado |
| Contract specifications point-in-time | Não estabelecida | GAP | Documentação corrente não prova arquivo histórico completo | Specs versionadas, mudanças de contrato, tick/lot size e settlement |
| Fee schedules point-in-time | Não estabelecida | GAP | Não há evidência documental de histórico completo no arquivo público | Fee schedules versionados por mercado, conta e período |
| Borrow/margin costs point-in-time | Não estabelecida | GAP | Não há evidência documental suficiente | Custos e disponibilidade aplicáveis ao desenho delta-neutral |
| Pelo menos 8 ativos comuns | Manifests oficiais futuros | NÃO VERIFICADO | Universo-alvo contém dez símbolos | Interseção temporal válida ainda desconhecida |
| Cobertura mínima de 24 meses | Manifests oficiais futuros | NÃO VERIFICADO | Scripts indicam intervalos desde 2020 | Arquivos reais por série/símbolo/mês não inventariados |
| Holdout prospectivo | Governança do programa | GAP DE PROCESSO | Exigência registrada | Deve ser congelado antes de qualquer inspeção de outcome |

## Riscos de integridade

1. **Arquivos substituídos:** a fonte oficial pode corrigir arquivos; hash, timestamp, versão e histórico de substituição são obrigatórios.
2. **Gaps silenciosos:** presença do arquivo não garante continuidade candle/event-level.
3. **Cobertura assimétrica:** símbolos e séries podem iniciar em datas diferentes, reduzindo a interseção comum.
4. **Retenção curta de API:** endpoint operacional não demonstra histórico completo.
5. **Eventos de funding:** timestamps, intervalos e eventos ausentes/duplicados precisam de reconciliação.
6. **Semântica das séries:** mark, index, premium e klines perp precisam de contratos e schemas versionados.
7. **Mudanças contratuais:** tick size, lot size, multiplier, settlement e regras podem variar.
8. **Custos incompletos:** fee, borrow, margem e liquidação podem invalidar inferência econômica se reconstruídos inadequadamente.
9. **Survivorship/listing:** a disponibilidade deve ser auditada por símbolo e data, sem preencher períodos inexistentes.
10. **Lookahead de correção:** arquivos corrigidos posteriormente precisam ser identificados; QA não pode fingir disponibilidade point-in-time original.

Issues públicos que documentam gaps ou arquivos corrigidos reforçam a necessidade de checksums, changelog e QA candle/event-level. Eles não são autorização para substituir ou corrigir dados silenciosamente.

## Gate D0 — MANIFEST-ONLY

**Requer autorização humana explícita.** D0 consulta apenas metadados oficiais e não baixa conteúdo de mercado.

### Escopo permitido

- listar manifests, nomes de arquivos, datas, tamanhos, `last-modified` e checksums;
- verificar os dez símbolos e pelo menos 24 meses;
- cobrir spot klines, USD-M perp klines, mark, index, premium e funding events;
- construir matriz `esperado / encontrado / ausente` por símbolo, série e período;
- estimar volume de armazenamento e número de arquivos;
- localizar evidência versionada para contract specs, fee schedules e borrow/margin;
- registrar retenção, proveniência, licença e política de correção.

### Proibido em D0

- baixar ZIP, CSV, Feather, Parquet ou qualquer conteúdo de mercado;
- consultar retornos, preços, funding realizado ou outcomes;
- calcular H01 ou qualquer estatística econômica;
- criar protocolo experimental;
- usar terceiros para preencher lacunas sem decisão humana nova.

### Critérios objetivos de aprovação de D0

D0 será aprovado somente se todos os requisitos materiais forem demonstrados por manifests/fontes oficiais:

1. pelo menos oito dos dez ativos têm interseção contínua mínima de 24 meses;
2. spot e USD-M perp klines existem na granularidade mínima de 5m;
3. mark, index e premium existem para a mesma interseção;
4. funding events possuem cobertura compatível e timestamps documentados;
5. checksums e metadados permitem inventário reproduzível;
6. gaps de disponibilidade são explicitamente mapeados, não inferidos;
7. existe rota defensável para specs e fees point-in-time;
8. borrow/margin aplicável pode ser reconstruído ou declarado não aplicável de modo auditável;
9. custo, espaço e retenção são conhecidos antes do download;
10. plano de development/holdout prospectivo pode ser congelado sem inspeção de outcome.

### Critérios objetivos de rejeição de D0

D0 será rejeitado e o programa continuará pausado se ocorrer qualquer condição material:

- menos de oito ativos com 24 meses comuns;
- ausência estrutural de funding, mark, index ou premium;
- arquivo sem checksums/proveniência suficiente para QA;
- histórico dependente de endpoint com retenção curta;
- specs, fees ou custos essenciais sem reconstrução point-in-time defensável;
- custo/licença/retenção incompatível com o programa;
- impossibilidade de reservar holdout antes da inspeção.

Resultado parcial não autoriza D1. Fontes de terceiros só podem ser consideradas após auditoria da fonte oficial e nova decisão humana.

## Gate D1 — DATASET CONTENT

D1 só pode começar após D0 aprovado e **nova autorização humana explícita**.

### Escopo permitido

- baixar somente o conjunto mínimo aprovado em D0;
- validar checksums antes de ingestão;
- preservar arquivos brutos imutáveis;
- registrar manifest, proveniência, timestamps e versões;
- executar QA estrutural de cobertura, schema, ordenação, duplicatas, gaps, timestamps e consistência entre séries;
- congelar development e holdout prospectivo antes de qualquer análise.

### Proibido em D1

- calcular outcomes, carry, P&L ou estatísticas de H01;
- escolher ativos/períodos por desempenho;
- preencher gaps silenciosamente;
- alterar conteúdo bruto;
- ampliar para OI/liquidações sem protocolo separado.

Open interest e liquidações não são requisitos de H01; permanecem reservados para V2-H02 e V2-H08.

## Custo e valor da informação

| Etapa | Custo científico | Valor de informação | Impacto esperado |
|---|---|---|---|
| D0 manifest-only | Baixo | Alto | Alta probabilidade de decidir se H01 é executável; baixa probabilidade de mudar imediatamente a conclusão operacional |
| D1 séries primárias | Baixo-médio | Alto, se D0 passar | Produz dataset auditável, mas ainda não testa H01 |
| Reconstrução de specs/custos | Potencialmente médio | Material | Pode viabilizar ou bloquear interpretação líquida de carry |

O VEI de D0 é alto porque ele pode refutar a executabilidade de H01 com pouco custo e sem consumir outcomes.

## Decisão científica documental

- Fonte primária potencial: **Binance Data Collection** para spot/perp klines, mark, index, premium e checksums.
- Funding histórico: **NÃO VERIFICADO** para 24 meses × dez ativos.
- Specs, fees e borrow/margin point-in-time: **GAP MATERIAL**.
- Dataset H01: **NÃO ACEITO**.
- V2-H01: **SELECTED_PENDING_DATA**, não ativa e não testada.
- Discovery V2: **PAUSED_AT_EXTERNAL_DATA_GATE**.
- Próxima ação autorizável exata: **HUMAN_AUTHORIZATION_FOR_H01_D0_MANIFEST_ONLY**.

Sem essa autorização, o programa permanece pausado. Nenhum dado foi adquirido, nenhuma API foi consultada, nenhuma análise foi executada e nenhuma hipótese foi ativada.
