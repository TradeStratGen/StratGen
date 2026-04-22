"""
backtest/backtester.py — v3
New: TRAILING STOP-LOSS

How trailing stop works:
  - Once in a trade, track the highest price seen (peak)
  - Stop-loss trails at: peak * (1 - trail_pct)
  - If price never rises: trail_pct acts like a normal stop-loss
  - If price rises 10% then falls 3%: you exit at +7% instead of hitting
    the original -2% stop or waiting for a fixed RSI2>68 exit

Example on a Bullish trade:
  Entry:        ₹22,000   (RSI2 < 20, MACD positive)
  Peak day 5:   ₹23,500   → trail stop now at 23,500 * 0.97 = ₹22,785
  Peak day 12:  ₹24,200   → trail stop now at 24,200 * 0.97 = ₹23,474
  Price day 15: ₹23,400   → hits trail stop → SELL at ₹23,400 = +6.4%

  Old behaviour (fixed TP at 7%): would have waited for ₹23,540 and maybe
  never hit it, then exited on RSI2>68 at ₹22,800 = only +3.6%

Trail percentages per regime (from strategy stop_loss field):
  Bullish:  3.0% trail  (wider — let trend run)
  Volatile: 1.5% trail  (tighter — protect gains fast in choppy market)
  Bearish:  1.2% trail  (very tight — quick reversal trades)
  Neutral:  2.0% trail  (moderate)
"""

from config import INITIAL_CAPITAL, POSITION_SIZE_FRAC
from utils.eval_utils import build_indicator_namespace, evaluate_expression


# Trail percentage = how far price can fall from peak before we exit
# Set per regime based on stop_loss from LLM strategy.
# Wider trail = holds longer = more profit per trade (but more risk).
# Default trail is slightly wider than the stop-loss to allow breathing room.
DEFAULT_TRAIL_PCT = 0.025   # 2.5% trail from peak


class Backtester:
    def __init__(self, df, strategy):
        self.df       = df
        self.strategy = strategy
        self.capital  = INITIAL_CAPITAL
        self.position = 0
        self.entry_price    = 0.0
        self.peak_price     = 0.0    # ← NEW: highest price seen since entry
        self.trail_stop     = 0.0    # ← NEW: current trailing stop price
        self.trades   = []
        self.order_events = []
        self.equity_curve = []

        self._sl_frac    = 0.02
        self._tp_frac    = 0.05
        self._trail_pct  = DEFAULT_TRAIL_PCT

    def run(self):
        for index, row in self.df.iterrows():
            price = float(row["Close"])
            indicator_ns = build_indicator_namespace(row, context="backtester", strict=True)

            # ── Update SL/TP/trail from current strategy ──────────────────
            strat_pre = getattr(self.strategy, "current_strategy", {})
            if strat_pre:
                sl = float(strat_pre.get("stop_loss",   self._sl_frac))
                tp = float(strat_pre.get("take_profit", self._tp_frac))
                self._sl_frac   = sl
                self._tp_frac   = tp
                # Trail is set to SL width — gives the same downside protection
                # but from the PEAK price, not just the entry price
                self._trail_pct = sl

            # ── In a position: update peak and check exits ─────────────────
            if self.position > 0:

                # Update peak price and trailing stop
                if price > self.peak_price:
                    self.peak_price = price
                    self.trail_stop = self.peak_price * (1 - self._trail_pct)

                # 1. Trailing stop hit (price fell too far from peak)
                if price <= self.trail_stop:
                    sell_qty = self.position
                    proceeds         = self.position * price
                    self.capital    += proceeds
                    gain_pct         = (price - self.entry_price) / self.entry_price * 100
                    self.trades.append((index, "SELL-TRAIL", price))
                    self._record_order_event(index, "SELL", "SELL-TRAIL", price, sell_qty, row, strat_pre)
                    self._reset_position()
                    self.equity_curve.append(self.capital)
                    continue

                # 2. Hard stop-loss (price below entry, trailing stop not yet set)
                #    This only fires in the first few bars before price moves up at all
                hard_sl = self.entry_price * (1 - self._sl_frac)
                if price <= hard_sl:
                    sell_qty = self.position
                    proceeds         = self.position * price
                    self.capital    += proceeds
                    self.trades.append((index, "SELL-SL", price))
                    self._record_order_event(index, "SELL", "SELL-SL", price, sell_qty, row, strat_pre)
                    self._reset_position()
                    self.equity_curve.append(self.capital)
                    continue

                # 3. Take-profit: remove hard cap — let trailing stop do the work
                #    Only use TP as a safety ceiling (2x the original TP)
                #    This allows riding trends much further than before
                safety_tp = self.entry_price * (1 + self._tp_frac * 2)
                if price >= safety_tp:
                    sell_qty = self.position
                    proceeds         = self.position * price
                    self.capital    += proceeds
                    self.trades.append((index, "SELL-TP", price))
                    self._record_order_event(index, "SELL", "SELL-TP", price, sell_qty, row, strat_pre)
                    self._reset_position()
                    self.equity_curve.append(self.capital)
                    continue

            # ── Strategy signal ───────────────────────────────────────────
            signal = self.strategy.generate_signal(row)
            strat = getattr(self.strategy, "current_strategy", {})
            if strat:
                evaluate_expression(strat.get("entry_condition", "False"), indicator_ns, context="backtester")
                evaluate_expression(strat.get("exit_condition", "False"), indicator_ns, context="backtester")

            if signal == "BUY" and self.position == 0:
                invest           = self.capital * POSITION_SIZE_FRAC
                self.position    = invest / price
                self.capital    -= invest
                self.entry_price = price
                self.peak_price  = price                           # ← reset peak
                self.trail_stop  = price * (1 - self._trail_pct)  # ← initial trail
                self.trades.append((index, "BUY", price))
                self._record_order_event(index, "BUY", "BUY", price, self.position, row, strat)

            elif signal == "SELL" and self.position > 0:
                sell_qty = self.position
                proceeds         = self.position * price
                self.capital    += proceeds
                self.trades.append((index, "SELL", price))
                self._record_order_event(index, "SELL", "SELL", price, sell_qty, row, strat)
                self._reset_position()

            total = self.capital + (self.position * price)
            self.equity_curve.append(total)

        return self.equity_curve, self.trades

    def _reset_position(self):
        self.position    = 0
        self.entry_price = 0.0
        self.peak_price  = 0.0
        self.trail_stop  = 0.0

    def _record_order_event(self, index, action, raw_action, price, quantity, row, strat):
        regime = "Unknown"
        try:
            regime = str(row.get("regime", "Unknown"))
        except Exception:
            pass

        strategy_payload = {
            "entry_condition": (strat or {}).get("entry_condition"),
            "stop_loss": float((strat or {}).get("stop_loss", self._sl_frac)),
            "take_profit": float((strat or {}).get("take_profit", self._tp_frac)),
            "reasoning": (strat or {}).get("reasoning", ""),
            "source": str((strat or {}).get("source", "fallback") or "fallback"),
            "raw_action": raw_action,
        }

        self.order_events.append(
            {
                "timestamp": index,
                "action": action,
                "raw_action": raw_action,
                "price": float(price),
                "quantity": float(quantity),
                "regime": regime,
                "strategy": strategy_payload,
            }
        )
