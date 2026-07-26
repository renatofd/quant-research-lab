# Lições Aprendidas

## Ciência

1. Profit Factor alto com poucos trades é evidência fraca.
2. Estabilidade local não implica estabilidade temporal.
3. Robustez in-sample não implica generalização.
4. Significância não implica relevância econômica.
5. Previsão de risco não implica retorno direcional.
6. Um efeito menor que custos não é “quase uma estratégia”.
7. Concentração em um ativo, bloco ou dia pode explicar o agregado.
8. Resultado na direção oposta pode falsificar a hipótese e ainda ensinar.
9. Falha de QA, dataset limitado e hipótese rejeitada são estados diferentes.
10. Holdout não precisa ser aberto quando desenvolvimento já refuta.

## Dados

1. Candles são bons para refutar alguns efeitos, mas fracos para confirmar
   microestrutura.
2. Volume OHLCV não identifica agressor, instituição ou fluxo.
3. AUM não é flow; candle não é livro; trade isolado não é execução.
4. Provenance e data de conhecimento são parte do dado.
5. Missing não deve ser preenchido só para passar um gate.
6. Uma limitação uniforme e oficial pode ser documentada sem fingir completude.

## Engenharia

1. QA mecânico deve ser separado do cálculo de outcomes.
2. Instrumentos isolados reduzem graus de liberdade.
3. Artefatos JSON e matrizes CSV facilitam auditoria do Markdown.
4. Paths e hashes registrados limitam reorganizações posteriores.
5. Logs e caches não pertencem ao release; manifests e ledgers pertencem.
6. CLIs científicos podem parecer “não usados” em análise estática e ainda
   serem essenciais.

## Gestão de pesquisa

1. Custo afundado não justifica continuar.
2. O valor esperado da informação deve preceder implementação.
3. Critérios de parada protegem contra exploração infinita.
4. Registrar uma rejeição economiza mais trabalho do que ocultá-la.
5. A conclusão correta pode ser não construir o produto inicialmente desejado.
