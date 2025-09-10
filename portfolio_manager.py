import json
import os
from typing import Dict, Union, Optional


class Portfolio:
    def __init__(self, initial_cash: float = 10000.0):
        """Initialize a new portfolio with initial cash amount."""
        self.cash = initial_cash
        self.holdings: Dict[str, int] = {}  # ticker -> quantity
        self.total_value = initial_cash

    def execute_buy(self, ticker: str, quantity: int, price: float) -> bool:
        """
        Execute a buy order for a given ticker.
        Returns True if the order was successful, False otherwise.
        """
        cost = quantity * price
        if cost > self.cash:
            return False

        self.cash -= cost
        self.holdings[ticker] = self.holdings.get(ticker, 0) + quantity
        self._update_total_value(price_dict={ticker: price})
        return True

    def execute_sell(self, ticker: str, quantity: int, price: float) -> bool:
        """
        Execute a sell order for a given ticker.
        Returns True if the order was successful, False otherwise.
        """
        if ticker not in self.holdings or self.holdings[ticker] < quantity:
            return False

        self.cash += quantity * price
        self.holdings[ticker] -= quantity

        if self.holdings[ticker] == 0:
            del self.holdings[ticker]

        self._update_total_value(price_dict={ticker: price})
        return True

    def close_all_positions(self, ticker: str, price: float) -> None:
        """Close all positions for a given ticker at the specified price."""
        if ticker in self.holdings:
            quantity = self.holdings[ticker]
            self.execute_sell(ticker, quantity, price)

    def _update_total_value(self, price_dict: Dict[str, float]) -> None:
        """Update the total portfolio value based on current holdings and prices."""
        holdings_value = sum(
            price_dict.get(ticker, 0) * quantity
            for ticker, quantity in self.holdings.items()
        )
        self.total_value = self.cash + holdings_value

    def get_position(self, ticker: str) -> int:
        """Get the current position size for a given ticker."""
        return self.holdings.get(ticker, 0)

    def save_portfolio_state(self, filepath: str = "portfolio_state.json") -> None:
        """Save the current portfolio state to a JSON file."""
        state = {
            "cash": self.cash,
            "holdings": self.holdings,
            "total_value": self.total_value
        }
        with open(filepath, 'w') as f:
            json.dump(state, f)

    @classmethod
    def load_portfolio_state(cls, filepath: str = "portfolio_state.json") -> 'Portfolio':
        """Load portfolio state from a JSON file or create a new portfolio if file doesn't exist."""
        if not os.path.exists(filepath):
            return cls()

        with open(filepath, 'r') as f:
            state = json.load(f)

        # Create with 0 since we'll set it from state
        portfolio = cls(initial_cash=0)
        portfolio.cash = state["cash"]
        portfolio.holdings = state["holdings"]
        portfolio.total_value = state["total_value"]
        return portfolio
