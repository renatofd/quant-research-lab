# Auditoria do Projeto

Data da auditoria: 2026-07-25  
Escopo: repositório `freqtrade`, incluindo arquivos ignorados em `user_data/`  
Modo: auditoria estrutural e limpeza conservadora; nenhum experimento executado

## Resumo executivo

O repositório contém um fork completo do Freqtrade, uma infraestrutura
científica própria, três gerações de pesquisa e aproximadamente 10 GB de dados e
artefatos locais antes da limpeza. O principal risco para publicação não era
código morto, mas a mistura entre:

- código upstream;
- instrumentos científicos;
- documentação final;
- dados brutos e evidência reprodutível;
- milhares de logs e caches;
- configuração operacional local.

A reorganização adotou índices públicos e regras de versionamento, sem mover
artefatos científicos históricos ou alterar caminhos usados pelos instrumentos.

## Inventário inicial

| Área | Arquivos | Tamanho aproximado | Classificação |
|---|---:|---:|---|
| Repositório Git rastreado | 772 | — | Código e documentação upstream |
| Arquivos raiz não rastreados | 46 | ~2,1 MB | Protocolos, relatórios e ledgers |
| `user_data/` | 134.917 | 10,02 GB | Código, dados, resultados e runtime |
| `user_data/lab/` | 103.500 | 8,91 GB | 3.678 runs, relatórios e infraestrutura |
| `user_data/discovery_v2/` | 16.128 | 413 MB | Dados, QA, instrumentos e resultados |
| `user_data/discovery_v3/` | 15.108 | 627 MB | Dados, QA, instrumentos e resultados |
| Logs | 3.595 | 3,27 GB | Descartável |
| Caches/bytecode Python | 95 | 1,13 MB | Descartável |
| Bancos e sidecars SQLite | 5 | 43,18 MB | Preservar |
| Temporários `.tmp/.bak/.orig` | 0 | 0 | Sem achados |

## Achados

### Dados e resultados

- `user_data/lab/runs/` concentrava a maior parte do volume local.
- Os dados brutos de Discovery V2/V3 são evidência reproduzível, mas não são
  adequados para Git.
- Manifests, checksums, relatórios finais, protocolos e ledgers são necessários
  à rastreabilidade e foram preservados.
- Bancos SQLite e arquivos WAL/SHM não foram removidos: podem conter estado
  científico ou transações ainda não consolidadas.

### Duplicação

Foram encontradas nove famílias de conteúdo idêntico na amostra de código e
documentos. As duplicações relevantes são:

- templates upstream e exemplos copiados para `user_data/`;
- aliases históricos de relatórios finais;
- snapshots de auditoria e seus estados `latest`;
- cinco JSON vazios de regiões ótimas rejeitadas.

Nenhum desses arquivos foi excluído. Nos exemplos, a duplicação é intencional;
nos resultados científicos, remover aliases poderia quebrar provenance ou
referências históricas.

### Código potencialmente obsoleto

- estratégias e famílias operacionais históricas continuam no repositório,
  embora cientificamente rejeitadas;
- módulos de Fases 1–4 permanecem necessários para reprodução e auditoria;
- scripts de aquisição e análise do Discovery V3 são executáveis isolados e não
  aparecem necessariamente em um grafo de imports.

Não houve evidência suficientemente forte para apagar módulos. “Não importado”
não equivale a “morto” em uma base de CLIs científicos.

### Notebooks

Existe apenas o notebook de exemplo do Freqtrade, além de `.gitkeep`. Não foi
classificado como notebook abandonado.

### Documentação histórica

`PROJECT.md`, `CURRENT_STATE.md` e `RESEARCH_HANDBOOK.md` descrevem fases antigas
e não são o estado atual. Foram mantidos como registro histórico, mas o README,
o relatório do Discovery V3 e o ledger definitivo passam a ser as fontes
canônicas.

### Git e release

- o remote local ainda aponta para `freqtrade/freqtrade`;
- o branch ativo é `develop`;
- `docker-compose.yml` já tinha uma alteração local anterior à auditoria e foi
  preservado;
- workflows de publicação do upstream dependiam de identidade e segredos do
  projeto original e não pertencem ao release científico.

## Limpeza aplicada

Foram removidos exclusivamente:

- 3.595 arquivos `.log`;
- 95 arquivos de cache/bytecode em `__pycache__`, `.pyc` ou `.pyo`;
- diretórios `__pycache__` que ficaram vazios;
- automações de deploy/pacotes específicas do upstream, sem impacto no código.

Economia local: aproximadamente **3,27 GB**.

Inventário após a limpeza: **131.262 arquivos** e **6,75 GB** em `user_data/`,
sem logs ou caches Python remanescentes.

Não foram removidos:

- dados brutos;
- bancos ou sidecars;
- manifests ou checksums;
- protocolos;
- relatórios finais;
- ledgers;
- resultados científicos;
- módulos Python;
- estratégias históricas;
- alteração local do usuário.

## Organização adotada

```text
.
├── freqtrade/                 # motor upstream
├── user_data/                 # instrumentos e evidência local
├── research/                  # índice público da pesquisa
├── reports/                   # índice público dos resultados
├── docs/                      # documentação técnica e de portfólio
├── scripts/                   # scripts upstream
├── config_examples/           # exemplos sanitizados
├── .github/                   # colaboração e CI
├── ARCHITECTURE.md
├── PROJECT_AUDIT.md
└── SECURITY_AUDIT.md
```

O pacote upstream não foi movido para `src/`: isso quebraria imports,
empacotamento, testes e compatibilidade com o Freqtrade sem gerar ganho
científico.

## Pendências intencionais

- configurar o novo remote do GitHub no momento da publicação;
- decidir se dados brutos serão depositados em repositório científico externo;
- não usar Git LFS sem uma política de retenção e custos;
- manter o holdout e os dados locais fora do histórico Git;
- fazer revisão humana final de autoria e metadados de citação.

## Decisão

O repositório está estruturalmente apto para um release público de código,
documentação e evidência resumida. Os dados locais permanecem deliberadamente
fora do pacote Git. A conclusão científica e todos os resultados foram
preservados.

O conjunto final elegível para adição contém 381 arquivos não rastreados
(22,82 MB), sem dados brutos, evidências blob, bancos, logs ou caches.
