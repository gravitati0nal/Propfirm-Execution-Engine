"""Core data types for exec_engine.

All order, fill, position, and account representations live here.
Uses only stdlib — no third-party dependencies.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Side(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderStatus(Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIAL = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


@dataclass
class Order:
    symbol: str
    side: Side
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    comment: str = ""
    magic: int = 0
    time_in_force: str = "GTC"
    slippage: Optional[int] = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)
    meta: dict = field(default_factory=dict)


@dataclass
class Fill:
    order_id: str
    broker_order_id: str
    status: OrderStatus
    symbol: str
    side: Side
    filled_qty: float
    avg_price: float
    message: str = ""
    timestamp: float = field(default_factory=time.time)
    raw: dict = field(default_factory=dict)


@dataclass
class Position:
    symbol: str
    side: Side
    quantity: float
    entry_price: float
    unrealized_pnl: float = 0.0
    ticket: str = ""
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


@dataclass
class Account:
    balance: float
    equity: float
    margin_used: float
    margin_free: float
    currency: str = "USD"
    account_id: str = ""
