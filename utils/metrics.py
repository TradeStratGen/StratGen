"""
utils/metrics.py
Computes all trading performance metrics from equity curve + trade list.

Functions:
    compute_metrics(equity, trades, risk_free_rate) -> dict
    print_metrics(metrics, label)
    compare_metrics(results_dict) -> dict
"""

import math


def compute_metrics(
    equity:           list,
    trades:           list,
    risk_free_rate:   float = 0.065,
    periods_per_year: int   = 252,
) -> dict:
    """
    Args:
        equity:           List of portfolio values, one per trading bar.
        trades:           List of (date, action, price) tuples.
        risk_free_rate:   Annual risk-free rate (0.065 = 6.5%, Indian gilt).
        periods_per_year: 252 for daily data.

    Returns dict with: total_return_pct, annualised_return_pct, win_rate_pct,
    avg_win_pct, avg_loss_pct, profit_factor, max_drawdown_pct,
    max_drawdown_duration_bars, sharpe_ratio, calmar_ratio, and more.
    """
    if not equity or len(equity) < 2:
        return _empty()

    initial = equity[0]
    final   = equity[-1]

    # ── Total return ──────────────────────────────────────────────────────
    total_return_pct = (final - initial) / initial * 100

    # ── CAGR ─────────────────────────────────────────────────────────────
    years = len(equity) / periods_per_year
    annualised_return_pct = ((final / initial) ** (1 / years) - 1) * 100 if years > 0 else 0.0

    # ── Win / loss from round trips ───────────────────────────────────────
    # Backtester emits SELL, SELL-SL, SELL-TP, SELL-TRAIL — all close a position
    SELL_ACTIONS = {"SELL", "SELL-SL", "SELL-TP", "SELL-TRAIL"}
    open_buys, win_pcts, loss_pcts = [], [], []
    for _, action, price in trades:
        if action == "BUY":
            open_buys.append(price)
        elif action in SELL_ACTIONS and open_buys:
            bp  = open_buys.pop(0)
            pct = (price - bp) / bp * 100
            (win_pcts if pct >= 0 else loss_pcts).append(pct)

    num_wins   = len(win_pcts)
    num_losses = len(loss_pcts)
    num_trades = num_wins + num_losses

    win_rate_pct  = num_wins  / num_trades * 100 if num_trades else 0.0
    avg_win_pct   = sum(win_pcts)  / num_wins    if num_wins   else 0.0
    avg_loss_pct  = sum(loss_pcts) / num_losses  if num_losses else 0.0
    gross_profit  = sum(win_pcts)
    gross_loss    = abs(sum(loss_pcts))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 999.0

    # ── Max drawdown ──────────────────────────────────────────────────────
    peak = equity[0]; max_dd_pct = 0.0
    dd_dur = 0; max_dd_dur = 0; in_dd = False

    for val in equity:
        if val >= peak:
            if in_dd:
                max_dd_dur = max(max_dd_dur, dd_dur)
            peak = val; dd_dur = 0; in_dd = False
        else:
            in_dd   = True
            dd_dur += 1
            max_dd_pct = max(max_dd_pct, (peak - val) / peak * 100)
    if in_dd:
        max_dd_dur = max(max_dd_dur, dd_dur)

    # ── Sharpe ratio ──────────────────────────────────────────────────────
    daily_returns = [
        (equity[i] - equity[i-1]) / equity[i-1]
        for i in range(1, len(equity))
        if equity[i-1] != 0
    ]
    if len(daily_returns) > 1:
        n      = len(daily_returns)
        mean_r = sum(daily_returns) / n
        var_r  = sum((r - mean_r)**2 for r in daily_returns) / (n - 1)
        std_r  = math.sqrt(var_r) if var_r > 0 else 0
        daily_rf = risk_free_rate / periods_per_year
        sharpe   = ((mean_r - daily_rf) / std_r * math.sqrt(periods_per_year)
                    if std_r > 0 else 0.0)
    else:
        sharpe = 0.0

    # ── Calmar ratio ──────────────────────────────────────────────────────
    calmar = annualised_return_pct / max_dd_pct if max_dd_pct > 0 else 0.0

    return {
        "initial":                    round(initial, 2),
        "final":                      round(final, 2),
        "total_return_pct":           round(total_return_pct, 2),
        "annualised_return_pct":      round(annualised_return_pct, 2),
        "num_trades":                 num_trades,
        "num_wins":                   num_wins,
        "num_losses":                 num_losses,
        "win_rate_pct":               round(win_rate_pct, 1),
        "avg_win_pct":                round(avg_win_pct, 2),
        "avg_loss_pct":               round(avg_loss_pct, 2),
        "profit_factor":              round(profit_factor, 2),
        "max_drawdown_pct":           round(max_dd_pct, 2),
        "max_drawdown_duration_bars": max_dd_dur,
        "sharpe_ratio":               round(sharpe, 3),
        "calmar_ratio":               round(calmar, 3),
        "total_bars":                 len(equity),
    }


def print_metrics(m: dict, label: str = "Strategy"):
    """Pretty-print a single metrics dict."""
    W = 52
    print(f"\n{'═'*W}")
    print(f"  {label}")
    print(f"{'═'*W}")
    print(f"  {'Capital':<30} ₹{m['initial']:>8,.0f} → ₹{m['final']:>10,.0f}")
    print(f"  {'Total return':<30} {m['total_return_pct']:>+10.2f}%")
    print(f"  {'Annualised return (CAGR)':<30} {m['annualised_return_pct']:>+10.2f}%")
    print(f"  {'─'*48}")
    print(f"  {'Completed trades':<30} {m['num_trades']:>11}")
    print(f"  {'  Wins':<30} {m['num_wins']:>9}   avg {m['avg_win_pct']:>+6.2f}%")
    print(f"  {'  Losses':<30} {m['num_losses']:>9}   avg {m['avg_loss_pct']:>+6.2f}%")
    print(f"  {'Win rate':<30} {m['win_rate_pct']:>10.1f}%")
    print(f"  {'Profit factor':<30} {m['profit_factor']:>11.2f}")
    print(f"  {'─'*48}")
    print(f"  {'Max drawdown':<30} {m['max_drawdown_pct']:>10.2f}%")
    print(f"  {'Max DD duration':<30} {m['max_drawdown_duration_bars']:>8} bars")
    print(f"  {'Sharpe ratio (ann.)':<30} {m['sharpe_ratio']:>11.3f}")
    print(f"  {'Calmar ratio':<30} {m['calmar_ratio']:>11.3f}")
    print(f"{'═'*W}")


def compare_metrics(results: dict) -> dict:
    """
    Compute and print a side-by-side comparison.

    Args:
        results: { label: (equity_list, trades_list) }

    Returns:
        { label: metrics_dict }

    Example:
        compare_metrics({
            "MA Crossover": (ma_equity, ma_trades),
            "LLM Strategy": (llm_equity, llm_trades),
            "Multi-Model":  (mm_equity,  mm_trades),
        })
    """
    computed = {lbl: compute_metrics(eq, tr) for lbl, (eq, tr) in results.items()}
    labels   = list(computed.keys())
    CW       = 13   # column width

    # Higher = better for all except drawdown (lower = better)
    lower_is_better = {"max_drawdown_pct", "num_losses", "max_drawdown_duration_bars"}

    rows = [
        ("Total return %",   "total_return_pct",           "{:>+.1f}%"),
        ("CAGR %",           "annualised_return_pct",       "{:>+.1f}%"),
        ("Win rate %",       "win_rate_pct",                "{:>.1f}%"),
        ("Trades",           "num_trades",                  "{:>}"),
        ("Avg win %",        "avg_win_pct",                 "{:>+.2f}%"),
        ("Avg loss %",       "avg_loss_pct",                "{:>+.2f}%"),
        ("Profit factor",    "profit_factor",               "{:>.2f}"),
        ("Max drawdown %",   "max_drawdown_pct",            "{:>.2f}%"),
        ("Sharpe ratio",     "sharpe_ratio",                "{:>.3f}"),
        ("Calmar ratio",     "calmar_ratio",                "{:>.3f}"),
        ("Final value",      "final",                       "₹{:>,.0f}"),
    ]

    W = 24 + (CW + 4) * len(labels)
    header = f"  {'Metric':<22}" + "".join(f"  {l[:CW]:>{CW}}" for l in labels)

    print(f"\n{'═'*W}")
    print(f"  STRATEGY COMPARISON")
    print(f"{'═'*W}")
    print(header)
    print(f"  {'─'*22}" + f"  {'─'*CW}" * len(labels))

    for row_label, key, fmt in rows:
        vals    = [computed[l][key] for l in labels]
        best_fn = min if key in lower_is_better else max
        try:
            best_val = best_fn(vals)
        except Exception:
            best_val = None

        line = f"  {row_label:<22}"
        for lbl, val in zip(labels, vals):
            cell = fmt.format(val)
            star = " ★" if val == best_val else "  "
            line += f"  {cell:>{CW}}{star}"
        print(line)

    print(f"{'═'*W}")
    return computed


def _empty() -> dict:
    return {k: 0 for k in [
        "initial","final","total_return_pct","annualised_return_pct",
        "num_trades","num_wins","num_losses","win_rate_pct",
        "avg_win_pct","avg_loss_pct","profit_factor",
        "max_drawdown_pct","max_drawdown_duration_bars",
        "sharpe_ratio","calmar_ratio","total_bars",
    ]}


# ── Smoke test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import random
    from datetime import date, timedelta
    random.seed(42)

    def make_equity(n, drift, vol):
        eq = [100000.0]
        for _ in range(n):
            eq.append(eq[-1] * (1 + random.gauss(drift, vol)))
        return eq

    def make_trades(equity, step=20):
        start  = date(2020, 1, 1)
        trades = []
        for i in range(0, len(equity) - step, step):
            trades.append((start + timedelta(days=i),        "BUY",  equity[i]))
            trades.append((start + timedelta(days=i + step), "SELL", equity[i + step]))
        return trades

    eq_ma  = make_equity(1250, 0.0004, 0.010)
    eq_llm = make_equity(1250, 0.0003, 0.008)
    eq_mm  = make_equity(1250, 0.0005, 0.009)

    tr_ma  = make_trades(eq_ma,  step=50)
    tr_llm = make_trades(eq_llm, step=15)
    tr_mm  = make_trades(eq_mm,  step=20)

    print_metrics(compute_metrics(eq_ma, tr_ma),   "MA Crossover")
    print_metrics(compute_metrics(eq_llm, tr_llm), "LLM Strategy")

    compare_metrics({
        "MA Crossover": (eq_ma,  tr_ma),
        "LLM Strategy": (eq_llm, tr_llm),
        "Multi-Model":  (eq_mm,  tr_mm),
    })