# Lessons Learned

## Scientific Method

1. A high Profit Factor based on few trades is weak Evidence.
2. Local stability does not imply temporal stability.
3. In-sample robustness does not imply Generalization.
4. Statistical significance does not imply economic relevance.
5. Risk predictability does not imply directional return predictability.
6. An effect smaller than costs is not “almost a strategy.”
7. Concentration in one asset, block, or day can explain an aggregate result.
8. An effect in the opposite direction can falsify a Hypothesis and still add
   knowledge.
9. Experimental failure, documented dataset limitation, blockage, and
   Hypothesis rejection are different states.
10. A Holdout need not be opened when development Evidence already refutes the
    Hypothesis.

## Data

1. Candles can refute some effects but are weak Evidence for microstructure
   mechanisms.
2. OHLCV volume does not identify aggressors, institutions, or order flow.
3. AUM is not flow; a candle is not an order book; an isolated trade is not an
   execution path.
4. Provenance and knowledge timestamps are part of the dataset.
5. Missing values must not be filled merely to pass a gate.
6. A uniform, official limitation can be documented without pretending the
   dataset is complete.

## Engineering

1. Mechanical QA must remain separate from outcome calculation.
2. Isolated instruments reduce degrees of freedom.
3. JSON Research Artifacts and CSV matrices make Markdown reports auditable.
4. Recorded paths and hashes constrain later repository reorganization.
5. Logs and caches do not belong in a release; manifests and Scientific Ledgers
   do.
6. Standalone scientific CLIs can appear unused in static analysis and still be
   essential to Reproducibility.

## Research Management

1. Sunk cost does not justify continuation.
2. Expected information value should be assessed before implementation.
3. Stopping criteria protect the project from endless exploration.
4. Recording a rejection prevents more wasted work than hiding it.
5. The correct conclusion may be not to build the product originally imagined.
