import yfinance as yf
import pandas as pd
import numpy as np
import time
from typing import Tuple, Optional, Literal
from rate_limiter import RateLimiter

Signal = Literal['BUY', 'SELL', 'HOLD']

# Create rate limiters for different API endpoints
MARKET_STATUS_LIMITER = RateLimiter(max_requests=2, time_window=1)
DATA_FETCH_LIMITER = RateLimiter(max_requests=2, time_window=1)


def get_market_status(ticker: str) -> tuple[bool, str, str]:
    """
    Check if the market is open for the given ticker.

    Returns:
        Tuple of (is_market_open, market_state, next_open_or_close)
    """
    try:
        # Wait for rate limit
        MARKET_STATUS_LIMITER.wait_if_needed()

        # Make the request
        stock = yf.Ticker(ticker)
        info = stock.info

        # Get current time in market's timezone
        current_time = pd.Timestamp.now(tz=info.get(
            'exchangeTimezoneName', 'America/New_York'))

        # Get market hours
        market_open = pd.Timestamp.now(tz=info.get('exchangeTimezoneName', 'America/New_York')).replace(
            hour=9, minute=30, second=0, microsecond=0
        )
        market_close = pd.Timestamp.now(tz=info.get('exchangeTimezoneName', 'America/New_York')).replace(
            hour=16, minute=0, second=0, microsecond=0
        )

        is_market_open = market_open <= current_time <= market_close

        # Get next event time
        if is_market_open:
            next_event = market_close
            state = f"OPEN - {info.get('exchange', 'Unknown Exchange')}"
            next_event_str = f"Closes at {next_event.strftime('%H:%M %Z')}"
        else:
            if current_time < market_open:
                next_event = market_open
                next_event_str = f"Opens at {next_event.strftime('%H:%M %Z')}"
            else:
                next_event = market_open + pd.Timedelta(days=1)
                next_event_str = f"Opens Tomorrow at {next_event.strftime('%H:%M %Z')}"
            state = f"CLOSED - {info.get('exchange', 'Unknown Exchange')}"

        return is_market_open, state, next_event_str
    except Exception as e:
        return False, "ERROR", str(e)


def fetch_stock_data(ticker: str, period: str = "1mo", interval: str = "1d") -> pd.DataFrame:
    """
    Fetch historical stock data from Yahoo Finance.

    Args:
        ticker: Stock symbol
        period: Data period (e.g., "1d", "1mo", "1y")
        interval: Data interval (e.g., "1m", "1h", "1d")

    Returns:
        DataFrame with stock data
    """
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        return df
    except Exception as e:
        raise ValueError(f"Error fetching data for {ticker}: {str(e)}")


def calculate_sma(data: pd.DataFrame, window: int) -> pd.Series:
    """Calculate Simple Moving Average."""
    return data['Close'].rolling(window=window).mean()


def calculate_volatility(data: pd.DataFrame, window: int = 20) -> float:
    """
    Calculate volatility as standard deviation of returns.
    For minute-based data, we use a smaller window by default.
    """
    # Convert window from minutes to number of periods if data is minute-based
    if isinstance(data.index, pd.DatetimeIndex) and data.index.freq == 'T':
        window = min(window, len(data) // 2)  # Ensure window isn't too large

    returns = data['Close'].pct_change()
    volatility = returns.rolling(window=window).std().iloc[-1]
    return volatility if volatility is not None else 0.01  # Default if no data


def generate_signal(short_sma: pd.Series, long_sma: pd.Series) -> Signal:
    """
    Generate trading signal based on SMA crossover.
    Returns 'BUY', 'SELL', or 'HOLD'.
    """
    if len(short_sma) < 2 or len(long_sma) < 2:
        return 'HOLD'

    # Current and previous values
    current_short = short_sma.iloc[-1]
    current_long = long_sma.iloc[-1]
    prev_short = short_sma.iloc[-2]
    prev_long = long_sma.iloc[-2]

    # Check for crossover
    if prev_short < prev_long and current_short > current_long:
        return 'BUY'
    elif prev_short > prev_long and current_short < current_long:
        return 'SELL'
    return 'HOLD'


def calculate_position_size(
    cash_to_invest: float,
    price: float,
    volatility: float,
    risk_factor: float = 0.02
) -> int:
    """
    Calculate the number of shares to trade based on volatility and risk.

    Args:
        cash_to_invest: Amount of cash available to invest
        price: Current stock price
        volatility: Stock price volatility (standard deviation)
        risk_factor: Risk factor (default 2% of portfolio)

    Returns:
        Number of shares to trade
    """
    if volatility == 0:
        volatility = 0.01  # Prevent division by zero

    # Adjust position size inversely with volatility
    position_value = (cash_to_invest * risk_factor) / volatility
    shares = int(position_value / price)

    # Ensure we don't exceed available cash
    shares = min(shares, int(cash_to_invest / price))
    return max(0, shares)  # Ensure non-negative
