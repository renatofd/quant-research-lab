\# Projeto Crypto Bot



\## Objetivo



Desenvolver um robô de trade usando Freqtrade.



\## Prioridades



1\. Código limpo.

2\. Compatível com Hyperopt.

3\. Fácil de manter.

4\. Estratégias modulares.

5\. Martingale por canal.



\## Regras



\- Nunca alterar docker-compose.

\- Nunca apagar funcionalidades existentes.

\- Sempre explicar alterações antes de aplicá-las.

\- Sempre executar backtest após mudanças.

\- Sempre corrigir erros encontrados.

\- Manter comentários claros no código.



\## Arquitetura desejada



channels/

&#x20;   manager.py

&#x20;   martingale.py



strategies/

&#x20;   ChannelStrategy.py



indicators/

&#x20;   trend.py

&#x20;   momentum.py

&#x20;   volatility.py



hyperopt/



reports/



scripts/

