# Discovery V3 — Recomendações objetivas

1. Não desenvolver bot com a evidência atual.
2. Não reabrir OHLCV, trend, relative strength, funding thresholds, basis horizons
   ou cross-exchange lags por otimização.
3. Uma futura geração só se justifica após obter **um** destes contratos:
   - book+trades sequenciados e point-in-time para H05/H09;
   - labels on-chain versionados por data de conhecimento para H06;
   - ETF flows com vintages e release timestamps para H07;
   - superfície de opções bid/ask/OI point-in-time para H08.
4. Preferir coleta prospectiva oficial a reconstruções retrospectivas sem relógio
   informacional.
5. Antes de novo gasto, exigir orçamento, tamanho amostral, custo de execução e regra
   de parada. Não coletar “porque talvez seja útil”.
