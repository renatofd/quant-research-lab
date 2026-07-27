from pandas import DataFrame


BUY = "BUY"
SELL = "SELL"
IGNORE = "IGNORE"


def add_shadow_decisions(dataframe: DataFrame) -> DataFrame:
    dataframe["shadow_real_decision"] = IGNORE

    if "enter_long" in dataframe:
        dataframe.loc[dataframe["enter_long"] == 1, "shadow_real_decision"] = BUY

    if "exit_long" in dataframe:
        dataframe.loc[dataframe["exit_long"] == 1, "shadow_real_decision"] = SELL

    dataframe["shadow_engine_decision"] = dataframe.get("passive_decision", IGNORE)
    dataframe["shadow_confidence"] = dataframe.get("decision_confidence", 0.0)
    dataframe["shadow_regime"] = dataframe.get("market_regime", "")
    dataframe["shadow_signal_score"] = dataframe.get("signal_score", 0.0)

    return dataframe
