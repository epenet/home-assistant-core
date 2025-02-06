"""Async owserver protocol implementation."""

from __future__ import annotations


def str2byteszero(s: str) -> bytes:
    """Transform string to zero-terminated bytes."""

    if not isinstance(s, str):
        raise TypeError
    return s.encode("ascii") + b"\x00"


def bytes2str(b: bytes) -> str:
    """Transform bytes to string."""

    if not isinstance(b, bytes):
        raise TypeError
    return b.decode("ascii")
