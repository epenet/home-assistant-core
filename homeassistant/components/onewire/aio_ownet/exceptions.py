"""Async owserver protocol implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .connection import OWServerRxHeader


class OWServerError(Exception):
    """Base class for all module errors."""


class OWServerConnectionError(OWServerError):
    """Raised when a socket call returns an error."""


class OWServerProtocolError(OWServerError):
    """Raised if no valid server response received."""


class OWServerMalformedHeaderError(OWServerProtocolError):
    """Raised for header parsing errors."""

    def __init__(self, msg: str, header: OWServerRxHeader) -> None:
        """Initialize the error."""
        self.msg = msg
        self.header = header

    def __str__(self) -> str:
        """Return a string representation of the error."""
        return f"{self.msg}, got {str(self.header)!r} decoded as {self.header!r}"


class OWServerShortReadError(OWServerProtocolError):
    """Raised if not enough data received."""

    def __init__(self, read: int, expected: int) -> None:
        """Initialize the error."""
        self.read = read
        self.expected = expected

    def __str__(self) -> str:
        """Return a string representation of the error."""
        return f"received {self.read} bytes instead of {self.expected}."


class OWServerTimeoutError(OWServerError):
    """Raised if response of server takes longer than a given timeout."""

    def __init__(self, elapsed: float, timeout: int) -> None:
        """Initialize the error."""
        self.elapsed = elapsed
        self.timeout = timeout

    def __str__(self) -> str:
        """Return a string representation of the error."""
        return (
            f"Communication with owserver aborted after {self.elapsed:.1f}s, "
            f"timeout of {self.timeout:.1f}s exceeded"
        )


class OWServerReturnError(OWServerError):
    """Raised when owserver returns error code."""

    def __init__(
        self, ret: int, msg: str | None = None, path: str | None = None
    ) -> None:
        """Initialize the error."""
        self.ret = ret
        self.msg = msg
        self.path = path

    def __str__(self) -> str:
        """Return a string representation of the error."""
        return f"Server return error {self.msg} ({self.ret}) on path {self.path}"
