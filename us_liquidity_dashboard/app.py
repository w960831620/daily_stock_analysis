from __future__ import annotations

from datetime import date, timedelta
from io import StringIO

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf


st.set_page_config(page_title="US Liquidity Dashboard", page_icon="💧", layout="wide")

YAHOO_TICKERS = {"SPY": "SPY", "QQQ": "QQQ", "VIX": "^VIX", "BTC": "BTC-USD"}
FRED_SERIES = ["WALCL", "RRPONTSYD", "SOFR", "IORB", "NFCI"]


def fetch_fred_series(series_id: str, start: str) -> pd.Series:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    frame = pd.read_csv(StringIO(response.text))
    if "DATE" not in frame.columns or series_id not in frame.columns:
        raise ValueError(f"FRED response missing {series_id}")
    frame["DATE"] = pd.to_datetime(frame["DATE"], errors="coerce")
    frame = frame.dropna(subset=["DATE"]).set_index("DATE")
    series = pd.to_numeric(frame[series_id], errors="coerce").dropna()
    series = series.loc[pd.Timestamp(start) :]
    if series_id == "WALCL":
        series = series / 1000.0
    elif series_id == "RRPONTSYD" and series.median() > 100000:
        series = series / 1000.0
    series.name = series_id
    return series


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def load_fred_data(start: str) -> pd.DataFrame:
    return pd.concat([fetch_fred_series(series_id, start) for series_id in FRED_SERIES], axis=1).sort_index()


@st.cache_data(ttl=60 * 60, show_spinner=False)
def load_yahoo_data(start: str) -> pd.DataFrame:
    raw = yf.download(list(YAHOO_TICKERS.values()), start=start, auto_adjust=True, progress=False, threads=True)
    if raw.empty:
        raise ValueError("Yahoo Finance returned empty data")
    close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
    close = close.rename(columns={ticker: label for label, ticker in YAHOO_TICKERS.items()})
    close.index = pd.to_datetime(close.index).tz_localize(None)
    return close.sort_index()


def make_demo_data(start: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = pd.date_range(pd.Timestamp(start), pd.Timestamp(date.today()), freq="B")
    n = len(rng)
    rs = np.random.default_rng(42)
    walcl = 7200 + np.cumsum(rs.normal(0.5, 4.0, n))
    rrp = np.maximum(150, 900 - np.linspace(0, 450, n) + rs.normal(0, 12, n))
    net_liq = walcl - rrp
    nfci = -0.25 + 0.15 * np.sin(np.linspace(0, 10, n)) + rs.normal(0, 0.02, n)
    sofr = 4.8 + 0.05 * np.sin(np.linspace(0, 5, n))
    iorb = 4.75 + 0.03 * np.sin(np.linspace(0, 5, n))
    spy = 420 + (net_liq - net_liq[0]) * 0.04 + np.cumsum(rs.normal(0.12, 2.1, n))
    qqq = 360 + (net_liq - net_liq[0]) * 0.05 + np.cumsum(rs.normal(0.10, 2.6, n))
    vix = np.maximum(11, 21 - pd.Series(net_liq).rank(pct=True).to_numpy() * 7 + rs.normal(0, 1.4, n))
    btc = 60000 + (net_liq - net_liq[0]) * 11 + np.cumsum(rs.normal(25, 720, n))
    fred = pd.DataFrame({"WALCL": walcl, "RRPONTSYD": rrp, "SOFR": sofr, "IORB": iorb, "NFCI": nfci}, index=rng)
    market = pd.DataFrame({"SPY": spy, "QQQ": qqq, "VIX": vix, "BTC": btc}, index=rng)
    return fred, market


def load_data(years: int) -> tuple[pd.DataFrame, pd.DataFrame, bool, str]:
    start = (date.today() - timedelta(days=365 * years)).isoformat()
    try:
        fred = load_fred_data(start)
        market = load_yahoo_data(start)
        if fred.empty or market.empty:
            raise ValueError("data source returned empty frame")
        return fred, market, False, ""
    except Exception as exc:
        fred, market = make_demo_data(start)
        return fred, market, True, str(exc)


def latest(series: pd.Series) -> float:
    series = series.dropna()
    return float(series.iloc[-1]) if not series.empty else float("nan")


def change_over(series: pd.Series, periods: int) -> float:
    series = series.dropna()
    if len(series) <= periods:
        return float("nan")
    return float(series.iloc[-1] - series.iloc[-periods - 1])


def trend_state(price: float, ma50: float) -> tuple[str, bool]:
    if pd.isna(price) or pd.isna(ma50):
        return "N/A", False
    if price > ma50:
        return "🟢 高于50MA，趋势偏强", True
    return "🔴 低于50MA，趋势偏弱", False


def vix_state(vix: float) -> tuple[str, bool]:
    if pd.isna(vix):
        return "N/A", False
    if vix < 20:
        return "🟢 低于20，波动压力可控", True
    if vix < 30:
        return "🟡 高于20，波动压力上升", False
    return "🔴 高波动状态", False


def compute_dashboard(fred: pd.DataFrame, market: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    index = fred.index.union(market.index).sort_values()
    frame = pd.concat([fred.reindex(index).ffill(), market.reindex(index).ffill()], axis=1)
    frame["NET_LIQUIDITY"] = frame["WALCL"] - frame["RRPONTSYD"]
    frame["SPY_50MA"] = frame["SPY"].rolling(50).mean()
    frame["QQQ_50MA"] = frame["QQQ"].rolling(50).mean()
    frame["BTC_50MA"] = frame["BTC"].rolling(50).mean()
    frame["SOFR_IORB"] = frame["SOFR"] - frame["IORB"]
    rows = frame.dropna(subset=["SPY", "QQQ", "VIX", "BTC"])
    last = rows.iloc[-1]
    net_4w = change_over(frame["NET_LIQUIDITY"], 20)
    nfci_4w = change_over(frame["NFCI"], 20)
    spread_now = latest(frame["SOFR_IORB"])
    spread_4w = change_over(frame["SOFR_IORB"], 20)
    spy_text, spy_bull = trend_state(last["SPY"], last["SPY_50MA"])
    qqq_text, qqq_bull = trend_state(last["QQQ"], last["QQQ_50MA"])
    btc_text, btc_bull = trend_state(last["BTC"], last["BTC_50MA"])
    vix_text, vix_bull = vix_state(last["VIX"])
    checks = [
        ("净流动性4周上升", net_4w > 0, f"{net_4w:,.0f}B"),
        ("SPY高于50MA", spy_bull, spy_text),
        ("QQQ高于50MA", qqq_bull, qqq_text),
        ("VIX低于20", vix_bull, vix_text),
        ("NFCI下降", nfci_4w < 0, f"{nfci_4w:,.2f}"),
        ("SOFR-IORB没有明显扩大", spread_now < 0.15 and spread_4w < 0.05, f"当前{spread_now:,.2f}%，4周变化{spread_4w:,.2f}%"),
    ]
    score = round(sum(100 / len(checks) for _, passed, _ in checks if passed))
    if score >= 70:
        light = "🟢 偏多"
        outlook = "Bullish"
    elif score >= 40:
        light = "🟡 中性"
        outlook = "Neutral"
    else:
        light = "🔴 偏空"
        outlook = "Bearish"
    positive = [name for name, passed, _ in checks if passed]
    negative = [name for name, passed, _ in checks if not passed]
    reason = "；".join([f"支持因素：{', '.join(positive) if positive else '暂无'}", f"拖累因素：{', '.join(negative) if negative else '暂无'}"])
    info = {
        "score": score,
        "light": light,
        "outlook": outlook,
        "reason": reason,
        "checks": checks,
        "spy_text": spy_text,
        "qqq_text": qqq_text,
        "btc_text": btc_text,
        "vix_text": vix_text,
        "net_4w": net_4w,
    }
    return frame, info


def net_liquidity_chart(frame: pd.DataFrame) -> go.Figure:
    plot = frame.dropna(subset=["NET_LIQUIDITY", "SPY"]).tail(756)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=plot.index, y=plot["NET_LIQUIDITY"], name="Net Liquidity (WALCL - RRPONTSYD, $B)", mode="lines", yaxis="y1"))
    fig.add_trace(go.Scatter(x=plot.index, y=plot["SPY"], name="SPY", mode="lines", yaxis="y2"))
    fig.update_layout(
        height=520,
        hovermode="x unified",
        xaxis_title="Date",
        yaxis=dict(title="Net Liquidity ($B)"),
        yaxis2=dict(title="SPY", overlaying="y", side="right"),
        legend=dict(orientation="h", y=1.08),
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig


st.title("US Liquidity Dashboard")
st.caption("Yahoo Finance: SPY, QQQ, ^VIX, BTC-USD | FRED: WALCL, RRPONTSYD, SOFR, IORB, NFCI")

with st.sidebar:
    years = st.slider("历史数据年数", min_value=2, max_value=10, value=5)
    if st.button("刷新数据"):
        st.cache_data.clear()
        st.rerun()

with st.spinner("正在加载数据..."):
    fred_data, market_data, demo_mode, demo_reason = load_data(years)
    dashboard_frame, dashboard = compute_dashboard(fred_data, market_data)

if demo_mode:
    st.warning(f"Demo Mode：FRED API、Yahoo Finance 或网络不可用，已使用模拟数据。原因：{demo_reason}")

score_col, light_col, outlook_col, net_col = st.columns(4)
score_col.metric("综合流动性评分", f"{dashboard['score']}/100")
light_col.metric("红黄绿灯", str(dashboard["light"]))
outlook_col.metric("未来1-4周 SPX/SPY 倾向", str(dashboard["outlook"]))
net_col.metric("Net Liquidity", f"{latest(dashboard_frame['NET_LIQUIDITY']):,.0f}B", f"{dashboard['net_4w']:,.0f}B / 4W")

st.subheader("趋势与状态")
c1, c2, c3, c4 = st.columns(4)
c1.metric("SPY趋势判断", str(dashboard["spy_text"]))
c2.metric("QQQ趋势判断", str(dashboard["qqq_text"]))
c3.metric("BTC趋势判断", str(dashboard["btc_text"]))
c4.metric("VIX状态", str(dashboard["vix_text"]), f"{latest(dashboard_frame['VIX']):,.2f}")

st.subheader("Net Liquidity 与 SPY")
st.plotly_chart(net_liquidity_chart(dashboard_frame), use_container_width=True)

st.subheader("未来1-4周 SPX/SPY 倾向")
st.write(f"**{dashboard['outlook']}**")
st.write(str(dashboard["reason"]))

st.subheader("评分明细")
score_rows = [{"指标": name, "是否加分": "是" if passed else "否", "说明": detail} for name, passed, detail in dashboard["checks"]]
st.dataframe(pd.DataFrame(score_rows), use_container_width=True, hide_index=True)

with st.expander("查看最近数据"):
    columns = ["WALCL", "RRPONTSYD", "NET_LIQUIDITY", "SOFR", "IORB", "SOFR_IORB", "NFCI", "SPY", "QQQ", "VIX", "BTC"]
    st.dataframe(dashboard_frame[columns].tail(30), use_container_width=True)

st.caption("Net Liquidity = WALCL - RRPONTSYD。该看板用于宏观流动性监控，不构成投资建议。")
