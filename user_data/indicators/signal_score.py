from pandas import DataFrame

from indicators.momentum import add_momentum_score
from indicators.regime import add_regime_score
from indicators.trend import add_trend_score
from indicators.volume import add_volume_score
from indicators.volatility import add_volatility_score


SIGNAL_SCORE_COLUMNS = [
    "score_trend",
    "score_momentum",
    "score_volume",
    "score_volatility",
    "score_regime",
]


def add_signal_score(dataframe: DataFrame) -> DataFrame:
    dataframe = add_trend_score(dataframe)
    dataframe = add_momentum_score(dataframe)
    dataframe = add_volume_score(dataframe)
    dataframe = add_volatility_score(dataframe)
    dataframe = add_regime_score(dataframe)

    dataframe["signal_score"] = dataframe[SIGNAL_SCORE_COLUMNS].sum(axis=1)

    return dataframe
