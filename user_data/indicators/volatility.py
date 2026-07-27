from pandas import DataFrame


def add_volatility_indicators(dataframe: DataFrame) -> DataFrame:
    dataframe["volume_mean_20"] = dataframe["volume"].rolling(20).mean()

    return dataframe


def add_volatility_score(dataframe: DataFrame) -> DataFrame:
    dataframe["score_volatility"] = 0.0

    rolling_volatility = dataframe["close"].pct_change().rolling(20).std()
    volatility_mean = rolling_volatility.rolling(50).mean()

    dataframe.loc[rolling_volatility <= volatility_mean * 1.2, "score_volatility"] = 1.0
    dataframe.loc[rolling_volatility > volatility_mean * 1.8, "score_volatility"] = -1.0

    return dataframe
