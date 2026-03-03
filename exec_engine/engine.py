"""ExecEngine — the main interface for order execution.

Users interact with this class exclusively. It delegates every call
to the underlying BrokerAdapter and adds structured logging.
"""

from __future__ import annotations

import logging
from typing import Optional

from exec_engine.adapter import BrokerAdapter
from exec_engine.types import (
    Account,
    Fill,
    Order,
    OrderType,
    Position,
    Side,
)

logger = logging.getLogger("exec_engine")


class ExecEngine:
    """Uniform order-management layer that wraps any BrokerAdapter."""

    def __init__(self, broker: BrokerAdapter) -> None:
        self.broker = broker

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Connect to the broker and log account summary."""
        self.broker.connect()
        acct = self.broker.account()
        logger.info(
            "Connected to %s | account=%s balance=%.2f equity=%.2f %s",
            self.broker.name,
            acct.account_id,
            acct.balance,
            acct.equity,
            acct.currency,
        )

    def disconnect(self) -> None:
        """Disconnect from the broker."""
        self.broker.disconnect()
        logger.info("Disconnected from %s", self.broker.name)

    # ------------------------------------------------------------------
    # Order management
    # ------------------------------------------------------------------

    def submit(self, order: Order) -> Fill:
        """Submit an order, logging request and response."""
        price_tag = f"@ {order.price}" if order.price is not None else f"@ {order.order_type.value}"
        logger.info(
            ">> %s %.2f %s %s | id=%s",
            order.side.value,
            order.quantity,
            order.symbol,
            price_tag,
            order.id,
        )
        fill = self.broker.submit(order)
        logger.info(
            "<< %s | broker_id=%s | price=%.5f | msg=%s",
            fill.status.value,
            fill.broker_order_id,
            fill.avg_price,
            fill.message,
        )
        return fill

    def cancel(self, broker_order_id: str) -> bool:
        """Cancel an open order by its broker-assigned ID."""
        result = self.broker.cancel(broker_order_id)
        logger.info("Cancel %s -> %s", broker_order_id, "OK" if result else "FAILED")
        return result

    def modify(self, broker_order_id: str, **kwargs: object) -> Fill:
        """Modify an existing order (price, sl, tp, quantity)."""
        fill = self.broker.modify(broker_order_id, **kwargs)
        logger.info("Modify %s -> %s", broker_order_id, fill.status.value)
        return fill

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def positions(self, symbol: Optional[str] = None) -> list[Position]:
        """Return open positions, optionally filtered by symbol."""
        return self.broker.positions(symbol)

    def open_orders(self, symbol: Optional[str] = None) -> list[dict]:
        """Return open/pending orders."""
        return self.broker.open_orders(symbol)

    def account(self) -> Account:
        """Return current account state."""
        return self.broker.account()

    # ------------------------------------------------------------------
    # Position management
    # ------------------------------------------------------------------

    def close(self, ticket: str) -> Fill:
        """Close a single position by ticket."""
        fill = self.broker.close_position(ticket)
        logger.info("Close %s -> %s", ticket, fill.status.value)
        return fill

    def close_all(self, symbol: Optional[str] = None) -> list[Fill]:
        """Close all positions, optionally filtered by symbol."""
        fills = self.broker.close_all(symbol)
        logger.info("Closed %d position(s) for %s", len(fills), symbol or "ALL")
        return fills

    def flatten(self, symbol: str) -> list[Fill]:
        """Alias for close_all(symbol)."""
        return self.close_all(symbol)

    # ------------------------------------------------------------------
    # Convenience shortcuts
    # ------------------------------------------------------------------

    def market_buy(
        self,
        symbol: str,
        qty: float,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        comment: str = "",
        magic: int = 0,
        **meta: object,
    ) -> Fill:
        """Submit a market buy order."""
        order = Order(
            symbol=symbol,
            side=Side.BUY,
            order_type=OrderType.MARKET,
            quantity=qty,
            stop_loss=sl,
            take_profit=tp,
            comment=comment,
            magic=magic,
            meta=meta,
        )
        return self.submit(order)

    def market_sell(
        self,
        symbol: str,
        qty: float,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        comment: str = "",
        magic: int = 0,
        **meta: object,
    ) -> Fill:
        """Submit a market sell order."""
        order = Order(
            symbol=symbol,
            side=Side.SELL,
            order_type=OrderType.MARKET,
            quantity=qty,
            stop_loss=sl,
            take_profit=tp,
            comment=comment,
            magic=magic,
            meta=meta,
        )
        return self.submit(order)

    def limit_buy(
        self,
        symbol: str,
        qty: float,
        price: float,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        comment: str = "",
        magic: int = 0,
        **meta: object,
    ) -> Fill:
        """Submit a limit buy order."""
        order = Order(
            symbol=symbol,
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            quantity=qty,
            price=price,
            stop_loss=sl,
            take_profit=tp,
            comment=comment,
            magic=magic,
            meta=meta,
        )
        return self.submit(order)

    def limit_sell(
        self,
        symbol: str,
        qty: float,
        price: float,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        comment: str = "",
        magic: int = 0,
        **meta: object,
    ) -> Fill:
        """Submit a limit sell order."""
        order = Order(
            symbol=symbol,
            side=Side.SELL,
            order_type=OrderType.LIMIT,
            quantity=qty,
            price=price,
            stop_loss=sl,
            take_profit=tp,
            comment=comment,
            magic=magic,
            meta=meta,
        )
        return self.submit(order)

    def stop_buy(
        self,
        symbol: str,
        qty: float,
        price: float,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        comment: str = "",
        magic: int = 0,
        **meta: object,
    ) -> Fill:
        """Submit a stop buy order."""
        order = Order(
            symbol=symbol,
            side=Side.BUY,
            order_type=OrderType.STOP,
            quantity=qty,
            price=price,
            stop_loss=sl,
            take_profit=tp,
            comment=comment,
            magic=magic,
            meta=meta,
        )
        return self.submit(order)

    def stop_sell(
        self,
        symbol: str,
        qty: float,
        price: float,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        comment: str = "",
        magic: int = 0,
        **meta: object,
    ) -> Fill:
        """Submit a stop sell order."""
        order = Order(
            symbol=symbol,
            side=Side.SELL,
            order_type=OrderType.STOP,
            quantity=qty,
            price=price,
            stop_loss=sl,
            take_profit=tp,
            comment=comment,
            magic=magic,
            meta=meta,
        )
        return self.submit(order)
