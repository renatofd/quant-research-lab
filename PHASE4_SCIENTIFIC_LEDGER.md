# PHASE4 SCIENTIFIC LEDGER

## Estado definitivo

- Fase: 4 — Economic Hypothesis Discovery
- Status: **ENCERRADA**
- Hipóteses ativas: **nenhuma**
- Bot operacional justificado: **não**
- Conclusão vinculante: **Não existe evidência científica suficiente para justificar um bot operacional.**

Este ledger substitui o ledger corrente da Fase 4 para fins decisórios. O arquivo histórico `user_data/discovery/reports/HYPOTHESIS_LEDGER_FINAL.md` permanece intocado.

## Hipóteses OHLCV A01–A11

| ID | Hipótese | Classificação final | Decisão/evidência central | Reabertura | Fontes principais |
|---|---|---|---|---|---|
| A01 | Liderança BTC e transmissão defasada | Rejeitada | `BTC LEAD-LAG HYPOTHESIS REJECTED IN PRIMARY SCOPE`. Houve beta descritivo, mas falharam utilidade econômica líquida, hit rate e especificidade contra pseudo-líderes/shift. | Proibida nos dados e desenho consumidos. | `PHASE4_FIRST_EXPERIMENT.md`; `user_data/lab/btc_leadership_report.{md,json}` |
| A02 | Persistência de volatilidade como previsão de risco | Rejeitada | `VOLATILITY PERSISTENCE HYPOTHESIS REJECTED IN PRIMARY SCOPE`. Efeito preditivo não satisfez o gate de concentração. | Proibida como variação do mesmo desenho nos dados consumidos. | `PHASE4_A02_PROTOCOL.md`; `user_data/lab/ph4_a02_volatility_persistence_report.{md,json}` |
| A03 | Assimetria de volatilidade e jumps assinados | Rejeitada | `SIGNED VOLATILITY ASYMMETRY HYPOTHESIS REJECTED IN PRIMARY SCOPE`. O incremento de MSE, Holm e concentração falharam. | Proibida no escopo atual. | `PHASE4_A03_PROTOCOL.md`; `user_data/lab/ph4_a03_signed_volatility_report.{md,json}` |
| A04 | Co-jumps, contágio e propagação cross-asset | Inconclusiva, encerrada pelo programa | `INCONCLUSIVE CO-JUMP PROPAGATION AUDIT`. A amostra/identificação não sustentou o teste; não houve unidades elegíveis suficientes. | Somente com dados completamente novos e autorização humana separada. | `PHASE4_A04_PROTOCOL.md`; `user_data/lab/ph4_a04_cojump_propagation_report.{md,json}` |
| A05 | Dispersão cross-sectional como estado de mercado | Rejeitada | `CROSS-SECTIONAL DISPERSION HYPOTHESIS REJECTED IN PRIMARY SCOPE`. A concentração excedeu o limite pré-registrado. | Proibida no escopo atual. | `PHASE4_A05_PROTOCOL.md`; `user_data/lab/ph4_a05_dispersion_risk_report.{md,json}` |
| A06 | Reversão cross-sectional em horizonte distinto | Encerrada/deferida | Não recebeu campanha independente válida: identificação inadequada e sobreposição material com mean reversion/cross-sectional já rejeitados. | Apenas hipótese econômica realmente nova, dados novos e autorização humana; não por mudança de horizonte. | `PHASE4_RESEARCH_ROADMAP.md`; gates finais da Fase 3 |
| A07 | Compressão de volatilidade seguida de expansão | Rejeitada | `VOLATILITY COMPRESSION HYPOTHESIS REJECTED IN PRIMARY SCOPE`. Beta, Holm e gates centrais falharam. | Proibida no escopo atual. | `PHASE4_A07_PROTOCOL.md`; `user_data/lab/ph4_a07_volatility_compression_report.{md,json}` |
| A08 | Proxy OHLCV de iliquidez/impacto | Rejeitada | `OHLCV ILLIQUIDITY-PROXY HYPOTHESIS REJECTED IN PRIMARY SCOPE`. Beta, ganho mínimo, Holm e replicação falharam com integridade válida. | Encerrada definitivamente para OHLCV. | `PH4_A08_PROTOCOL.md`; `user_data/discovery/reports/ph4_a08_illiquidity_proxy_report.{md,json}` |
| A09 | Persistência de volume como proxy de atividade/risco | Rejeitada | `OHLCV VOLUME-PERSISTENCE HYPOTHESIS REJECTED IN PRIMARY SCOPE`. P1 melhorou MSE 14,0669% e MAE 5,4506%, mas concentrou 74,2851% no bloco 1, 69,1177% em 2025-10-10 e 32,1426% em AVAX. P2 melhorou apenas 0,6836%/0,6634%. | Encerrada definitivamente no escopo OHLCV. | `PH4_A09_PROTOCOL.md`; `user_data/discovery/reports/ph4_a09_volume_persistence_report.{md,json}` |
| A10 | Falsos rompimentos/liquidity grabs com candles | Encerrada/deferida | Não é identificável de modo defensável apenas com candles e sobrepõe famílias de breakout já rejeitadas. | Somente com dados de microestrutura materialmente novos e autorização humana. | `PHASE4_RESEARCH_ROADMAP.md`; gates finais da Fase 3 |
| A11 | Sazonalidade de calendário/sessão/weekend | Rejeitada | `OHLCV CALENDAR-SEASONALITY HYPOTHESIS REJECTED IN PRIMARY SCOPE`. Nos 11 contrastes, retornos líquidos médios/medianos a 0,30% foram negativos; nenhum ganho MSE/MAE atingiu 5% ou replicou em 7/10 pares e 4/5 blocos. | Encerrada definitivamente no escopo testado. | `PH4_A11_PROTOCOL.md`; `user_data/discovery/reports/ph4_a11_calendar_seasonality_report.{md,json}` |

## Hipóteses B12–B26

Nenhuma foi testada. Todas estão **bloqueadas por dados indisponíveis** no laboratório atual e não constituem próxima etapa automática.

| ID | Hipótese | Status | Dado ausente determinante |
|---|---|---|---|
| B12 | Funding/basis como carry e crowding | Bloqueada por dados | Funding e basis de derivativos |
| B13 | Open interest + funding | Bloqueada por dados | Open interest e funding |
| B14 | Cascatas de liquidação | Bloqueada por dados | Eventos/fluxos de liquidação |
| B15 | Liderança spot versus perp | Bloqueada por dados | Séries spot e perp sincronizadas |
| B16 | Order flow agressor/passivo | Bloqueada por dados | Trades com lado agressor |
| B17 | Livro, profundidade e retirada de liquidez | Bloqueada por dados | Livro de ofertas histórico |
| B18 | Fragmentação entre exchanges | Bloqueada por dados | Dados multi-exchange sincronizados |
| B19 | Dispersão de funding/carry | Bloqueada por dados | Funding/basis cross-sectional |
| B20 | Fluxos de stablecoins para exchanges | Bloqueada por dados | Fluxos de stablecoins/exchanges |
| B21 | Fluxos on-chain de exchanges | Bloqueada por dados | Dados on-chain rotulados |
| B22 | Surpresas macroeconômicas | Bloqueada por dados | Calendário e surpresa macro point-in-time |
| B23 | Prêmios de variance/jump/skew em opções | Bloqueada por dados | Superfícies/opções históricas |
| B24 | Unlocks e vesting | Bloqueada por dados | Eventos de oferta point-in-time |
| B25 | Listings, delistings e eventos regulatórios | Bloqueada por dados | Base de eventos curada point-in-time |
| B26 | Atenção e sentimento | Bloqueada por dados | Dados de atenção/sentimento com proveniência |

## Famílias anteriores

Trend, score, Pullback, N-of-M, ensembles e a MeanReversion implementada permanecem encerradas. Nenhum resultado da Fase 4 reabre essas arquiteturas.

## Regra de encerramento

Não há hipótese ativa. Reabertura exige simultaneamente dados materialmente novos, hipótese econômica nova e pré-registrada, holdout prospectivo e autorização humana separada. Retuning, novos indicadores OHLCV ou renomeação de famílias rejeitadas não constituem reabertura válida.
