"""
llm/parser.py — v7
Fixed REGIME_FALLBACKS: Bearish no longer uses MACD_hist (always negative
in downtrends → fires too often). Uses RSI2 only for rarity.
"""
import json, re

REQUIRED_FIELDS  = ["entry_condition", "exit_condition", "stop_loss", "take_profit"]
ALLOWED_VARS     = {"Close", "SMA_20", "SMA_50", "RSI", "RSI2", "MACD_hist", "ATR_pct", "volatility"}
FORBIDDEN_TOKENS = ["import", "__", "exec", "eval", "open", "os.", "sys."]

# These fallbacks are used when LLM output fails validation.
# Each is calibrated to fire 5-15% of its regime's rows:
#   Bullish:  RSI2<20 in uptrend fires ~10-15% (pullbacks)
#   Bearish:  RSI2<8 in downtrend fires ~5-8% (deep oversold only)
#   Volatile: RSI2<15 with ATR filter fires ~5-10%
#   Neutral:  MACD>0 + RSI2 range fires ~10-15%
REGIME_FALLBACKS = {
    "Bullish":  {
        "entry_condition": "Close > SMA_20 and RSI2 < 20 and MACD_hist > 0",
        "exit_condition":  "Close < SMA_50 or RSI > 75",
        "stop_loss": 0.025, "take_profit": 0.07,
        "reasoning": "Fallback: oversold pullback entry in confirmed uptrend",
    },
    "Bearish":  {
        # ATR_pct < 0.016 = daily range < 1.6% of price
        # Filters out panic-selling days where RSI2 stays low for weeks
        # Cuts fire rate from 38% → ~9% (calm oversold only)
        "entry_condition": "RSI2 < 8 and ATR_pct < 0.016",
        "exit_condition":  "RSI2 > 55 or Close > SMA_20",
        "stop_loss": 0.015, "take_profit": 0.03,
        "reasoning": "Fallback: extreme oversold with calm volatility — not panic selling",
    },
    "Volatile": {
        # RSI2 < 10 (tighter than 12) keeps fire rate ~19%, under the new 25% limit
        "entry_condition": "RSI2 < 10 and ATR_pct < 0.022",
        "exit_condition":  "RSI2 > 68 or Close < SMA_50",
        "stop_loss": 0.012, "take_profit": 0.025,
        "reasoning": "Fallback: extreme oversold with controlled volatility for mean reversion",
    },
    "Neutral":  {
        "entry_condition": "Close > SMA_20 * 0.99 and MACD_hist > -100 and RSI2 > 25 and RSI2 < 65",
        "exit_condition":  "Close < SMA_20 * 0.98 or RSI2 > 75 or RSI > 72",
        "stop_loss": 0.018, "take_profit": 0.04,
        "reasoning": "Fallback: price near SMA_20, MACD not deeply negative, RSI2 in middle range",
    },
}
_DEFAULT_FALLBACK = REGIME_FALLBACKS["Neutral"]

REGIME_WARN_FIRE = 0.40
REGIME_REJECT_FIRE = 0.50


def parse_strategy(raw_text: str, regime_df=None, regime: str = "") -> dict:
    fallback = REGIME_FALLBACKS.get(regime, _DEFAULT_FALLBACK)

    if not raw_text or not raw_text.strip():
        out = fallback.copy()
        out["source"] = "fallback"
        out["fallback_reason"] = "empty-llm-output"
        return out

    data = _extract_json(_strip_fences(raw_text))
    if data is None:
        out = fallback.copy()
        out["source"] = "fallback"
        out["fallback_reason"] = "invalid-json-output"
        return out

    for f in REQUIRED_FIELDS:
        if f not in data:
            data[f] = fallback[f]

    entry = _validate_condition(data["entry_condition"], "entry_condition") or fallback["entry_condition"]
    exit_ = _validate_condition(data["exit_condition"],  "exit_condition")  or fallback["exit_condition"]

    fire_rate = None
    if regime_df is not None and len(regime_df) > 10:
        fire_rate = _measure_fire_rate(entry, regime_df)
        if fire_rate > REGIME_REJECT_FIRE:
            print(f"[Parser] [{regime}] entry fires {fire_rate:.0%} > {REGIME_REJECT_FIRE:.0%} — fallback entry")
            entry     = fallback["entry_condition"]
            fire_rate = _measure_fire_rate(entry, regime_df)
        elif fire_rate > REGIME_WARN_FIRE:
            print(f"[Parser] [{regime}] entry fire rate high ({fire_rate:.0%}) but accepted")
        if fire_rate == 0.0:
            print(f"[Parser] [{regime}] entry never fires — accepted")
        print(f"[Parser] [{regime}] fire rate: {fire_rate:.1%}  ok")

    reasoning = str(data.get("reasoning", fallback.get("reasoning", "")))[:200]

    out = {
        "entry_condition": entry,
        "exit_condition":  exit_,
        "stop_loss":       _clamp(data["stop_loss"],   0.005, 0.15, fallback["stop_loss"]),
        "take_profit":     _clamp(data["take_profit"], 0.005, 0.40, fallback["take_profit"]),
        "reasoning":       reasoning,
        "source":          "llm-generated",
    }
    if fire_rate is not None:
        out["fire_rate"] = round(float(fire_rate), 4)
    return out


def _measure_fire_rate(condition: str, df) -> float:
    count, total = 0, 0
    cols = list(ALLOWED_VARS) + ["returns"]
    for _, row in df.iterrows():
        ns = {}
        for col in cols:
            if col in row.index:
                try: ns[col] = float(row[col])
                except: ns[col] = 0.0
        try:
            if eval(condition, {"__builtins__": {}}, ns): count += 1
            total += 1
        except: pass
    return count / total if total else 0.0


def _validate_condition(expr, field):
    if not isinstance(expr, str) or not expr.strip(): return None
    expr = _normalize_condition(expr)
    if expr.lower() in ("false", "true"): return None
    for tok in FORBIDDEN_TOKENS:
        if tok in expr: return None
    tokens = set(re.findall(r"\b[A-Za-z_]\w*\b", expr))
    if not (tokens & ALLOWED_VARS): return None
    try: compile(expr, "<string>", "eval")
    except SyntaxError: return None
    return expr


def _normalize_condition(expr) -> str:
    s = str(expr).strip()
    s = s.replace("&&", " and ").replace("||", " or ")
    s = re.sub(r"\bAND\b", "and", s)
    s = re.sub(r"\bOR\b", "or", s)
    s = re.sub(r"\bNOT\b", "not", s)
    s = re.sub(r"(?<![<>=!])=(?!=)", "==", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _strip_fences(text):
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        inner = lines[1:]
        if inner and inner[-1].strip() == "```": inner = inner[:-1]
        text = "\n".join(inner).strip()
    return text


def _extract_json(text):
    try: return json.loads(text)
    except: pass

    # Minor format issues: single quotes, bare keys, trailing commas
    normalized = text
    normalized = re.sub(r"([{,]\s*)([A-Za-z_][\w]*)\s*:", r'\1"\2":', normalized)
    normalized = re.sub(r",\s*([}\]])", r"\1", normalized)
    normalized = normalized.replace("'", '"')
    try:
        return json.loads(normalized)
    except:
        pass

    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        frag = m.group()
        try:
            return json.loads(frag)
        except:
            frag = re.sub(r"([{,]\s*)([A-Za-z_][\w]*)\s*:", r'\1"\2":', frag)
            frag = re.sub(r",\s*([}\]])", r"\1", frag)
            frag = frag.replace("'", '"')
            try: return json.loads(frag)
            except: pass
    return None


def _clamp(value, lo, hi, default):
    try:
        f = float(str(value).replace("%", "").strip())
        if f > 1.0: f /= 100.0
        return round(max(lo, min(hi, f)), 4)
    except: return default