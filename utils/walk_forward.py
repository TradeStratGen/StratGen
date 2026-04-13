"""
utils/walk_forward.py — v2
Fixed: primes on train split, tests on test split (full consecutive rows).
Uses the same MultiModelStrategy architecture.
"""
from backtest.backtester import Backtester
from utils.metrics import compute_metrics


def walk_forward_test(
    df,
    strategy_factory,
    train_frac: float = 0.7,
    n_splits:   int   = 3,
    verbose:    bool  = True,
) -> list:
    """
    Walk-forward validation.

    Args:
        df:               Full df with indicators + regime.
        strategy_factory: Zero-arg callable returning a fresh strategy with .prime(df).
        train_frac:       Fraction of each window for training.
        n_splits:         Number of windows.

    Returns:
        List of result dicts per split.
    """
    n      = len(df)
    window = n // n_splits
    results = []

    print(f"\n[WalkForward] {n_splits} splits  window={window} bars  train={train_frac:.0%}")
    print()

    for i in range(n_splits):
        start    = i * window
        end      = start + window if i < n_splits - 1 else n
        split_df = df.iloc[start:end].copy()

        train_n  = int(len(split_df) * train_frac)
        train_df = split_df.iloc[:train_n]
        test_df  = split_df.iloc[train_n:]

        if len(test_df) < 30:
            print(f"  Split {i+1}: test window too small ({len(test_df)} bars), skipping")
            continue

        print(f"  Split {i+1}: train {train_df.index[0].date()} → {train_df.index[-1].date()} "
              f"({len(train_df)} bars)  |  "
              f"test {test_df.index[0].date()} → {test_df.index[-1].date()} "
              f"({len(test_df)} bars)")

        strategy = strategy_factory()
        try:
            strategy.prime(train_df, pause_seconds=0)
        except Exception as e:
            print(f"  Split {i+1}: prime failed — {e}")
            continue

        bt             = Backtester(test_df, strategy)
        equity, trades = bt.run()
        m              = compute_metrics(equity, trades)

        result = {
            "split":      i + 1,
            "test_start": test_df.index[0].date(),
            "test_end":   test_df.index[-1].date(),
            "return":     m["total_return_pct"],
            "win_rate":   m["win_rate_pct"],
            "sharpe":     m["sharpe_ratio"],
            "max_dd":     m["max_drawdown_pct"],
            "trades":     m["num_trades"],
        }
        results.append(result)

        if verbose:
            print(f"           return={result['return']:+.1f}%  "
                  f"trades={result['trades']}  "
                  f"win={result['win_rate']:.0f}%  "
                  f"sharpe={result['sharpe']:.2f}  "
                  f"maxDD={result['max_dd']:.1f}%")

    if results:
        avg_r  = sum(r["return"]   for r in results) / len(results)
        avg_sh = sum(r["sharpe"]   for r in results) / len(results)
        avg_wr = sum(r["win_rate"] for r in results) / len(results)
        good   = sum(1 for r in results if r["return"] > 0)

        print(f"\n[WalkForward] Summary across {len(results)} splits:")
        print(f"  Avg return : {avg_r:+.1f}%")
        print(f"  Avg Sharpe : {avg_sh:.2f}")
        print(f"  Avg win    : {avg_wr:.0f}%")
        print(f"  Profitable : {good}/{len(results)}")
        verdict = "✓ Consistent" if good == len(results) else f"⚠ Failed {len(results)-good}/{len(results)} splits"
        print(f"  Verdict    : {verdict}")

    return results