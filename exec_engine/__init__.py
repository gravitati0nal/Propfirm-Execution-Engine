"""exec_engine — Minimal execution engine for uniform order management across any broker API.

Interact with ExecEngine and the dataclasses below.
Never import broker-specific code beyond initial adapter setup.

Note: This module exports its own ConnectionError which shadows the
builtin. Use ``exec_engine.ConnectionError`` (or the fully qualified
``exec_engine.exceptions.ConnectionError``) to distinguish it.
"""

__version__ = "0.1.0"

from exec_engine.adapter import BrokerAdapter
from exec_engine.engine import ExecEngine
from exec_engine.exceptions import (
    BrokerError,
    ConnectionError,
    ExecEngineError,
    OrderError,
)
from exec_engine.types import (
    Account,
    Fill,
    Order,
    OrderStatus,
    OrderType,
    Position,
    Side,
)

__all__ = [
    "ExecEngine",
    "BrokerAdapter",
    "Order",
    "Fill",
    "Position",
    "Account",
    "Side",
    "OrderType",
    "OrderStatus",
    "ExecEngineError",
    "ConnectionError",
    "OrderError",
    "BrokerError",
]
