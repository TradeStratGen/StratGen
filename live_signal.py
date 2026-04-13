"""
live_signal.py
Run with:  python live_signal.py
Or:        python main.py --live

What it does:
  1. Fetches latest NIFTY data (up to today)
  2. Detects today's regime
  3. Loads pre-generated LLM strategies (or generates fresh ones)
  4. Evaluates entry/exit conditions on TODAY's row
  5. Prints the signal clearly
  6. Optionally logs to signals.json
  7. Optionally sends to Dhan paper trading API

HOW TO READ THE OUTPUT:
  ✅ BUY  = entry condition is True today → paper buy NIFTY
  🔴 SELL = exit condition is True today → paper sell
  ⏸  HOLD = neither condition met → do nothing
  📊 Shows the exact condition that triggered and today's indicator values

DHAN PAPER TRADING SETUP (see bottom of this file):
  1. Register at https://dhan.co
  2. Go to Developer → API → Generate token
  3. Use sandbox=True in DhanHQ to paper trade
  4. Set DHAN_ACCESS_TOKEN and DHAN_CLIENT_ID in .env
"""

import os
import json
import datetime
import argparse
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def run_live_signal(place_order: bool = False, log_file: str = "signals.json"):
    from data.fetch_data import fetch_data
    from indicators.indicators import add_indicators
    from regime.regime import apply_regime
    from llm.llm_strategy import LLMStrategy

    print("\n" + "="*60)
    print("  STRATGEN — LIVE SIGNAL")
    print(f"  {datetime.datetime.now().strftime('%A, %d %b %Y  %H:%M:%S')}")
    print("="*60)

    # ── 1. Fetch latest data ───────────────────────────────────────────
    df = fetch_data()
    df = add_indicators(df)
    df = apply_regime(df)

    today_row = df.iloc[-1]
    today     = df.index[-1].date()

    print(f"\n[Market] Latest bar: {today}")
    print(f"  Close     : ₹{today_row['Close']:,.2f}")
    print(f"  SMA_20    : ₹{today_row['SMA_20']:,.2f}")
    print(f"  SMA_50    : ₹{today_row['SMA_50']:,.2f}")
    print(f"  RSI       : {today_row['RSI']:.1f}")
    print(f"  RSI2      : {today_row['RSI2']:.1f}")
    print(f"  MACD_hist : {today_row.get('MACD_hist', float('nan')):.3f}")
    print(f"  ATR_pct   : {today_row.get('ATR_pct', float('nan')):.4f}")
    print(f"  Regime    : {today_row['regime']}")

    # ── 2. Load or generate LLM strategy ──────────────────────────────
    strategy_cache = Path("strategy_cache.json")

    if strategy_cache.exists():
        print("\n[LLM] Loading cached strategies from strategy_cache.json...")
        with open(strategy_cache) as f:
            cached = json.load(f)
        # Check if cache is from today
        if cached.get("date") == str(today):
            print("[LLM] Cache is fresh (today) — using it")
            strategies = cached["strategies"]
        else:
            print(f"[LLM] Cache is from {cached.get('date')} — regenerating...")
            strategies = _regenerate_and_cache(df, strategy_cache, today)
    else:
        print("\n[LLM] No cache found — generating strategies...")
        strategies = _regenerate_and_cache(df, strategy_cache, today)

    # ── 3. Evaluate signal for today's regime ─────────────────────────
    regime = today_row["regime"]
    strat  = strategies.get(regime, {})

    if not strat:
        print(f"\n⚠  No strategy found for regime '{regime}'")
        return

    entry_cond = strat.get("entry_condition", "False")
    exit_cond  = strat.get("exit_condition",  "False")
    reasoning  = strat.get("reasoning", "")

    # Build namespace for eval
    ns = {}
    for col in ["Close","SMA_20","SMA_50","RSI","RSI2","MACD_hist","ATR_pct","volatility"]:
        if col in today_row.index:
            try: ns[col] = float(today_row[col])
            except: ns[col] = 0.0

    try:
        entry_fires = bool(eval(entry_cond, {"__builtins__": {}}, ns))
        exit_fires  = bool(eval(exit_cond,  {"__builtins__": {}}, ns))
    except Exception as e:
        print(f"⚠  Condition eval error: {e}")
        entry_fires = exit_fires = False

    # ── 4. Print signal ───────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print(f"  REGIME      : {regime}")
    print(f"  STRATEGY    : {entry_cond}")
    print(f"  REASONING   : {reasoning}")
    print(f"  Stop-loss   : {strat.get('stop_loss', 0)*100:.1f}%")
    print(f"  Take-profit : {strat.get('take_profit', 0)*100:.1f}%")
    print(f"{'─'*60}")

    if entry_fires and not exit_fires:
        signal = "BUY"
        print(f"\n  ✅ SIGNAL: BUY")
        print(f"     Entry condition TRUE: {entry_cond}")
    elif exit_fires:
        signal = "SELL"
        print(f"\n  🔴 SIGNAL: SELL")
        print(f"     Exit condition TRUE: {exit_cond}")
    else:
        signal = "HOLD"
        print(f"\n  ⏸  SIGNAL: HOLD")
        print(f"     Entry: {entry_cond}  → {entry_fires}")
        print(f"     Exit:  {exit_cond}  → {exit_fires}")

    print(f"{'─'*60}\n")

    # ── 5. Log signal ─────────────────────────────────────────────────
    log_entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "date":      str(today),
        "regime":    regime,
        "signal":    signal,
        "close":     float(today_row["Close"]),
        "rsi":       float(today_row["RSI"]),
        "rsi2":      float(today_row.get("RSI2", 0)),
        "strategy":  strat,
    }

    logs = []
    log_path = Path(log_file)
    if log_path.exists():
        try:
            with open(log_path) as f:
                logs = json.load(f)
        except Exception:
            logs = []

    logs.append(log_entry)
    with open(log_path, "w") as f:
        json.dump(logs, f, indent=2)
    print(f"[Log] Signal saved to {log_file}")

    # ── 6. Dhan paper trading (optional) ─────────────────────────────
    if place_order and signal in ("BUY", "SELL"):
        _place_dhan_paper_order(signal, float(today_row["Close"]))

    return signal, log_entry


def _regenerate_and_cache(df, cache_path, today):
    from llm.llm_strategy import LLMStrategy
    strategy = LLMStrategy(backend="ollama", verbose=True)
    strategy.prime(df, pause_seconds=0)
    strategies = strategy.all_strategies
    with open(cache_path, "w") as f:
        json.dump({"date": str(today), "strategies": strategies}, f, indent=2)
    print(f"[LLM] Strategies saved to {cache_path}")
    return strategies


def _place_dhan_paper_order(signal: str, price: float):
    """
    Dhan paper trading integration.

    SETUP STEPS:
    1. Go to https://dhan.co → Login → My Profile → Developer → API
    2. Click 'Generate Access Token'
    3. Add to your .env file:
           DHAN_ACCESS_TOKEN=your_token_here
           DHAN_CLIENT_ID=your_client_id_here
    4. Install: pip install dhanhq
    5. Dhan sandbox uses real API but paper money — no real trades placed
    """
    token     = os.getenv("DHAN_ACCESS_TOKEN", "")
    client_id = os.getenv("DHAN_CLIENT_ID", "")

    if not token or not client_id:
        print("[Dhan] ⚠  DHAN_ACCESS_TOKEN or DHAN_CLIENT_ID not set in .env")
        print("[Dhan]    Set them and re-run with --order to place paper trades")
        return

    try:
        from dhanhq import dhanhq
        dhan = dhanhq(client_id, token)

        # NIFTY 50 index security ID on Dhan
        NIFTY_SECURITY_ID = "13"
        quantity           = 1    # 1 lot for paper trading

        if signal == "BUY":
            order = dhan.place_order(
                security_id   = NIFTY_SECURITY_ID,
                exchange_segment = dhan.NSE,
                transaction_type = dhan.BUY,
                quantity      = quantity,
                order_type    = dhan.MARKET,
                product_type  = dhan.INTRA,
                price         = 0,
            )
        else:
            order = dhan.place_order(
                security_id   = NIFTY_SECURITY_ID,
                exchange_segment = dhan.NSE,
                transaction_type = dhan.SELL,
                quantity      = quantity,
                order_type    = dhan.MARKET,
                product_type  = dhan.INTRA,
                price         = 0,
            )

        print(f"[Dhan] Paper order placed: {signal} NIFTY @ ₹{price:,.2f}")
        print(f"[Dhan] Response: {order}")

    except ImportError:
        print("[Dhan] dhanhq not installed — run: pip install dhanhq")
    except Exception as e:
        print(f"[Dhan] Order failed: {e}")


# ── CLI entry point ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="StratGen Live Signal")
    parser.add_argument("--order", action="store_true",
                        help="Place paper order on Dhan (requires DHAN_ACCESS_TOKEN in .env)")
    parser.add_argument("--log",   default="signals.json",
                        help="Path to signal log file (default: signals.json)")
    args = parser.parse_args()

    run_live_signal(place_order=args.order, log_file=args.log)