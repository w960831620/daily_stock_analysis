import numpy as np
import pandas as pd
import yfinance as yf

FRED_URL = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id={}'


def fred(code, demo_base=100):
    try:
        df = pd.read_csv(FRED_URL.format(code))
        dcol = 'observation_date' if 'observation_date' in df.columns else 'DATE'
        vcol = code if code in df.columns else df.columns[-1]
        s = pd.to_numeric(df[vcol].replace('.', np.nan), errors='coerce')
        s.index = pd.to_datetime(df[dcol])
        return s.dropna().sort_index(), False
    except Exception:
        idx = pd.date_range(end=pd.Timestamp.today().normalize(), periods=900, freq='D')
        rng = np.random.default_rng(abs(hash(code)) % 2**32)
        return pd.Series(demo_base + rng.normal(0, demo_base * .002, len(idx)).cumsum(), index=idx), True


def market(ticker, base=100):
    try:
        df = yf.download(ticker, period='2y', auto_adjust=True, progress=False, threads=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        if df.empty:
            raise RuntimeError('empty data')
        return df[['Close']].dropna(), False
    except Exception:
        idx = pd.date_range(end=pd.Timestamp.today().normalize(), periods=520, freq='B')
        rng = np.random.default_rng(abs(hash(ticker)) % 2**32)
        close = base * np.exp(np.cumsum(rng.normal(.0004, .012, len(idx))))
        if ticker == '^VIX':
            close = np.clip(18 + rng.normal(0, 4, len(idx)).cumsum() * .02, 10, 45)
        return pd.DataFrame({'Close': close}, index=idx), True


def last(s):
    return float(s.dropna().iloc[-1])


def change(s, n):
    s = s.dropna()
    return float(s.iloc[-1] - s.iloc[-n]) if len(s) > n else 0.0


def trend(df):
    c = df.Close.dropna()
    ma = c.rolling(50).mean().iloc[-1]
    return ('多头' if c.iloc[-1] >= ma else '空头', float(c.iloc[-1]), float(ma))
