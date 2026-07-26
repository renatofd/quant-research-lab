from pandas import DataFrame
import talib.abstract as ta


def _unique_periods(periods, alias_period: int) -> list[int]:
    return list(dict.fromkeys([*(int(period) for period in periods), int(alias_period)]))


def add_trend_indicators(
    dataframe: DataFrame,
    fast_periods,
    slow_periods,
    trend_periods,
    fast_alias_period: int = 9,
    slow_alias_period: int = 21,
    trend_alias_period: int = 200,
) -> DataFrame:
    for period in _unique_periods(fast_periods, fast_alias_period):
        dataframe[f"ema_fast_{period}"] = ta.EMA(dataframe, timeperiod=period)

    for period in _unique_periods(slow_periods, slow_alias_period):
        dataframe[f"ema_slow_{period}"] = ta.EMA(dataframe, timeperiod=period)

    for period in _unique_periods(trend_periods, trend_alias_period):
        dataframe[f"ema_trend_{period}"] = ta.EMA(dataframe, timeperiod=period)

    dataframe["ema_9"] = dataframe[f"ema_fast_{fast_alias_period}"]
    dataframe["ema_21"] = dataframe[f"ema_slow_{slow_alias_period}"]
    dataframe["ema_200"] = dataframe[f"ema_trend_{trend_alias_period}"]

    return dataframe


def add_trend_score(dataframe: DataFrame) -> DataFrame:
    dataframe["score_trend"] = 0.0

    uptrend = (
        (dataframe["ema_9"] > dataframe["ema_21"])
        & (dataframe["ema_21"] > dataframe["ema_200"])
        & (dataframe["close"] > dataframe["ema_200"])
    )
    downtrend = (
        (dataframe["ema_9"] < dataframe["ema_21"])
        & (dataframe["ema_21"] < dataframe["ema_200"])
        & (dataframe["close"] < dataframe["ema_200"])
    )

    dataframe.loc[uptrend, "score_trend"] = 1.0
    dataframe.loc[downtrend, "score_trend"] = -1.0

    return dataframe
