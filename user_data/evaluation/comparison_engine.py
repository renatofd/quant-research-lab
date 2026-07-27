from pandas import DataFrame

from evaluation.metrics import (
    avoided_losing_trades,
    decision_accuracy,
    forward_return,
    missed_profitable_trades,
    return_difference,
    simulated_return,
)


def compare_shadow_decisions(dataframe: DataFrame, horizon: int = 12) -> dict:
    returns = forward_return(dataframe, horizon=horizon)
    real_return = simulated_return(dataframe, "shadow_real_decision", returns)
    engine_return = simulated_return(dataframe, "shadow_engine_decision", returns)

    return {
        "decision_engine_accuracy": decision_accuracy(dataframe),
        "avoided_losing_trades": avoided_losing_trades(dataframe, returns),
        "missed_profitable_trades": missed_profitable_trades(dataframe, returns),
        "real_simulated_return": real_return,
        "engine_simulated_return": engine_return,
        "return_difference": return_difference(real_return, engine_return),
        "horizon_candles": horizon,
    }
