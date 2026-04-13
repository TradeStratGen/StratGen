"""
llm/prompts.py — v5
New: ATR_pct, MACD_hist, RSI2 in variables + snapshot.
New: "reasoning" field in JSON output for explainability (Q5).
"""

REGIME_CONFIG = {
    "Bullish": {
        "context": (
            "Uptrend confirmed: Close > SMA_20 > SMA_50, MACD histogram positive. "
            "Enter on PULLBACKS where RSI2 (2-day RSI) dips below 25 and MACD stays positive. "
            "RSI2 fires rarely — much more selective than 14-day RSI. "
            "Exit when trend breaks (Close < SMA_50) or RSI overbought above 75."
        ),
        "entry": "Close > SMA_20 and RSI2 < 25 and MACD_hist > 0",
        "exit":  "Close < SMA_50 or RSI > 75",
        "sl": 0.025, "tp": 0.07,
        "reasoning_example": "Buying pullbacks in confirmed uptrend; RSI2 below 25 ensures oversold entry with MACD momentum",
    },
    "Bearish": {
        "context": (
            "Downtrend: Close < SMA_20 < SMA_50. Capital preservation mode. "
            "CRITICAL: RSI2 < 8 alone fires 38% of bearish rows because RSI2 stays low in downtrends. "
            "You MUST include ATR_pct < 0.016 to filter out panic-selling days. "
            "Only enter when oversold AND volatility is calm. This fires ~5-10 times per year."
        ),
        "entry": "RSI2 < 8 and ATR_pct < 0.016",
        "exit":  "RSI2 > 55 or Close > SMA_20",
        "sl": 0.015, "tp": 0.03,
        "reasoning_example": "Calm oversold reversal in downtrend — ATR filter excludes panic-selling days",
    },
    "Volatile": {
        "context": (
            "High volatility, no trend. ATR_pct elevated but manageable. "
            "RSI2 below 15 = extreme oversold mean-reversion signal. "
            "Keep ATR_pct below 0.025 to avoid entering during dangerous wide-swing days. "
            "Target: condition fires 15-25% of volatile rows. Quick exit on RSI2 recovery."
        ),
        "entry": "RSI2 < 15 and ATR_pct < 0.025",
        "exit":  "RSI2 > 68 or Close < SMA_50",
        "sl": 0.012, "tp": 0.025,
        "reasoning_example": "Mean reversion in choppy market; RSI2 below 15 with ATR cap for risk management",
    },
    "Neutral": {
        "context": (
            "No clear trend direction. Price oscillates near moving averages. "
            "IMPORTANT: Do NOT require SMA_20 > SMA_50 — in Neutral regime this is rarely true. "
            "Instead use: Close near or above SMA_20 (within 1%), MACD histogram not deeply negative, "
            "and RSI2 in middle range 25-65 (not at extremes). "
            "This combination fires 10-15% of neutral rows — exactly what we want."
        ),
        "entry": "Close > SMA_20 * 0.99 and MACD_hist > -100 and RSI2 > 25 and RSI2 < 65",
        "exit":  "Close < SMA_20 * 0.98 or RSI2 > 75 or RSI > 72",
        "sl": 0.018, "tp": 0.04,
        "reasoning_example": "Entry when price near SMA_20 with MACD not deeply negative and RSI2 in middle range",
    },
}

_DEFAULT = REGIME_CONFIG["Neutral"]


def build_prompt(regime: str, row=None) -> str:
    cfg      = REGIME_CONFIG.get(regime, _DEFAULT)
    snapshot = _format_snapshot(row) if row is not None else ""

    return f"""You are a systematic quantitative trader for NIFTY 50.

REGIME: {regime.upper()}
CONTEXT: {cfg["context"]}
{snapshot}
AVAILABLE VARIABLES — use ONLY these exact names:
  Close      current closing price
  SMA_20     20-day moving average
  SMA_50     50-day moving average
  RSI        14-day RSI (0-100)
  RSI2       2-day RSI, more selective (0-100)
  MACD_hist  MACD histogram: positive=bullish momentum, negative=bearish
  ATR_pct    Average True Range as fraction of price (0.012 = 1.2% daily range)

STRICT OUTPUT RULES:
1. Output ONLY a JSON object. No markdown, no text before or after.
2. Conditions must be valid Python boolean expressions.
3. NEVER write literal False or True.
4. stop_loss and take_profit are decimal fractions like 0.02 meaning 2%.
5. reasoning = ONE sentence explaining why this entry fits the regime.

EXAMPLE for {regime.upper()}:
{{"entry_condition": "{cfg["entry"]}", "exit_condition": "{cfg["exit"]}", "stop_loss": {cfg["sl"]}, "take_profit": {cfg["tp"]}, "reasoning": "{cfg["reasoning_example"]}"}}

Output the JSON for {regime.upper()} now. You may vary RSI/RSI2 thresholds by up to ±5:"""


def _format_snapshot(row) -> str:
    fields = [
        ("Close",     "₹{:.2f}"),
        ("SMA_20",    "₹{:.2f}"),
        ("SMA_50",    "₹{:.2f}"),
        ("RSI",       "{:.1f}"),
        ("RSI2",      "{:.1f}"),
        ("MACD_hist", "{:.3f}"),
        ("ATR_pct",   "{:.4f}"),
    ]
    lines = ["CURRENT VALUES:"]
    for col, fmt in fields:
        try:
            lines.append(f"  {col:<12} = {fmt.format(float(row[col]))}")
        except Exception:
            pass
    return "\n".join(lines) + "\n"