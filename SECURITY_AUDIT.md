# Auditoria de Segurança

Data: 2026-07-25  
Escopo: arquivos rastreados, arquivos raiz candidatos a publicação e código/
documentação científica em `user_data/`

## Resultado

Não foram encontrados segredos reais no conjunto candidato a publicação. A
varredura de alta confiança encontrou um bloco PEM deliberadamente truncado em
`docs/exchanges.md`; a varredura genérica encontrou tokens de documentação e
credenciais estáticas de testes. A revisão contextual confirmou que são
placeholders, tokens expirados de exemplo ou fixtures, não credenciais locais.

Não foram encontrados:

- chaves privadas;
- tokens GitHub reais;
- access keys AWS;
- e-mails pessoais do mantenedor;
- caminhos contendo nome pessoal;
- IPs privados incorporados ao código científico;
- credenciais literais em módulos, relatórios ou protocolos.

## Achado local importante

`user_data/config.json` contém valores locais para autenticação da API do
Freqtrade. O arquivo já é ignorado pelo Git e continuará fora da publicação.
Os valores não foram exibidos, copiados ou alterados.

Medidas:

- `user_data/config.json` permanece ignorado;
- `.env`, bancos, WAL/SHM e logs permanecem ignorados;
- exemplos públicos usam placeholders;
- a documentação proíbe publicar configurações reais;
- recomenda-se rotacionar qualquer segredo que já tenha sido compartilhado fora
  deste diretório, ainda que ele nunca tenha entrado no Git.

## Workflows e supply chain

O repositório herdou workflows do Freqtrade para Docker Hub, GHCR, deploy de
documentação, atualização de tiers e limpeza de pacotes. Esses fluxos estavam
ligados à identidade do upstream e poderiam solicitar permissões ou segredos
irrelevantes no fork.

Para o release científico:

- fluxos de publicação e manutenção específicos do upstream foram removidos;
- a CI de testes e análise de segurança foi preservada;
- actions existentes usam commits fixados, reduzindo risco de tag mutável;
- segredos não são necessários para validar documentação, JSON ou bytecode.

## Riscos residuais

| Risco | Impacto | Mitigação |
|---|---|---|
| Publicar `user_data/config.json` manualmente | Crítico | `.gitignore`, revisão antes do commit e rotação |
| Adicionar dados brutos enormes ao Git | Alto | regras explícitas para `raw/`, `evidence/`, bancos e logs |
| Executar workflow do upstream contra namespace errado | Alto | remoção dos workflows de deploy/pacotes |
| Confiar em resultado científico sem provenance | Alto | manifests, checksums, ledger e relatório final |
| Dependências de terceiros vulneráveis | Variável | Dependabot, lock/pins existentes e revisão periódica |
| Código operacional histórico ser confundido com recomendação | Alto | disclaimer e status científico no README |

## Política para novos arquivos

Antes de um commit:

```bash
git status --short
git diff --cached
```

Verifique especialmente:

- `.env*`;
- `user_data/config*.json`;
- `*.sqlite*`;
- `*.pem`, `*.key`, `*.p12`, `*.pfx`;
- logs;
- dumps de terminal;
- URLs assinadas;
- cookies e headers de autenticação;
- paths pessoais.

Nunca “sanitize” um segredo apenas parcialmente. Remova-o do histórico, revogue-o
na origem e gere outro.

## Decisão

**Aprovado para publicação com as regras de exclusão atuais.** A aprovação vale
para o conjunto candidato ao Git, não para todo o conteúdo local de
`user_data/`. Dados e configurações ignorados não devem ser forçados com
`git add -f`.
