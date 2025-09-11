import json
import os
from typing import Dict, Union, Optional


class Portfolio:
    def __init__(self, initial_cash: float = 10000.0):
        """Initialize a new portfolio with initial cash amount."""
        self.cash = float(initial_cash)  # Ensure it's a float
        # ticker -> quantity (positive for long, negative for short)
        self.holdings: Dict[str, int] = {}
        self.margin_requirement = 0.5  # 50% margin requirement for shorts
        self.total_value = float(initial_cash)  # Ensure it's a float
        # ticker -> average entry price
        self.short_positions: Dict[str, float] = {}

        # Validate initial values
        if self.cash != 10000.0 and initial_cash == 10000.0:
            self.cash = 10000.0
            self.total_value = 10000.0

    def execute_buy(self, ticker: str, quantity: int, price: float) -> bool:
        """
        Execute a buy order for a given ticker.
        If there's an existing short position, this will close it first.
        Returns True if the order was successful, False otherwise.
        """
        current_position = self.holdings.get(ticker, 0)
        cost = quantity * price

        # If we have a short position
        if current_position < 0:
            # Calculate profit/loss from closing short
            short_entry_price = self.short_positions.get(ticker, price)
            short_profit = (short_entry_price - price) * abs(current_position)
            self.cash += short_profit

            # Remove short position tracking
            if ticker in self.short_positions:
                del self.short_positions[ticker]

            # Adjust quantity to account for closing short
            quantity = max(0, quantity + current_position)
            cost = quantity * price

        if cost > self.cash:
            return False

        self.cash -= cost
        self.holdings[ticker] = current_position + quantity

        if self.holdings[ticker] == 0:
            del self.holdings[ticker]

        self._update_total_value(price_dict={ticker: price})
        return True

    def execute_sell(self, ticker: str, quantity: int, price: float, allow_short: bool = True) -> bool:
        """
        Execute a sell order for a given ticker.
        Can create or increase a short position if allow_short is True.
        Returns True if the order was successful, False otherwise.
        """
        current_position = self.holdings.get(ticker, 0)

        # If we're closing a long position
        if current_position > 0:
            sell_quantity = min(quantity, current_position)
            self.cash += sell_quantity * price
            self.holdings[ticker] = current_position - sell_quantity

            if self.holdings[ticker] == 0:
                del self.holdings[ticker]

            quantity -= sell_quantity  # Reduce quantity by amount sold

        # If we still have quantity to sell and shorting is allowed
        if quantity > 0 and allow_short:
            margin_required = quantity * price * self.margin_requirement

            if margin_required > self.cash:
                return False

            # Track average entry price for short position
            if ticker not in self.short_positions:
                self.short_positions[ticker] = price
            else:
                # Update average entry price
                current_short = abs(self.holdings.get(ticker, 0))
                total_short = current_short + quantity
                self.short_positions[ticker] = (
                    (current_short *
                     self.short_positions[ticker] + quantity * price)
                    / total_short
                )

            self.holdings[ticker] = current_position - quantity
            self.cash -= margin_required  # Reserve margin requirement

        self._update_total_value(price_dict={ticker: price})
        return True

    def close_all_positions(self, ticker: str, price: float) -> None:
        """
        Close all positions (both long and short) for a given ticker at the specified price.
        For long positions: sells all shares
        For short positions: buys to cover all short shares
        """
        if ticker in self.holdings:
            quantity = self.holdings[ticker]
            if quantity > 0:  # Long position
                self.execute_sell(ticker, quantity, price)
            else:  # Short position
                self.execute_buy(ticker, abs(quantity), price)
            # Clear any remaining tracking
            if ticker in self.holdings:
                del self.holdings[ticker]
            if ticker in self.short_positions:
                del self.short_positions[ticker]

    def _update_total_value(self, price_dict: Dict[str, float]) -> None:
        """Update the total portfolio value based on current holdings and prices."""
        # If no holdings, total value should equal cash
        if not self.holdings:
            self.total_value = self.cash
            return

        value = self.cash

        for ticker, quantity in self.holdings.items():
            current_price = price_dict.get(ticker, 0)

            if quantity > 0:  # Long position
                value += current_price * quantity
            else:  # Short position
                short_entry_price = self.short_positions.get(
                    ticker, current_price)
                # Return margin requirement when calculating total value
                margin_held = abs(quantity) * current_price * \
                    self.margin_requirement
                unrealized_profit = (short_entry_price -
                                     current_price) * abs(quantity)
                value += margin_held + unrealized_profit

        self.total_value = value

    def get_position(self, ticker: str) -> int:
        """Get the current position size for a given ticker."""
        return self.holdings.get(ticker, 0)

    def save_portfolio_state(self, filepath: str = "portfolio_state.json") -> None:
        """Save the current portfolio state to a JSON file."""
        state = {
            "cash": self.cash,
            "holdings": self.holdings,
            "total_value": self.total_value,
            "short_positions": self.short_positions
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
        portfolio.short_positions = state.get(
            "short_positions", {})  # Backward compatibility
        return portfolio
