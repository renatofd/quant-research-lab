from pandas import DataFrame
import talib.abstract as ta


TREND = "TREND"
RANGE = "RANGE"
BREAKOUT = "BREAKOUT"
HIGH_VOLATILITY = "HIGH_VOLATILITY"


def add_market_regime(dataframe: DataFrame) -> DataFrame:
    dataframe["regime_adx"] = ta.ADX(dataframe, timeperiod=14)
    dataframe["regime_atr"] = ta.ATR(dataframe, timeperiod=14)
    dataframe["regime_ema_200_slope"] = dataframe["ema_200"].diff(5) / dataframe["ema_200"]
    dataframe["regime_volatility"] = dataframe["close"].pct_change().rolling(20).std()
    dataframe["regime_atr_mean"] = dataframe["regime_atr"].rolling(50).mean()
    dataframe["regime_volume_mean"] = dataframe["volume"].rolling(20).mean()

    high_volatility = (
        (dataframe["regime_atr"] > dataframe["regime_atr_mean"] * 1.8)
        | (dataframe["regime_volatility"] > dataframe["regime_volatility"].rolling(50).mean() * 1.8)
    )
    breakout = (
        (dataframe["regime_adx"] > 20)
        & (dataframe["volume"] > dataframe["regime_volume_mean"] * 1.8)
        & (dataframe["regime_atr"] > dataframe["regime_atr_mean"] * 1.2)
    )
    trend = (dataframe["regime_adx"] > 25) & (dataframe["regime_ema_200_slope"].abs() > 0.002)

    dataframe["market_regime"] = RANGE
    dataframe.loc[trend, "market_regime"] = TREND
    dataframe.loc[breakout, "market_regime"] = BREAKOUT
    dataframe.loc[high_volatility, "market_regime"] = HIGH_VOLATILITY

    return dataframe


def add_regime_score(dataframe: DataFrame) -> DataFrame:
    dataframe["score_regime"] = 0.0

    dataframe.loc[dataframe["market_regime"] == TREND, "score_regime"] = 1.0
    dataframe.loc[dataframe["market_regime"] == BREAKOUT, "score_regime"] = 0.5
    dataframe.loc[dataframe["market_regime"] == RANGE, "score_regime"] = 0.0
    dataframe.loc[dataframe["market_regime"] == HIGH_VOLATILITY, "score_regime"] = -1.0

    return dataframe
