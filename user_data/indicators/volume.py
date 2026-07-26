from pandas import DataFrame


def add_volume_score(dataframe: DataFrame) -> DataFrame:
    dataframe["score_volume"] = 0.0

    strong_volume = dataframe["volume"] > dataframe["volume_mean_20"] * 1.5
    weak_volume = dataframe["volume"] < dataframe["volume_mean_20"] * 0.8

    dataframe.loc[strong_volume, "score_volume"] = 1.0
    dataframe.loc[weak_volume, "score_volume"] = -1.0

    return dataframe
