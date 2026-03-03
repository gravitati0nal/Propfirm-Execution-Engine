"""Tests for exec_engine.engine.ExecEngine using a MockBroker."""

from __future__ import annotations

import logging
from typing import Optional

from exec_engine.adapter import BrokerAdapter
from exec_engine.engine import ExecEngine
from exec_engine.types import (
    Account,
    Fill,
    Order,
    OrderStatus,
    OrderType,
    Position,
    Side,
)


# ======================================================================
# Mock broker — canned responses + call tracking
# ======================================================================

class MockBroker(BrokerAdapter):
    """Fake broker adapter for testing."""

    def __init__(self) -> None:
        self._connected = False
        self.calls: list[tuple[str, tuple, dict]] = []
        self._positions: list[Position] = []

    def _record(self, method: str, *args: object, **kwargs: object) -> None:
        self.calls.append((method, args, kwargs))

    def connect(self) -> None:
        self._record("connect")
        self._connected = True

    def disconnect(self) -> None:
        self._record("disconnect")
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def name(self) -> str:
        return "MockBroker"

    def submit(self, order: Order) -> Fill:
        self._record("submit", order)
        return Fill(
            order_id=order.id,
            broker_order_id="BROKER-001",
            status=OrderStatus.FILLED,
            symbol=order.symbol,
            side=order.side,
            filled_qty=order.quantity,
            avg_price=1.08432,
        )

    def cancel(self, broker_order_id: str) -> bool:
        self._record("cancel", broker_order_id)
        return True

    def modify(
        self,
        broker_order_id: str,
        price: Optional[float] = None,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        quantity: Optional[float] = None,
    ) -> Fill:
        self._record("modify", broker_order_id, price=price, sl=sl, tp=tp, quantity=quantity)
        return Fill(
            order_id="",
            broker_order_id=broker_order_id,
            status=OrderStatus.SUBMITTED,
            symbol="EURUSD",
            side=Side.BUY,
            filled_qty=0.0,
            avg_price=0.0,
        )

    def positions(self, symbol: Optional[str] = None) -> list[Position]:
        self._record("positions", symbol)
        if symbol:
            return [p for p in self._positions if p.symbol == symbol]
        return list(self._positions)

    def open_orders(self, symbol: Optional[str] = None) -> list[dict]:
        self._record("open_orders", symbol)
        return []

    def account(self) -> Account:
        self._record("account")
        return Account(
            balance=50000.0,
            equity=50100.0,
            margin_used=1000.0,
            margin_free=49100.0,
            currency="USD",
            account_id="MOCK-123",
        )

    def close_position(self, ticket: str) -> Fill:
        self._record("close_position", ticket)
        return Fill(
            order_id="",
            broker_order_id=f"CLOSE-{ticket}",
            status=OrderStatus.FILLED,
            symbol="EURUSD",
            side=Side.SELL,
            filled_qty=1.0,
            avg_price=1.08500,
        )


# ======================================================================
# Helpers
# ======================================================================

def _find_call(broker: MockBroker, method: str) -> tuple[str, tuple, dict] | None:
    for call in broker.calls:
        if call[0] == method:
            return call
    return None


def _engine() -> tuple[ExecEngine, MockBroker]:
    broker = MockBroker()
    return ExecEngine(broker), broker


# ======================================================================
# Tests
# ======================================================================

def test_connect_logs_account(caplog):
    engine, broker = _engine()
    with caplog.at_level(logging.INFO, logger="exec_engine"):
        engine.connect()
    assert _find_call(broker, "connect") is not None
    assert _find_call(broker, "account") is not None
    assert "Connected to MockBroker" in caplog.text


def test_submit_delegates_to_broker():
    engine, broker = _engine()
    order = Order(symbol="EURUSD", side=Side.BUY, order_type=OrderType.MARKET, quantity=0.5)
    fill = engine.submit(order)
    call = _find_call(broker, "submit")
    assert call is not None
    submitted_order = call[1][0]
    assert submitted_order is order
    assert fill.status == OrderStatus.FILLED
    assert fill.broker_order_id == "BROKER-001"


def test_submit_logs_order(caplog):
    engine, _ = _engine()
    order = Order(symbol="EURUSD", side=Side.BUY, order_type=OrderType.MARKET, quantity=0.5)
    with caplog.at_level(logging.INFO, logger="exec_engine"):
        engine.submit(order)
    assert "BUY" in caplog.text
    assert "0.50" in caplog.text
    assert "EURUSD" in caplog.text
    assert "FILLED" in caplog.text


def test_market_buy_builds_correct_order():
    engine, broker = _engine()
    engine.market_buy("EURUSD", 0.5)
    call = _find_call(broker, "submit")
    assert call is not None
    order: Order = call[1][0]
    assert order.side == Side.BUY
    assert order.order_type == OrderType.MARKET
    assert order.quantity == 0.5
    assert order.symbol == "EURUSD"


def test_market_sell_builds_correct_order():
    engine, broker = _engine()
    engine.market_sell("GBPUSD", 1.0)
    call = _find_call(broker, "submit")
    assert call is not None
    order: Order = call[1][0]
    assert order.side == Side.SELL
    assert order.order_type == OrderType.MARKET
    assert order.quantity == 1.0
    assert order.symbol == "GBPUSD"


def test_limit_buy_includes_price():
    engine, broker = _engine()
    engine.limit_buy("EURUSD", 0.5, 1.0800)
    call = _find_call(broker, "submit")
    assert call is not None
    order: Order = call[1][0]
    assert order.order_type == OrderType.LIMIT
    assert order.side == Side.BUY
    assert order.price == 1.0800


def test_stop_buy_includes_price():
    engine, broker = _engine()
    engine.stop_buy("EURUSD", 0.5, 1.0900)
    call = _find_call(broker, "submit")
    assert call is not None
    order: Order = call[1][0]
    assert order.order_type == OrderType.STOP
    assert order.side == Side.BUY
    assert order.price == 1.0900


def test_cancel_delegates():
    engine, broker = _engine()
    result = engine.cancel("12345")
    call = _find_call(broker, "cancel")
    assert call is not None
    assert call[1][0] == "12345"
    assert result is True


def test_modify_delegates():
    engine, broker = _engine()
    engine.modify("12345", sl=1.05)
    call = _find_call(broker, "modify")
    assert call is not None
    assert call[1][0] == "12345"
    assert call[2]["sl"] == 1.05


def test_flatten_calls_close_all():
    engine, broker = _engine()
    broker._positions = [
        Position(symbol="EURUSD", side=Side.BUY, quantity=1.0, entry_price=1.08, ticket="T1"),
    ]
    fills = engine.flatten("EURUSD")
    assert _find_call(broker, "positions") is not None
    assert _find_call(broker, "close_position") is not None
    assert len(fills) == 1


def test_close_delegates():
    engine, broker = _engine()
    fill = engine.close("ticket123")
    call = _find_call(broker, "close_position")
    assert call is not None
    assert call[1][0] == "ticket123"
    assert fill.status == OrderStatus.FILLED


def test_positions_delegates():
    engine, broker = _engine()
    engine.positions()
    call = _find_call(broker, "positions")
    assert call is not None


def test_convenience_methods_set_meta():
    engine, broker = _engine()
    engine.market_buy("X", 1, custom_field="abc")
    call = _find_call(broker, "submit")
    assert call is not None
    order: Order = call[1][0]
    assert order.meta == {"custom_field": "abc"}
