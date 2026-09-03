import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="Breakout Scanner", layout="wide")
st.title("📈 Stock Breakout Scanner")

# --- User input ---
tickers_input = st.text_input("Enter tickers (comma-separated)", "AAPL, NVDA, TSLA")
TICKERS = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]
LOOKBACK_DAYS = 150
run_button = st.button("Run Scan")

def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def compute_macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line

def flag_hammer(df):
    body = (df['Close'] - df['Open']).abs()
    lower_wick = df[['Open', 'Close']].min(axis=1) - df['Low']
    upper_wick = df['High'] - df[['Open', 'Close']].max(axis=1)
    total_range = df['High'] - df['Low']
    return (lower_wick >= 2 * body) & (upper_wick <= body * 0.5) & (total_range > 0)

def flag_bullish_engulfing(df):
    prev_open = df['Open'].shift(1)
    prev_close = df['Close'].shift(1)
    prev_is_bearish = prev_close < prev_open
    curr_is_bullish = df['Close'] > df['Open']
    engulfs = (df['Open'] <= prev_close) & (df['Close'] >= prev_open)
    return prev_is_bearish & curr_is_bullish & engulfs

if run_button:
    results_summary = []
    alerts = []

    for ticker in TICKERS:
        with st.spinner(f"Fetching {ticker}..."):
            data = yf.download(ticker, period=f"{LOOKBACK_DAYS}d", interval="1d", progress=False)

        if data.empty:
            st.warning(f"No data for {ticker}, skipping.")
            continue

        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        df = data.copy()
        df['SMA20'] = df['Close'].rolling(window=20).mean()
        df['SMA50'] = df['Close'].rolling(window=50).mean()
        df['RSI14'] = compute_rsi(df['Close'], 14)
        df['MACD'], df['MACD_Signal'] = compute_macd(df['Close'])
        df['AvgVol20'] = df['Volume'].rolling(window=20).mean()
        df['VolSpikeRatio'] = df['Volume'] / df['AvgVol20']
        df['Hammer'] = flag_hammer(df)
        df['BullishEngulfing'] = flag_bullish_engulfing(df)

        latest = df.iloc[-1]
        trend_bullish = (latest['Close'] > latest['SMA20'] > latest['SMA50']) and (latest['MACD'] > latest['MACD_Signal'])
        volume_spike = latest['VolSpikeRatio'] >= 1.5
        pattern_aligned = bool(latest['Hammer']) or bool(latest['BullishEngulfing'])
        is_breakout = trend_bullish and volume_spike and pattern_aligned

        results_summary.append({
            "Ticker": ticker, "Close": round(latest['Close'], 2),
            "SMA20": round(latest['SMA20'], 2), "SMA50": round(latest['SMA50'], 2),
            "RSI14": round(latest['RSI14'], 1), "MACD": round(latest['MACD'], 3),
            "MACD_Signal": round(latest['MACD_Signal'], 3),
            "VolSpikeRatio": round(latest['VolSpikeRatio'], 2),
            "Hammer": bool(latest['Hammer']), "BullishEngulfing": bool(latest['BullishEngulfing']),
            "TrendBullish": trend_bullish, "BREAKOUT": is_breakout
        })
        if is_breakout:
            alerts.append(ticker)

    st.subheader("Scan Summary")
    st.dataframe(pd.DataFrame(results_summary), use_container_width=True)

    st.subheader("Breakout Alerts")
    if alerts:
        for t in alerts:
            st.success(f"🚀 {t} — bullish trend + volume spike + pattern aligned")
    else:
        st.info("No breakout alerts today.")
