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
from utils.eval_utils import INDICATOR_NAMESPACE_COLUMNS


REGIME_VOL_WINDOW = 75


def add_regime_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds ATR and MACD to df in-place before regime detection.
    Called by apply_regime() — you don't need to call this separately.
    """
    # ── ATR (Average True Range) — measures volatility in price terms ─────
    required_ohlc = ["High", "Low", "Close"]
    missing_ohlc = [c for c in required_ohlc if c not in df.columns]
    if missing_ohlc:
        raise ValueError(f"[regime] Missing OHLC columns required for ATR_pct: {', '.join(missing_ohlc)}")

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

    # Explicit fallback compute path if ATR_pct missing for any reason
    if "ATR_pct" not in df.columns:
        atr = tr.rolling(14).mean()
        df["ATR_pct"] = atr / close

    # ── MACD — measures trend momentum ───────────────────────────────────
    ema12        = close.ewm(span=12, adjust=False).mean()
    ema26        = close.ewm(span=26, adjust=False).mean()
    df["MACD"]   = ema12 - ema26
    df["MACD_signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_hist"]   = df["MACD"] - df["MACD_signal"]

    return df


def add_causal_volatility_thresholds(df: pd.DataFrame, window: int = REGIME_VOL_WINDOW) -> pd.DataFrame:
    """
    Adds history-only volatility features to remove look-ahead bias.

    For each row t:
      - rolling_vol[t] is the trailing mean volatility over the last `window` bars.
      - rolling_vol_thresh[t] is the trailing quantile computed from *past* rolling_vol values
        (via shift(1)), so today's threshold never uses today's or future data.
    """
    q = VOLATILITY_PERCENTILE / 100.0

    df["rolling_vol"] = (
        df["volatility"]
        .rolling(window=window, min_periods=window)
        .mean()
    )

    df["rolling_vol_thresh"] = (
        df["rolling_vol"]
        .shift(1)
        .rolling(window=window, min_periods=window)
        .quantile(q)
    )
    return df


def detect_regime(row) -> str:
    """
    Classify a single row into: Bullish, Bearish, Volatile, Neutral.

    Logic:
      Bullish  = price above both MAs AND MACD histogram positive (uptrend confirmed)
      Bearish  = price below both MAs AND MACD histogram negative (downtrend confirmed)
      Volatile = neither trend condition, but rolling_vol is above its causal threshold
      Neutral  = everything else
    """
    needed = ["Close", "SMA_20", "SMA_50", "MACD_hist"]
    if any(pd.isna(row.get(c, float("nan"))) for c in needed):
        return "Neutral"

    price = row["Close"]
    sma20 = row["SMA_20"]
    sma50 = row["SMA_50"]
    macd_h = row["MACD_hist"]
    rolling_vol = row.get("rolling_vol", np.nan)
    rolling_thr = row.get("rolling_vol_thresh", np.nan)

    price_bullish = price > sma20 and sma20 > sma50
    price_bearish = price < sma20 and sma20 < sma50
    macd_positive = macd_h > 0
    macd_negative = macd_h < 0
    high_vol = pd.notna(rolling_vol) and pd.notna(rolling_thr) and (rolling_vol > rolling_thr)

    if price_bullish and macd_positive:
        return "Bullish"
    if price_bearish and macd_negative:
        return "Bearish"
    if high_vol:
        return "Volatile"
    return "Neutral"


def apply_regime(df: pd.DataFrame) -> pd.DataFrame:
    """
    Main entry point. Adds ATR + MACD, then classifies each row.
    Drops rows where indicators aren't ready yet (first ~26 bars).
    """
    df = add_regime_indicators(df)
    df = add_causal_volatility_thresholds(df, window=REGIME_VOL_WINDOW)

    df["regime"] = df.apply(
        detect_regime, axis=1
    )

    # Strict: strategies must never evaluate rows with missing required indicators
    df = df.dropna(subset=list(INDICATOR_NAMESPACE_COLUMNS)).copy()
    if df.empty:
        raise ValueError("[regime] No rows left after required-indicator filtering (includes ATR_pct)")

    # Report regime distribution
    dist = df["regime"].value_counts()
    print("[Regime] Distribution:")
    for r, count in dist.items():
        pct = count / len(df) * 100
        print(f"         {r:10s}  {count:4d} rows  ({pct:.0f}%)")

    return df