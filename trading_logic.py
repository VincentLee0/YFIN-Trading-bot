import yfinance as yf
import pandas as pd
import numpy as np
from typing import Tuple, Optional, Literal

Signal = Literal['BUY', 'SELL', 'HOLD']


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
