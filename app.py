import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as px
from plotly.subplots import make_subplots

# App Header
st.set_page_config(layout="wide")
st.title("📈 Advanced Multi-Indicator Breakout Scanner")
st.markdown("Tracking Moving Averages, MACD, RSI, Volume Spikes, and Candlestick Patterns.")

# Sidebar Configuration
st.sidebar.header("Scanner Settings")
ticker = st.sidebar.text_input("Enter Stock Ticker", value="NVDA").upper()
days = st.sidebar.slider("Historical Days to Fetch", min_value=50, max_value=365, value=150)

# Fetch Data
@st.cache_data
def load_data(symbol, period):
    data = yf.download(symbol, period=f"{period}d")
    return data

if ticker:
    with st.spinner("Analyzing historical market data..."):
        df = load_data(ticker, days)
        
    if not df.empty:
        # --- 1. CALCULATE INDICATORS ---
        # Moving Averages
        df['20_SMA'] = df['Close'].rolling(window=20).mean()
        df['50_SMA'] = df['Close'].rolling(window=50).mean()
        
        # RSI (Native Pandas calculation to avoid TA-Lib installation errors)
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # MACD
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
        
        # Volume Average
        df['20_Vol_Avg'] = df['Volume'].rolling(window=20).mean()

        # --- 2. BUILD THE INTERACTIVE CHART WITH SUBPLOTS ---
        # Create a layout with 3 rows: Candlesticks (Row 1), RSI (Row 2), MACD (Row 3)
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                            vertical_spacing=0.05, 
                            row_heights=[0.5, 0.2, 0.3])

        # Row 1: Candlestick Chart
        fig.add_trace(px.Candlestick(x=df.index, open=df['Open'], high=df['High'], 
                                     low=df['Low'], close=df['Close'], name="Price"), row=1, col=1)
        # Add SMAs to Row 1
        fig.add_trace(px.Scatter(x=df.index, y=df['20_SMA'], mode='lines', name='20 SMA', line=dict(color='orange')), row=1, col=1)
        fig.add_trace(px.Scatter(x=df.index, y=df['50_SMA'], mode='lines', name='50 SMA', line=dict(color='blue')), row=1, col=1)

        # Row 2: RSI
        fig.add_trace(px.Scatter(x=df.index, y=df['RSI'], mode='lines', name='RSI', line=dict(color='purple')), row=2, col=1)
        # Add RSI reference lines (Overbought 70 / Oversold 30)
        fig.add_shape(type="line", x0=df.index[0], y0=70, x1=df.index[-1], y1=70, line=dict(color="red", dash="dash"), row=2, col=1)
        fig.add_shape(type="line", x0=df.index[0], y0=30, x1=df.index[-1], y1=30, line=dict(color="green", dash="dash"), row=2, col=1)

        # Row 3: MACD
        fig.add_trace(px.Scatter(x=df.index, y=df['MACD'], mode='lines', name='MACD', line=dict(color='green')), row=3, col=1)
        fig.add_trace(px.Scatter(x=df.index, y=df['Signal_Line'], mode='lines', name='Signal', line=dict(color='red')), row=3, col=1)

        # Chart Layout Adjustments
        fig.update_layout(height=800, xaxis_rangeslider_visible=False, template="seaborn")
        fig.update_yaxes(title_text="Price ($)", row=1, col=1)
        fig.update_yaxes(title_text="RSI", row=2, col=1)
        fig.update_yaxes(title_text="MACD", row=3, col=1)

        # Render Chart in Streamlit
        st.plotly_chart(fig, use_container_width=True)

        # --- 3. TRIGGER CONDITIONS (Scanner Signals) ---
        st.subheader("🚨 Live Indicator Diagnostic Scan")
        
        # Grab most recent data points for checking
        latest = df.iloc[-1]
        prev_volume = latest['Volume']
        avg_volume = latest['20_Vol_Avg']
        
        # Check volume spike condition (150% or higher)
        vol_spike = prev_volume >= (avg_volume * 1.5)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Current RSI", f"{latest['RSI']:.2f}", help="Below 40 is heavily oversold")
        with col2:
            st.metric("Current Volume", f"{int(latest['Volume']):,}", help="Comparing against 20-day average")
        with col3:
            st.metric("20-Day Vol Avg", f"{int(avg_volume):,}")

        # Summary Checklist
        st.markdown("### Setup Checklist Status:")
        st.write(f"✅ **Trend:** 20 SMA is above 50 SMA: `{latest['20_SMA'] > latest['50_SMA']}`")
        st.write(f"✅ **Momentum:** RSI is under 40 (Oversold): `{latest['RSI'] < 40}`")
        st.write(f"✅ **Volume Spike:** Volume is 150%+ of average: `{vol_spike}`")
        st.write(f"✅ **MACD:** Crossing Signal Line: `{latest['MACD'] > latest['Signal_Line']}`")

    else:
        st.error("No data found. Please verify the stock ticker symbol.")
