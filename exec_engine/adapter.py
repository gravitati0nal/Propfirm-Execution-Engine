"""Abstract broker adapter interface.

Every broker integration must subclass BrokerAdapter and implement
all abstract methods. The adapter is responsible for all broker-specific
translation — enum mapping, payload construction, response parsing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from exec_engine.types import Account, Fill, Order, Position


class BrokerAdapter(ABC):
    """Base class for all broker adapters.

    Subclass this and implement every abstract method/property
    to connect exec_engine to a specific broker API.
    """

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    @abstractmethod
    def connect(self) -> None:
        """Establish a connection to the broker.

        Raises:
            exec_engine.exceptions.ConnectionError: on failure.
        """

    @abstractmethod
    def disconnect(self) -> None:
        """Cleanly disconnect from the broker."""

    @property
    @abstractmethod
    def connected(self) -> bool:
        """Return True if the broker connection is active."""

    # ------------------------------------------------------------------
    # Order management
    # ------------------------------------------------------------------

    @abstractmethod
    def submit(self, order: Order) -> Fill:
        """Submit an order to the broker and return a Fill."""

    @abstractmethod
    def cancel(self, broker_order_id: str) -> bool:
        """Cancel an open order. Return True on success."""

    @abstractmethod
    def modify(
        self,
        broker_order_id: str,
        price: Optional[float] = None,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        quantity: Optional[float] = None,
    ) -> Fill:
        """Modify an existing order. Return updated Fill."""

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @abstractmethod
    def positions(self, symbol: Optional[str] = None) -> list[Position]:
        """Return open positions, optionally filtered by symbol."""

    @abstractmethod
    def open_orders(self, symbol: Optional[str] = None) -> list[dict]:
        """Return open/pending orders as list of dicts."""

    @abstractmethod
    def account(self) -> Account:
        """Return current account state."""

    # ------------------------------------------------------------------
    # Position management
    # ------------------------------------------------------------------

    @abstractmethod
    def close_position(self, ticket: str) -> Fill:
        """Close a single position identified by its ticket."""

    def close_all(self, symbol: Optional[str] = None) -> list[Fill]:
        """Close all open positions, optionally filtered by symbol.

        Default implementation iterates positions and closes each one.
        Override this if the broker provides a bulk-close endpoint.
        """
        fills: list[Fill] = []
        for pos in self.positions(symbol):
            fills.append(self.close_position(pos.ticket))
        return fills

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of this broker adapter."""
