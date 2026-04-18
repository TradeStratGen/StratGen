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

st.set_page_config(
    page_title="StratGen · LLM Tournament",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600&display=swap');

*, *::before, *::after { box-sizing: border-box; }
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }

.stApp { background-color: #080b14; color: #c9d1e0; }
.block-container { padding: 18px 24px 32px !important; max-width: 100% !important; }
body {
    font-size: 14px;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: #060910 !important;
    border-right: 1px solid #0f1e33 !important;
}
[data-testid="stSidebarContent"] { padding: 20px 16px; }
[data-testid="collapsedControl"] {
    color: #334155 !important;
    background: #0c1220 !important;
    border: 1px solid #0f1e33 !important;
    border-radius: 4px !important;
}
.sidebar-brand { font-family:'Space Mono',monospace; font-size:20px; font-weight:700; color:#e2e8f0; letter-spacing:-.02em; margin-bottom:2px; }
.sidebar-tagline { font-family:'Space Mono',monospace; font-size:10px; letter-spacing:.16em; color:#94a3b8; text-transform:uppercase; margin-bottom:20px; }
.sidebar-row { display:flex; justify-content:space-between; align-items:center; padding:7px 0; border-bottom:1px solid #0d1929; font-family:'Space Mono',monospace; }
.sidebar-row .s-lbl { font-size:10px; letter-spacing:.1em; text-transform:uppercase; color:#64748b; }
.sidebar-row .s-val { font-size:9px; color:#e2e8f0; }

/* KPI strip */
.kpi-strip { display:grid; grid-template-columns:repeat(6,1fr); gap:1px; background:#0d1929; border:1px solid #0d1929; border-radius:8px; overflow:hidden; margin-bottom:14px; }
.kpi-cell  { background:#0b1120; padding:13px 15px; }
.kpi-lbl   { font-family:'Space Mono',monospace; font-size:8px; letter-spacing:.14em; text-transform:uppercase; color:#1e3a5f; margin-bottom:6px; }
.kpi-val   { font-family:'Space Mono',monospace; font-size:17px; font-weight:700; color:#dde4f0; line-height:1; }
.kpi-dlt   { font-family:'Space Mono',monospace; font-size:9px; margin-top:4px; }
.c-grn { color:#10b981; } .c-red { color:#ef4444; } .c-dim { color:#cbd5f5; }

/* Regime banner */
.regime-banner { display:flex; align-items:center; gap:10px; padding:9px 16px; border-radius:6px; margin-bottom:14px; font-family:'Space Mono',monospace; }
.r-dot  { width:7px; height:7px; border-radius:50%; flex-shrink:0; }
.r-name { font-size:10px; font-weight:700; letter-spacing:.14em; text-transform:uppercase; }
.r-info { font-size:9px; color:#94a3b8; margin-left:4px; }
.r-meta { margin-left:auto; font-size:8px; color:#1e3a5f; letter-spacing:.06em; }

/* Section header */
.sec-hdr { font-family:'Space Mono',monospace; font-size:11px; letter-spacing:.2em; text-transform:uppercase; color:#cbd5f5; border-bottom:1px solid #0d1929; padding-bottom:7px; margin-bottom:10px; }

/* ── Tournament cards (redesigned) ── */
.tc-list { display:flex; flex-direction:column; gap:6px; }

.tc-card {
    background: #0b1120;
    border: 1px solid #0d1929;
    border-radius: 6px;
    overflow: hidden;
}
.tc-card.tc-live {
    border-color: rgba(255,255,255,.12);
}

/* header row inside card */
.tc-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 9px 12px;
    border-bottom: 1px solid #0d1929;
    flex-wrap: wrap;
}
.tc-regime {
    font-family: 'Space Mono', monospace;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: .16em;
    text-transform: uppercase;
}
.tc-winner-badge {
    font-family: 'Space Mono', monospace;
    font-size: 8px;
    padding: 2px 8px;
    border-radius: 3px;
}
.tc-live-tag {
    font-family: 'Space Mono', monospace;
    font-size: 7px;
    padding: 2px 6px;
    border-radius: 3px;
    background: rgba(255,255,255,.06);
    color: #94a3b8;
    margin-left: auto;
    letter-spacing: .1em;
    text-transform: uppercase;
}

/* body: two columns — models | conditions */
.tc-body {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0;
}
.tc-col {
    padding: 9px 12px;
}
.tc-col:first-child {
    border-right: 1px solid #0d1929;
}

.tc-row-label {
    font-family: 'Space Mono', monospace;
    font-size: 7px;
    letter-spacing: .14em;
    text-transform: uppercase;
    color: #2a4a6a;
    margin-bottom: 6px;
}

/* model score rows */
.tc-model-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 4px;
    font-family: 'Space Mono', monospace;
    font-size: 9px;
}
.tc-model-name { color: #8ba3bb; }
.tc-model-name.winner { color: #e2e8f0; font-weight: 700; }
.tc-model-ret { }
.tc-model-ret.winner { font-weight: 700; }

/* condition rows */
.tc-cond {
    display: flex;
    gap: 6px;
    margin-bottom: 4px;
    font-family: 'Space Mono', monospace;
    font-size: 8.5px;
    line-height: 1.55;
}
.tc-cond-key {
    color: #6ea8d4;
    font-weight: 700;
    min-width: 36px;
    flex-shrink: 0;
}
.tc-cond-val { color: #a8bdd4; }

/* footer: SL / TP */
.tc-footer {
    display: flex;
    gap: 18px;
    padding: 7px 12px;
    border-top: 1px solid #0d1929;
    background: #080e1a;
    font-family: 'Space Mono', monospace;
    font-size: 8px;
}
.tc-footer-key { color: #6ea8d4; font-weight: 700; margin-right: 4px; }
.tc-footer-val { color: #94a3b8; }

/* Trade table */
.tscroll { max-height:370px; overflow-y:auto; border-radius:6px; background:#0b1120; border:1px solid #0d1929; }
.tscroll::-webkit-scrollbar { width:3px; }
.tscroll::-webkit-scrollbar-thumb { background:#0d1929; border-radius:2px; }
.ttable { width:100%; border-collapse:collapse; font-family:'Space Mono',monospace; font-size:9px; }
.ttable th { color:#94a3b8; font-size:10px; letter-spacing:.16em; text-transform:uppercase; padding:7px 10px; border-bottom:1px solid #0d1929; text-align:left; font-weight:400; position:sticky; top:0; background:#0b1120; z-index:1; }
.ttable td { padding:6px 10px; border-bottom:1px solid #080b14; color:#e2e8f0; font-size: 11px;}
.ttable tr:last-child td { border-bottom:none; }
.ttable tr:hover td { background:#0d1929; }
.sig-b { color:#10b981; font-weight:700; } .sig-s { color:#ef4444; font-weight:700; }
.pnl-p { color:#10b981; } .pnl-n { color:#ef4444; } .pnl-d { color:#1e3a5f; }

/* Chart wrap */
.cwrap { background:#0b1120; border:1px solid #0d1929; border-radius:6px; padding:4px 4px 0; }

/* Dist bar */
.dist-bar-outer { display:flex; height:5px; border-radius:3px; overflow:hidden; margin-bottom:8px; }
.dist-labels { display:flex; gap:14px; flex-wrap:wrap; }
.dist-lbl { display:flex; align-items:center; gap:5px; font-family:'Space Mono',monospace; font-size:8px; color:#cbd5f5; }
.dist-dot { width:5px; height:5px; border-radius:50%; }

/* Streamlit elements */
#MainMenu, footer { visibility:hidden; }
header[data-testid="stHeader"] { background:transparent !important; }
.stButton > button { background:#0b1120 !important; color:#334155 !important; border:1px solid #0d1929 !important; border-radius:4px !important; font-family:'Space Mono',monospace !important; font-size:8px !important; letter-spacing:.14em !important; text-transform:uppercase !important; width:100% !important; padding:8px !important; }
.stButton > button:hover { color:#475569 !important; border-color:#1e3a5f !important; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
REGIME_COLORS = {"Bullish":"#10b981","Bearish":"#ef4444","Volatile":"#f59e0b","Neutral":"#6366f1"}

PLOTLY_THEME = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="#0b1120",

    font=dict(
        family="Space Mono",
        color="#e2e8f0",   # ✅ lighter readable gray (tailwind slate-400)
        size=11           # ✅ slightly bigger
    ),

    xaxis=dict(
        gridcolor="#0d1929",
        showgrid=True,
        zeroline=False,
        tickfont=dict(size=10, color="#94a3b8")
    ),

    yaxis=dict(
        gridcolor="#0d1929",
        showgrid=True,
        zeroline=False,
        tickfont=dict(size=10, color="#94a3b8")
    ),

    margin=dict(l=0, r=0, t=20, b=0),
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

    ma_bt = Backtester(df, MovingAverageStrategy())
    ma_eq, ma_tr = ma_bt.run()

    multi = MultiModelStrategy(models=["qwen2.5:7b-instruct","llama3.2:3b"], verbose=False)
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
    pk=equity[0]; dd=0
    for v in equity:
        pk=max(pk,v); dd=max(dd,(pk-v)/pk*100)
    return {"final":f,"return":ret,"trades":len(trades),"win_rate":wr,"max_dd":dd}


def sec(title):
    st.markdown(f"<div class='sec-hdr'>{title}</div>", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("<div class='sidebar-brand'>StratGen</div>", unsafe_allow_html=True)
    st.markdown("<div class='sidebar-tagline'>LLM Multi-Model Tournament</div>", unsafe_allow_html=True)

    sidebar_items = [
        ("Index","NIFTY 50"),("Period","Jan 2020 – Now"),("Capital","₹1,00,000"),
        ("Model A","qwen2.5:7b"),("Model B","llama3.2:3b"),
        ("Strategy","Regime-Aware"),("Baseline","MA Crossover"),
    ]
    sb_html = ""
    for lbl, val in sidebar_items:
        sb_html += f"<div class='sidebar-row'><span class='s-lbl'>{lbl}</span><span class='s-val'>{val}</span></div>"
    st.markdown(sb_html, unsafe_allow_html=True)
    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    if st.button("↺  Re-run Pipeline"):
        st.cache_data.clear(); st.rerun()

    st.markdown(
        "<div style='font-family:Space Mono,monospace;font-size:7px;color:#0d1929;"
        "letter-spacing:.12em;text-transform:uppercase;margin-top:32px'>Educational use only</div>",
        unsafe_allow_html=True,
    )


# ── Load ──────────────────────────────────────────────────────────────────────
st.markdown(
    "<div style='font-family:Space Mono,monospace;font-size:22px;font-weight:700;"
    "color:#dde4f0;letter-spacing:-.02em;margin-bottom:2px'>StratGen</div>"
    "<div style='font-family:Space Mono,monospace;font-size:11px;letter-spacing:.18em;"
    "text-transform:uppercase;color:#94a3b8;margin-bottom:16px'>"
    "LLM-Driven · Regime-Aware · Multi-Model Tournament · NIFTY 50</div>",
    unsafe_allow_html=True,
)

with st.spinner("Running pipeline: data → indicators → regime → LLM tournament → backtest…"):
    df, ma_eq, ma_tr, mm_eq, mm_tr, multi = load_and_run()

ma_m   = calc(ma_eq, ma_tr)
mm_m   = calc(mm_eq, mm_tr)
mr     = multi.model_results
bpr    = multi.best_per_regime
strats = multi.final_strategies
cr     = df["regime"].iloc[-1]
cc     = REGIME_COLORS.get(cr, "#6366f1")


# ── Regime banner ─────────────────────────────────────────────────────────────
best_model_short = bpr.get(cr,{}).get("model","?").split(":")[0].split("/")[-1]
best_ret         = bpr.get(cr,{}).get("return",0)
st.markdown(
    f"<div class='regime-banner' style='background:{cc}11;border:1px solid {cc}33'>"
    f"<div class='r-dot' style='background:{cc};box-shadow:0 0 7px {cc}88'></div>"
    f"<span class='r-name' style='color:{cc}'>Live Regime: {cr}</span>"
    f"<span class='r-info'>&#183; Best model this regime: "
    f"<span style='color:{cc}'>{best_model_short}</span> "
    f"<span style='color:#334155'>({best_ret:+.1f}%)</span></span>"
    f"<span class='r-meta'>NIFTY 50 &nbsp;&#183;&nbsp; &#8377;1,00,000 capital &nbsp;&#183;&nbsp; "
    f"LLM strategy vs MA crossover baseline</span>"
    f"</div>",
    unsafe_allow_html=True,
)


# ── KPI strip ─────────────────────────────────────────────────────────────────
alpha    = mm_m["return"] - ma_m["return"]
dd_delta = mm_m["max_dd"] - ma_m["max_dd"]

kpis = [
    ("Portfolio Value",    f"&#8377;{mm_m['final']:,.0f}",  f"+&#8377;{mm_m['final']-100000:,.0f}", "c-grn"),
    ("Multi-Model Return", f"{mm_m['return']:+.1f}%",       f"vs MA {ma_m['return']:+.1f}%  &#916;{alpha:+.1f}%",
     "c-grn" if alpha >= 0 else "c-red"),
    ("Win Rate",           f"{mm_m['win_rate']:.1f}%",      f"MA {ma_m['win_rate']:.1f}%",
     "c-grn" if mm_m["win_rate"] >= ma_m["win_rate"] else "c-red"),
    ("Total Trades",       str(mm_m["trades"]),              f"MA {ma_m['trades']} trades", "c-dim"),
    ("Max Drawdown",       f"{mm_m['max_dd']:.1f}%",        f"MA {ma_m['max_dd']:.1f}%  &#916;{dd_delta:+.1f}%",
     "c-grn" if dd_delta <= 0 else "c-red"),
    ("MA Baseline Value",  f"&#8377;{ma_m['final']:,.0f}",  f"+&#8377;{ma_m['final']-100000:,.0f}", "c-dim"),
]

html_kpi = "<div class='kpi-strip'>"
for lbl, val, dlt, cls in kpis:
    html_kpi += (
        f"<div class='kpi-cell'>"
        f"<div class='kpi-lbl'>{lbl}</div>"
        f"<div class='kpi-val'>{val}</div>"
        f"<div class='kpi-dlt {cls}'>{dlt}</div>"
        f"</div>"
    )
html_kpi += "</div>"
st.markdown(html_kpi, unsafe_allow_html=True)


# ── Equity Curve  |  Trade Log ────────────────────────────────────────────────
eq_col, tr_col = st.columns([3, 2], gap="small")

with eq_col:
    sec("Equity Curve — Multi-Model vs MA Crossover")

    dates  = df.index[-len(mm_eq):]
    fig_eq = go.Figure()

    prev, bs = None, None
    for date, regime in df["regime"].iloc[-len(mm_eq):].items():
        if regime != prev:
            if prev:
                fig_eq.add_vrect(x0=bs, x1=date,
                    fillcolor=REGIME_COLORS.get(prev,"#6366f1"), opacity=0.04, line_width=0)
            prev, bs = regime, date
    if prev:
        fig_eq.add_vrect(x0=bs, x1=dates[-1],
            fillcolor=REGIME_COLORS.get(prev,"#6366f1"), opacity=0.04, line_width=0)

    fig_eq.add_trace(go.Scatter(
        x=dates, y=ma_eq[-len(dates):], name="MA Crossover",
        line=dict(color="#1e3a5f", width=1.5, dash="dot"),
    ))
    fig_eq.add_trace(go.Scatter(
        x=dates, y=mm_eq[-len(dates):], name="Multi-Model",
        line=dict(color="#10b981", width=2),
        fill="tonexty", fillcolor="rgba(16,185,129,0.04)",
    ))
    fig_eq.add_hline(y=100000, line_dash="dot", line_color="#0d1929", line_width=1)

    di = {d: i for i, d in enumerate(dates)}
    for d, act, p in mm_tr:
        if d in di:
            idx = di[d]; v = mm_eq[idx] if idx < len(mm_eq) else None
            if v:
                fig_eq.add_trace(go.Scatter(
                    x=[d], y=[v], mode="markers", showlegend=False,
                    marker=dict(
                        symbol="triangle-up" if act=="BUY" else "triangle-down",
                        size=7, opacity=0.85,
                        color="#10b981" if act=="BUY" else "#ef4444",
                    ),
                ))

    fig_eq.update_layout(
        **PLOTLY_THEME, height=360,
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1,
                    bgcolor="rgba(0,0,0,0)", font=dict(size=11, color="#e2e8f0")),
    )
    fig_eq.update_yaxes(tickprefix="₹", tickformat=",.0f")

    st.markdown("<div class='cwrap'>", unsafe_allow_html=True)
    st.plotly_chart(fig_eq, use_container_width=True, config={"displayModeBar": False})
    st.markdown("</div>", unsafe_allow_html=True)

with tr_col:
    sec("Recent Trades — Multi-Model (last 40)")

    rows_t, bq = [], []
    for date, act, price in mm_tr:
        if act == "BUY":
            bq.append((date, price))
            rows_t.append({
                "date":   date.strftime("%d %b %y"),
                "sig":    "BUY",
                "price":  f"&#8377;{price:,.0f}",
                "pnl":    "&#8212;",
                "regime": df.loc[date,"regime"] if date in df.index else "?",
            })
        elif act == "SELL" and bq:
            _, bp = bq.pop(0)
            pct   = (price - bp) / bp * 100
            rows_t.append({
                "date":   date.strftime("%d %b %y"),
                "sig":    "SELL",
                "price":  f"&#8377;{price:,.0f}",
                "pnl":    f"{'+'if pct>=0 else ''}{pct:.1f}%",
                "regime": df.loc[date,"regime"] if date in df.index else "?",
            })

    if rows_t:
        recent = list(reversed(rows_t[-40:]))
        tbody  = ""
        for r in recent:
            sc  = "sig-b" if r["sig"]=="BUY" else "sig-s"
            pv  = r["pnl"]
            pc  = "pnl-p" if pv.startswith("+") else ("pnl-n" if pv.startswith("-") else "pnl-d")
            rc2 = REGIME_COLORS.get(r["regime"],"#334155")
            tbody += (
                "<tr>"
                f"<td>{r['date']}</td>"
                f"<td class='{sc}'>{r['sig']}</td>"
                f"<td>{r['price']}</td>"
                f"<td class='{pc}'>{pv}</td>"
                f"<td><span style='color:{rc2}'>{r['regime']}</span></td>"
                "</tr>"
            )
        st.markdown(
            "<div class='tscroll'>"
            "<table class='ttable'>"
            "<thead><tr><th>Date</th><th>Signal</th><th>Price</th><th>P&amp;L</th><th>Regime</th></tr></thead>"
            f"<tbody>{tbody}</tbody>"
            "</table></div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div style='color:#1e3a5f;font-family:Space Mono,monospace;font-size:10px;padding:20px 0'>No trades recorded.</div>",
            unsafe_allow_html=True,
        )


# ── Tournament Cards  |  Comparison Charts ────────────────────────────────────
st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
tour_col, charts_col = st.columns([3, 2], gap="small")

with tour_col:
    sec("Tournament — LLM Regime Strategies")

    model_names     = list(mr.keys())
    regimes_ordered = ["Bullish", "Bearish", "Volatile", "Neutral"]
    regimes_present = [r for r in regimes_ordered if r in bpr]

    cards_html = "<div class='tc-list'>"

    for regime in regimes_present:
        rc_color  = REGIME_COLORS.get(regime, "#6366f1")
        winner_m  = bpr[regime]["model"]
        w_short   = winner_m.split(":")[0].split("/")[-1]
        w_ret     = bpr[regime]["return"]
        strat     = strats.get(regime, {})
        is_active = (regime == cr)

        badge_bg  = rc_color + "22"
        badge_bd  = rc_color + "55"
        live_cls  = " tc-live" if is_active else ""
        live_tag  = f"<span class='tc-live-tag'>&#9679; LIVE</span>" if is_active else ""

        # ── model score rows
        model_rows_html = ""
        for mn in model_names:
            ret_val = mr[mn]["metrics"].get(regime, {}).get("return", 0)
            is_w    = (mn == winner_m)
            short   = mn.split(":")[0].split("/")[-1]
            name_cls = "tc-model-name winner" if is_w else "tc-model-name"
            ret_color = rc_color if is_w else "#4a6a80"
            crown   = "&#9733; " if is_w else "&nbsp;&nbsp; "
            model_rows_html += (
                f"<div class='tc-model-row'>"
                f"<span class='{name_cls}'>{crown}{short}</span>"
                f"<span class='tc-model-ret {'winner' if is_w else ''}' style='color:{ret_color}'>{ret_val:+.1f}%</span>"
                f"</div>"
            )

        # ── conditions
        entry_cond = strat.get("entry_condition", "—")
        exit_cond  = strat.get("exit_condition",  "—")
        sl_val     = strat.get("stop_loss", 0) * 100
        tp_val     = strat.get("take_profit", 0) * 100

        cards_html += (
            f"<div class='tc-card{live_cls}' style='border-left:3px solid {rc_color}'>"

            # header
            f"<div class='tc-header'>"
            f"<span class='tc-regime' style='color:{rc_color}'>{regime.upper()}</span>"
            f"<span class='tc-winner-badge' style='background:{badge_bg};color:{rc_color};border:1px solid {badge_bd}'>"
            f"&#9733; {w_short} &nbsp;{w_ret:+.1f}%</span>"
            f"{live_tag}"
            f"</div>"

            # body — models left, conditions right
            f"<div class='tc-body'>"

            f"<div class='tc-col'>"
            f"<div class='tc-row-label'>Models</div>"
            f"{model_rows_html}"
            f"</div>"

            f"<div class='tc-col'>"
            f"<div class='tc-row-label'>Conditions</div>"
            f"<div class='tc-cond'><span class='tc-cond-key'>Entry</span><span class='tc-cond-val'>{entry_cond}</span></div>"
            f"<div class='tc-cond'><span class='tc-cond-key'>Exit</span><span class='tc-cond-val'>{exit_cond}</span></div>"
            f"</div>"

            f"</div>"  # /tc-body

            # footer
            f"<div class='tc-footer'>"
            f"<span><span class='tc-footer-key'>SL</span><span class='tc-footer-val'>{sl_val:.1f}%</span></span>"
            f"<span><span class='tc-footer-key'>TP</span><span class='tc-footer-val'>{tp_val:.1f}%</span></span>"
            f"</div>"

            f"</div>"  # /tc-card
        )

    cards_html += "</div>"
    st.markdown(cards_html, unsafe_allow_html=True)


with charts_col:
    sec("Strategy Comparison — Key Metrics")

    cats    = ["Return %","Win Rate %","Max DD %","Trades"]
    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(
        name="MA Baseline", x=cats,
        y=[ma_m["return"],ma_m["win_rate"],ma_m["max_dd"],ma_m["trades"]],
        marker_color="#1e3a5f", opacity=0.95,
    ))
    fig_bar.add_trace(go.Bar(
        name="Multi-Model", x=cats,
        y=[mm_m["return"],mm_m["win_rate"],mm_m["max_dd"],mm_m["trades"]],
        marker_color="#10b981", opacity=0.95,
    ))
    fig_bar.update_layout(
        **PLOTLY_THEME, height=180, barmode="group",
        legend=dict(orientation="h", yanchor="bottom", y=1.01,
                    bgcolor="rgba(0,0,0,0)", font=dict(size=11, color="#e2e8f0")),
    )
    st.markdown("<div class='cwrap'>", unsafe_allow_html=True)
    st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False})
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    sec("Per-Regime Returns by Model")

    regimes_list = list(bpr.keys())
    fig_rr       = go.Figure()
    colors_m = ["#818cf8", "#fbbf24", "#34d399", "#f87171"]
    for i, mn in enumerate(model_names):
        rets = [
            mr[mn]["metrics"].get("per_regime",{}).get(r,{}).get("return",0)
            for r in regimes_list
        ]
        fig_rr.add_trace(go.Bar(
            name=mn.split(":")[0].split("/")[-1],
            x=regimes_list, y=rets,
            marker_color=colors_m[i % len(colors_m)], opacity=0.9,
        ))
    fig_rr.update_layout(
        **PLOTLY_THEME, height=160, barmode="group",
        legend=dict(orientation="h", yanchor="bottom", y=1.01,
                    bgcolor="rgba(0,0,0,0)", font=dict(size=11, color="#e2e8f0")),
    )
    fig_rr.update_xaxes(
        tickfont=dict(size=11, color="#e2e8f0")
    )

    fig_rr.update_yaxes(
        ticksuffix="%",
        tickfont=dict(size=11, color="#e2e8f0")
    )
    st.markdown("<div class='cwrap'>", unsafe_allow_html=True)
    st.plotly_chart(fig_rr, use_container_width=True, config={"displayModeBar": False})
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    sec("Regime Distribution")

    rc_counts = df["regime"].value_counts()
    total_pts = rc_counts.sum()
    dist_segs = dist_labels_html = ""
    for reg, cnt in rc_counts.items():
        pct = cnt / total_pts * 100
        clr = REGIME_COLORS.get(reg,"#6366f1")
        dist_segs        += f"<div style='width:{pct:.1f}%;background:{clr};height:100%'></div>"
        dist_labels_html += (
            f"<div class='dist-lbl'>"
            f"<div class='dist-dot' style='background:{clr}'></div>"
            f"{reg} {pct:.0f}%</div>"
        )

    st.markdown(
        f"<div class='dist-bar-outer'>{dist_segs}</div>"
        f"<div class='dist-labels'>{dist_labels_html}</div>",
        unsafe_allow_html=True,
    )


# ── NIFTY Price Chart ─────────────────────────────────────────────────────────
st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
sec("NIFTY 50 — Price Coloured by Regime")

fig_p = go.Figure()
for regime, color in REGIME_COLORS.items():
    mask = df["regime"] == regime
    fig_p.add_trace(go.Scatter(
        x=df.index[mask], y=df["Close"][mask],
        mode="markers", name=regime,
        marker=dict(color=color, size=2, opacity=0.6),
    ))
fig_p.add_trace(go.Scatter(x=df.index, y=df["SMA_20"], name="SMA 20",
    line=dict(color="#6366f1", width=1, dash="dot")))
fig_p.add_trace(go.Scatter(x=df.index, y=df["SMA_50"], name="SMA 50",
    line=dict(color="#f59e0b", width=1, dash="dot")))
fig_p.update_layout(
    **PLOTLY_THEME, height=220,
    legend=dict(orientation="h", yanchor="bottom", y=1.01,
                bgcolor="rgba(0,0,0,0)", font=dict(size=11, color="#e2e8f0")),
)
fig_p.update_yaxes(tickprefix="₹", tickformat=",.0f")

st.markdown("<div class='cwrap'>", unsafe_allow_html=True)
st.plotly_chart(fig_p, use_container_width=True, config={"displayModeBar": False})
st.markdown("</div>", unsafe_allow_html=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(
    "<div style='text-align:center;padding:24px 0 8px;"
    "color:#0d1929;font-size:7px;font-family:Space Mono,monospace;letter-spacing:.2em'>"
    "STRATGEN &nbsp;&#183;&nbsp; LLM MULTI-MODEL TOURNAMENT &nbsp;&#183;&nbsp; EDUCATIONAL USE ONLY"
    "</div>",
    unsafe_allow_html=True,
)