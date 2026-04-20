"""
Log-driven Streamlit dashboard for StratGen.

Reads analytics directly from:
  logs/signals/
  logs/orders/
  logs/reports/
  logs/weekly/

Run:
  streamlit run dashboard/app.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from config import INITIAL_CAPITAL, RISK_FREE_RATE
except Exception:
    INITIAL_CAPITAL = 100000
    RISK_FREE_RATE = 0.065

LOGS_DIR = ROOT_DIR / "logs"
SIGNALS_DIR = LOGS_DIR / "signals"
ORDERS_DIR = LOGS_DIR / "orders"
REPORTS_DIR = LOGS_DIR / "reports"
WEEKLY_DIR = LOGS_DIR / "weekly"
LEGACY_SIGNALS_FILE = ROOT_DIR / "signals.json"


st.set_page_config(
    page_title="StratGen Dashboard",
    page_icon="📊",
    layout="wide",
)

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.2rem; padding-bottom: 1.5rem;}
    [data-testid="stMetricValue"] {font-size: 1.5rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


def _safe_read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _to_timestamp(value: Any) -> pd.Timestamp:
    return pd.to_datetime(value, errors="coerce")


def _to_numeric(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _normalize_source(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return "unknown"
    if raw == "live":
        return "live-llm"
    if raw in {"backtest-ma", "backtest-mm", "live-llm", "unknown"}:
        return raw
    return raw


def _ordered_sources(source_values: list[str]) -> list[str]:
    canonical = ["backtest-ma", "backtest-mm", "live-llm", "unknown"]
    extras = [s for s in source_values if s not in canonical]
    return [s for s in canonical if s in source_values] + sorted(extras)


@st.cache_data(ttl=60)
def load_signal_logs() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for file_path in sorted(SIGNALS_DIR.glob("signal_*.json")):
        payload = _safe_read_json(file_path)
        if not isinstance(payload, dict):
            continue

        indicators = payload.get("indicators", {}) or {}
        rows.append(
            {
                "source_file": file_path.name,
                "timestamp": _to_timestamp(payload.get("timestamp")),
                "date": _to_timestamp(payload.get("date")).date() if pd.notna(_to_timestamp(payload.get("date"))) else None,
                "regime": str(payload.get("regime", "Unknown")),
                "signal": str(payload.get("signal", "UNKNOWN")).upper(),
                "strategy_source": str(payload.get("strategy_source", (payload.get("strategy", {}) or {}).get("source", "unknown")) or "unknown"),
                "close": _to_numeric(indicators.get("Close", payload.get("close", 0.0))),
                "entry_condition": (payload.get("strategy", {}) or {}).get("entry_condition", ""),
                "exit_condition": (payload.get("strategy", {}) or {}).get("exit_condition", ""),
                "reasoning": (payload.get("strategy", {}) or {}).get("reasoning", ""),
            }
        )

    if LEGACY_SIGNALS_FILE.exists():
        legacy_payload = _safe_read_json(LEGACY_SIGNALS_FILE)
        if isinstance(legacy_payload, list):
            for item in legacy_payload:
                if not isinstance(item, dict):
                    continue
                rows.append(
                    {
                        "source_file": LEGACY_SIGNALS_FILE.name,
                        "timestamp": _to_timestamp(item.get("timestamp")),
                        "date": _to_timestamp(item.get("date")).date() if pd.notna(_to_timestamp(item.get("date"))) else None,
                        "regime": str(item.get("regime", "Unknown")),
                        "signal": str(item.get("signal", "UNKNOWN")).upper(),
                        "strategy_source": str(item.get("strategy_source", (item.get("strategy", {}) or {}).get("source", "unknown")) or "unknown"),
                        "close": _to_numeric(item.get("close", 0.0)),
                        "entry_condition": (item.get("strategy", {}) or {}).get("entry_condition", ""),
                        "exit_condition": (item.get("strategy", {}) or {}).get("exit_condition", ""),
                        "reasoning": (item.get("strategy", {}) or {}).get("reasoning", ""),
                    }
                )

    if not rows:
        return pd.DataFrame(
            columns=[
                "source_file",
                "timestamp",
                "date",
                "regime",
                "signal",
                "strategy_source",
                "close",
                "entry_condition",
                "exit_condition",
                "reasoning",
            ]
        )

    df = pd.DataFrame(rows)
    df = df.dropna(subset=["date"])
    df = df.drop_duplicates(subset=["timestamp", "date", "regime", "signal", "source_file"], keep="last")
    return df.sort_values(["date", "timestamp"], ascending=[True, True]).reset_index(drop=True)


@st.cache_data(ttl=60)
def load_order_logs() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for file_path in sorted(ORDERS_DIR.glob("order_*.json")):
        payload = _safe_read_json(file_path)
        if not isinstance(payload, dict):
            continue

        action = str(payload.get("action", "UNKNOWN")).upper()
        quantity = _to_numeric(payload.get("quantity", 1), default=1.0)
        if quantity <= 0:
            quantity = 1.0

        date_parsed = _to_timestamp(payload.get("date"))
        timestamp = _to_timestamp(payload.get("timestamp"))

        rows.append(
            {
                "source_file": file_path.name,
                "timestamp": timestamp if pd.notna(timestamp) else date_parsed,
                "date": date_parsed.date() if pd.notna(date_parsed) else None,
                "action": action,
                "regime": str(payload.get("regime", "Unknown")),
                "price": _to_numeric(payload.get("price", 0.0)),
                "quantity": quantity,
                "source": _normalize_source(payload.get("source", "unknown")),
                "strategy_source": str(payload.get("strategy_source", "unknown") or "unknown").strip() or "unknown",
                "stop_loss_pct": _to_numeric(payload.get("stop_loss_pct", 0.0)),
                "take_profit_pct": _to_numeric(payload.get("take_profit_pct", 0.0)),
            }
        )

    if not rows:
        return pd.DataFrame(
            columns=[
                "source_file",
                "timestamp",
                "date",
                "action",
                "regime",
                "price",
                "quantity",
                "source",
                "strategy_source",
                "stop_loss_pct",
                "take_profit_pct",
            ]
        )

    df = pd.DataFrame(rows)
    df = df.dropna(subset=["date"])
    return df.sort_values(["timestamp", "date"], ascending=[True, True]).reset_index(drop=True)


@st.cache_data(ttl=60)
def load_report_logs() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for file_path in sorted(REPORTS_DIR.glob("report_*.json")):
        payload = _safe_read_json(file_path)
        if not isinstance(payload, dict):
            continue
        rows.append(
            {
                "source_file": file_path.name,
                "date": _to_timestamp(payload.get("date")).date() if pd.notna(_to_timestamp(payload.get("date"))) else None,
                "today_signal": payload.get("today_signal", ""),
                "today_regime": payload.get("today_regime", ""),
                "winner_model": payload.get("winner_model", ""),
                "llm_return": _to_numeric((payload.get("summary", {}) or {}).get("llm_return", 0.0)),
                "llm_win_rate": _to_numeric((payload.get("summary", {}) or {}).get("llm_win_rate", 0.0)),
                "llm_max_dd": _to_numeric((payload.get("summary", {}) or {}).get("llm_max_dd", 0.0)),
                "llm_sharpe": _to_numeric((payload.get("summary", {}) or {}).get("llm_sharpe", 0.0)),
                "llm_trades": _to_numeric((payload.get("summary", {}) or {}).get("llm_trades", 0.0)),
            }
        )

    if not rows:
        return pd.DataFrame(
            columns=[
                "source_file",
                "date",
                "today_signal",
                "today_regime",
                "winner_model",
                "llm_return",
                "llm_win_rate",
                "llm_max_dd",
                "llm_sharpe",
                "llm_trades",
            ]
        )

    df = pd.DataFrame(rows)
    df = df.dropna(subset=["date"])
    return df.sort_values("date").reset_index(drop=True)


@st.cache_data(ttl=60)
def load_weekly_logs() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for file_path in sorted(WEEKLY_DIR.glob("week_*.json")):
        payload = _safe_read_json(file_path)
        if not isinstance(payload, list):
            continue
        for item in payload:
            if not isinstance(item, dict):
                continue
            rows.append(
                {
                    "source_file": file_path.name,
                    "date": _to_timestamp(item.get("date")).date() if pd.notna(_to_timestamp(item.get("date"))) else None,
                    "signal": str(item.get("signal", "")).upper(),
                    "regime": str(item.get("regime", "")),
                    "llm_return": _to_numeric(item.get("llm_return", 0.0)),
                    "llm_win_rate": _to_numeric(item.get("llm_win_rate", 0.0)),
                    "ma_return": _to_numeric(item.get("ma_return", 0.0)),
                    "winner_model": str(item.get("winner_model", "")),
                }
            )

    if not rows:
        return pd.DataFrame(
            columns=[
                "source_file",
                "date",
                "signal",
                "regime",
                "llm_return",
                "llm_win_rate",
                "ma_return",
                "winner_model",
            ]
        )

    df = pd.DataFrame(rows)
    df = df.dropna(subset=["date"])
    return df.sort_values("date").reset_index(drop=True)


def apply_common_filters(
    df: pd.DataFrame,
    date_col: str,
    start_date,
    end_date,
    regime: str,
    regime_col: str,
    signal_value: str,
    signal_col: str,
    source_values: list[str] | None = None,
    source_col: str = "source",
) -> pd.DataFrame:
    if df.empty:
        return df

    filtered = df.copy()
    filtered = filtered[(filtered[date_col] >= start_date) & (filtered[date_col] <= end_date)]

    if regime != "All":
        filtered = filtered[filtered[regime_col] == regime]

    if signal_value != "All":
        filtered = filtered[filtered[signal_col] == signal_value]

    if source_col in filtered.columns and source_values:
        selected = [s for s in source_values if s and s != "All"]
        if selected:
            filtered = filtered[filtered[source_col].isin(selected)]

    return filtered


def build_closed_trades(orders_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, float, float]:
    if orders_df.empty:
        return pd.DataFrame(), pd.DataFrame(), 0.0, 0.0

    trade_orders = orders_df[orders_df["action"].isin(["BUY", "SELL"])].copy()
    trade_orders = trade_orders.sort_values(["timestamp", "date"]).reset_index(drop=True)

    open_lots: list[dict[str, Any]] = []
    closed_rows: list[dict[str, Any]] = []
    unmatched_sell_qty = 0.0

    for row in trade_orders.itertuples(index=False):
        action = row.action
        quantity = float(row.quantity)

        if action == "BUY":
            open_lots.append(
                {
                    "entry_timestamp": row.timestamp,
                    "entry_date": row.date,
                    "entry_price": float(row.price),
                    "qty_remaining": quantity,
                    "entry_regime": row.regime,
                    "entry_source": row.source,
                    "entry_strategy_source": str(getattr(row, "strategy_source", "unknown") or "unknown"),
                }
            )
            continue

        if action == "SELL":
            qty_to_close = quantity

            while qty_to_close > 0 and open_lots:
                lot = open_lots[0]
                matched_qty = min(qty_to_close, lot["qty_remaining"])

                entry_price = float(lot["entry_price"])
                exit_price = float(row.price)
                pnl_abs = (exit_price - entry_price) * matched_qty
                pnl_pct = ((exit_price - entry_price) / entry_price * 100.0) if entry_price else 0.0

                closed_rows.append(
                    {
                        "entry_date": lot["entry_date"],
                        "exit_date": row.date,
                        "entry_timestamp": lot["entry_timestamp"],
                        "exit_timestamp": row.timestamp,
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "quantity": matched_qty,
                        "pnl": pnl_abs,
                        "pnl_pct": pnl_pct,
                        "entry_regime": lot["entry_regime"],
                        "exit_regime": row.regime,
                        "entry_source": lot["entry_source"],
                        "exit_source": row.source,
                        "entry_strategy_source": lot.get("entry_strategy_source", "unknown"),
                        "exit_strategy_source": str(getattr(row, "strategy_source", "unknown") or "unknown"),
                        "result": "WIN" if pnl_abs > 0 else ("LOSS" if pnl_abs < 0 else "FLAT"),
                    }
                )

                lot["qty_remaining"] -= matched_qty
                qty_to_close -= matched_qty

                if lot["qty_remaining"] <= 0:
                    open_lots.pop(0)

            if qty_to_close > 0:
                unmatched_sell_qty += qty_to_close

    open_qty = sum(lot["qty_remaining"] for lot in open_lots)

    open_positions = pd.DataFrame(open_lots) if open_lots else pd.DataFrame()
    if not open_positions.empty:
        open_positions = open_positions.rename(columns={"qty_remaining": "quantity"})
        open_positions = open_positions[
            ["entry_date", "entry_timestamp", "entry_price", "quantity", "entry_regime", "entry_source", "entry_strategy_source"]
        ].reset_index(drop=True)

    if not closed_rows:
        return pd.DataFrame(), open_positions, open_qty, unmatched_sell_qty

    trades = pd.DataFrame(closed_rows)
    trades = trades.sort_values("exit_timestamp").reset_index(drop=True)
    return trades, open_positions, open_qty, unmatched_sell_qty


def get_latest_price_from_logs(signals_df: pd.DataFrame, orders_df: pd.DataFrame) -> float:
    latest_signal_price = None
    latest_order_price = None

    if not signals_df.empty:
        priced_signals = signals_df.dropna(subset=["timestamp"]).copy()
        priced_signals = priced_signals[priced_signals["close"] > 0]
        if not priced_signals.empty:
            latest_signal_price = float(priced_signals.sort_values("timestamp").iloc[-1]["close"])

    if not orders_df.empty:
        priced_orders = orders_df.dropna(subset=["timestamp"]).copy()
        priced_orders = priced_orders[priced_orders["price"] > 0]
        if not priced_orders.empty:
            latest_order_price = float(priced_orders.sort_values("timestamp").iloc[-1]["price"])

    if latest_signal_price is not None:
        return latest_signal_price
    if latest_order_price is not None:
        return latest_order_price
    return 0.0


def compute_unrealized_pnl(open_positions: pd.DataFrame, latest_price: float) -> tuple[float, pd.DataFrame]:
    if open_positions.empty or latest_price <= 0:
        return 0.0, pd.DataFrame()

    marked = open_positions.copy()
    marked["latest_price"] = float(latest_price)
    marked["unrealized_pnl"] = (marked["latest_price"] - marked["entry_price"]) * marked["quantity"]
    marked["unrealized_pnl_pct"] = (marked["latest_price"] / marked["entry_price"] - 1.0) * 100.0

    total_unrealized = float(marked["unrealized_pnl"].sum())
    return total_unrealized, marked


def compute_advanced_metrics(closed_trades: pd.DataFrame, daily_df: pd.DataFrame) -> dict[str, float]:
    if closed_trades.empty:
        gross_profit = 0.0
        gross_loss = 0.0
        avg_win = 0.0
        avg_loss = 0.0
    else:
        wins = closed_trades[closed_trades["pnl"] > 0]
        losses = closed_trades[closed_trades["pnl"] < 0]

        gross_profit = float(wins["pnl"].sum()) if not wins.empty else 0.0
        gross_loss = abs(float(losses["pnl"].sum())) if not losses.empty else 0.0
        avg_win = float(wins["pnl_pct"].mean()) if not wins.empty else 0.0
        avg_loss = float(losses["pnl_pct"].mean()) if not losses.empty else 0.0

    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)

    sharpe_ratio = 0.0
    calmar_ratio = 0.0

    if not daily_df.empty and "total_equity" in daily_df.columns:
        equity = daily_df["total_equity"].astype(float)
        if len(equity) > 1 and float(equity.iloc[0]) > 0:
            daily_returns = equity.pct_change().replace([float("inf"), float("-inf")], pd.NA).dropna()

            if len(daily_returns) > 1:
                mean_ret = float(daily_returns.mean())
                std_ret = float(daily_returns.std(ddof=1))
                daily_rf = float(RISK_FREE_RATE) / 252.0
                if std_ret > 0:
                    sharpe_ratio = ((mean_ret - daily_rf) / std_ret) * (252.0 ** 0.5)

            n = len(daily_returns)
            if n > 0:
                total_return = float(equity.iloc[-1] / equity.iloc[0]) - 1.0
                annualized_return = (1.0 + total_return) ** (252.0 / n) - 1.0 if (1.0 + total_return) > 0 else -1.0
                max_dd_decimal = abs(float(daily_df["drawdown_pct"].min())) / 100.0 if "drawdown_pct" in daily_df.columns else 0.0
                if max_dd_decimal > 0:
                    calmar_ratio = annualized_return / max_dd_decimal

    return {
        "sharpe_ratio": float(sharpe_ratio),
        "calmar_ratio": float(calmar_ratio),
        "profit_factor": float(profit_factor),
        "avg_win_pct": float(avg_win),
        "avg_loss_pct": float(avg_loss),
    }


def compute_regime_performance(closed_trades: pd.DataFrame, group_by: str) -> pd.DataFrame:
    if closed_trades.empty:
        return pd.DataFrame(columns=["regime", "total_pnl", "trades", "wins", "win_rate_pct", "avg_pnl_per_trade"])

    if group_by not in {"entry_regime", "exit_regime"}:
        group_by = "entry_regime"

    grouped = (
        closed_trades.groupby(group_by, dropna=False)
        .agg(
            total_pnl=("pnl", "sum"),
            trades=("pnl", "count"),
            wins=("result", lambda x: (x == "WIN").sum()),
        )
        .reset_index()
        .rename(columns={group_by: "regime"})
    )

    grouped["regime"] = grouped["regime"].fillna("Unknown")
    grouped["win_rate_pct"] = grouped.apply(
        lambda row: (float(row["wins"]) / float(row["trades"]) * 100.0) if float(row["trades"]) > 0 else 0.0,
        axis=1,
    )
    grouped["avg_pnl_per_trade"] = grouped.apply(
        lambda row: (float(row["total_pnl"]) / float(row["trades"])) if float(row["trades"]) > 0 else 0.0,
        axis=1,
    )

    return grouped.sort_values("total_pnl", ascending=False).reset_index(drop=True)


def compute_source_performance(orders_df: pd.DataFrame) -> pd.DataFrame:
    if orders_df.empty or "source" not in orders_df.columns:
        return pd.DataFrame(columns=["source", "total_pnl", "trades", "wins", "win_rate_pct"])

    rows: list[dict[str, Any]] = []
    for source_name in sorted(orders_df["source"].dropna().unique().tolist()):
        source_orders = orders_df[orders_df["source"] == source_name].copy()
        closed_trades, _, _, _ = build_closed_trades(source_orders)
        if closed_trades.empty:
            rows.append({
                "source": source_name,
                "total_pnl": 0.0,
                "trades": 0,
                "wins": 0,
                "win_rate_pct": 0.0,
            })
            continue

        wins = int((closed_trades["result"] == "WIN").sum())
        trades = int(len(closed_trades))
        rows.append(
            {
                "source": source_name,
                "total_pnl": float(closed_trades["pnl"].sum()),
                "trades": trades,
                "wins": wins,
                "win_rate_pct": (wins / trades * 100.0) if trades else 0.0,
            }
        )

    if not rows:
        return pd.DataFrame(columns=["source", "total_pnl", "trades", "wins", "win_rate_pct"])

    return pd.DataFrame(rows).sort_values("total_pnl", ascending=False).reset_index(drop=True)


def compute_strategy_origin_mix(closed_trades: pd.DataFrame) -> dict[str, float]:
    if closed_trades.empty or "entry_strategy_source" not in closed_trades.columns:
        return {"llm_generated_pct": 0.0, "fallback_pct": 0.0, "known_trades": 0, "unknown_trades": 0}

    src = closed_trades["entry_strategy_source"].fillna("unknown").astype(str).str.strip().str.lower()
    llm_count = int((src == "llm-generated").sum())
    fallback_count = int((src == "fallback").sum())
    known = llm_count + fallback_count
    unknown = int(len(src)) - known

    if known == 0:
        return {"llm_generated_pct": 0.0, "fallback_pct": 0.0, "known_trades": 0, "unknown_trades": unknown}

    return {
        "llm_generated_pct": (llm_count / known) * 100.0,
        "fallback_pct": (fallback_count / known) * 100.0,
        "known_trades": known,
        "unknown_trades": unknown,
    }


def build_daily_analytics(closed_trades: pd.DataFrame, start_date, end_date, unrealized_pnl: float = 0.0) -> tuple[pd.DataFrame, pd.DataFrame]:
    date_index = pd.date_range(start=start_date, end=end_date, freq="D")

    if closed_trades.empty:
        daily = pd.DataFrame(index=date_index)
        daily["daily_pnl"] = 0.0
        daily["trades"] = 0
        daily["wins"] = 0
        daily["realized_equity"] = float(INITIAL_CAPITAL)
        daily["total_equity"] = float(INITIAL_CAPITAL) + float(unrealized_pnl)
        daily["drawdown_pct"] = 0.0
        equity = daily[["realized_equity", "total_equity", "drawdown_pct"]].copy()
        return daily.reset_index(names="date"), equity

    daily = (
        closed_trades.groupby("exit_date", as_index=True)
        .agg(
            daily_pnl=("pnl", "sum"),
            trades=("pnl", "count"),
            wins=("result", lambda x: (x == "WIN").sum()),
        )
        .sort_index()
    )

    daily.index = pd.to_datetime(daily.index)
    daily = daily.reindex(date_index, fill_value=0)

    daily["realized_equity"] = float(INITIAL_CAPITAL) + daily["daily_pnl"].cumsum()
    daily["total_equity"] = daily["realized_equity"] + float(unrealized_pnl)
    running_peak = daily["total_equity"].cummax()
    daily["drawdown_pct"] = (daily["total_equity"] / running_peak - 1.0) * 100.0

    equity = daily[["realized_equity", "total_equity", "drawdown_pct"]].copy()
    return daily.reset_index(names="date"), equity


def fmt_inr(value: float) -> str:
    return f"₹{value:,.2f}"


def fmt_pct(value: float) -> str:
    return f"{value:+.2f}%"


def fmt_ratio(value: float) -> str:
    return f"{value:.2f}"


def main():
    st.title("StratGen Trading Dashboard")
    st.caption("Analytics from on-disk logs: signals, orders, daily reports, weekly summaries")

    signals_df = load_signal_logs()
    orders_df = load_order_logs()
    reports_df = load_report_logs()
    weekly_df = load_weekly_logs()

    all_dates: list[pd.Timestamp] = []
    for df, col in [(signals_df, "date"), (orders_df, "date"), (reports_df, "date"), (weekly_df, "date")]:
        if not df.empty and col in df.columns:
            all_dates.extend(pd.to_datetime(df[col], errors="coerce").dropna().tolist())

    if all_dates:
        min_date = min(all_dates).date()
        max_date = max(all_dates).date()
    else:
        today = pd.Timestamp.today().date()
        min_date = today
        max_date = today

    all_regimes = sorted(
        set(signals_df.get("regime", pd.Series(dtype=str)).dropna().tolist())
        | set(orders_df.get("regime", pd.Series(dtype=str)).dropna().tolist())
    )
    regime_options = ["All"] + all_regimes if all_regimes else ["All"]

    signal_values = sorted(
        set(signals_df.get("signal", pd.Series(dtype=str)).dropna().str.upper().tolist())
        | set(orders_df.get("action", pd.Series(dtype=str)).dropna().str.upper().tolist())
    )
    if "UNKNOWN" in signal_values:
        signal_values.remove("UNKNOWN")
    signal_options = ["All"] + signal_values if signal_values else ["All", "BUY", "SELL", "HOLD"]

    source_values = sorted(set(orders_df.get("source", pd.Series(dtype=str)).dropna().tolist()))
    source_options = _ordered_sources(source_values) if source_values else ["backtest-ma", "backtest-mm", "live-llm", "unknown"]

    with st.sidebar:
        st.subheader("Filters")
        selected_range = st.date_input(
            "Date range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )
        if isinstance(selected_range, tuple) and len(selected_range) == 2:
            start_date, end_date = selected_range
        else:
            start_date = min_date
            end_date = max_date

        selected_regime = st.selectbox("Regime", options=regime_options, index=0)
        selected_signal = st.selectbox("Signal type", options=signal_options, index=0)
        selected_sources = st.multiselect(
            "Source",
            options=source_options,
            default=source_options,
        )

        if not selected_sources:
            selected_sources = source_options

        st.divider()
        st.subheader("Data coverage")
        st.write(f"Signals: {len(signals_df)}")
        st.write(f"Orders: {len(orders_df)}")
        st.write(f"Reports: {len(reports_df)}")
        st.write(f"Weekly rows: {len(weekly_df)}")

        if st.button("Refresh data"):
            st.cache_data.clear()
            st.rerun()

    filtered_signals = apply_common_filters(
        signals_df,
        date_col="date",
        start_date=start_date,
        end_date=end_date,
        regime=selected_regime,
        regime_col="regime",
        signal_value=selected_signal,
        signal_col="signal",
        source_values=None,
    )

    base_filtered_orders = apply_common_filters(
        orders_df,
        date_col="date",
        start_date=start_date,
        end_date=end_date,
        regime=selected_regime,
        regime_col="regime",
        signal_value=selected_signal,
        signal_col="action",
        source_values=None,
        source_col="source",
    )

    filtered_orders = apply_common_filters(
        base_filtered_orders,
        date_col="date",
        start_date=start_date,
        end_date=end_date,
        regime="All",
        regime_col="regime",
        signal_value="All",
        signal_col="action",
        source_values=selected_sources,
        source_col="source",
    )

    price_reference_signals = apply_common_filters(
        signals_df,
        date_col="date",
        start_date=start_date,
        end_date=end_date,
        regime=selected_regime,
        regime_col="regime",
        signal_value="All",
        signal_col="signal",
        source_values=None,
    )

    price_reference_orders = apply_common_filters(
        orders_df,
        date_col="date",
        start_date=start_date,
        end_date=end_date,
        regime=selected_regime,
        regime_col="regime",
        signal_value="All",
        signal_col="action",
        source_values=selected_sources,
        source_col="source",
    )

    closed_trades, open_positions, open_qty, unmatched_sell_qty = build_closed_trades(filtered_orders)
    latest_price = get_latest_price_from_logs(price_reference_signals, price_reference_orders)
    unrealized_pnl, marked_open_positions = compute_unrealized_pnl(open_positions, latest_price)
    daily_df, equity_df = build_daily_analytics(closed_trades, start_date, end_date, unrealized_pnl=unrealized_pnl)
    advanced = compute_advanced_metrics(closed_trades, daily_df)

    regime_group_mode = st.radio(
        "Regime grouping basis",
        options=["Entry Regime", "Exit Regime"],
        horizontal=True,
    )
    regime_group_col = "entry_regime" if regime_group_mode == "Entry Regime" else "exit_regime"
    regime_perf_df = compute_regime_performance(closed_trades, regime_group_col)
    source_perf_df = compute_source_performance(filtered_orders)
    strategy_mix = compute_strategy_origin_mix(closed_trades)

    total_realized_pnl = float(closed_trades["pnl"].sum()) if not closed_trades.empty else 0.0
    total_equity = float(INITIAL_CAPITAL) + total_realized_pnl + unrealized_pnl
    closed_count = int(len(closed_trades))
    wins = int((closed_trades["result"] == "WIN").sum()) if not closed_trades.empty else 0
    win_rate = (wins / closed_count * 100.0) if closed_count else 0.0
    max_drawdown = abs(float(daily_df["drawdown_pct"].min())) if not daily_df.empty else 0.0

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Realized PnL", fmt_inr(total_realized_pnl))
    k2.metric("Unrealized PnL", fmt_inr(unrealized_pnl))
    k3.metric("Total Equity", fmt_inr(total_equity), fmt_inr(total_realized_pnl + unrealized_pnl))
    k4.metric("Closed Trades", f"{closed_count}")
    k5.metric("Win Rate", f"{win_rate:.1f}%")
    k6.metric("Max Drawdown", f"{max_drawdown:.2f}%")

    if not source_perf_df.empty:
        st.markdown("#### Source Metrics")
        metric_cols = st.columns(min(4, len(source_perf_df)))
        for idx, row in source_perf_df.head(4).iterrows():
            col = metric_cols[idx % len(metric_cols)]
            col.metric(
                str(row["source"]),
                fmt_inr(float(row["total_pnl"])),
                f"WR {float(row['win_rate_pct']):.1f}% • Trades {int(row['trades'])}",
            )

    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Sharpe Ratio", fmt_ratio(advanced["sharpe_ratio"]))
    a2.metric("Calmar Ratio", fmt_ratio(advanced["calmar_ratio"]))
    a3.metric("Profit Factor", fmt_ratio(advanced["profit_factor"]))
    a4.metric("Avg Win / Loss", f"{advanced['avg_win_pct']:+.2f}% / {advanced['avg_loss_pct']:+.2f}%")

    t1, t2 = st.columns(2)
    t1.metric("LLM-Generated Trades %", f"{strategy_mix['llm_generated_pct']:.1f}%")
    t2.metric("Fallback Trades %", f"{strategy_mix['fallback_pct']:.1f}%")
    if strategy_mix["unknown_trades"] > 0:
        st.caption(
            f"Strategy-source transparency: {strategy_mix['known_trades']} labeled trades, "
            f"{strategy_mix['unknown_trades']} legacy unlabeled trades."
        )

    st.caption(
        f"Latest mark price used for unrealized PnL: {fmt_inr(latest_price)}"
        if latest_price > 0
        else "Latest mark price unavailable in filtered logs; unrealized PnL is 0."
    )

    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("Equity Curve")
        if not equity_df.empty:
            st.line_chart(equity_df[["realized_equity", "total_equity"]], use_container_width=True)
        else:
            st.info("No equity data for selected filters.")

    with c2:
        st.subheader("Drawdown")
        if not equity_df.empty:
            st.area_chart(equity_df[["drawdown_pct"]], use_container_width=True)
        else:
            st.info("No drawdown data for selected filters.")

    st.subheader("Daily PnL")
    daily_view = daily_df[["date", "daily_pnl", "trades", "wins"]].copy()
    daily_view["date"] = pd.to_datetime(daily_view["date"]).dt.date
    st.bar_chart(daily_view.set_index("date")[["daily_pnl"]], use_container_width=True)

    st.subheader("Regime-wise Performance")
    if regime_perf_df.empty:
        st.info("No closed trades available for regime-wise analysis in selected filters.")
    else:
        rc1, rc2 = st.columns(2)
        with rc1:
            st.markdown("**Total PnL by Regime**")
            regime_pnl = regime_perf_df[["regime", "total_pnl"]].set_index("regime")
            st.bar_chart(regime_pnl, use_container_width=True)
        with rc2:
            st.markdown("**Win Rate and Trade Count by Regime**")
            regime_comp = regime_perf_df[["regime", "win_rate_pct", "trades"]].set_index("regime")
            st.bar_chart(regime_comp, use_container_width=True)

        regime_table = regime_perf_df[["regime", "total_pnl", "win_rate_pct", "trades", "wins", "avg_pnl_per_trade"]].copy()
        st.dataframe(
            regime_table,
            use_container_width=True,
            hide_index=True,
            column_config={
                "total_pnl": st.column_config.NumberColumn("Total PnL", format="₹ %.2f"),
                "win_rate_pct": st.column_config.NumberColumn("Win Rate", format="%.2f%%"),
                "trades": st.column_config.NumberColumn("Trades", format="%d"),
                "wins": st.column_config.NumberColumn("Wins", format="%d"),
                "avg_pnl_per_trade": st.column_config.NumberColumn("Avg PnL / Trade", format="₹ %.2f"),
            },
        )

    st.subheader("Source-wise Performance")
    if source_perf_df.empty:
        st.info("No order logs available for source comparison in selected filters.")
    else:
        s1, s2 = st.columns(2)
        with s1:
            st.markdown("**PnL per Source**")
            st.bar_chart(source_perf_df[["source", "total_pnl"]].set_index("source"), use_container_width=True)
        with s2:
            st.markdown("**Win Rate and Trade Count per Source**")
            st.bar_chart(source_perf_df[["source", "win_rate_pct", "trades"]].set_index("source"), use_container_width=True)

        st.dataframe(
            source_perf_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "total_pnl": st.column_config.NumberColumn("Total PnL", format="₹ %.2f"),
                "win_rate_pct": st.column_config.NumberColumn("Win Rate", format="%.2f%%"),
                "trades": st.column_config.NumberColumn("Trades", format="%d"),
                "wins": st.column_config.NumberColumn("Wins", format="%d"),
            },
        )

    tab1, tab2, tab3 = st.tabs(["Trade History", "Signals", "Data Quality"])

    with tab1:
        st.markdown("### Closed Trades")
        if closed_trades.empty:
            st.info("No closed trades for selected filters.")
        else:
            trade_table = closed_trades[
                [
                    "entry_date",
                    "exit_date",
                    "entry_price",
                    "exit_price",
                    "quantity",
                    "pnl",
                    "pnl_pct",
                    "entry_regime",
                    "exit_regime",
                    "entry_strategy_source",
                    "exit_strategy_source",
                    "result",
                ]
            ].copy()
            trade_table["entry_date"] = pd.to_datetime(trade_table["entry_date"]).dt.date
            trade_table["exit_date"] = pd.to_datetime(trade_table["exit_date"]).dt.date
            st.dataframe(
                trade_table.sort_values("exit_date", ascending=False),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "entry_price": st.column_config.NumberColumn("Entry", format="₹ %.2f"),
                    "exit_price": st.column_config.NumberColumn("Exit", format="₹ %.2f"),
                    "quantity": st.column_config.NumberColumn("Qty", format="%.4f"),
                    "pnl": st.column_config.NumberColumn("PnL", format="₹ %.2f"),
                    "pnl_pct": st.column_config.NumberColumn("PnL %", format="%.2f%%"),
                },
            )

        st.markdown("### Open Positions")
        if marked_open_positions.empty:
            st.info("No open positions in selected filters.")
        else:
            open_table = marked_open_positions[
                [
                    "entry_date",
                    "entry_price",
                    "latest_price",
                    "quantity",
                    "unrealized_pnl",
                    "unrealized_pnl_pct",
                    "entry_regime",
                    "entry_source",
                    "entry_strategy_source",
                ]
            ].copy()
            open_table["entry_date"] = pd.to_datetime(open_table["entry_date"]).dt.date
            st.dataframe(
                open_table.sort_values("entry_date", ascending=False),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "entry_price": st.column_config.NumberColumn("Entry", format="₹ %.2f"),
                    "latest_price": st.column_config.NumberColumn("Latest", format="₹ %.2f"),
                    "quantity": st.column_config.NumberColumn("Qty", format="%.4f"),
                    "unrealized_pnl": st.column_config.NumberColumn("Unrealized PnL", format="₹ %.2f"),
                    "unrealized_pnl_pct": st.column_config.NumberColumn("Unrealized %", format="%.2f%%"),
                },
            )

    with tab2:
        st.markdown("### Signal Log")
        if filtered_signals.empty:
            st.info("No signals for selected filters.")
        else:
            signal_table = filtered_signals[
                [
                    "date",
                    "timestamp",
                    "regime",
                    "signal",
                    "strategy_source",
                    "close",
                    "entry_condition",
                    "exit_condition",
                    "reasoning",
                    "source_file",
                ]
            ].copy()
            signal_table["date"] = pd.to_datetime(signal_table["date"]).dt.date
            st.dataframe(
                signal_table.sort_values(["date", "timestamp"], ascending=False),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "close": st.column_config.NumberColumn("Close", format="₹ %.2f"),
                },
            )

    with tab3:
        st.markdown("### Validation & Data Quality")
        st.write(f"Open quantity not closed by SELL logs: {open_qty:.4f}")
        st.write(f"Unmatched SELL quantity (without prior BUY): {unmatched_sell_qty:.4f}")
        st.write(f"Initial capital used for equity: {fmt_inr(float(INITIAL_CAPITAL))}")
        st.write(f"Latest mark price used: {fmt_inr(latest_price) if latest_price > 0 else 'N/A'}")
        st.write(f"Realized PnL: {fmt_inr(total_realized_pnl)}")
        st.write(f"Unrealized PnL: {fmt_inr(unrealized_pnl)}")
        st.write(f"Total equity (realized + unrealized): {fmt_inr(total_equity)}")

        with st.expander("How calculations are derived"):
            st.markdown(
                "- Trades are reconstructed from order logs only (`BUY` paired FIFO with `SELL`).\n"
                "- Realized PnL uses: `(exit_price - entry_price) * matched_quantity`.\n"
                "- Open positions are unmatched FIFO BUY lots after SELL pairing.\n"
                "- Unrealized PnL uses latest mark from logs: `(latest_price - entry_price) * open_quantity`.\n"
                "- Daily PnL is grouped by `exit_date` of closed trades.\n"
                "- Total equity curve = realized equity + unrealized PnL (marked at latest available price).\n"
                "- Drawdown is computed from total equity peak-to-trough in filtered range."
            )


if __name__ == "__main__":
    main()
