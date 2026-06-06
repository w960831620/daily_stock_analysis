"""
US Liquidity Dashboard
美股流动性红黄绿灯看板

Run:
    streamlit run app.py
"""

from __future__ import annotations

import io
import math
import time
from datetime import date, timedelta
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf


# =============================
# Page config
# =============================
st.set_page_config(
    page_title="US Liquidity Dashboard",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded",
)


FRED_SERIES = {
    "WALCL": "Fed Total Assets / 美联储总资产",
    "WTREGEN": "TGA Treasury General Account / 财政部现金账户",
    "RRPONTSYD": "Reverse Repo / 隔夜逆回购",
    "RESBALNS": "Bank Reserves / 银行准备金",
    "SOFR": "SOFR",
    "IORB": "IORB",
    "NFCI": "Chicago Fed NFCI / 金融条件",
    "BAMLH0A0HYM2": "HY Spread / 高收益债利差",
}

MARKET_TICKERS = {
    "SPX": "^GSPC",
    "SPY": "SPY",
    "QQQ": "QQQ",
    "VIX": "^VIX",
    "BTC": "BTC-USD",
    "HYG": "HYG",
    "TLT": "TLT",
    "DXY_PROXY": "UUP",
}


# =============================
# Utilities
# =============================
def _to_numeric(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def latest_value(s: pd.Series, default: float = np.nan) -> float:
    s = s.dropna()
    if s.empty:
        return default
    return float(s.iloc[-1])


def pct_change_days(s: pd.Series, days: int) -> float:
    s = s.dropna()
    if len(s) < 2:
        return np.nan
    end = s.iloc[-1]
    # use approximate calendar position, then nearest available observation
    target_date = s.index[-1] - pd.Timedelta(days=days)
    past = s.loc[:target_date]
    if past.empty:
        past_val = s.iloc[0]
    else:
        past_val = past.iloc[-1]
    if past_val == 0 or pd.isna(past_val):
        return np.nan
    return float((end / past_val - 1) * 100)


def abs_change_days(s: pd.Series, days: int) -> float:
    s = s.dropna()
    if len(s) < 2:
        return np.nan
    target_date = s.index[-1] - pd.Timedelta(days=days)
    past = s.loc[:target_date]
    past_val = past.iloc[0] if past.empty else past.iloc[-1]
    return float(s.iloc[-1] - past_val)


def zscore_last(s: pd.Series, window: int = 252) -> float:
    s = s.dropna()
    if len(s) < 30:
        return np.nan
    recent = s.tail(min(window, len(s)))
    std = recent.std()
    if std == 0 or pd.isna(std):
        return np.nan
    return float((recent.iloc[-1] - recent.mean()) / std)


def traffic_light(score: float) -> Tuple[str, str, str]:
    if score >= 70:
        return "🟢", "Green", "流动性/风险偏好偏多"
    if score >= 45:
        return "🟡", "Yellow", "中性震荡，等待确认"
    return "🔴", "Red", "流动性/风险偏好偏空"


def fmt_num(x: float, digits: int = 2, suffix: str = "") -> str:
    if x is None or pd.isna(x):
        return "N/A"
    return f"{x:,.{digits}f}{suffix}"


def fred_unit_to_billion(series_id: str, s: pd.Series) -> pd.Series:
    """Convert major FRED balance-sheet series to USD billions when possible.

    WALCL / WTREGEN / RESBALNS are usually in millions of dollars.
    RRPONTSYD is usually in billions of dollars. This heuristic keeps the
    dashboard robust even if FRED metadata changes.
    """
    s = s.copy()
    if series_id in {"WALCL", "WTREGEN", "RESBALNS"}:
        return s / 1000.0
    if series_id == "RRPONTSYD":
        # If values look like millions, convert to billions; otherwise keep.
        median = s.dropna().median()
        return s / 1000.0 if median and median > 100000 else s
    return s


# =============================
# Data loading
# =============================
@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def fetch_fred_series(series_id: str, start: str) -> pd.Series:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    if "DATE" not in df.columns or series_id not in df.columns:
        raise ValueError(f"FRED response does not contain {series_id}")
    df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce")
    df = df.dropna(subset=["DATE"]).set_index("DATE")
    s = _to_numeric(df[series_id]).dropna()
    s = s.loc[pd.to_datetime(start) :]
    return fred_unit_to_billion(series_id, s)


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def fetch_market_data(start: str) -> pd.DataFrame:
    tickers = list(MARKET_TICKERS.values())
    raw = yf.download(
        tickers=tickers,
        start=start,
        progress=False,
        auto_adjust=True,
        group_by="column",
        threads=True,
    )
    if raw.empty:
        raise ValueError("Yahoo Finance returned empty data")

    if isinstance(raw.columns, pd.MultiIndex):
        close = raw["Close"].copy()
    else:
        close = raw[["Close"]].copy()
        close.columns = tickers[:1]

    rename = {v: k for k, v in MARKET_TICKERS.items()}
    close = close.rename(columns=rename)
    close.index = pd.to_datetime(close.index).tz_localize(None)
    return close.sort_index()


def make_demo_data(years: int = 5) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rng = pd.date_range(date.today() - timedelta(days=365 * years), date.today(), freq="B")
    n = len(rng)
    np.random.seed(42)

    walcl = 7200 + np.cumsum(np.random.normal(0, 2.5, n))
    tga = 650 + 120 * np.sin(np.linspace(0, 14, n)) + np.random.normal(0, 15, n)
    rrp = np.maximum(100, 1200 - np.linspace(0, 850, n) + np.random.normal(0, 20, n))
    reserves = 3100 + np.cumsum(np.random.normal(0, 3, n))
    nfci = -0.35 + 0.12 * np.sin(np.linspace(0, 10, n)) + np.random.normal(0, 0.02, n)
    hy = 3.6 + 0.45 * np.sin(np.linspace(0, 16, n)) + np.random.normal(0, 0.05, n)
    sofr = 4.8 + 0.05 * np.sin(np.linspace(0, 4, n))
    iorb = 4.75 + 0.02 * np.sin(np.linspace(0, 4, n))

    net = walcl - tga - rrp
    spx = 4200 + (net - net[0]) * 0.35 + np.cumsum(np.random.normal(0.7, 18, n))
    qqq = 350 + (spx - spx[0]) / 55 + np.cumsum(np.random.normal(0, 1.2, n))
    vix = np.maximum(11, 21 - pct_rank_series(pd.Series(net)).values * 8 + np.random.normal(0, 1.5, n))
    btc = 45000 + (net - net[0]) * 12 + np.cumsum(np.random.normal(20, 550, n))

    fred = pd.DataFrame(
        {
            "WALCL": walcl,
            "WTREGEN": tga,
            "RRPONTSYD": rrp,
            "RESBALNS": reserves,
            "SOFR": sofr,
            "IORB": iorb,
            "NFCI": nfci,
            "BAMLH0A0HYM2": hy,
        },
        index=rng,
    )
    market = pd.DataFrame(
        {
            "SPX": spx,
            "SPY": spx / 10,
            "QQQ": qqq,
            "VIX": vix,
            "BTC": btc,
            "HYG": 75 + np.cumsum(np.random.normal(0.01, 0.08, n)),
            "TLT": 92 + np.cumsum(np.random.normal(0.00, 0.25, n)),
            "DXY_PROXY": 29 + np.cumsum(np.random.normal(0.00, 0.04, n)),
        },
        index=rng,
    )
    return fred, market


def pct_rank_series(s: pd.Series, window: int = 252) -> pd.Series:
    return s.rolling(window, min_periods=30).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1])


def load_all_data(years: int) -> Tuple[pd.DataFrame, pd.DataFrame, bool, List[str]]:
    start = (date.today() - timedelta(days=365 * years)).isoformat()
    errors: List[str] = []
    demo_mode = False

    fred_frames = {}
    try:
        for sid in FRED_SERIES:
            fred_frames[sid] = fetch_fred_series(sid, start)
        fred = pd.DataFrame(fred_frames).sort_index()
    except Exception as e:
        errors.append(f"FRED 获取失败，已切换 Demo Mode：{e}")
        demo_mode = True
        fred, market = make_demo_data(years)
        return fred, market, demo_mode, errors

    try:
        market = fetch_market_data(start)
    except Exception as e:
        errors.append(f"Yahoo Finance 获取失败，已切换 Demo Mode：{e}")
        demo_mode = True
        fred, market = make_demo_data(years)
        return fred, market, demo_mode, errors

    return fred, market, demo_mode, errors


# =============================
# Signal engine
# =============================
def prepare_model_frame(fred: pd.DataFrame, market: pd.DataFrame) -> pd.DataFrame:
    daily_index = market.index.union(fred.index).sort_values()
    f = fred.reindex(daily_index).ffill()
    m = market.reindex(daily_index).ffill()
    df = pd.concat([f, m], axis=1)

    df["NET_LIQ"] = df["WALCL"] - df["WTREGEN"] - df["RRPONTSYD"]
    df["NET_LIQ_4W_CHG"] = df["NET_LIQ"].diff(20)
    df["NET_LIQ_13W_CHG"] = df["NET_LIQ"].diff(65)
    df["SPX_50MA"] = df["SPX"].rolling(50).mean()
    df["SPX_200MA"] = df["SPX"].rolling(200).mean()
    df["QQQ_50MA"] = df["QQQ"].rolling(50).mean()
    df["QQQ_200MA"] = df["QQQ"].rolling(200).mean()
    df["BTC_50MA"] = df["BTC"].rolling(50).mean()
    df["VIX_20MA"] = df["VIX"].rolling(20).mean()
    df["HY_20MA"] = df["BAMLH0A0HYM2"].rolling(20).mean()
    df["SOFR_IORB"] = df["SOFR"] - df["IORB"]
    df["NFCI_4W_CHG"] = df["NFCI"].diff(20)
    return df.dropna(how="all")


def add_score(points: List[Tuple[str, float, str]], name: str, value: float, reason: str) -> None:
    points.append((name, max(0.0, min(float(value), 100.0)), reason))


def compute_score(df: pd.DataFrame) -> Tuple[float, pd.DataFrame, List[str], List[str]]:
    points: List[Tuple[str, float, str]] = []
    reasons_pos: List[str] = []
    reasons_neg: List[str] = []

    row = df.dropna(subset=["SPX"]).iloc[-1]

    net_4w = abs_change_days(df["NET_LIQ"], 28)
    net_13w = abs_change_days(df["NET_LIQ"], 91)
    reserves_4w = abs_change_days(df["RESBALNS"], 28)
    nfci = latest_value(df["NFCI"])
    nfci_4w = abs_change_days(df["NFCI"], 28)
    hy = latest_value(df["BAMLH0A0HYM2"])
    hy_4w = abs_change_days(df["BAMLH0A0HYM2"], 28)
    vix = latest_value(df["VIX"])
    vix_4w = abs_change_days(df["VIX"], 28)
    sofr_iorb = latest_value(df["SOFR_IORB"])

    # 1. Core liquidity
    net4_score = 80 if net_4w > 150 else 65 if net_4w > 0 else 35 if net_4w > -150 else 15
    add_score(points, "净流动性4周变化", net4_score, f"4周变化 {fmt_num(net_4w, 0)} 十亿美元")
    if net_4w > 0:
        reasons_pos.append("净流动性4周改善")
    else:
        reasons_neg.append("净流动性4周下降")

    net13_score = 80 if net_13w > 300 else 60 if net_13w > 0 else 35 if net_13w > -300 else 15
    add_score(points, "净流动性13周变化", net13_score, f"13周变化 {fmt_num(net_13w, 0)} 十亿美元")

    reserve_score = 75 if reserves_4w > 75 else 60 if reserves_4w > 0 else 40 if reserves_4w > -75 else 20
    add_score(points, "银行准备金变化", reserve_score, f"4周变化 {fmt_num(reserves_4w, 0)} 十亿美元")

    # 2. Financial conditions and credit
    nfci_score = 80 if nfci < -0.35 and nfci_4w <= 0 else 65 if nfci < 0 and nfci_4w <= 0.05 else 40 if nfci < 0.2 else 20
    add_score(points, "NFCI金融条件", nfci_score, f"NFCI {fmt_num(nfci, 2)}，4周变化 {fmt_num(nfci_4w, 2)}")
    if nfci_4w <= 0:
        reasons_pos.append("NFCI下行，金融条件边际宽松")
    else:
        reasons_neg.append("NFCI上行，金融条件边际收紧")

    hy_score = 80 if hy < 3.5 and hy_4w <= 0 else 65 if hy < 4.5 else 40 if hy < 5.5 else 20
    add_score(points, "高收益债利差", hy_score, f"HY Spread {fmt_num(hy, 2)}%，4周变化 {fmt_num(hy_4w, 2)}")
    if hy_4w > 0.3:
        reasons_neg.append("高收益债利差扩大，信用压力升温")

    funding_score = 80 if sofr_iorb < 0.05 else 60 if sofr_iorb < 0.15 else 35 if sofr_iorb < 0.30 else 15
    add_score(points, "SOFR-IORB资金压力", funding_score, f"SOFR-IORB {fmt_num(sofr_iorb, 2)}%")

    # 3. Risk appetite
    vix_score = 85 if vix < 15 and vix_4w <= 0 else 70 if vix < 20 else 45 if vix < 28 else 20
    add_score(points, "VIX风险偏好", vix_score, f"VIX {fmt_num(vix, 2)}，4周变化 {fmt_num(vix_4w, 2)}")
    if vix < 20:
        reasons_pos.append("VIX处于可控区间")
    else:
        reasons_neg.append("VIX偏高，市场波动压力仍在")

    # 4. Price confirmation
    spx_score = 50
    if row["SPX"] > row["SPX_50MA"] > row["SPX_200MA"]:
        spx_score = 85
        reasons_pos.append("SPX站上50日与200日均线，价格确认偏多")
    elif row["SPX"] > row["SPX_200MA"]:
        spx_score = 65
    elif row["SPX"] < row["SPX_50MA"] < row["SPX_200MA"]:
        spx_score = 20
        reasons_neg.append("SPX跌破关键均线，价格结构偏弱")
    else:
        spx_score = 45
    add_score(points, "SPX趋势确认", spx_score, f"SPX {fmt_num(row['SPX'], 0)} / 50MA {fmt_num(row['SPX_50MA'], 0)} / 200MA {fmt_num(row['SPX_200MA'], 0)}")

    qqq_score = 50
    if row["QQQ"] > row["QQQ_50MA"] > row["QQQ_200MA"]:
        qqq_score = 85
        reasons_pos.append("QQQ趋势强于长期均线，科技权重风险偏好尚可")
    elif row["QQQ"] > row["QQQ_200MA"]:
        qqq_score = 65
    elif row["QQQ"] < row["QQQ_50MA"] < row["QQQ_200MA"]:
        qqq_score = 20
        reasons_neg.append("QQQ均线结构转弱")
    else:
        qqq_score = 45
    add_score(points, "QQQ趋势确认", qqq_score, f"QQQ {fmt_num(row['QQQ'], 2)}")

    btc_score = 70 if row["BTC"] > row["BTC_50MA"] else 40
    add_score(points, "BTC风险偏好", btc_score, f"BTC {fmt_num(row['BTC'], 0)} / 50MA {fmt_num(row['BTC_50MA'], 0)}")

    weights = {
        "净流动性4周变化": 0.18,
        "净流动性13周变化": 0.12,
        "银行准备金变化": 0.10,
        "NFCI金融条件": 0.13,
        "高收益债利差": 0.10,
        "SOFR-IORB资金压力": 0.08,
        "VIX风险偏好": 0.10,
        "SPX趋势确认": 0.10,
        "QQQ趋势确认": 0.06,
        "BTC风险偏好": 0.03,
    }

    score_df = pd.DataFrame(points, columns=["指标", "分数", "说明"])
    score = float(sum(score_df.loc[i, "分数"] * weights.get(score_df.loc[i, "指标"], 0) for i in score_df.index))
    score = max(0.0, min(100.0, score))
    return score, score_df, reasons_pos, reasons_neg


def prediction_text(score: float, positives: List[str], negatives: List[str]) -> Tuple[str, str, str]:
    light, color, desc = traffic_light(score)
    if score >= 70:
        direction = "Bullish / 偏多"
        rhythm = "未来1-4周更偏向震荡上行或回调可买，前提是净流动性继续改善且VIX不快速上冲。"
    elif score >= 45:
        direction = "Neutral / 中性"
        rhythm = "未来1-4周更偏向震荡，适合等价格确认；不宜单靠流动性信号重仓押方向。"
    else:
        direction = "Bearish / 偏空"
        rhythm = "未来1-4周需要防回撤，尤其关注信用利差、VIX、SOFR-IORB是否继续恶化。"

    reason = "；".join((positives[:3] + negatives[:3])[:5])
    if not reason:
        reason = desc
    return direction, rhythm, reason


# =============================
# Charts
# =============================
def make_net_liquidity_chart(df: pd.DataFrame) -> go.Figure:
    plot_df = df.dropna(subset=["NET_LIQ", "SPX"]).tail(900)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=plot_df.index,
            y=plot_df["NET_LIQ"],
            name="Net Liquidity（十亿美元）",
            mode="lines",
            yaxis="y1",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=plot_df.index,
            y=plot_df["SPX"],
            name="SPX",
            mode="lines",
            yaxis="y2",
        )
    )
    fig.update_layout(
        title="Net Liquidity vs SPX",
        xaxis_title="Date",
        yaxis=dict(title="Net Liquidity / 十亿美元"),
        yaxis2=dict(title="SPX", overlaying="y", side="right"),
        hovermode="x unified",
        height=520,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def make_market_chart(df: pd.DataFrame) -> go.Figure:
    plot_df = df.dropna(subset=["SPX"]).tail(450)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df["SPX"], name="SPX", mode="lines"))
    fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df["SPX_50MA"], name="SPX 50MA", mode="lines"))
    fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df["SPX_200MA"], name="SPX 200MA", mode="lines"))
    fig.update_layout(title="SPX Trend Confirmation", height=420, hovermode="x unified")
    return fig


def make_score_gauge(score: float) -> go.Figure:
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            number={"suffix": "/100"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"thickness": 0.35},
                "steps": [
                    {"range": [0, 45], "color": "#f8d7da"},
                    {"range": [45, 70], "color": "#fff3cd"},
                    {"range": [70, 100], "color": "#d1e7dd"},
                ],
                "threshold": {"line": {"width": 4}, "thickness": 0.75, "value": score},
            },
            title={"text": "Liquidity Score"},
        )
    )
    fig.update_layout(height=260, margin=dict(l=20, r=20, t=50, b=10))
    return fig


def trend_label(price: float, ma50: float, ma200: float) -> str:
    if pd.isna(price) or pd.isna(ma50) or pd.isna(ma200):
        return "N/A"
    if price > ma50 > ma200:
        return "🟢 强趋势"
    if price > ma200:
        return "🟡 中性偏强"
    if price < ma50 < ma200:
        return "🔴 弱趋势"
    return "🟡 分歧"


# =============================
# UI
# =============================
st.title("💧 US Liquidity Dashboard")
st.caption("美股流动性红黄绿灯 + SPX走势预测。用途是监控风险环境，不是保证收益的交易信号。")

with st.sidebar:
    st.header("设置")
    years = st.slider("历史数据年数", min_value=2, max_value=10, value=5, step=1)
    auto_refresh_hours = st.selectbox("页面自动刷新", ["关闭", "1小时", "3小时", "6小时", "12小时"], index=3)
    st.write("数据源：FRED + Yahoo Finance")
    if st.button("立即刷新缓存"):
        st.cache_data.clear()
        st.rerun()

refresh_map = {"1小时": 3600, "3小时": 10800, "6小时": 21600, "12小时": 43200}
if auto_refresh_hours != "关闭":
    st.markdown(f"<meta http-equiv='refresh' content='{refresh_map[auto_refresh_hours]}'>", unsafe_allow_html=True)

with st.spinner("正在获取 FRED 与 Yahoo Finance 数据..."):
    fred, market, demo_mode, errors = load_all_data(years)
    df = prepare_model_frame(fred, market)
    score, score_df, positives, negatives = compute_score(df)

light, color, desc = traffic_light(score)
direction, rhythm, reason = prediction_text(score, positives, negatives)
last = df.dropna(subset=["SPX"]).iloc[-1]

if demo_mode:
    st.warning("当前为 Demo Mode：外部数据获取失败，页面使用模拟数据演示。联网后重新刷新即可。")
for e in errors:
    st.info(e)

col1, col2, col3, col4 = st.columns([1.1, 1.1, 1.4, 1.4])
with col1:
    st.metric("红黄绿灯", f"{light} {color}", desc)
with col2:
    st.metric("流动性评分", f"{score:.0f}/100")
with col3:
    st.metric("SPX走势判断", direction)
with col4:
    st.metric("数据日期", str(df.dropna(subset=["SPX"]).index[-1].date()))

st.plotly_chart(make_score_gauge(score), use_container_width=True)

st.subheader("结论")
st.write(f"**{direction}**：{rhythm}")
st.write(f"**主要依据：**{reason}")

k1, k2, k3, k4, k5 = st.columns(5)
with k1:
    st.metric("Net Liquidity", fmt_num(latest_value(df["NET_LIQ"]), 0, " B"), fmt_num(abs_change_days(df["NET_LIQ"], 28), 0, " B / 4W"))
with k2:
    st.metric("SPX", fmt_num(last["SPX"], 0), trend_label(last["SPX"], last["SPX_50MA"], last["SPX_200MA"]))
with k3:
    st.metric("QQQ", fmt_num(last["QQQ"], 2), trend_label(last["QQQ"], last["QQQ_50MA"], last["QQQ_200MA"]))
with k4:
    st.metric("VIX", fmt_num(last["VIX"], 2), fmt_num(abs_change_days(df["VIX"], 28), 2, " / 4W"))
with k5:
    st.metric("NFCI", fmt_num(last["NFCI"], 2), fmt_num(abs_change_days(df["NFCI"], 28), 2, " / 4W"))

st.divider()

st.subheader("核心图表")
st.plotly_chart(make_net_liquidity_chart(df), use_container_width=True)
st.plotly_chart(make_market_chart(df), use_container_width=True)

st.subheader("因子评分明细")
st.dataframe(score_df, use_container_width=True, hide_index=True)

with st.expander("查看原始数据尾部"):
    cols = [
        "WALCL",
        "WTREGEN",
        "RRPONTSYD",
        "RESBALNS",
        "NET_LIQ",
        "SOFR",
        "IORB",
        "SOFR_IORB",
        "NFCI",
        "BAMLH0A0HYM2",
        "SPX",
        "QQQ",
        "VIX",
        "BTC",
    ]
    st.dataframe(df[cols].tail(30), use_container_width=True)

st.caption(
    "说明：净流动性 = 美联储总资产 - TGA - RRP。FRED余额表指标统一近似为十亿美元。"
    "该模型用于风险监控和节奏判断，不构成投资建议。"
)
