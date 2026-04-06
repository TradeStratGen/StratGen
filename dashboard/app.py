import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
from data.fetch_data import fetch_data
from indicators.indicators import add_indicators
from regime.regime import apply_regime
from strategies.ma_strategy import MovingAverageStrategy
from backtest.backtester import Backtester
st.title("📈 Trading Bot Dashboard")

df = fetch_data()
df = add_indicators(df)
df = apply_regime(df)

strategy = MovingAverageStrategy()
bt = Backtester(df, strategy)

equity, trades = bt.run()

st.metric("Final Portfolio Value", f"{equity[-1]:,.2f}")
st.metric("Total Trades", len(trades))

st.line_chart(equity)

st.subheader("Recent Trades")
st.write(trades[-10:])