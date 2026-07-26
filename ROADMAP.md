# Roadmap

## Estado atual

O release 1.0.0 consolida uma pesquisa encerrada. O roadmap não contém
desenvolvimento de bot, otimização ou novas variações das hipóteses rejeitadas.

## Curto prazo — manutenção

- publicar código e documentação sem dados locais;
- habilitar private vulnerability reporting;
- executar auditoria externa de links, hashes e decisões;
- adicionar testes de integridade para ledgers e schemas;
- documentar processo de depósito externo de datasets.

## Médio prazo — reprodutibilidade

- empacotar manifests de dados em formato independente de plataforma;
- criar checks automatizados que não executem outcomes;
- registrar erratas sem sobrescrever artefatos;
- manter compatibilidade com atualizações de segurança do Freqtrade.

## Pesquisa futura condicionada

Uma nova geração só deve começar se existir dataset point-in-time, auditável e
economicamente indispensável para uma hipótese não reciclada. As classes
prioritárias são:

1. livro de ofertas sequenciado junto com trades;
2. labels on-chain versionados pela data de conhecimento;
3. fluxos oficiais/auditados de ETF com vintages;
4. superfície histórica executável de opções;
5. novo holdout prospectivo reservado antes do desenho.

## Fora do roadmap

- indicadores populares ou combinações arbitrárias;
- Hyperopt de hipóteses encerradas;
- alteração de custos para resgatar resultado;
- novos horizons/thresholds após outcome;
- montagem de ensemble com efeitos economicamente negativos;
- deploy operacional sem promoção científica.

## Critério para Discovery V4

Discovery V4 só pode existir se:

- o dado novo resolver um bloqueio causal específico;
- provenance, licença e custo forem aceitáveis;
- a pergunta puder ser falsificada com um experimento mínimo;
- o valor esperado da informação superar custo e complexidade;
- protocolo e critérios forem congelados antes dos outcomes.
