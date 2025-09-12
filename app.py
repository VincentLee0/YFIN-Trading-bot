import os
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

# Set up portfolio state file path
PORTFOLIO_STATE_FILE = os.path.join(os.path.dirname(
    os.path.abspath(__file__)), 'portfolio_state.json')

# Initialize session state
if 'portfolio' not in st.session_state:
    try:
        st.session_state.portfolio = Portfolio.load_portfolio_state(
            PORTFOLIO_STATE_FILE)
    except PermissionError:
        st.error(
            "Permission denied when accessing portfolio state file. Please check file permissions.")
        st.session_state.portfolio = Portfolio(initial_cash=10000.0)
    except Exception as e:
        st.error(f"Error loading portfolio state: {str(e)}")
        st.session_state.portfolio = Portfolio(initial_cash=10000.0)
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


# Define stock categories
STOCK_OPTIONS = {
    "United States (NYSE/NASDAQ)": {
        "Technology": ["AAPL - Apple Inc.", "MSFT - Microsoft", "GOOGL - Alphabet", "META - Meta Platforms", "NVDA - NVIDIA"],
        "Finance": ["JPM - JPMorgan Chase", "BAC - Bank of America", "GS - Goldman Sachs", "V - Visa Inc."],
        "Retail": ["AMZN - Amazon", "WMT - Walmart", "COST - Costco", "TGT - Target"],
        "Healthcare": ["JNJ - Johnson & Johnson", "PFE - Pfizer", "UNH - UnitedHealth", "ABBV - AbbVie"],
        "Industrial": ["BA - Boeing", "CAT - Caterpillar", "GE - General Electric", "MMM - 3M Company"]
    },
    "United Kingdom (LSE)": {
        "Finance": ["HSBA.L - HSBC", "BARC.L - Barclays", "LLOY.L - Lloyds Banking", "NWG.L - NatWest Group"],
        "Energy": ["BP.L - BP", "SHEL.L - Shell", "SSE.L - SSE plc"],
        "Consumer": ["TSCO.L - Tesco", "ULVR.L - Unilever", "DGE.L - Diageo"],
        "Healthcare": ["GSK.L - GSK plc", "AZN.L - AstraZeneca", "SN.L - Smith & Nephew"],
        "Industrial": ["RR.L - Rolls-Royce", "BAE.L - BAE Systems", "CRH.L - CRH plc"]
    }
}

# Sidebar controls
with st.sidebar:
    st.title("Trading Controls")

    # Initialize selected stocks in session state if not present
    if 'selected_stocks' not in st.session_state:
        st.session_state.selected_stocks = set()

    # Market and Stock Selection
    selected_market = st.selectbox(
        "Select Market",
        options=list(STOCK_OPTIONS.keys()),
        index=0,
        key="market_selector"
    )

    selected_sector = st.selectbox(
        "Select Sector",
        options=list(STOCK_OPTIONS[selected_market].keys()),
        index=0,
        key="sector_selector"
    )

    # Multi-stock selection
    available_stocks = STOCK_OPTIONS[selected_market][selected_sector]
    selected_stock = st.selectbox(
        "Select Stock",
        options=available_stocks,
        index=0,
        key="stock_selector"
    )

    # Extract ticker from selection
    current_ticker = selected_stock.split(" - ")[0].strip()

    # Add/Remove stock buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Add Stock", key="add_stock"):
            st.session_state.selected_stocks.add(current_ticker)
    with col2:
        if st.button("Remove Stock", key="remove_stock"):
            st.session_state.selected_stocks.discard(current_ticker)

    # Display selected stocks
    st.subheader("Selected Stocks for Trading")
    if not st.session_state.selected_stocks:
        st.warning("No stocks selected. Add stocks to begin trading.")
    else:
        for ticker in st.session_state.selected_stocks:
            st.info(f"🔹 {ticker}")

    # Option to clear all stocks
    if st.session_state.selected_stocks and st.button("Clear All Stocks", type="secondary"):
        if not st.session_state.trading_active:
            st.session_state.selected_stocks.clear()
            st.rerun()
        else:
            st.error("Cannot clear stocks while trading is active")

    # Optional manual ticker input
    st.divider()
    st.caption("Or enter ticker manually:")
    manual_ticker = st.text_input(
        "Custom Ticker", "", help="Enter any valid ticker symbol")
    if manual_ticker:
        manual_ticker = manual_ticker.upper()
        if st.button("Add Custom Stock"):
            st.session_state.selected_stocks.add(manual_ticker)

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
            try:
                # Create a fresh portfolio
                new_portfolio = Portfolio(initial_cash=10000.0)

                # Reset all session state
                st.session_state.portfolio = new_portfolio
                st.session_state.total_trades = 0
                st.session_state.trade_log = []
                st.session_state.last_update = None
                st.session_state.start_time = None

                # Save the fresh state
                new_portfolio.save_portfolio_state(PORTFOLIO_STATE_FILE)
                st.success("Portfolio successfully reset to $10,000")
                st.rerun()
            except PermissionError as e:
                st.error(
                    f"Permission denied when resetting portfolio. Please check file permissions.")
            except Exception as e:
                st.error(f"Error resetting portfolio: {str(e)}")
        else:
            st.error(
                "Cannot reset portfolio while trading is active. Stop trading first.")

    # Control buttons
    # Check if any selected stocks are in open markets
    markets_status = []
    if st.session_state.selected_stocks:
        for stock in st.session_state.selected_stocks:
            is_open, _, _ = get_market_status(stock)
            markets_status.append(is_open)
        any_market_open = any(markets_status)
    else:
        any_market_open = False

    start_stop_button = st.button(
        "Start Trading" if not st.session_state.trading_active else "Stop Trading",
        disabled=not any_market_open and not st.session_state.trading_active
    )

    if not any_market_open and not st.session_state.trading_active:
        st.warning("⚠️ Cannot start trading when no selected markets are open")

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
    status_cols = st.columns([1, 1])

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
# Charts and Analysis
if not st.session_state.selected_stocks:
    st.warning("Please select stocks to display charts")
else:
    try:
        for current_ticker in st.session_state.selected_stocks:
            with st.expander(f"{current_ticker} Chart", expanded=True):
                try:
                    # Get 1-day data with 1-minute intervals
                    data = fetch_stock_data(current_ticker, "1d", "1m")
                    if data.empty:
                        st.error(f"No data available for {current_ticker}")
                        continue

                    # Calculate indicators for this stock
                    short_sma = calculate_sma(data, short_window)
                    long_sma = calculate_sma(data, long_window)
                    volatility = calculate_volatility(data)
                    signal = generate_signal(short_sma, long_sma)

                    # Market status for this stock
                    is_market_open, market_state, next_event = get_market_status(
                        current_ticker)
                    market_status = "🟢 Market Open" if is_market_open else "🔴 Market Closed"
                    st.write(f"Market Status: {market_status} | {next_event}")

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
                        title=f"{current_ticker} Price and SMA",
                        yaxis_title="Price",
                        xaxis_title="Time",
                        width=800,
                        height=500,
                        margin=dict(l=50, r=50, t=50, b=50),
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
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

                    # Display chart
                    st.plotly_chart(fig, use_container_width=True,
                                    config={'displayModeBar': False})

                    # Display stock metrics
                    metric_cols = st.columns(4)
                    with metric_cols[0]:
                        st.metric("Current Price",
                                  f"${data['Close'].iloc[-1]:.2f}")
                    with metric_cols[1]:
                        st.metric("Volatility", f"{volatility:.4f}")
                    with metric_cols[2]:
                        signal_color = {
                            'BUY': 'green',
                            'SELL': 'red',
                            'HOLD': 'gray'
                        }[signal]
                        st.markdown(
                            f"<h3 style='color: {signal_color}'>Signal: {signal}</h3>",
                            unsafe_allow_html=True
                        )
                    with metric_cols[3]:
                        position = portfolio.get_position(current_ticker)
                        position_type = "LONG" if position > 0 else "SHORT" if position < 0 else "NONE"
                        st.metric(
                            "Position", f"{abs(position) if position else 0} shares {position_type}")

                except Exception as e:
                    st.error(f"Error analyzing {current_ticker}: {str(e)}")
                    continue

    except Exception as e:
        st.error(f"Error displaying charts: {str(e)}")

# Trading logic and execution
if st.session_state.trading_active and st.session_state.selected_stocks:
    try:
        # Update timestamps
        st.session_state.last_update = datetime.now()
        if not st.session_state.start_time:
            st.session_state.start_time = datetime.now()

        # Display runtime
        if st.session_state.start_time:
            runtime = datetime.now() - st.session_state.start_time
            hours = runtime.seconds // 3600
            minutes = (runtime.seconds % 3600) // 60
            seconds = runtime.seconds % 60
            st.info(f"Runtime: {hours:02d}:{minutes:02d}:{seconds:02d}")

        # Check for markets closing soon and close positions if needed
        portfolio = st.session_state.portfolio
        # Create a copy of keys to avoid modification during iteration
        for ticker in list(portfolio.holdings.keys()):
            try:
                is_open, market_state, next_event = get_market_status(ticker)
                if is_open and "market closes in" in next_event.lower():
                    # Extract minutes until close from the next_event string
                    time_str = next_event.lower().split(
                        "market closes in")[1].strip()
                    minutes_to_close = 0
                    if "hour" in time_str:
                        hours = int(time_str.split()[0])
                        minutes_to_close = hours * 60
                    elif "minute" in time_str:
                        minutes_to_close = int(time_str.split()[0])

                    # If market closes in 10 minutes or less, close all positions for this stock
                    if minutes_to_close <= 10:
                        position = portfolio.get_position(ticker)
                        if position != 0:  # If we have any position
                            stock_data = fetch_stock_data(ticker, "1d", "1m")
                            close_price = stock_data['Close'].iloc[-1]
                            position_type = "LONG" if position > 0 else "SHORT"
                            if portfolio.close_all_positions(ticker, close_price):
                                add_trade_log(
                                    f"PRE-CLOSE: Closed {position_type} position: {abs(position)} shares of {ticker} at ${close_price:.2f}"
                                )

            except Exception as e:
                st.error(f"Error checking market close for {ticker}: {str(e)}")
                continue

        # Calculate cash per stock
        num_stocks = len(st.session_state.selected_stocks)
        cash_per_stock = portfolio.cash / num_stocks

        # Process each selected stock
        for active_ticker in st.session_state.selected_stocks:
            try:
                # Fetch data for current stock
                stock_data = fetch_stock_data(active_ticker, "1d", "1m")
                current_price = stock_data['Close'].iloc[-1]

                # Calculate indicators
                stock_short_sma = calculate_sma(stock_data, short_window)
                stock_long_sma = calculate_sma(stock_data, long_window)
                stock_volatility = calculate_volatility(stock_data)
                stock_signal = generate_signal(stock_short_sma, stock_long_sma)

                if stock_signal != 'HOLD':
                    position = portfolio.get_position(active_ticker)
                    # Use equal portion of cash for each stock
                    shares = calculate_position_size(
                        cash_per_stock, current_price, stock_volatility, risk_factor
                    )

                    if stock_signal == 'BUY':
                        # If we have a short position, close it first
                        if position < 0:
                            if portfolio.execute_buy(active_ticker, abs(position), current_price):
                                add_trade_log(
                                    f"COVER SHORT: {abs(position)} shares of {active_ticker} at ${current_price:.2f}"
                                )
                        # Then open or add to long position
                        if shares > 0 and portfolio.execute_buy(active_ticker, shares, current_price):
                            add_trade_log(
                                f"BUY LONG: {shares} shares of {active_ticker} at ${current_price:.2f}"
                            )
                    else:  # SELL
                        # If we have a long position, close it first
                        if position > 0:
                            if portfolio.execute_sell(active_ticker, position, current_price):
                                add_trade_log(
                                    f"SELL LONG: {position} shares of {active_ticker} at ${current_price:.2f}"
                                )
                        # Then open or add to short position
                        if shares > 0 and portfolio.execute_sell(active_ticker, shares, current_price, allow_short=True):
                            add_trade_log(
                                f"SELL SHORT: {shares} shares of {active_ticker} at ${current_price:.2f}"
                            )

            except Exception as e:
                st.error(f"Error trading {active_ticker}: {str(e)}")
                continue

        portfolio.save_portfolio_state()
        st.rerun()

    except Exception as e:
        st.error(f"Error in trading execution: {str(e)}")

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
