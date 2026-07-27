from pandas import DataFrame


BUY = "BUY"
SELL = "SELL"
IGNORE = "IGNORE"

SCORE_COLUMNS = [
    "score_trend",
    "score_momentum",
    "score_volume",
    "score_volatility",
    "score_regime",
]
DECISION_THRESHOLD = 2.0


def _score_reason(column: str, value: float) -> dict:
    if value > 0:
        direction = "positive"
    elif value < 0:
        direction = "negative"
    else:
        direction = "neutral"

    return {
        "source": column.replace("score_", ""),
        "score": float(value),
        "direction": direction,
    }


def _decision_from_score(score: float) -> str:
    if score >= DECISION_THRESHOLD:
        return BUY
    if score <= -DECISION_THRESHOLD:
        return SELL
    return IGNORE


def add_passive_decision(dataframe: DataFrame) -> DataFrame:
    dataframe["passive_decision"] = dataframe["signal_score"].apply(_decision_from_score)
    dataframe["decision_confidence"] = (
        dataframe["signal_score"].abs() / len(SCORE_COLUMNS)
    ).clip(upper=1.0)
    dataframe["decision_reasons"] = dataframe[SCORE_COLUMNS].apply(
        lambda row: [_score_reason(column, row[column]) for column in SCORE_COLUMNS],
        axis=1,
    )

    return dataframe
