"""Tests for exec_engine.types — enums and dataclasses."""

import time

from exec_engine.types import (
    Account,
    Fill,
    Order,
    OrderStatus,
    OrderType,
    Position,
    Side,
)


def test_order_generates_unique_id():
    order = Order(symbol="EURUSD", side=Side.BUY, order_type=OrderType.MARKET, quantity=1.0)
    assert isinstance(order.id, str)
    assert len(order.id) == 12


def test_two_orders_have_different_ids():
    a = Order(symbol="EURUSD", side=Side.BUY, order_type=OrderType.MARKET, quantity=1.0)
    b = Order(symbol="EURUSD", side=Side.BUY, order_type=OrderType.MARKET, quantity=1.0)
    assert a.id != b.id


def test_market_order_no_price_is_valid():
    order = Order(symbol="GBPUSD", side=Side.SELL, order_type=OrderType.MARKET, quantity=0.5)
    assert order.price is None


def test_order_defaults():
    order = Order(symbol="X", side=Side.BUY, order_type=OrderType.LIMIT, quantity=1.0, price=100.0)
    assert order.comment == ""
    assert order.magic == 0
    assert order.time_in_force == "GTC"
    assert order.meta == {}
    assert order.stop_loss is None
    assert order.take_profit is None
    assert order.slippage is None


def test_fill_timestamp_is_recent():
    before = time.time()
    fill = Fill(
        order_id="abc",
        broker_order_id="xyz",
        status=OrderStatus.FILLED,
        symbol="EURUSD",
        side=Side.BUY,
        filled_qty=1.0,
        avg_price=1.08,
    )
    after = time.time()
    assert before <= fill.timestamp <= after


def test_side_enum_values():
    assert Side.BUY.value == "BUY"
    assert Side.SELL.value == "SELL"


def test_order_type_enum_values():
    assert OrderType.MARKET.value == "MARKET"
    assert OrderType.LIMIT.value == "LIMIT"
    assert OrderType.STOP.value == "STOP"
    assert OrderType.STOP_LIMIT.value == "STOP_LIMIT"


def test_order_status_has_seven_members():
    assert len(OrderStatus) == 7
    expected = {"PENDING", "SUBMITTED", "FILLED", "PARTIAL", "CANCELLED", "REJECTED", "EXPIRED"}
    assert {s.name for s in OrderStatus} == expected


def test_position_minimal_construction():
    pos = Position(symbol="EURUSD", side=Side.BUY, quantity=1.0, entry_price=1.0800)
    assert pos.symbol == "EURUSD"
    assert pos.unrealized_pnl == 0.0
    assert pos.ticket == ""
    assert pos.stop_loss is None
    assert pos.take_profit is None


def test_account_minimal_construction():
    acct = Account(balance=10000.0, equity=10050.0, margin_used=500.0, margin_free=9550.0)
    assert acct.currency == "USD"
    assert acct.account_id == ""
