"""
backtest/backtester.py — v2
Key improvements over v1:
  1. Position sizing: trades POSITION_SIZE_FRAC of capital (not all-in)
  2. Stop-loss actually EXECUTED: if price drops below entry * (1 - sl), sell
  3. Take-profit EXECUTED: if price rises above entry * (1 + tp), sell
  4. Remaining capital earns nothing (cash), but multiple positions could overlap
     if position sizing < 1.0
"""
from config import INITIAL_CAPITAL, POSITION_SIZE_FRAC


class Backtester:
    def __init__(self, df, strategy):
        self.df       = df
        self.strategy = strategy
        self.capital  = INITIAL_CAPITAL
        self.position = 0        # shares held
        self.entry_price = 0     # price at which we bought
        self.trades   = []
        self.equity_curve = []

        # Pull SL/TP from strategy if available (LLMStrategy stores them)
        self._sl_frac = 0.02     # default 2% stop-loss
        self._tp_frac = 0.05     # default 5% take-profit

    def run(self):
        for index, row in self.df.iterrows():
            price = float(row["Close"])

            # ── Update SL/TP from current strategy if available ───────────
            strat = getattr(self.strategy, "current_strategy", {})
            if strat:
                self._sl_frac = float(strat.get("stop_loss",   self._sl_frac))
                self._tp_frac = float(strat.get("take_profit", self._tp_frac))

            # ── Check stop-loss and take-profit BEFORE signal ─────────────
            if self.position > 0:
                sl_price = self.entry_price * (1 - self._sl_frac)
                tp_price = self.entry_price * (1 + self._tp_frac)

                if price <= sl_price:
                    # Stop-loss triggered
                    proceeds        = self.position * price
                    self.capital   += proceeds
                    self.trades.append((index, "SELL-SL", price))
                    self.position   = 0
                    self.entry_price = 0
                    self.equity_curve.append(self.capital)
                    continue

                if price >= tp_price:
                    # Take-profit triggered
                    proceeds        = self.position * price
                    self.capital   += proceeds
                    self.trades.append((index, "SELL-TP", price))
                    self.position   = 0
                    self.entry_price = 0
                    self.equity_curve.append(self.capital)
                    continue

            # ── Strategy signal ───────────────────────────────────────────
            signal = self.strategy.generate_signal(row)

            if signal == "BUY" and self.position == 0:
                # Invest only POSITION_SIZE_FRAC of current capital
                invest          = self.capital * POSITION_SIZE_FRAC
                self.position   = invest / price
                self.capital   -= invest
                self.entry_price = price
                self.trades.append((index, "BUY", price))

            elif signal in ("SELL", "SELL-SL", "SELL-TP") and self.position > 0:
                proceeds        = self.position * price
                self.capital   += proceeds
                self.trades.append((index, "SELL", price))
                self.position   = 0
                self.entry_price = 0

            total = self.capital + (self.position * price)
            self.equity_curve.append(total)

        return self.equity_curve, self.trades