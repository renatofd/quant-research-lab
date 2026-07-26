# Contribuindo

Obrigado por ajudar a tornar esta pesquisa mais verificável. Este é um
laboratório científico encerrado sob o conjunto de dados atual, construído sobre
o Freqtrade. Contribuições devem preservar tanto a compatibilidade upstream
quanto a trilha de evidência.

## Formas úteis de contribuir

- auditar um protocolo ou relatório;
- melhorar testes, documentação e acessibilidade;
- reproduzir artefatos a partir do mesmo manifest;
- reportar inconsistências entre ledger, JSON e Markdown;
- propor um dataset novo com provenance point-in-time;
- corrigir bugs sem mudar o estimando ou a decisão científica.

Não são aceitas como simples melhorias:

- otimização de parâmetros de hipóteses rejeitadas;
- novas combinações de indicadores;
- alteração retroativa de gates;
- transformação de relações estatísticas em estratégia;
- abertura de holdout para “ver se melhora”;
- remoção ou reescrita de resultados negativos.

## Antes de abrir uma mudança

Abra uma issue para mudanças metodológicas ou de arquitetura. Informe:

1. problema observável;
2. arquivos afetados;
3. impacto sobre reprodução e compatibilidade;
4. se algum resultado, hash, protocolo ou holdout pode ser alterado;
5. validação proposta.

Uma nova hipótese só pode ser discutida quando trouxer mecanismo econômico e
dados materialmente novos. Ela exige pré-registro antes de qualquer outcome.

## Ambiente

```bash
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install -r requirements-dev.txt
```

## Validação mínima

```bash
pre-commit run --all-files
pytest
```

Para mudanças limitadas ao laboratório, execute também `py_compile` nos módulos
afetados e valide todos os JSON modificados. Não execute campanhas científicas
como efeito colateral de testes.

## Regras de código

- Python e comentários de código em inglês; documentação científica pode usar
  português ou inglês de forma consistente;
- funções públicas documentadas;
- mudanças pequenas e focadas;
- paths portáveis com `pathlib`;
- seeds, versões, períodos e custos explícitos;
- escrita atômica para artefatos;
- nenhuma credencial ou path pessoal;
- dependências novas somente com justificativa.

## Regras de integridade científica

- não modificar artefatos finais para ajustar a narrativa;
- preservar protocolo e resultado como documentos distintos;
- separar QA mecânico de análise de outcomes;
- registrar qualquer desvio;
- não tratar dado ausente como zero;
- não escolher unidade de bootstrap após observar o resultado;
- não declarar hipótese rejeitada quando houve falha experimental;
- não declarar vantagem sem relevância econômica após custos;
- não reabrir linha encerrada sem dados e mecanismo novos.

## Pull requests

O PR deve:

- explicar motivação e escopo;
- listar arquivos criados, alterados e removidos;
- declarar se resultados científicos permaneceram byte a byte intactos;
- anexar os comandos de validação;
- informar uso de IA e confirmar revisão humana;
- atualizar documentação e changelog quando aplicável.

Não inclua dados brutos, bancos, logs, `.env` ou `user_data/config.json`.

## Licença

Ao contribuir, você concorda que sua contribuição será distribuída sob os termos
da GNU GPL v3 ou posterior, compatíveis com o trabalho derivado do Freqtrade.
