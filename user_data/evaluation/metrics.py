from pandas import DataFrame, Series


BUY = "BUY"


def forward_return(dataframe: DataFrame, horizon: int = 12) -> Series:
    return dataframe["close"].shift(-horizon) / dataframe["close"] - 1


def decision_accuracy(dataframe: DataFrame) -> float:
    comparable = dataframe["shadow_real_decision"].notna() & dataframe["shadow_engine_decision"].notna()
    if comparable.sum() == 0:
        return 0.0

    return float(
        (
            dataframe.loc[comparable, "shadow_real_decision"]
            == dataframe.loc[comparable, "shadow_engine_decision"]
        ).mean()
    )


def avoided_losing_trades(dataframe: DataFrame, returns: Series) -> int:
    avoided = (
        (dataframe["shadow_real_decision"] == BUY)
        & (dataframe["shadow_engine_decision"] != BUY)
        & (returns < 0)
    )

    return int(avoided.sum())


def missed_profitable_trades(dataframe: DataFrame, returns: Series) -> int:
    missed = (
        (dataframe["shadow_real_decision"] == BUY)
        & (dataframe["shadow_engine_decision"] != BUY)
        & (returns > 0)
    )

    return int(missed.sum())


def simulated_return(dataframe: DataFrame, decision_column: str, returns: Series) -> float:
    entries = dataframe[decision_column] == BUY
    return float(returns.loc[entries].fillna(0.0).sum())


def return_difference(real_return: float, engine_return: float) -> float:
    return float(engine_return - real_return)
