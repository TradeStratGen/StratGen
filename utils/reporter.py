"""
utils/reporter.py

Saves daily signal reports and order logs with structured naming:
  logs/
    signals/
      signal_Volatile_2026-04-18.json      ← one per day
    orders/
      order_BUY_Volatile_2026-04-18.json   ← one per trade action
    reports/
      report_2026-04-18.json               ← full daily report
    weekly/
      week_2026-W16.json                   ← auto-aggregated weekly

Usage:
    from utils.reporter import DailyReporter
    reporter = DailyReporter()
    reporter.log_signal(regime, signal, strategy, indicators)
    reporter.log_order(action, price, regime, strategy)
    reporter.save_daily_report(ma_metrics, llm_metrics, strategies)
"""

import json
import os
import datetime
from pathlib import Path


class DailyReporter:
    def __init__(self, log_dir: str = "logs"):
        self.today    = datetime.date.today().isoformat()
        self.now      = datetime.datetime.now().isoformat()
        self.log_dir  = Path(log_dir)

        # Create directory structure
        for sub in ["signals", "orders", "reports", "weekly"]:
            (self.log_dir / sub).mkdir(parents=True, exist_ok=True)

    # ── Signal log ────────────────────────────────────────────────────────

    def log_signal(
        self,
        regime:     str,
        signal:     str,          # BUY / SELL / HOLD
        strategy:   dict,
        indicators: dict,
    ) -> Path:
        """
        Save today's signal with full context.
        File: logs/signals/signal_{regime}_{date}.json
        """
        payload = {
            "timestamp":  self.now,
            "date":       self.today,
            "regime":     regime,
            "signal":     signal,
            "strategy_source": str(strategy.get("source", "fallback") or "fallback"),
            "strategy": {
                "entry_condition": strategy.get("entry_condition"),
                "exit_condition":  strategy.get("exit_condition"),
                "stop_loss":       strategy.get("stop_loss"),
                "take_profit":     strategy.get("take_profit"),
                "reasoning":       strategy.get("reasoning", ""),
                "source":          str(strategy.get("source", "fallback") or "fallback"),
            },
            "indicators": indicators,
        }

        path = self.log_dir / "signals" / f"signal_{regime}_{self.today}.json"
        self._write(path, payload)
        print(f"[Reporter] Signal saved → {path}")
        return path

    # ── Order log ─────────────────────────────────────────────────────────

    @staticmethod
    def _normalize_source_tag(source: str) -> str:
        raw = str(source or "").strip().lower()
        if not raw:
            return "unknown"
        if raw == "live":
            return "live-llm"
        return raw

    def log_order(
        self,
        action:    str,           # BUY / SELL — HOLD is silently ignored
        price:     float,
        regime:    str,
        strategy:  dict,
        quantity:  int = 1,
        source:    str = "paper", # paper / dhan / backtest
        broker_status: str = "success",
        dhan_response: dict = None,
        timestamp: str = "",
        date: str = "",
        file_suffix: str = "",
    ) -> Path | None:
        """
        Save a trade order. HOLD signals are NOT logged as orders.
        File: logs/orders/order_{action}_{regime}_{date}_{hhmm}.json
        Timestamp suffix prevents same-day overwrites for multiple trades.
        """
        # Do not log HOLD as an order — it is a decision, not an execution
        if action == "HOLD":
            return None

        ts_out = timestamp or self.now
        dt_out = date or self.today

        payload = {
            "timestamp":     ts_out,
            "date":          dt_out,
            "action":        action,
            "regime":        regime,
            "price":         price,
            "quantity":      quantity,
            "source":        self._normalize_source_tag(source),
            "broker_status": str(broker_status or "unknown").strip().lower() or "unknown",
            "strategy_source": str(strategy.get("source", "fallback") or "fallback"),
            "stop_loss_pct": strategy.get("stop_loss", 0),
            "take_profit_pct": strategy.get("take_profit", 0),
            "stop_loss_price":   round(price * (1 - strategy.get("stop_loss", 0)), 2),
            "take_profit_price": round(price * (1 + strategy.get("take_profit", 0)), 2),
            "entry_condition": strategy.get("entry_condition"),
            "reasoning":     strategy.get("reasoning", ""),
            "dhan_response": dhan_response or {},
        }

        safe_regime = str(regime).replace("/", "-").replace(" ", "_")
        base = f"order_{action}_{safe_regime}_{dt_out}"

        if file_suffix:
            path = self.log_dir / "orders" / f"{base}_{file_suffix}.json"
        else:
            hhmm = datetime.datetime.now().strftime("%H%M")
            path = self.log_dir / "orders" / f"{base}_{hhmm}.json"

        self._write(path, payload)
        print(f"[Reporter] Order saved → {path}")
        return path

    def export_backtest_orders(
        self,
        order_events: list,
        source: str = "backtest",
        run_tag: str = "",
    ) -> int:
        """
        Export backtest BUY/SELL events into logs/orders using existing order JSON schema.
        """
        if not order_events:
            return 0

        written = 0
        for i, event in enumerate(order_events):
            action = str(event.get("action", "")).upper()
            if action not in ("BUY", "SELL"):
                continue

            ts = event.get("timestamp")
            ts_text = str(ts)
            date_text = self.today
            time_part = f"{i:06d}"

            try:
                dt_obj = datetime.datetime.fromisoformat(ts_text.replace("Z", "+00:00"))
                date_text = dt_obj.date().isoformat()
                time_part = dt_obj.strftime("%H%M%S")
            except Exception:
                pass

            suffix = f"{time_part}_{i:03d}"
            if run_tag:
                suffix = f"{run_tag}_{suffix}"

            strategy = event.get("strategy", {}) or {}
            self.log_order(
                action=action,
                price=float(event.get("price", 0.0)),
                regime=str(event.get("regime", "Unknown")),
                strategy=strategy,
                quantity=float(event.get("quantity", 1.0)),
                source=source,
                broker_status="success",
                dhan_response={},
                timestamp=ts_text,
                date=date_text,
                file_suffix=suffix,
            )
            written += 1

        return written

    # ── Daily report ──────────────────────────────────────────────────────

    def save_daily_report(
        self,
        ma_metrics:   dict,
        llm_metrics:  dict,
        strategies:   dict,
        winner_model: str = "",
        today_signal: str = "",
        today_regime: str = "",
    ) -> Path:
        """
        Full daily report combining backtest results + today's signal.
        File: logs/reports/report_{date}.json
        """
        payload = {
            "timestamp":   self.now,
            "date":        self.today,
            "today_signal": today_signal,
            "today_regime": today_regime,
            "winner_model": winner_model,
            "strategies":  strategies,
            "backtest": {
                "ma_crossover": ma_metrics,
                "llm_multi_model": llm_metrics,
            },
            "summary": {
                "llm_return":    llm_metrics.get("total_return_pct", 0),
                "llm_win_rate":  llm_metrics.get("win_rate_pct", 0),
                "llm_max_dd":    llm_metrics.get("max_drawdown_pct", 0),
                "llm_sharpe":    llm_metrics.get("sharpe_ratio", 0),
                "llm_trades":    llm_metrics.get("num_trades", 0),
                "ma_return":     ma_metrics.get("total_return_pct", 0),
            },
        }

        path = self.log_dir / "reports" / f"report_{self.today}.json"
        self._write(path, payload)
        print(f"[Reporter] Daily report saved → {path}")

        # Auto-aggregate into weekly file
        self._update_weekly(payload)
        return path

    # ── Weekly aggregation ────────────────────────────────────────────────

    def _update_weekly(self, daily_payload: dict):
        """Append today's summary to the current ISO week file."""
        week_num  = datetime.date.today().isocalendar()[1]
        year      = datetime.date.today().year
        week_key  = f"{year}-W{week_num:02d}"
        path      = self.log_dir / "weekly" / f"week_{week_key}.json"

        weekly = []
        if path.exists():
            try:
                weekly = json.loads(path.read_text())
            except Exception:
                weekly = []

        # Avoid duplicate entries for the same date
        weekly = [w for w in weekly if w.get("date") != self.today]
        weekly.append({
            "date":         self.today,
            "signal":       daily_payload.get("today_signal"),
            "regime":       daily_payload.get("today_regime"),
            "llm_return":   daily_payload["summary"]["llm_return"],
            "llm_win_rate": daily_payload["summary"]["llm_win_rate"],
            "ma_return":    daily_payload["summary"]["ma_return"],
            "winner_model": daily_payload.get("winner_model"),
        })

        self._write(path, weekly)
        print(f"[Reporter] Weekly log updated → {path}")

    # ── Trade history ─────────────────────────────────────────────────────

    def load_all_orders(self) -> list:
        """Load all order files sorted by date. Useful for P&L summary."""
        orders_dir = self.log_dir / "orders"
        orders = []
        for f in sorted(orders_dir.glob("order_*.json")):
            try:
                orders.append(json.loads(f.read_text()))
            except Exception:
                pass
        return orders

    def print_trade_history(self):
        """Print all logged paper trades in a readable table."""
        orders = self.load_all_orders()
        if not orders:
            print("[Reporter] No orders logged yet.")
            return

        print(f"\n{'═'*70}")
        print(f"  PAPER TRADE HISTORY  ({len(orders)} orders)")
        print(f"{'═'*70}")
        print(f"  {'Date':<12} {'Action':<6} {'Regime':<10} {'Price':>10} {'Source':<8}")
        print(f"  {'─'*12} {'─'*6} {'─'*10} {'─'*10} {'─'*8}")
        for o in orders:
            print(f"  {o['date']:<12} {o['action']:<6} {o['regime']:<10} "
                  f"₹{o['price']:>9,.2f} {o['source']:<8}")
        print(f"{'═'*70}\n")

    # ── Internal ──────────────────────────────────────────────────────────

    @staticmethod
    def _write(path: Path, data):
        path.write_text(json.dumps(data, indent=2, default=str))