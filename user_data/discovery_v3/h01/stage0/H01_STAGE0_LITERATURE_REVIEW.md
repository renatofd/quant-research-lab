# H01 — Liquidation Cascades: Stage 0 Literature Review

Decision: **PASS TO STAGE 1**  
Decision date: 2026-07-24  
No code was written and no market data was downloaded in this stage.

## Economic mechanism

Leveraged perpetual-futures positions are forcibly closed when maintenance
margin is breached. Those closures are urgent, largely price-insensitive orders.
When forced flow exceeds immediately available depth, it moves the traded price.
Because the mark price used for liquidation follows the market, the first price
move can breach other accounts' margins, creating a positive feedback loop:

`price shock → forced orders → market impact → new margin breaches → more forced orders`

Arbitrage and shared risk constraints can transmit the derivatives dislocation
to spot and to other venues. Once forced inventory is exhausted, temporary price
impact may partly reverse. The economically relevant question is therefore not
whether liquidation accompanies volatility, but whether actual forced flow
contains incremental, time-ordered information about a subsequent, executable
price response after costs.

## Why a profit opportunity could exist

The proposed source of predictability is a mechanical margin constraint, not a
technical indicator. Potential predictability can arise because:

- liquidations must execute promptly and cannot wait for a better price;
- exchange-specific margin engines and fragmented liquidity make adjustment
  non-instantaneous across venues;
- capacity limits of market makers can create temporary continuation while the
  cascade is active;
- after forced flow ends, inventory rebalancing can reverse temporary impact.

This does not establish profitability. The same mechanism raises slippage,
latency, adverse-selection and tail-risk costs, so an apparent return effect may
be non-executable.

## Supporting literature

1. Cheng, Liu and Wang, *Liquidation, Leverage and Optimal Margin in Bitcoin
   Futures Markets* (2021), documents substantial forced liquidations and
   extreme leverage in BitMEX data and shows that conventional return assumptions
   understate liquidation risk.  
   <https://arxiv.org/abs/2102.04591>
2. Lim, *The Anatomy of a Crypto Cascade: Minute-Level Evidence from the
   October 2025 Crash* (2026), reports futures-led price discovery and reflexive
   mark-price/liquidation dynamics across Binance and Bybit for BTC, ETH and SOL.
   This is a recent working paper and must not be treated as independent
   confirmation.  
   <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6579278>
3. Lim, *Hidden Liquidity, Displayed Depth, and Execution Risk During a Bitcoin
   Perpetual Futures Liquidation Cascade* (2026), uses Bybit trade and L50
   order-book data to show that displayed depth can be misleading during a
   cascade. This supports the execution-risk caveat rather than profitability.
4. Alexander, Deng, Zou and Zurek, *Hedging with Automatic Liquidation and
   Leverage Selection on Bitcoin Futures* (European Journal of Operational
   Research, 2023), models automatic liquidation as a material feature of
   leveraged bitcoin-futures risk.  
   <https://doi.org/10.1016/j.ejor.2022.10.036>
5. Bank of Canada, *Liquidation Mechanisms and Price Impacts in DeFi* (2025),
   provides evidence that mechanically triggered liquidation can have price
   impact in a distinct crypto-market structure.  
   <https://www.bankofcanada.ca/2025/07/staff-working-paper-2025-22/>

## Markets in which the mechanism has been observed

- BitMEX bitcoin futures;
- Binance and Bybit BTC, ETH and SOL perpetual futures;
- decentralized lending/liquidation markets.

The evidence spans venues but is concentrated in a small number of stress
episodes. It supports the mechanism, not a stable tradable edge.

## Stage 0 falsification assessment

The mechanism is economically coherent, directly tied to binding leverage
constraints, and observed in more than one market structure. It therefore
survives the literature gate.

Stage 0 does **not** confirm any prediction horizon, direction, threshold,
tradability or strategy. H01 may advance only if Stage 1 finds actual historical
liquidation events with reliable timestamps and provenance. OHLCV volatility,
wick size or volume alone are not acceptable liquidation proxies.

## Scientific-cost decision

- Expected information: high, because actual forced flow can distinguish a
  mechanical market event from generic price/volume association.
- Main false-positive risk: event selection after observing returns and
  mistaking contemporaneous crash intensity for forward prediction.
- Main feasibility risk: incomplete public liquidation histories and inadequate
  order-book data.
- Next action: inventory official event-level liquidation, trade, price,
  open-interest and depth data; do not acquire data until the inventory is
  complete.
