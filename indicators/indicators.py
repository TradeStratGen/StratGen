"""
indicators/indicators.py — v2
Adds SMA, RSI, volatility, returns.
ATR and MACD are added by regime/regime.py to avoid duplication.
"""
import pandas as pd
import numpy as np


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    close = df["Close"]

    # Moving averages
    df["SMA_20"] = close.rolling(20).mean()
    df["SMA_50"] = close.rolling(50).mean()

    # Daily returns and rolling volatility
    df["returns"]    = close.pct_change()
    df["volatility"] = df["returns"].rolling(20).std()

    # RSI (14-day)
    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rs    = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))

    # RSI(2) — 2-day RSI fires much more selectively, better for entries
    delta2 = close.diff()
    gain2  = delta2.clip(lower=0).rolling(2).mean()
    loss2  = (-delta2.clip(upper=0)).rolling(2).mean()
    rs2    = gain2 / loss2
    df["RSI2"] = 100 - (100 / (1 + rs2))

    df.dropna(inplace=True)
    return df