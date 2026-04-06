import pandas as pd

def detect_regime(row):
    if any(pd.isna([row["Close"], row["SMA_20"], row["SMA_50"]])):
        return "Neutral"

    if row["Close"] > row["SMA_20"] and row["SMA_20"] > row["SMA_50"]:
        return "Bullish"

    elif row["Close"] < row["SMA_20"] and row["SMA_20"] < row["SMA_50"]:
        return "Bearish"

    elif row["volatility"] > 0.02:
        return "Volatile"

    return "Neutral"


def apply_regime(df):
    df["regime"] = df.apply(detect_regime, axis=1)
    return df