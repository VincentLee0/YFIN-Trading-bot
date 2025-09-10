import streamlit as st
import plotly.graph_objects as go
from datetime import datetime
import time
import pandas as pd

from trading_logic import (
    fetch_stock_data,
    calculate_sma,
    calculate_volatility,
    generate_signal,
    calculate_position_size
)
from portfolio_manager import Portfolio

# Page config
st.set_page_config(page_title="Trading Bot Simulator", layout="wide")

# Initialize session state
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = Portfolio.load_portfolio_state()
if 'trading_active' not in st.session_state:
    st.session_state.trading_active = False
if 'trade_log' not in st.session_state:
    st.session_state.trade_log = []


def add_trade_log(message: str):
    """Add a message to the trade log with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.trade_log.insert(0, f"{timestamp}: {message}")


# Sidebar controls
with st.sidebar:
    st.title("Trading Controls")
    ticker = st.text_input("Stock Ticker", value="AAPL").upper()

    # SMA Parameters
    st.subheader("SMA Parameters")
    short_window = st.slider("Short SMA Window (minutes)", 1, 15, 5)
    long_window = st.slider("Long SMA Window (minutes)", 5, 30, 15)

    # Trading Parameters
    st.subheader("Trading Parameters")
    risk_factor = st.slider("Risk Factor (%)", 1, 5, 2) / 100

    # Control buttons
    if st.button("Start Trading" if not st.session_state.trading_active else "Stop Trading"):
        st.session_state.trading_active = not st.session_state.trading_active

        if not st.session_state.trading_active:  # If stopping
            portfolio = st.session_state.portfolio
            try:
                data = fetch_stock_data(ticker, "1d", "1m")
                current_price = data['Close'].iloc[-1]
                portfolio.close_all_positions(ticker, current_price)
                portfolio.save_portfolio_state()
                add_trade_log(
                    f"Closed all positions for {ticker} at ${current_price:.2f}")
            except Exception as e:
                st.error(f"Error closing positions: {str(e)}")

# Main area
st.title("Trading Bot Simulator")

# Portfolio metrics
col1, col2, col3 = st.columns(3)
portfolio = st.session_state.portfolio

with col1:
    st.metric("Cash", f"${portfolio.cash:.2f}")
with col2:
    holdings_value = sum(portfolio.holdings.values())
    st.metric("Holdings", f"{holdings_value} shares")
with col3:
    st.metric("Total Value", f"${portfolio.total_value:.2f}")

# Charts
try:
    # Fetch data with error handling
    try:
        # Get 1-day data with 1-minute intervals
        data = fetch_stock_data(ticker, "1d", "1m")
        if data.empty:
            st.error(
                f"No data available for {ticker}. Please check the ticker symbol.")
            st.stop()
    except Exception as e:
        st.error(f"Error fetching data for {ticker}: {str(e)}")
        st.stop()

    # Calculate indicators
    short_sma = calculate_sma(data, short_window)
    long_sma = calculate_sma(data, long_window)

    # Create price chart
    fig = go.Figure()

    # Candlestick chart
    fig.add_trace(go.Candlestick(
        x=data.index,
        open=data['Open'],
        high=data['High'],
        low=data['Low'],
        close=data['Close'],
        name='Price'
    ))

    # Add SMAs
    fig.add_trace(go.Scatter(
        x=data.index,
        y=short_sma,
        name=f'SMA {short_window}',
        line=dict(color='blue')
    ))

    fig.add_trace(go.Scatter(
        x=data.index,
        y=long_sma,
        name=f'SMA {long_window}',
        line=dict(color='orange')
    ))

    fig.update_layout(
        title=f"{ticker} Price and SMA",
        yaxis_title="Price",
        xaxis_title="Time",
        width=800,  # Set fixed width
        height=500,  # Set fixed height
        margin=dict(l=50, r=50, t=50, b=50),  # Adjust margins
        paper_bgcolor='rgba(0,0,0,0)',  # Transparent background
        plot_bgcolor='rgba(0,0,0,0)',   # Transparent plot area
        xaxis=dict(
            showgrid=True,
            gridcolor='rgba(128,128,128,0.2)',
            showline=True,
            linewidth=1,
            linecolor='rgba(128,128,128,0.2)'
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(128,128,128,0.2)',
            showline=True,
            linewidth=1,
            linecolor='rgba(128,128,128,0.2)'
        )
    )

    # Create a container with custom width
    container = st.container()
    with container:
        st.plotly_chart(fig, use_container_width=True, config={
                        'displayModeBar': False}, key="stock_chart")

    # Trading logic
    if st.session_state.trading_active:
        current_price = data['Close'].iloc[-1]
        volatility = calculate_volatility(data)
        signal = generate_signal(short_sma, long_sma)

        if signal != 'HOLD':
            if signal == 'BUY':
                # Calculate position size
                cash_to_invest = portfolio.cash * 0.5  # Use 50% of available cash
                shares = calculate_position_size(
                    cash_to_invest, current_price, volatility, risk_factor
                )

                if shares > 0 and portfolio.execute_buy(ticker, shares, current_price):
                    add_trade_log(
                        f"BUY: {shares} shares of {ticker} at ${current_price:.2f}"
                    )
            else:  # SELL
                shares = portfolio.get_position(ticker)
                if shares > 0 and portfolio.execute_sell(ticker, shares, current_price):
                    add_trade_log(
                        f"SELL: {shares} shares of {ticker} at ${current_price:.2f}"
                    )

        portfolio.save_portfolio_state()
        st.rerun()

except Exception as e:
    st.error(f"Error: {str(e)}")

# Trade Log
st.subheader("Trade Log")
for log in st.session_state.trade_log[:50]:  # Show last 50 trades
    st.text(log)
