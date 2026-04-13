"""
regime/regime.py  — v2
Improvements over v1:
  - Volatility threshold is PERCENTILE-based (not hardcoded 0.02)
  - ATR added as a secondary volatility signal
  - MACD added as trend-strength confirmation
  - Regime labels are more accurate as a result
"""
import pandas as pd
import numpy as np
from config import VOLATILITY_PERCENTILE


def add_regime_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds ATR and MACD to df in-place before regime detection.
    Called by apply_regime() — you don't need to call this separately.
    """
    # ── ATR (Average True Range) — measures volatility in price terms ─────
    high  = df["High"]
    low   = df["Low"]
    close = df["Close"]

    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low  - close.shift(1)).abs(),
    ], axis=1).max(axis=1)

    df["ATR"]    = tr.rolling(14).mean()
    df["ATR_pct"] = df["ATR"] / df["Close"]   # ATR as % of price (normalised)

    # ── MACD — measures trend momentum ───────────────────────────────────
    ema12        = close.ewm(span=12, adjust=False).mean()
    ema26        = close.ewm(span=26, adjust=False).mean()
    df["MACD"]   = ema12 - ema26
    df["MACD_signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_hist"]   = df["MACD"] - df["MACD_signal"]

    return df


def compute_volatility_threshold(df: pd.DataFrame) -> float:
    """
    Returns the PERCENTILE-based volatility threshold.
    Anything above this is 'high volatility'.
    Much better than a hardcoded 0.02 which never adapts to market conditions.
    """
    return df["volatility"].quantile(VOLATILITY_PERCENTILE / 100)


def detect_regime(row, vol_threshold: float) -> str:
    """
    Classify a single row into: Bullish, Bearish, Volatile, Neutral.

    Logic:
      Bullish  = price above both MAs AND MACD histogram positive (uptrend confirmed)
      Bearish  = price below both MAs AND MACD histogram negative (downtrend confirmed)
      Volatile = neither trend condition, but volatility is in top 25%
      Neutral  = everything else
    """
    # Skip rows with missing indicators
    needed = ["Close", "SMA_20", "SMA_50", "volatility", "MACD_hist"]
    if any(pd.isna(row.get(c, float("nan"))) for c in needed):
        return "Neutral"

    price    = row["Close"]
    sma20    = row["SMA_20"]
    sma50    = row["SMA_50"]
    macd_h   = row["MACD_hist"]
    vol      = row["volatility"]

    price_bullish = price > sma20 and sma20 > sma50
    price_bearish = price < sma20 and sma20 < sma50
    macd_positive = macd_h > 0
    macd_negative = macd_h < 0
    high_vol      = vol > vol_threshold

    if price_bullish and macd_positive:
        return "Bullish"
    elif price_bearish and macd_negative:
        return "Bearish"
    elif high_vol:
        return "Volatile"
    else:
        return "Neutral"


def apply_regime(df: pd.DataFrame) -> pd.DataFrame:
    """
    Main entry point. Adds ATR + MACD, then classifies each row.
    Drops rows where indicators aren't ready yet (first ~26 bars).
    """
    df = add_regime_indicators(df)
    vol_threshold = compute_volatility_threshold(df)

    df["regime"] = df.apply(
        lambda row: detect_regime(row, vol_threshold), axis=1
    )

    # Report regime distribution
    dist = df["regime"].value_counts()
    print("[Regime] Distribution:")
    for r, count in dist.items():
        pct = count / len(df) * 100
        print(f"         {r:10s}  {count:4d} rows  ({pct:.0f}%)")

    return df