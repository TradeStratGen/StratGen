"""
llm/llm_strategy.py — v6
Hold: 10 bars. Cooldown: 5 bars.
"""

import time, json
from strategies.base_strategy import BaseStrategy
from llm.client import OllamaClient, OpenRouterClient
from llm.prompts import build_prompt
from llm.parser import parse_strategy

REGIME_FALLBACKS = {
    "Bullish":  {"entry_condition": "Close > SMA_20 and Close < SMA_20 * 1.015 and RSI > 44 and RSI < 56", "exit_condition": "Close < SMA_50 or RSI > 76", "stop_loss": 0.025, "take_profit": 0.07},
    "Bearish":  {"entry_condition": "RSI < 28", "exit_condition": "RSI > 52 or Close > SMA_20", "stop_loss": 0.015, "take_profit": 0.03},
    "Volatile": {"entry_condition": "RSI < 30", "exit_condition": "RSI > 68 or Close < SMA_50", "stop_loss": 0.012, "take_profit": 0.025},
    "Neutral":  {"entry_condition": "SMA_20 > SMA_50 and RSI > 52 and RSI < 62", "exit_condition": "SMA_20 < SMA_50 or RSI > 70 or RSI < 46", "stop_loss": 0.02, "take_profit": 0.045},
}
_DEFAULT_FALLBACK = REGIME_FALLBACKS["Neutral"]

MIN_HOLD_BARS      = 10
POST_SELL_COOLDOWN = 5

class LLMStrategy(BaseStrategy):
    def __init__(self, backend="ollama", model=None, verbose=True):
        super().__init__()
        self.verbose = verbose
        if backend == "ollama":
            self.client = OllamaClient(model=model or "qwen2.5:7b-instruct")
            print(f"[LLM] Backend: Ollama ({self.client.model})")
        else:
            self.client = OpenRouterClient(model=model or "gemma")
            print(f"[LLM] Backend: OpenRouter ({self.client.model})")
        self._strategies      = {}
        self._active_strategy = {}
        self._active_regime   = ""
        self._in_position     = False
        self._bars_held       = 0
        self._bars_since_sell = POST_SELL_COOLDOWN

    def prime(self, df, pause_seconds=0.0):
        regimes = list(df["regime"].dropna().unique())
        print(f"\n[LLM] Pre-generating for {len(regimes)} regimes: {regimes}")
        print(f"[LLM] Discipline: hold>={MIN_HOLD_BARS} bars, cooldown>={POST_SELL_COOLDOWN} bars\n")
        for i, regime in enumerate(regimes):
            regime_df  = df[df["regime"] == regime]
            sample_row = regime_df.iloc[-1]
            self._generate_for_regime(regime, sample_row, regime_df)
            if pause_seconds > 0 and i < len(regimes) - 1:
                time.sleep(pause_seconds)
        print("\n[LLM] Final strategies:")
        for regime, strat in self._strategies.items():
            fb     = REGIME_FALLBACKS.get(regime, _DEFAULT_FALLBACK)
            is_llm = strat.get("entry_condition") != fb["entry_condition"]
            tag    = "[LLM]     " if is_llm else "[FALLBACK]"
            print(f"  {tag} {regime:12s} -> {strat.get('entry_condition')}")
        print()

    def _generate_for_regime(self, regime, sample_row, regime_df):
        if self.verbose: print(f"[LLM] Generating for '{regime}'...")
        fallback = REGIME_FALLBACKS.get(regime, _DEFAULT_FALLBACK)
        try:
            raw    = self.client.generate(build_prompt(regime, sample_row))
            parsed = parse_strategy(raw, regime_df=regime_df, regime=regime)
            self._strategies[regime] = parsed if parsed else fallback.copy()
            if self.verbose and parsed:
                print(f"      entry : {parsed.get('entry_condition')}")
                print(f"      exit  : {parsed.get('exit_condition')}")
        except Exception as e:
            print(f"      Error: {e} — regime fallback")
            self._strategies[regime] = fallback.copy()

    def generate_signal(self, row) -> str:
        regime = str(row.get("regime", "Neutral"))
        if regime != self._active_regime:
            self._active_strategy = self._strategies.get(regime, REGIME_FALLBACKS.get(regime, _DEFAULT_FALLBACK).copy())
            self._active_regime = regime
        ns    = _row_to_namespace(row)
        entry = _safe_eval(self._active_strategy.get("entry_condition", "False"), ns)
        exit_ = _safe_eval(self._active_strategy.get("exit_condition",  "False"), ns)
        if self._in_position:
            self._bars_held += 1
            if exit_ and self._bars_held >= MIN_HOLD_BARS:
                self._in_position     = False
                self._bars_held       = 0
                self._bars_since_sell = 0
                return "SELL"
            return "HOLD"
        else:
            self._bars_since_sell += 1
            if entry and self._bars_since_sell >= POST_SELL_COOLDOWN:
                self._in_position    = True
                self._bars_held      = 0
                return "BUY"
            return "HOLD"

    @property
    def all_strategies(self): return self._strategies
    @property
    def current_strategy(self): return self._active_strategy

def _row_to_namespace(row) -> dict:
    ns = {}
    for col in ["Close","SMA_20","SMA_50","RSI","volatility","returns"]:
        if col in row.index:
            try: ns[col] = float(row[col])
            except: ns[col] = 0.0
    return ns

def _safe_eval(expr, ns) -> bool:
    try:    return bool(eval(expr, {"__builtins__": {}}, ns))
    except: return False
