"""
main.py — StratGen final
Runs: MA baseline + multi-model tournament + walk-forward validation

Usage:
    python main.py              # full backtest + walk-forward
    python main.py --live       # today's signal only (fast)
    python main.py --no-wf      # skip walk-forward (faster backtest)
"""

import argparse
from dotenv import load_dotenv
load_dotenv()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live",  action="store_true", help="Run live signal only")
    parser.add_argument("--no-wf", action="store_true", help="Skip walk-forward validation")
    args = parser.parse_args()

    # ── Live mode: fast path ───────────────────────────────────────────
    if args.live:
        from live_signal import run_live_signal
        run_live_signal()
        return

    # ── Full backtest mode ─────────────────────────────────────────────
    from data.fetch_data import fetch_data
    from indicators.indicators import add_indicators
    from regime.regime import apply_regime
    from strategies.ma_strategy import MovingAverageStrategy
    from llm.multi_model import MultiModelStrategy
    from backtest.backtester import Backtester
    from utils.metrics import compute_metrics, print_metrics, compare_metrics
    from utils.walk_forward import walk_forward_test

    print("Fetching data...")
    df = fetch_data()
    df = add_indicators(df)
    df = apply_regime(df)

    # ── 1. MA baseline ──────────────────────────────────────────────────
    print("\n--- Baseline: MA Crossover ---")
    ma_eq, ma_tr = Backtester(df, MovingAverageStrategy()).run()
    print_metrics(compute_metrics(ma_eq, ma_tr), "MA Crossover (Baseline)")

    # ── 2. Multi-model tournament ────────────────────────────────────────
    print("\n--- Multi-Model Tournament ---")
    multi = MultiModelStrategy(
        models=["qwen2.5:7b-instruct", "llama3.2:3b"],
        verbose=True,
    )
    multi.prime(df)
    mm_eq, mm_tr = Backtester(df, multi).run()
    print_metrics(compute_metrics(mm_eq, mm_tr), "Multi-Model (best per regime)")

    # ── 3. Show strategy reasoning ───────────────────────────────────────
    print("\n--- LLM Strategy Reasoning ---")
    for regime, strat in multi.final_strategies.items():
        print(f"\n  {regime}:")
        print(f"    Entry     : {strat.get('entry_condition')}")
        print(f"    Exit      : {strat.get('exit_condition')}")
        print(f"    SL / TP   : {strat.get('stop_loss',0)*100:.1f}%  /  {strat.get('take_profit',0)*100:.1f}%")
        print(f"    Reasoning : {strat.get('reasoning', '—')}")

    # ── 4. Comparison table ──────────────────────────────────────────────
    compare_metrics({
        "MA Crossover": (ma_eq, ma_tr),
        "Multi-Model":  (mm_eq, mm_tr),
    })

    # ── 5. Walk-forward validation ───────────────────────────────────────
    if not args.no_wf:
        print("\n--- Walk-Forward Validation ---")
        from llm.multi_model import MultiModelStrategy as MMS

        def strategy_factory():
            return MMS(models=["qwen2.5:7b-instruct", "llama3.2:3b"], verbose=False)

        walk_forward_test(df, strategy_factory, train_frac=0.7, n_splits=3)
    else:
        print("\n[Skipped walk-forward — run without --no-wf to enable]")

    # ── 6. Live signal preview ───────────────────────────────────────────
    print("\n--- Today's Signal (from trained multi-model) ---")
    today_row = df.iloc[-1]
    regime    = today_row["regime"]
    strat     = multi.final_strategies.get(regime, {})
    if strat:
        ns = {}
        for col in ["Close","SMA_20","SMA_50","RSI","RSI2","MACD_hist","ATR_pct","volatility"]:
            if col in today_row.index:
                try: ns[col] = float(today_row[col])
                except: ns[col] = 0.0
        try:
            entry = bool(eval(strat.get("entry_condition","False"), {"__builtins__":{}}, ns))
            exit_ = bool(eval(strat.get("exit_condition","False"),  {"__builtins__":{}}, ns))
            sig   = "BUY" if entry and not exit_ else ("SELL" if exit_ else "HOLD")
        except:
            sig = "HOLD"
        icon = {"BUY":"✅","SELL":"🔴","HOLD":"⏸"}
        print(f"  Regime   : {regime}")
        print(f"  Signal   : {icon.get(sig,'')} {sig}")
        print(f"  Reasoning: {strat.get('reasoning','—')}")


if __name__ == "__main__":
    main()