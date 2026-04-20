"""
live_signal.py  —  Daily signal runner

Run every morning after 9:15am IST (NSE open):
    python live_signal.py              # signal only, no order
    python live_signal.py --order      # signal + place Dhan paper order
    python live_signal.py --history    # print all past paper trades

Files saved automatically:
    logs/signals/signal_{regime}_{date}.json
    logs/orders/order_{action}_{regime}_{date}.json
    logs/reports/report_{date}.json
    logs/weekly/week_{year}-W{nn}.json
"""

import os
import json
import datetime
import argparse
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


STATE_PATH = Path("logs/state.json")


def _load_position_state() -> dict:
    default_state = {
        "in_position": False,
        "updated_at": datetime.datetime.now().isoformat(),
        "last_action": "INIT",
    }

    if not STATE_PATH.exists():
        return default_state

    try:
        data = json.loads(STATE_PATH.read_text())
        return {
            "in_position": bool(data.get("in_position", False)),
            "updated_at": str(data.get("updated_at", default_state["updated_at"])),
            "last_action": str(data.get("last_action", "INIT")),
        }
    except Exception:
        return default_state


def _save_position_state(state: dict):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "in_position": bool(state.get("in_position", False)),
        "updated_at": datetime.datetime.now().isoformat(),
        "last_action": str(state.get("last_action", "UNKNOWN")),
    }
    STATE_PATH.write_text(json.dumps(payload, indent=2))


def run_live_signal(place_order: bool = False):
    from data.fetch_data import fetch_data
    from indicators.indicators import add_indicators
    from regime.regime import apply_regime
    from llm.llm_strategy import LLMStrategy
    from utils.reporter import DailyReporter

    reporter = DailyReporter(log_dir="logs")
    today    = datetime.date.today().isoformat()
    state    = _load_position_state()

    print("\n" + "="*62)
    print("  STRATGEN — DAILY SIGNAL")
    print(f"  {datetime.datetime.now().strftime('%A, %d %b %Y  %H:%M:%S')}")
    print("="*62)

    # ── 1. Data ────────────────────────────────────────────────────────────
    df = fetch_data()
    df = add_indicators(df)
    df = apply_regime(df)

    today_row = df.iloc[-1]
    bar_date  = df.index[-1].date()

    indicators = {}
    for col in ["Close","SMA_20","SMA_50","RSI","RSI2","MACD_hist","ATR_pct","volatility"]:
        if col in today_row.index:
            try: indicators[col] = round(float(today_row[col]), 4)
            except: indicators[col] = None

    print(f"\n[Market] Latest bar: {bar_date}")
    print(f"  Close     : ₹{indicators.get('Close', 0):,.2f}")
    print(f"  SMA_20    : ₹{indicators.get('SMA_20', 0):,.2f}")
    print(f"  SMA_50    : ₹{indicators.get('SMA_50', 0):,.2f}")
    print(f"  RSI       : {indicators.get('RSI', 0):.1f}")
    print(f"  RSI2      : {indicators.get('RSI2', 0):.1f}")
    print(f"  MACD_hist : {indicators.get('MACD_hist', 0):.3f}")
    print(f"  ATR_pct   : {indicators.get('ATR_pct', 0):.4f}")
    print(f"  Regime    : {today_row['regime']}")

    # ── 2. Load or generate strategy ───────────────────────────────────────
    cache_path = Path("strategy_cache.json")
    strategies = None

    if cache_path.exists():
        cached = json.loads(cache_path.read_text())
        if cached.get("date") == today:
            print("\n[LLM] Using today's cached strategies")
            strategies = cached["strategies"]

    if not strategies:
        print("\n[LLM] Generating fresh strategies...")
        strategy_obj = LLMStrategy(backend="ollama", verbose=True)
        strategy_obj.prime(df, pause_seconds=0)
        strategies = strategy_obj.all_strategies
        cache_path.write_text(json.dumps({"date": today, "strategies": strategies}, indent=2))
        print(f"[LLM] Saved to {cache_path}")

    # ── 3. Evaluate today's signal ─────────────────────────────────────────
    regime = str(today_row["regime"])
    strat  = strategies.get(regime, {})

    entry_cond = strat.get("entry_condition", "False")
    exit_cond  = strat.get("exit_condition",  "False")

    ns = {k: v for k, v in indicators.items() if v is not None}
    try:
        entry_fires = bool(eval(entry_cond, {"__builtins__": {}}, ns))
        exit_fires  = bool(eval(exit_cond,  {"__builtins__": {}}, ns))
    except Exception:
        entry_fires = exit_fires = False

    if entry_fires and not exit_fires:
        signal = "BUY"
    elif exit_fires:
        signal = "SELL"
    else:
        signal = "HOLD"

    raw_signal = signal

    # ── 3b. Enforce position-state discipline (matches backtester position logic)
    # Flat account   -> BUY allowed, SELL blocked
    # In position    -> SELL allowed, BUY blocked
    if not state["in_position"] and raw_signal == "SELL":
        signal = "HOLD"
    elif state["in_position"] and raw_signal == "BUY":
        signal = "HOLD"

    if raw_signal != signal:
        print(f"[State] Raw signal {raw_signal} blocked (in_position={state['in_position']}) -> HOLD")

    # ── 4. Print signal ────────────────────────────────────────────────────
    icons = {"BUY": "✅", "SELL": "🔴", "HOLD": "⏸ "}
    print(f"\n{'─'*62}")
    print(f"  REGIME    : {regime}")
    print(f"  ENTRY     : {entry_cond}")
    print(f"  EXIT      : {exit_cond}")
    print(f"  REASONING : {strat.get('reasoning', '—')}")
    print(f"  SL / TP   : {strat.get('stop_loss',0)*100:.1f}%  /  "
          f"{strat.get('take_profit',0)*100:.1f}%")
    print(f"{'─'*62}")
    print(f"\n  {icons[signal]} SIGNAL: {signal}")
    if signal == "BUY":
        sl_price = indicators['Close'] * (1 - strat.get('stop_loss', 0.02))
        tp_price = indicators['Close'] * (1 + strat.get('take_profit', 0.04))
        print(f"     Entry at : ₹{indicators['Close']:,.2f}")
        print(f"     Stop-loss: ₹{sl_price:,.2f}")
        print(f"     Target   : ₹{tp_price:,.2f}")
    elif signal == "SELL":
        print(f"     Exit condition fired: {exit_cond}")
    else:
        print(f"     Entry condition: {entry_cond} → {entry_fires}")
        print(f"     Exit  condition: {exit_cond}  → {exit_fires}")
    print(f"{'─'*62}\n")

    # ── 4b. Persist position state only on valid executions ───────────────
    if signal == "BUY":
        state["in_position"] = True
        state["last_action"] = "BUY"
        _save_position_state(state)
    elif signal == "SELL":
        state["in_position"] = False
        state["last_action"] = "SELL"
        _save_position_state(state)

    # ── 5. Save signal log ─────────────────────────────────────────────────
    reporter.log_signal(regime, signal, strat, indicators)
    # Only BUY/SELL are logged as orders — reporter silently skips HOLD
    reporter.log_order(signal, indicators['Close'], regime, strat,
                       source="live-llm")

    # ── Wire daily report (was defined but never called) ──────────────────
    reporter.save_daily_report(
        ma_metrics={},
        llm_metrics={},
        strategies=strategies,
        winner_model="ollama",
        today_signal=signal,
        today_regime=regime,
    )

    # ── 6. Dhan paper trade ────────────────────────────────────────────────
    if place_order and signal in ("BUY", "SELL"):
        _place_dhan_order(signal, indicators['Close'])

    return signal


def _place_dhan_order(action: str, price: float) -> dict:
    """
    Place a paper order on Dhan.

    SETUP:
    1. Go to dhan.co → login → My Profile → Developer → Apps
    2. Create App → any Redirect URL (use https://localhost)
    3. Generate Access Token
    4. Add to .env:
           DHAN_ACCESS_TOKEN=eyJ...
           DHAN_CLIENT_ID=1000...
    5. pip install dhanhq
    """
    token     = os.getenv("DHAN_ACCESS_TOKEN", "")
    client_id = os.getenv("DHAN_CLIENT_ID", "")

    if not token or not client_id:
        print("\n[Dhan] ⚠  Credentials missing.")
        print("[Dhan]    Add DHAN_ACCESS_TOKEN and DHAN_CLIENT_ID to .env")
        print("[Dhan]    Then run:  python live_signal.py --order")
        return {}

    # ── Safety: explicit opt-in for live broker execution ─────────────────
    # Default is paper-only. Set DHAN_LIVE=1 in .env ONLY for real orders.
    is_live = os.getenv("DHAN_LIVE", "0").strip() == "1"
    if not is_live:
        print(f"\n[Dhan] PAPER MODE (DHAN_LIVE not set) — order NOT sent to broker.")
        print(f"[Dhan] Intended: {action} @ ₹{price:,.2f}")
        print("[Dhan] Set DHAN_LIVE=1 in .env to enable real execution.")
        return {"paper_only": True, "action": action, "price": price}

    try:
        from dhanhq import dhanhq
        dhan = dhanhq(client_id, token)

        # NIFTY 50 index on Dhan — security_id varies by instrument
        # For NIFTY50 index ETF (NIFTYBEES) use security_id = "1333"
        # For NIFTY futures use the relevant monthly contract
        # For pure signal tracking, use NIFTYBEES (most liquid ETF)
        NIFTYBEES_SECURITY_ID = "1333"
        QUANTITY = 1   # 1 unit for paper tracking

        order = dhan.place_order(
            security_id      = NIFTYBEES_SECURITY_ID,
            exchange_segment = dhan.NSE,
            transaction_type = dhan.BUY if action == "BUY" else dhan.SELL,
            quantity         = QUANTITY,
            order_type       = dhan.MARKET,
            product_type     = dhan.CNC,   # CNC = delivery (holds overnight)
            price            = 0,
        )

        print(f"\n[Dhan] ✅ Paper order placed: {action} @ ₹{price:,.2f}")
        print(f"[Dhan] Order ID: {order.get('data', {}).get('orderId', 'N/A')}")
        return order

    except ImportError:
        print("[Dhan] dhanhq not installed → pip install dhanhq")
        return {}
    except Exception as e:
        print(f"[Dhan] Order failed: {e}")
        return {}


def print_history():
    from utils.reporter import DailyReporter
    reporter = DailyReporter(log_dir="logs")
    reporter.print_trade_history()

    # Also show weekly summary if available
    import glob
    weekly_files = sorted(glob.glob("logs/weekly/week_*.json"))
    if weekly_files:
        print("\nWeekly summaries:")
        for wf in weekly_files[-4:]:   # last 4 weeks
            week = json.loads(Path(wf).read_text())
            wname = Path(wf).stem
            print(f"\n  {wname}:")
            for day in week:
                sig_icon = {"BUY":"↑","SELL":"↓","HOLD":"—"}.get(day.get("signal",""),"?")
                print(f"    {day['date']}  {sig_icon} {day.get('signal','?'):<5} "
                      f"{day.get('regime','?'):<10} "
                      f"LLM: {day.get('llm_return',0):+.1f}%")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="StratGen Daily Signal")
    parser.add_argument("--order",   action="store_true",
                        help="Place paper order on Dhan")
    parser.add_argument("--history", action="store_true",
                        help="Print all past paper trades")
    args = parser.parse_args()

    if args.history:
        print_history()
    else:
        run_live_signal(place_order=args.order)