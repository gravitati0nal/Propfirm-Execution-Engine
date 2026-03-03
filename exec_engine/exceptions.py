"""Exceptions for the exec_engine library."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from exec_engine.types import Order


class ExecEngineError(Exception):
    """Base exception for all exec_engine errors."""


class ConnectionError(ExecEngineError):
    """Raised when a broker connection attempt fails."""


class OrderError(ExecEngineError):
    """Raised when order submission, modification, or cancellation fails.

    Attributes:
        order: The Order object that caused the failure, if available.
    """

    def __init__(self, message: str, order: Order | None = None) -> None:
        super().__init__(message)
        self.order = order


class BrokerError(ExecEngineError):
    """Raised on unexpected broker API errors.

    Attributes:
        raw_response: The raw response received from the broker.
    """

    def __init__(self, message: str, raw_response: Any = None) -> None:
        super().__init__(message)
        self.raw_response = raw_response
