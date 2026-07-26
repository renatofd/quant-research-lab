# Política de Segurança

## Versões suportadas

| Versão | Suporte |
|---|---|
| 1.x | Correções de segurança e integridade |
| snapshots anteriores | Somente documentação histórica |

## Como reportar

Não abra uma issue pública para:

- credenciais expostas;
- execução arbitrária de código;
- vulnerabilidades de dependências exploráveis;
- bypass de holdout ou adulteração silenciosa de resultados;
- arquivos com dados pessoais.

Use o recurso **Private vulnerability reporting** do GitHub no repositório
publicado. Inclua:

1. componente e versão;
2. impacto;
3. passos mínimos para reproduzir;
4. evidência sem segredos reais;
5. mitigação sugerida, se houver.

Se o canal privado ainda não estiver habilitado, não publique o detalhe:
solicite em uma issue genérica que os mantenedores ativem um canal de segurança.

## Prazo e divulgação

O projeto confirmará o recebimento quando houver manutenção ativa, avaliará
severidade e coordenará divulgação após a correção. Não há SLA comercial.

## Segredos

Nunca envie chaves de exchange, tokens, cookies, `.env`,
`user_data/config.json`, bancos ou dumps de sessão. Se um segredo entrar em um
commit:

1. revogue-o imediatamente;
2. gere outro;
3. remova-o do histórico;
4. documente o incidente sem republicar o valor.

## Escopo científico

Inconsistências que possam alterar uma decisão científica são tratadas como
problemas de integridade. Não “corrija” silenciosamente um relatório final:
preserve o artefato, registre uma errata e atualize o ledger.
