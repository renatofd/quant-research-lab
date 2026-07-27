# Historical Project Brief

> **Archived context:** this document records the project's original
> bot-oriented scope. It is not the current project definition. For the current
> scientific status, read the [README](README.md), the
> [Scientific Summary](docs/SCIENTIFIC_SUMMARY.md), and the definitive
> [Scientific Ledger](user_data/discovery_v3/governance/SCIENTIFIC_LEDGER.md).

## Original Objective

The project initially aimed to build a trading bot on Freqtrade.

## Original Priorities

1. Clean source code.
2. Hyperopt compatibility.
3. Maintainability.
4. Modular strategies.
5. Channel-based position sizing.

## Original Working Rules

- Do not modify `docker-compose.yml`.
- Do not delete existing functionality.
- Explain changes before applying them.
- Run a backtest after each strategy change.
- Fix discovered defects.
- Keep code comments clear.

## Original Target Layout

```text
channels/
    manager.py
    martingale.py

strategies/
    ChannelStrategy.py

indicators/
    trend.py
    momentum.py
    volatility.py

hyperopt/
reports/
scripts/
```

## Why This Brief Was Superseded

The project later adopted falsification, Generalization, Reproducibility, and
economic validation as its primary goals. The required path became:

```text
Hypothesis → Evidence → Replication → Economic Edge → Bot
```

No Hypothesis completed that path, so operational bot development was closed.
This file remains available to document the project's evolution.
