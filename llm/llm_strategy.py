"""
llm/llm_strategy.py — v6
Hold: 10 bars. Cooldown: 5 bars.
"""

import time, json
from pathlib import Path
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
CACHE_PATH = Path("strategy_cache_llm.json")
GEN_RETRIES = 5

class LLMStrategy(BaseStrategy):
    def __init__(self, backend="ollama", model=None, verbose=True):
        super().__init__()
        self.verbose = verbose
        self.backend = backend
        self.model_name = model or ("qwen2.5:7b-instruct" if backend == "ollama" else "gemma")
        if backend == "ollama":
            self.client = OllamaClient(model=self.model_name)
            print(f"[LLM] Backend: Ollama ({self.client.model})")
        else:
            self.client = OpenRouterClient(model=self.model_name)
            print(f"[LLM] Backend: OpenRouter ({self.client.model})")
        self._strategies      = {}
        self._active_strategy = {}
        self._active_regime   = ""
        self._in_position     = False
        self._bars_held       = 0
        self._bars_since_sell = POST_SELL_COOLDOWN
        self._cache = self._load_cache()
        self._cache_key = f"{self.backend}:{self.client.model}"

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
            src = str(strat.get("source", "fallback"))
            tag = "[LLM]     " if src == "llm-generated" else "[FALLBACK]"
            print(f"  {tag} {regime:12s} -> {strat.get('entry_condition')}")
        print()

    def _generate_for_regime(self, regime, sample_row, regime_df):
        if self.verbose: print(f"[LLM] Generating for '{regime}'...")
        fallback = REGIME_FALLBACKS.get(regime, _DEFAULT_FALLBACK)

        cached = self._get_cached_regime(regime)
        if cached and cached.get("source") == "llm-generated":
            self._strategies[regime] = cached
            if self.verbose:
                print(f"      source: llm-generated (cached, reused)")
            return

        last_error = None
        fallback_reason = "all-retries-exhausted"
        for attempt in range(1, GEN_RETRIES + 1):
            try:
                raw = self.client.generate(build_prompt(regime, sample_row, retry_index=attempt))
                parsed = parse_strategy(raw, regime_df=regime_df, regime=regime)
                if parsed and parsed.get("source") == "llm-generated":
                    self._strategies[regime] = parsed
                    self._set_cached_regime(regime, parsed)
                    if self.verbose:
                        print(f"      source: llm-generated (attempt {attempt}/{GEN_RETRIES})")
                        print(f"      entry : {parsed.get('entry_condition')}")
                        print(f"      exit  : {parsed.get('exit_condition')}")
                    return
                fallback_reason = str((parsed or {}).get("fallback_reason", "parser-returned-fallback"))
                if self.verbose:
                    print(f"      Parser fallback reason: {fallback_reason}")
            except Exception as e:
                last_error = e
                fallback_reason = f"exception: {e}"

            if self.verbose:
                print(f"      LLM retry {attempt}/{GEN_RETRIES} failed")

        # Reuse last good LLM strategy if available (preferred over fallback)
        last_good = self._get_last_good_regime(regime)
        if last_good:
            self._strategies[regime] = last_good
            if self.verbose:
                print(f"      source: llm-generated (reused last-good) | reason: {fallback_reason}")
            return

        fallback_payload = fallback.copy()
        fallback_payload["source"] = "fallback"
        fallback_payload["fallback_reason"] = fallback_reason
        self._strategies[regime] = fallback_payload
        if self.verbose:
            print(f"      source: fallback | reason: {fallback_reason}")

    def _load_cache(self) -> dict:
        if not CACHE_PATH.exists():
            return {"strategies": {}}
        try:
            data = json.loads(CACHE_PATH.read_text())
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {"strategies": {}}

    def _save_cache(self):
        try:
            CACHE_PATH.write_text(json.dumps(self._cache, indent=2))
        except Exception:
            pass

    def _get_cached_regime(self, regime: str) -> dict | None:
        model_bucket = self._cache.get("strategies", {}).get(self._cache_key, {})
        item = model_bucket.get(regime)
        return item if isinstance(item, dict) else None

    def _set_cached_regime(self, regime: str, strategy: dict):
        self._cache.setdefault("strategies", {}).setdefault(self._cache_key, {})[regime] = strategy
        if str(strategy.get("source", "")).strip().lower() == "llm-generated":
            self._cache.setdefault("last_good", {}).setdefault(self._cache_key, {})[regime] = strategy
        self._save_cache()

    def _get_last_good_regime(self, regime: str) -> dict | None:
        item = self._cache.get("last_good", {}).get(self._cache_key, {}).get(regime)
        if isinstance(item, dict) and item.get("source") == "llm-generated":
            return item
        return None

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
