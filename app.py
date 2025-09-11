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
    calculate_position_size,
    get_market_status
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
if 'last_update' not in st.session_state:
    st.session_state.last_update = None
if 'start_time' not in st.session_state:
    st.session_state.start_time = None
if 'total_trades' not in st.session_state:
    st.session_state.total_trades = 0


def add_trade_log(message: str):
    """Add a message to the trade log with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.trade_log.insert(0, f"{timestamp}: {message}")
    st.session_state.total_trades += 1


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

    # Portfolio Reset
    st.subheader("Portfolio Management")
    if st.button("Reset Portfolio to $10,000", type="secondary"):
        if not st.session_state.trading_active:  # Only allow reset when not trading
            # Create a fresh portfolio
            new_portfolio = Portfolio(initial_cash=10000.0)

            # Reset all session state
            st.session_state.portfolio = new_portfolio
            st.session_state.total_trades = 0
            st.session_state.trade_log = []
            st.session_state.last_update = None
            st.session_state.start_time = None

            # Save the fresh state
            try:
                # Delete existing file if it exists
                import os
                if os.path.exists("portfolio_state.json"):
                    os.remove("portfolio_state.json")
                # Save new state
                new_portfolio.save_portfolio_state()
                st.success("Portfolio successfully reset to $10,000")
                st.rerun()
            except Exception as e:
                st.error(f"Error resetting portfolio: {str(e)}")
        else:
            st.error(
                "Cannot reset portfolio while trading is active. Stop trading first.")

    # Control buttons
    is_market_open, _, _ = get_market_status(ticker)
    start_stop_button = st.button(
        "Start Trading" if not st.session_state.trading_active else "Stop Trading",
        disabled=not is_market_open and not st.session_state.trading_active
    )

    if not is_market_open and not st.session_state.trading_active:
        st.warning("⚠️ Cannot start trading when market is closed")

    if start_stop_button:
        st.session_state.trading_active = not st.session_state.trading_active

        if st.session_state.trading_active:  # If starting
            st.session_state.start_time = datetime.now()
        else:  # If stopping
            # Reset timers
            st.session_state.start_time = None
            st.session_state.last_update = None
            portfolio = st.session_state.portfolio
            try:
                # Close all positions for all tickers in the portfolio
                data = fetch_stock_data(ticker, "1d", "1m")
                current_price = data['Close'].iloc[-1]

                # Get all unique tickers in the portfolio
                tickers_to_close = set(portfolio.holdings.keys())

                # Close positions for each ticker
                for ticker_to_close in tickers_to_close:
                    try:
                        # Get current price for this ticker
                        ticker_data = fetch_stock_data(
                            ticker_to_close, "1d", "1m")
                        close_price = ticker_data['Close'].iloc[-1]

                        # Get position type and size before closing
                        position = portfolio.get_position(ticker_to_close)
                        position_type = "LONG" if position > 0 else "SHORT"

                        # Close the position
                        portfolio.close_all_positions(
                            ticker_to_close, close_price)

                        # Log the closure
                        add_trade_log(
                            f"Closed {position_type} position: {abs(position)} shares of {ticker_to_close} at ${close_price:.2f}"
                        )
                    except Exception as e:
                        st.error(
                            f"Error closing {ticker_to_close} position: {str(e)}")

                portfolio.save_portfolio_state()
            except Exception as e:
                st.error(f"Error during shutdown: {str(e)}")

# Main area
st.title("Trading Bot Simulator")

# Status indicator
status_container = st.container()
with status_container:
    status_cols = st.columns([1, 1, 2])

    # Bot Status
    with status_cols[0]:
        if st.session_state.trading_active:
            st.success("🤖 Bot Status: ACTIVE")
        else:
            st.warning("🤖 Bot Status: INACTIVE")

    # Last Update
    with status_cols[1]:
        if st.session_state.last_update:
            st.info(
                f"Last Update: {st.session_state.last_update.strftime('%H:%M:%S')}")

    # Market Status
    with status_cols[2]:
        is_market_open, market_state, next_event = get_market_status(ticker)
        if is_market_open:
            st.success(f"📈 Market {market_state} | {next_event}")
        else:
            st.warning(f"📉 Market {market_state} | {next_event}")

# Portfolio metrics
col1, col2, col3 = st.columns(3)
portfolio = st.session_state.portfolio

# Calculate holdings value
holdings_value = 0
if portfolio.holdings:
    try:
        prices = {}
        for ticker_in_portfolio in portfolio.holdings.keys():
            ticker_data = fetch_stock_data(ticker_in_portfolio, "1d", "1m")
            price = ticker_data['Close'].iloc[-1]
            prices[ticker_in_portfolio] = price
            qty = portfolio.holdings[ticker_in_portfolio]
            if qty > 0:  # Long position
                holdings_value += qty * price
            else:  # Short position
                short_entry_price = portfolio.short_positions.get(
                    ticker_in_portfolio, price)
                unrealized_profit = (short_entry_price - price) * abs(qty)
                margin_held = abs(qty) * price * portfolio.margin_requirement
                holdings_value += margin_held + unrealized_profit

        # Update total value with current prices
        portfolio._update_total_value(prices)
    except Exception as e:
        st.error(f"Error updating portfolio values: {str(e)}")
else:
    # This will set total value equal to cash
    portfolio._update_total_value({})

with col1:
    st.metric("Cash Available", f"${portfolio.cash:.2f}")
with col2:
    st.metric("Holdings Value", f"${holdings_value:.2f}")
with col3:
    st.metric("Total Portfolio Value", f"${portfolio.total_value:.2f}",
              delta=f"${(portfolio.total_value - 10000):+.2f}")

# Position Details Header
st.subheader("Position Details")
position_cols = st.columns(2)
with position_cols[0]:
    long_positions = sum(qty for qty in portfolio.holdings.values() if qty > 0)
    st.metric("Long Positions", f"{long_positions} shares")
with position_cols[1]:
    short_positions = sum(abs(qty)
                          for qty in portfolio.holdings.values() if qty < 0)
    st.metric("Short Positions", f"{short_positions} shares")

# Always update total value with current prices
try:
    if portfolio.holdings:
        prices = {}
        for ticker_in_portfolio in portfolio.holdings.keys():
            ticker_data = fetch_stock_data(ticker_in_portfolio, "1d", "1m")
            prices[ticker_in_portfolio] = ticker_data['Close'].iloc[-1]
        portfolio._update_total_value(prices)
    else:
        # This will set total value equal to cash
        portfolio._update_total_value({})
except Exception as e:
    st.error(f"Error updating portfolio value: {str(e)}")

# Position Details and Total Value
with st.expander("Position Details"):
    if not portfolio.holdings:
        st.info("No open positions")
    for ticker, qty in portfolio.holdings.items():
        if qty != 0:
            position_type = "LONG" if qty > 0 else "SHORT"
            if qty < 0:
                entry_price = portfolio.short_positions.get(ticker, 0)
                current_price = prices.get(ticker, 0)
                pnl = (entry_price - current_price) * abs(qty)
                st.text(
                    f"{ticker}: {abs(qty)} shares {position_type} (Entry: ${entry_price:.2f}, Current: ${current_price:.2f}, P&L: ${pnl:.2f})")
            else:
                current_price = prices.get(ticker, 0)
                pnl = (current_price - entry_price) * \
                    qty if 'entry_price' in locals() else 0
                st.text(
                    f"{ticker}: {qty} shares {position_type} (Current: ${current_price:.2f}, P&L: ${pnl:.2f})")

# Display total value after ensuring it's up to date
st.metric("Total Value", f"${portfolio.total_value:.2f}",
          # Show actual P&L from initial investment
          delta=f"${(portfolio.total_value - 10000):+.2f}")

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

    # Trading information display
    current_price = data['Close'].iloc[-1]
    volatility = calculate_volatility(data)
    signal = generate_signal(short_sma, long_sma)

    # Display current market information
    market_info_container = st.container()
    with market_info_container:
        market_col1, market_col2, market_col3, market_col4 = st.columns(4)
        with market_col1:
            st.metric("Current Price", f"${current_price:.2f}")
        with market_col2:
            st.metric("Volatility", f"{volatility:.4f}")
        with market_col3:
            signal_color = {
                'BUY': 'green',
                'SELL': 'red',
                'HOLD': 'gray'
            }[signal]
            st.markdown(
                f"<h3 style='color: {signal_color}'>Signal: {signal}</h3>", unsafe_allow_html=True)
        with market_col4:
            if st.session_state.start_time:
                runtime = datetime.now() - st.session_state.start_time
                st.metric(
                    "Running Time", f"{runtime.seconds//3600}h {(runtime.seconds % 3600)//60}m {runtime.seconds % 60}s")

    # Trading logic
    if st.session_state.trading_active:
        # Update last_update timestamp
        st.session_state.last_update = datetime.now()

        # Initialize start_time if not set
        if not st.session_state.start_time:
            st.session_state.start_time = datetime.now()

        if signal != 'HOLD':
            position = portfolio.get_position(ticker)
            cash_to_invest = portfolio.cash * 0.5  # Use 50% of available cash
            shares = calculate_position_size(
                cash_to_invest, current_price, volatility, risk_factor
            )

            if signal == 'BUY':
                # If we have a short position, close it first
                if position < 0:
                    if portfolio.execute_buy(ticker, abs(position), current_price):
                        add_trade_log(
                            f"COVER SHORT: {abs(position)} shares of {ticker} at ${current_price:.2f}"
                        )
                # Then open or add to long position
                if shares > 0 and portfolio.execute_buy(ticker, shares, current_price):
                    add_trade_log(
                        f"BUY LONG: {shares} shares of {ticker} at ${current_price:.2f}"
                    )
            else:  # SELL
                # If we have a long position, close it first
                if position > 0:
                    if portfolio.execute_sell(ticker, position, current_price):
                        add_trade_log(
                            f"SELL LONG: {position} shares of {ticker} at ${current_price:.2f}"
                        )
                # Then open or add to short position
                if shares > 0 and portfolio.execute_sell(ticker, shares, current_price, allow_short=True):
                    add_trade_log(
                        f"SELL SHORT: {shares} shares of {ticker} at ${current_price:.2f}"
                    )

        portfolio.save_portfolio_state()
        st.rerun()

except Exception as e:
    st.error(f"Error: {str(e)}")

# Trading Statistics
stats_container = st.container()
with stats_container:
    st.subheader("Trading Statistics")
    stats_col1, stats_col2, stats_col3 = st.columns(3)
    with stats_col1:
        st.metric("Total Trades", st.session_state.total_trades)
    with stats_col2:
        initial_value = 10000  # Default starting value
        current_value = portfolio.total_value
        profit_loss = current_value - initial_value
        profit_loss_pct = (profit_loss / initial_value) * \
            100 if initial_value != 0 else 0

        # Show realized P&L (based on cash changes) when no positions
        if not portfolio.holdings:
            realized_pnl = portfolio.cash - initial_value
            realized_pnl_pct = (realized_pnl / initial_value) * 100
            st.metric("Realized P/L", f"${realized_pnl:.2f}",
                      f"{realized_pnl_pct:+.2f}%")
        else:
            # Show unrealized P&L when positions are open
            st.metric("Unrealized P/L", f"${profit_loss:.2f}",
                      f"{profit_loss_pct:+.2f}%")
    with stats_col3:
        trades_per_hour = 0
        if st.session_state.start_time:
            runtime = (datetime.now() -
                       st.session_state.start_time).total_seconds() / 3600
            if runtime > 0:
                trades_per_hour = st.session_state.total_trades / runtime
        st.metric("Trades per Hour", f"{trades_per_hour:.1f}")

# Trade Log
st.subheader("Recent Trades")
for log in st.session_state.trade_log[:50]:  # Show last 50 trades
    st.text(log)
