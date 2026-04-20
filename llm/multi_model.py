"""
llm/multi_model.py  — v2

KEY FIX: tournament now backtests each model on the FULL df (all regimes),
not on isolated per-regime rows. Per-regime isolation fails because
regime rows are non-consecutive and the 10-bar hold period never completes.

Tournament logic:
  For each model → generate strategies for all regimes → backtest FULL df
  → pick the model with the best overall return
  → use that model's strategies as final_strategies
"""

import time, json
from pathlib import Path
from strategies.base_strategy import BaseStrategy
from llm.client import OllamaClient, OpenRouterClient
from llm.prompts import build_prompt
from llm.parser import parse_strategy, REGIME_FALLBACKS
from backtest.backtester import Backtester
from utils.metrics import compute_metrics
from config import MIN_HOLD_BARS, POST_SELL_COOLDOWN

_DEFAULT_FALLBACK = REGIME_FALLBACKS["Neutral"]
GEN_RETRIES = 5
MULTI_CACHE_PATH = Path("strategy_cache_multi_model.json")


# ── Thin strategy wrapper used inside the tournament ─────────────────────────

class _ModelStrategy(BaseStrategy):
    """A fully working strategy for one model's set of regime rules."""

    def __init__(self, strategies: dict):
        super().__init__()
        self.strategies       = strategies
        self._active_strategy = {}
        self._active_regime   = ""
        self._in_position     = False
        self._bars_held       = 0
        self._bars_since_sell = POST_SELL_COOLDOWN
        self.best_per_regime: dict = {}

    @property
    def current_strategy(self):
        return self._active_strategy

    def generate_signal(self, row) -> str:
        regime = str(row.get("regime", "Neutral"))
        if regime != self._active_regime:
            self._active_strategy = self.strategies.get(
                regime, REGIME_FALLBACKS.get(regime, _DEFAULT_FALLBACK).copy()
            )
            self._active_regime = regime

        ns    = _ns(row)
        entry = _eval(self._active_strategy.get("entry_condition", "False"), ns)
        exit_ = _eval(self._active_strategy.get("exit_condition",  "False"), ns)

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


# ── Main multi-model class ────────────────────────────────────────────────────

class MultiModelStrategy(BaseStrategy):
    """
    Generates strategies from N models, backtests each on the FULL df,
    picks the winner by total return, and uses winner's strategies.

    Usage:
        multi = MultiModelStrategy(models=["qwen2.5:7b-instruct", "llama3.2:3b"])
        multi.prime(df)
        bt = Backtester(df, multi)
        equity, trades = bt.run()
    """

    def __init__(self, models: list = None, verbose: bool = True):
        super().__init__()
        self.verbose      = verbose
        self.model_names  = models or ["qwen2.5:7b-instruct", "llama3.2:3b"]
        self._cache = self._load_cache()

        self.model_results:    dict = {}   # model -> {strategies, return, metrics}
        self.winner_model:     str  = ""
        self.final_strategies: dict = {}

        self._active_strategy: dict = {}
        self._active_regime:   str  = ""
        self._in_position:     bool = False
        self._bars_held:       int  = 0
        self._bars_since_sell: int  = POST_SELL_COOLDOWN

    # ── Tournament ────────────────────────────────────────────────────────

    def prime(self, df, pause_seconds: float = 0.0):
        regimes = list(df["regime"].dropna().unique())
        print(f"\n[MultiModel] Models  : {self.model_names}")
        print(f"[MultiModel] Regimes : {regimes}")
        print(f"[MultiModel] Method  : full-df backtest per model\n")

        for model_name in self.model_names:
            print(f"{'─'*55}")
            print(f"[MultiModel] Generating — {model_name}")
            print(f"{'─'*55}")

            client     = OllamaClient(model=model_name)
            strategies = self._generate_all(client, model_name, df, regimes)

            print(f"\n[MultiModel] Backtesting {model_name} on full df...")
            strat_obj      = _ModelStrategy(strategies)
            bt             = Backtester(df, strat_obj)
            equity, trades = bt.run()
            m = compute_metrics(equity, trades)

            # --- REAL per-regime returns ---
            per_regime = {}
            regimes = df["regime"].unique()

            for r in regimes:
                mask = df["regime"] == r
                if mask.sum() < 10:
                    continue

                sub_df = df[mask]

                try:
                    bt_r = Backtester(sub_df, _ModelStrategy(strategies))
                    eq_r, tr_r = bt_r.run()
                    m_r = compute_metrics(eq_r, tr_r)

                    per_regime[r] = {
                        "return": m_r.get("total_return_pct", 0)
                    }
                except:
                    per_regime[r] = {"return": 0}

            m["per_regime"] = per_regime

            m["per_regime"] = per_regime

            self.model_results[model_name] = {
                "strategies": strategies,
                "equity":     equity,
                "trades":     trades,
                "metrics":    m,
            }
            print(f"  return={m['total_return_pct']:+.1f}%  "
                  f"trades={m['num_trades']}  "
                  f"win={m['win_rate_pct']:.0f}%  "
                  f"sharpe={m['sharpe_ratio']:.2f}")

            if pause_seconds > 0:
                time.sleep(pause_seconds)

        self._pick_winner()
        self._compute_best_per_regime()
        self._print_table()

    def _generate_all(self, client, model_name, df, regimes) -> dict:
        strategies = {}
        for regime in regimes:
            regime_df  = df[df["regime"] == regime]
            sample_row = regime_df.iloc[-1]
            fallback   = REGIME_FALLBACKS.get(regime, _DEFAULT_FALLBACK)
            if self.verbose:
                print(f"  [{model_name[:22]:<22}] '{regime}'...")

            cached = self._get_cached_regime(model_name, regime)
            if cached and cached.get("source") == "llm-generated":
                strategies[regime] = cached
                if self.verbose:
                    print("  " + " " * 24 + "source: llm-generated (cached, reused)")
                continue

            last_error = None
            fallback_reason = "all-retries-exhausted"
            for attempt in range(1, GEN_RETRIES + 1):
                try:
                    raw = client.generate(build_prompt(regime, sample_row, retry_index=attempt))
                    parsed = parse_strategy(raw, regime_df=regime_df, regime=regime)
                    if parsed and parsed.get("source") == "llm-generated":
                        strategies[regime] = parsed
                        self._set_cached_regime(model_name, regime, parsed)
                        if self.verbose:
                            print("  " + " " * 24 + f"source: llm-generated (attempt {attempt}/{GEN_RETRIES})")
                            print(f"  {'':24}  entry: {strategies[regime].get('entry_condition')}")
                        break
                    fallback_reason = str((parsed or {}).get("fallback_reason", "parser-returned-fallback"))
                    if self.verbose:
                        print("  " + " " * 24 + f"parser fallback reason: {fallback_reason}")
                except Exception as e:
                    last_error = e
                    fallback_reason = f"exception: {e}"

                if self.verbose:
                    print("  " + " " * 24 + f"retry {attempt}/{GEN_RETRIES} failed")

            if regime not in strategies:
                last_good = self._get_last_good_regime(model_name, regime)
                if last_good:
                    strategies[regime] = last_good
                    if self.verbose:
                        print("  " + " " * 24 + f"source: llm-generated (reused last-good) | reason: {fallback_reason}")
                    continue

                fallback_payload = fallback.copy()
                fallback_payload["source"] = "fallback"
                fallback_payload["fallback_reason"] = fallback_reason
                strategies[regime] = fallback_payload
                if self.verbose:
                    print("  " + " " * 24 + f"source: fallback | reason: {fallback_reason}")
        return strategies

    def _load_cache(self) -> dict:
        if not MULTI_CACHE_PATH.exists():
            return {"strategies": {}}
        try:
            data = json.loads(MULTI_CACHE_PATH.read_text())
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {"strategies": {}}

    def _save_cache(self):
        try:
            MULTI_CACHE_PATH.write_text(json.dumps(self._cache, indent=2))
        except Exception:
            pass

    def _get_cached_regime(self, model_name: str, regime: str) -> dict | None:
        item = self._cache.get("strategies", {}).get(model_name, {}).get(regime)
        return item if isinstance(item, dict) else None

    def _set_cached_regime(self, model_name: str, regime: str, strategy: dict):
        self._cache.setdefault("strategies", {}).setdefault(model_name, {})[regime] = strategy
        if str(strategy.get("source", "")).strip().lower() == "llm-generated":
            self._cache.setdefault("last_good", {}).setdefault(model_name, {})[regime] = strategy
        self._save_cache()

    def _get_last_good_regime(self, model_name: str, regime: str) -> dict | None:
        item = self._cache.get("last_good", {}).get(model_name, {}).get(regime)
        if isinstance(item, dict) and item.get("source") == "llm-generated":
            return item
        return None

    def _pick_winner(self):
        """Pick the model with the best total return on full df."""
        best_ret   = -999
        best_model = self.model_names[0]

        for mn, data in self.model_results.items():
            ret = data["metrics"]["total_return_pct"]
            if ret > best_ret:
                best_ret   = ret
                best_model = mn

        self.winner_model     = best_model
        self.final_strategies = self.model_results[best_model]["strategies"]

    def _compute_best_per_regime(self):
        """
        Compute best model per regime based on per-regime returns.
        Used by dashboard.
        """
        best = {}

        for model_name, data in self.model_results.items():
            metrics = data.get("metrics", {})
            regime_metrics = metrics.get("per_regime", {})

            for regime, vals in regime_metrics.items():
                ret = vals.get("return", 0)

                if regime not in best or ret > best[regime]["return"]:
                    best[regime] = {
                        "model": model_name,
                        "return": ret
                    }

        self.best_per_regime = best

    def _print_table(self):
        print(f"\n{'═'*65}")
        print(f"  MULTI-MODEL TOURNAMENT RESULTS (full-df backtest)")
        print(f"{'═'*65}")

        col = 14
        hdr = f"  {'Model':<24}"
        for lbl in ["Return %", "Win Rate %", "Sharpe", "Trades"]:
            hdr += f"  {lbl:>{col}}"
        print(hdr)
        print(f"  {'─'*24}" + f"  {'─'*col}" * 4)

        for mn, data in self.model_results.items():
            m    = data["metrics"]
            star = "  ★ WINNER" if mn == self.winner_model else ""
            short = mn.split(":")[0].split("/")[-1]
            print(
                f"  {short:<24}"
                f"  {m['total_return_pct']:>+{col}.1f}%"
                f"  {m['win_rate_pct']:>{col}.1f}%"
                f"  {m['sharpe_ratio']:>{col}.3f}"
                f"  {m['num_trades']:>{col}}"
                f"{star}"
            )

        print(f"{'─'*65}")
        print(f"  Winner: {self.winner_model}")
        print(f"\n  Final strategies from winner:")
        for regime, strat in self.final_strategies.items():
            short = self.winner_model.split(":")[0].split("/")[-1]
            print(f"  [{short}] {regime:12s} → {strat.get('entry_condition')}")
        print(f"{'═'*65}\n")

    # ── BaseStrategy interface ────────────────────────────────────────────

    def generate_signal(self, row) -> str:
        regime = str(row.get("regime", "Neutral"))
        if regime != self._active_regime:
            self._active_strategy = self.final_strategies.get(
                regime, REGIME_FALLBACKS.get(regime, _DEFAULT_FALLBACK).copy()
            )
            self._active_regime = regime

        ns    = _ns(row)
        entry = _eval(self._active_strategy.get("entry_condition", "False"), ns)
        exit_ = _eval(self._active_strategy.get("exit_condition",  "False"), ns)

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
    def current_strategy(self): return self._active_strategy
    @property
    def all_strategies(self):   return self.final_strategies

    def print_report(self):
        print("\n[MultiModel] Winner per metric:")
        for mn, data in self.model_results.items():
            m = data["metrics"]
            short = mn.split(":")[0].split("/")[-1]
            win = "★" if mn == self.winner_model else " "
            print(f"  {win} {short:<20} return={m['total_return_pct']:+.1f}%  trades={m['num_trades']}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ns(row) -> dict:
    ns = {}
    for col in ["Close","SMA_20","SMA_50","RSI","RSI2","MACD_hist","ATR_pct","volatility","returns"]:
        if col in row.index:
            try:    ns[col] = float(row[col])
            except: ns[col] = 0.0
    return ns

def _eval(expr: str, ns: dict) -> bool:
    try:    return bool(eval(expr, {"__builtins__": {}}, ns))
    except: return False