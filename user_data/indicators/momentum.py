from pandas import DataFrame
import talib.abstract as ta


def add_momentum_indicators(dataframe: DataFrame) -> DataFrame:
    dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

    return dataframe


def add_momentum_score(dataframe: DataFrame) -> DataFrame:
    dataframe["score_momentum"] = 0.0

    dataframe.loc[(dataframe["rsi"] >= 45) & (dataframe["rsi"] <= 60), "score_momentum"] = 1.0
    dataframe.loc[(dataframe["rsi"] < 30) | (dataframe["rsi"] > 75), "score_momentum"] = -1.0

    return dataframe
