# Discovery V2 — Final Executive Report

## Final recommendation: DO NOT PROMOTE

Discovery V2 did not find a robust economic advantage that justifies an operational bot.

H01 tested the clearest directly monetizable mechanism in the acquired derivatives data: positive-funding/positive-basis cash-and-carry. It failed in development and sealed holdout; every one of 729 matched-day sensitivity deletions preserved rejection, proving that the official missing day did not drive the result.

H02 added official point-in-time open-interest/taker metrics and tested whether long crowding predicts deleveraging. It also failed with adequate samples. Net short returns were negative in development and holdout, and OI/flow produced negative incremental value beyond funding alone.

The H02 QA history exposed useful methodological lessons: publication timestamps are asynchronous event times, coverage gates belong to the frozen scientific window rather than each daily object, and only prerequired fields may determine admissibility. All failed QA interpretations remain preserved; the final contract uses native backward as-of joins and no imputation.

No remaining catalog hypothesis is executable with the acquired data. They require genuinely new families, not OHLCV proxies: reconstructible order books/trades, liquidation events, options surfaces, point-in-time ETF/macro/on-chain data, CME, or synchronized multi-venue/CEX–DEX records.

The research is therefore closed under the approved stopping rule. A bot remains prohibited.
