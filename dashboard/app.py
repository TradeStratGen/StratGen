"""
dashboard/app.py — StratGen v2 with Multi-Model Tournament
Run: streamlit run dashboard/app.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from dotenv import load_dotenv
load_dotenv()

st.set_page_config(page_title="StratGen", page_icon="📈", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
.stApp { background-color: #0a0e1a; color: #e2e8f0; }
[data-testid="stSidebar"] { background-color: #0d1224; border-right: 1px solid #1e2d4a; }
[data-testid="metric-container"] { background:#111827; border:1px solid #1e2d4a; border-radius:8px; padding:16px; }
[data-testid="metric-container"] label { color:#64748b !important; font-size:11px !important; letter-spacing:.1em; text-transform:uppercase; font-family:'IBM Plex Mono',monospace !important; }
[data-testid="metric-container"] [data-testid="stMetricValue"] { color:#f1f5f9 !important; font-family:'IBM Plex Mono',monospace !important; font-size:22px !important; }
.strategy-card { background:#111827; border:1px solid #1e2d4a; border-radius:8px; padding:14px 18px; margin-bottom:10px; font-family:'IBM Plex Mono',monospace; font-size:12px; }
.regime-label { font-size:10px; letter-spacing:.15em; text-transform:uppercase; margin-bottom:8px; font-family:'IBM Plex Sans',sans-serif; font-weight:600; }
.bullish { border-left:3px solid #10b981; } .bullish .regime-label { color:#10b981; }
.bearish { border-left:3px solid #ef4444; } .bearish .regime-label { color:#ef4444; }
.volatile{ border-left:3px solid #f59e0b; } .volatile .regime-label{ color:#f59e0b; }
.neutral { border-left:3px solid #6366f1; } .neutral  .regime-label{ color:#6366f1; }
.cond { color:#93c5fd; margin:3px 0; line-height:1.6; }
.risk { color:#64748b; font-size:11px; margin-top:8px; }
.winner-badge { display:inline-block; padding:1px 8px; border-radius:4px; font-size:10px; background:#10b98122; color:#10b981; border:1px solid #10b98144; margin-left:8px; font-family:'IBM Plex Mono',monospace; }
.section-header { font-family:'IBM Plex Mono',monospace; font-size:10px; letter-spacing:.15em; text-transform:uppercase; color:#475569; border-bottom:1px solid #1e2d4a; padding-bottom:8px; margin:20px 0 14px 0; }
.tournament-row { display:flex; align-items:center; padding:8px 12px; border-radius:6px; margin-bottom:6px; background:#111827; border:1px solid #1e2d4a; font-family:'IBM Plex Mono',monospace; font-size:12px; }
.t-regime { width:90px; font-weight:500; }
.t-model  { flex:1; color:#94a3b8; }
.t-return { width:80px; text-align:right; font-weight:500; }
.t-winner { width:90px; text-align:right; }
</style>
""", unsafe_allow_html=True)

REGIME_COLORS = {"Bullish":"#10b981","Bearish":"#ef4444","Volatile":"#f59e0b","Neutral":"#6366f1"}
PLOTLY_THEME  = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#111827",
    font=dict(family="IBM Plex Mono", color="#94a3b8", size=11),
    xaxis=dict(gridcolor="#1e2d4a", showgrid=True, zeroline=False),
    yaxis=dict(gridcolor="#1e2d4a", showgrid=True, zeroline=False),
    margin=dict(l=0, r=0, t=24, b=0),
)


@st.cache_data(ttl=3600)
def load_and_run():
    from data.fetch_data import fetch_data
    from indicators.indicators import add_indicators
    from regime.regime import apply_regime
    from strategies.ma_strategy import MovingAverageStrategy
    from llm.multi_model import MultiModelStrategy
    from backtest.backtester import Backtester

    df = fetch_data()
    df = add_indicators(df)
    df = apply_regime(df)

    # MA baseline
    ma_bt = Backtester(df, MovingAverageStrategy())
    ma_eq, ma_tr = ma_bt.run()

    # Multi-model tournament
    multi = MultiModelStrategy(
        models=["qwen2.5:7b-instruct", "llama3.2:3b"],
        verbose=False,
    )
    multi.prime(df)
    mm_bt = Backtester(df, multi)
    mm_eq, mm_tr = mm_bt.run()

    return df, ma_eq, ma_tr, mm_eq, mm_tr, multi


def calc(equity, trades):
    i = equity[0]; f = equity[-1]
    ret   = (f - i) / i * 100
    sells = [p for _,t,p in trades if t=="SELL"]
    buys  = [p for _,t,p in trades if t=="BUY"]
    wins  = sum(1 for s,b in zip(sells,buys) if s>b)
    wr    = wins/len(sells)*100 if sells else 0
    pk = equity[0]; dd = 0
    for v in equity:
        pk = max(pk,v); dd = max(dd,(pk-v)/pk*100)
    return {"final":f,"return":ret,"trades":len(trades),"win_rate":wr,"max_dd":dd}


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### StratGen")
    st.markdown("<p style='color:#475569;font-size:12px;margin-top:-10px'>LLM Multi-Model Tournament</p>", unsafe_allow_html=True)
    st.divider()
    st.markdown("**Index:** NIFTY 50")
    st.markdown("**Period:** Jan 2020 – Present")
    st.markdown("**Capital:** ₹1,00,000")
    st.markdown("**Models:** qwen2.5:7b · llama3.2:3b")
    st.divider()
    if st.button("🔄 Re-run", use_container_width=True):
        st.cache_data.clear(); st.rerun()
    st.markdown("<p style='color:#475569;font-size:11px;margin-top:12px'>Educational use only.</p>", unsafe_allow_html=True)


# ── Load ──────────────────────────────────────────────────────────────────────
st.markdown("# StratGen Dashboard")
st.markdown("<p style='color:#475569;margin-top:-12px'>LLM-Driven Market Regime–Aware Trading · Multi-Model Tournament</p>", unsafe_allow_html=True)

with st.spinner("Running pipeline: data → regime → LLM tournament → backtest…"):
    df, ma_eq, ma_tr, mm_eq, mm_tr, multi = load_and_run()

ma_m  = calc(ma_eq, ma_tr)
mm_m  = calc(mm_eq, mm_tr)
mr    = multi.model_results
bpr   = multi.best_per_regime
strats = multi.final_strategies

# Current regime banner
cr = df["regime"].iloc[-1]; cc = REGIME_COLORS.get(cr,"#6366f1")
st.markdown(
    f"<div style='background:{cc}18;border:1px solid {cc}44;border-radius:8px;"
    f"padding:10px 20px;margin-bottom:20px;display:flex;align-items:center;gap:12px'>"
    f"<span style='width:9px;height:9px;border-radius:50%;background:{cc};"
    f"display:inline-block;box-shadow:0 0 8px {cc}'></span>"
    f"<span style='font-family:IBM Plex Mono;font-size:13px;color:{cc}'>"
    f"CURRENT REGIME: {cr.upper()}</span>"
    f"<span style='margin-left:auto;font-size:11px;color:#475569;font-family:IBM Plex Mono'>"
    f"Active model: {bpr.get(cr,{}).get('model','?').split(':')[0].split('/')[-1]}</span></div>",
    unsafe_allow_html=True,
)

# ── KPIs ──────────────────────────────────────────────────────────────────────
st.markdown("<div class='section-header'>Performance Summary</div>", unsafe_allow_html=True)
c1,c2,c3,c4,c5,c6 = st.columns(6)
c1.metric("Multi-Model Value",  f"₹{mm_m['final']:,.0f}",   f"+₹{mm_m['final']-100000:,.0f}")
c2.metric("Multi-Model Return", f"{mm_m['return']:+.1f}%",   f"MA: {ma_m['return']:+.1f}%")
c3.metric("Win Rate",           f"{mm_m['win_rate']:.1f}%",  f"MA: {ma_m['win_rate']:.1f}%")
c4.metric("Total Trades",       str(mm_m["trades"]),          f"MA: {ma_m['trades']}")
c5.metric("Max Drawdown",       f"-{mm_m['max_dd']:.1f}%",  f"MA: -{ma_m['max_dd']:.1f}%")
c6.metric("MA Final Value",     f"₹{ma_m['final']:,.0f}",   f"+₹{ma_m['final']-100000:,.0f}")

# ── Equity curve ──────────────────────────────────────────────────────────────
st.markdown("<div class='section-header'>Equity Curve — Multi-Model vs MA Crossover</div>", unsafe_allow_html=True)
dates = df.index[-len(mm_eq):]
fig_eq = go.Figure()

# Regime bands
prev, bs = None, None
for date, regime in df["regime"].iloc[-len(mm_eq):].items():
    if regime != prev:
        if prev: fig_eq.add_vrect(x0=bs,x1=date,fillcolor=REGIME_COLORS.get(prev,"#6366f1"),opacity=0.05,line_width=0)
        prev, bs = regime, date
if prev: fig_eq.add_vrect(x0=bs,x1=dates[-1],fillcolor=REGIME_COLORS.get(prev,"#6366f1"),opacity=0.05,line_width=0)

fig_eq.add_trace(go.Scatter(x=dates,y=ma_eq[-len(dates):],name="MA Crossover",
    line=dict(color="#6366f1",width=1.5,dash="dot")))
fig_eq.add_trace(go.Scatter(x=dates,y=mm_eq[-len(dates):],name="Multi-Model",
    line=dict(color="#10b981",width=2)))
fig_eq.add_hline(y=100000,line_dash="dot",line_color="#334155",line_width=1)

# Trade markers
di = {d:i for i,d in enumerate(dates)}
for d,act,p in mm_tr:
    if d in di:
        i = di[d]; v = mm_eq[i] if i < len(mm_eq) else None
        if v: fig_eq.add_trace(go.Scatter(x=[d],y=[v],mode="markers",showlegend=False,
            marker=dict(symbol="triangle-up" if act=="BUY" else "triangle-down",
                        size=9,color="#10b981" if act=="BUY" else "#ef4444")))

fig_eq.update_layout(**PLOTLY_THEME, height=340,
    legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="right",x=1,
                bgcolor="rgba(0,0,0,0)",font=dict(size=11)))
fig_eq.update_yaxes(tickprefix="₹",tickformat=",.0f")
st.plotly_chart(fig_eq, use_container_width=True)

# ── Tournament + strategies ───────────────────────────────────────────────────
col_l, col_r = st.columns([3, 2])

with col_l:
    st.markdown("<div class='section-header'>Tournament — Best Model per Regime</div>", unsafe_allow_html=True)

    model_names = list(mr.keys())
    for regime in ["Bullish","Bearish","Volatile","Neutral"]:
        if regime not in bpr: continue
        col   = REGIME_COLORS.get(regime,"#6366f1")
        winner_model = bpr[regime]["model"]
        w_short      = winner_model.split(":")[0].split("/")[-1]
        w_ret        = bpr[regime]["return"]
        css          = regime.lower()
        active       = regime == cr
        border       = f"border:1px solid {col}88" if active else "border:1px solid #1e2d4a"
        strat        = strats.get(regime, {})

        # Per-model returns for this regime
        model_cells = ""
        for mn in model_names:
            ret = mr[mn]["metrics"].get(regime,{}).get("return",0)
            is_w = mn == winner_model
            clr  = "#10b981" if is_w else "#64748b"
            wgt  = "font-weight:500" if is_w else ""
            crown = " ★" if is_w else ""
            short = mn.split(":")[0].split("/")[-1]
            model_cells += f"<span style='color:{clr};{wgt};margin-right:16px'>{short}: {ret:+.1f}%{crown}</span>"

        st.markdown(f"""
        <div class='strategy-card {css}' style='{border}'>
          <div class='regime-label'>{regime}{"  ← active" if active else ""}
            <span class='winner-badge'>★ {w_short}</span>
          </div>
          <div style='margin-bottom:6px;font-size:11px'>{model_cells}</div>
          <div class='cond'>Entry : {strat.get("entry_condition","—")}</div>
          <div class='cond'>Exit  : {strat.get("exit_condition","—")}</div>
          <div class='risk'>SL: {strat.get("stop_loss",0)*100:.1f}%  |  TP: {strat.get("take_profit",0)*100:.1f}%</div>
        </div>""", unsafe_allow_html=True)

with col_r:
    st.markdown("<div class='section-header'>Strategy Comparison</div>", unsafe_allow_html=True)
    fig_bar = go.Figure()
    cats = ["Return %","Win Rate %","Max DD %","Trades"]
    fig_bar.add_trace(go.Bar(name="MA",x=cats,
        y=[ma_m["return"],ma_m["win_rate"],ma_m["max_dd"],ma_m["trades"]],
        marker_color="#6366f1",opacity=0.85))
    fig_bar.add_trace(go.Bar(name="Multi-Model",x=cats,
        y=[mm_m["return"],mm_m["win_rate"],mm_m["max_dd"],mm_m["trades"]],
        marker_color="#10b981",opacity=0.9))
    fig_bar.update_layout(**PLOTLY_THEME,height=210,barmode="group",
        legend=dict(orientation="h",yanchor="bottom",y=1.02,
                    bgcolor="rgba(0,0,0,0)",font=dict(size=10)))
    st.plotly_chart(fig_bar, use_container_width=True)

    # Per-regime returns heatmap-style
    st.markdown("<div class='section-header' style='margin-top:8px'>Per-Regime Returns by Model</div>", unsafe_allow_html=True)
    regimes_list = list(bpr.keys())
    fig_rr = go.Figure()
    colors_m = ["#6366f1","#f59e0b","#10b981","#ef4444"]
    for i, mn in enumerate(model_names):
        rets = [mr[mn]["metrics"].get(r,{}).get("return",0) for r in regimes_list]
        fig_rr.add_trace(go.Bar(
            name=mn.split(":")[0].split("/")[-1],
            x=regimes_list, y=rets,
            marker_color=colors_m[i % len(colors_m)], opacity=0.85,
        ))
    fig_rr.update_layout(**PLOTLY_THEME,height=200,barmode="group",
        legend=dict(orientation="h",yanchor="bottom",y=1.02,
                    bgcolor="rgba(0,0,0,0)",font=dict(size=10)))
    fig_rr.update_yaxes(ticksuffix="%")
    st.plotly_chart(fig_rr, use_container_width=True)

    # Regime distribution pie
    st.markdown("<div class='section-header' style='margin-top:4px'>Regime Distribution</div>", unsafe_allow_html=True)
    rc = df["regime"].value_counts()
    fig_pie = go.Figure(go.Pie(
        labels=rc.index, values=rc.values, hole=0.55,
        marker_colors=[REGIME_COLORS.get(r,"#6366f1") for r in rc.index],
        textfont=dict(family="IBM Plex Mono",size=11),
    ))
    fig_pie.update_layout(**PLOTLY_THEME,height=180,
        legend=dict(font=dict(size=10),bgcolor="rgba(0,0,0,0)"))
    st.plotly_chart(fig_pie, use_container_width=True)

# ── Trade log ─────────────────────────────────────────────────────────────────
st.markdown("<div class='section-header'>Recent Multi-Model Trades (last 30)</div>", unsafe_allow_html=True)
rows, bq = [], []
for date,act,price in mm_tr:
    if act=="BUY":
        bq.append((date,price))
        rows.append({"Date":date.strftime("%d %b %Y"),"Signal":"BUY","Price":f"₹{price:,.2f}","P&L":"—","Regime":df.loc[date,"regime"] if date in df.index else "?"})
    elif act=="SELL" and bq:
        bd,bp = bq.pop(0)
        pct   = (price-bp)/bp*100
        rows.append({"Date":date.strftime("%d %b %Y"),"Signal":"SELL","Price":f"₹{price:,.2f}",
                     "P&L":f"{'+'if pct>=0 else ''}{pct:.1f}%",
                     "Regime":df.loc[date,"regime"] if date in df.index else "?"})

if rows:
    tdf = pd.DataFrame(rows[-30:]).iloc[::-1]
    def cs(v): return "color:#10b981;font-weight:600" if v=="BUY" else "color:#ef4444;font-weight:600"
    def cp(v): return "color:#10b981" if str(v).startswith("+") else ("color:#ef4444" if str(v).startswith("-") else "color:#64748b")
    styled = (tdf.style.map(cs,subset=["Signal"]).map(cp,subset=["P&L"])
              .set_properties(**{"font-family":"IBM Plex Mono","font-size":"12px"})
              .hide(axis="index"))
    st.dataframe(styled, use_container_width=True, height=300)

# ── Price chart ───────────────────────────────────────────────────────────────
st.markdown("<div class='section-header'>NIFTY 50 — Price Coloured by Regime</div>", unsafe_allow_html=True)
fig_p = go.Figure()
for regime,color in REGIME_COLORS.items():
    mask = df["regime"]==regime
    fig_p.add_trace(go.Scatter(x=df.index[mask],y=df["Close"][mask],mode="markers",name=regime,
        marker=dict(color=color,size=2,opacity=0.7)))
fig_p.add_trace(go.Scatter(x=df.index,y=df["SMA_20"],name="SMA 20",line=dict(color="#6366f1",width=1,dash="dot")))
fig_p.add_trace(go.Scatter(x=df.index,y=df["SMA_50"],name="SMA 50",line=dict(color="#f59e0b",width=1,dash="dot")))
fig_p.update_layout(**PLOTLY_THEME,height=280,
    legend=dict(orientation="h",yanchor="bottom",y=1.02,bgcolor="rgba(0,0,0,0)",font=dict(size=10)))
fig_p.update_yaxes(tickprefix="₹",tickformat=",.0f")
st.plotly_chart(fig_p, use_container_width=True)

st.markdown("<div style='text-align:center;padding:28px 0 12px;color:#1e2d4a;font-size:10px;font-family:IBM Plex Mono;letter-spacing:.1em'>STRATGEN · LLM MULTI-MODEL TOURNAMENT · EDUCATIONAL USE ONLY</div>", unsafe_allow_html=True)