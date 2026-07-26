# Guia de Publicação

## 1. Revise o escopo

Publique código, documentação, manifests selecionados e resultados agregados.
Não publique o data lake local.

## 2. Configure um remote próprio

O checkout histórico pode apontar para o upstream Freqtrade. Crie o repositório
de destino e revise antes de alterar remotes:

```bash
git remote -v
git remote rename origin upstream
git remote add origin <URL_DO_NOVO_REPOSITORIO>
```

Não execute o comando até possuir a URL correta e autorização sobre o destino.

## 3. Inspecione os arquivos

```bash
git status --short
git check-ignore -v user_data/config.json
git diff
```

Depois de selecionar arquivos:

```bash
git diff --cached --stat
git diff --cached
```

Nunca use `git add -f` em `user_data/config.json`, `.env`, `raw/`, `evidence/`,
bancos ou logs.

## 4. Verifique dados sensíveis

Procure tokens, chaves, paths pessoais, IPs privados e dumps. Se um segredo já
entrou no histórico, apagar o arquivo no último commit não basta: revogue e
reescreva o histórico antes de publicar.

## 5. Valide

- Markdown e links relativos;
- JSON;
- `CITATION.cff`;
- `py_compile` dos módulos científicos;
- testes que não executem campanhas;
- GitHub Actions sem segredos de upstream.

## 6. Metadados do GitHub

Sugestão de descrição:

> Falsifiable quantitative-research lab built on Freqtrade; rigorous negative
> results, preregistered gates and reproducible scientific governance.

Tópicos:

`quantitative-research`, `crypto`, `reproducibility`, `falsification`,
`freqtrade`, `research-engineering`, `open-science`

Habilite:

- Issues;
- Discussions;
- Private vulnerability reporting;
- branch protection;
- Dependabot alerts.

## 7. Release

Crie a tag somente após validação:

```bash
git tag -s v1.0.0 -m "Quantitative Research Lab v1.0.0"
```

Assinatura é recomendada, não obrigatória. Use
[`RELEASE_NOTES_v1.0.0.md`](../RELEASE_NOTES_v1.0.0.md) como texto da release.

## 8. Licença

Não substitua `LICENSE` por MIT. O trabalho combinado deriva do Freqtrade e
permanece GPLv3 ou posterior. Preserve `NOTICE.md` e a atribuição upstream.
