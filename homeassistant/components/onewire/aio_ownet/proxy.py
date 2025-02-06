"""Async owserver protocol implementation."""

from __future__ import annotations

import asyncio
import contextlib
import logging

from .connection import MAX_PAYLOAD, OWServerConnection
from .definitions import OWServerCommonPath, OWServerControlFlag, OWServerMessageType
from .exceptions import (
    OWServerConnectionError,
    OWServerProtocolError,
    OWServerReturnError,
)
from .utils import bytes2str, str2byteszero

_LOGGER = logging.getLogger(__name__)


class OWServerStatelessProxy:
    """A stateless proxy object for an owserver."""

    def __init__(self, host: str, port: int) -> None:
        """Initialize the proxy object."""
        self._host = host
        self._port = port
        self._flags = 0
        self._return_code_messages: tuple[str, ...] = ()

    def _get_return_code_message(self, ret: int) -> str:
        """Return the error message for the given return code."""
        if self._return_code_messages:
            with contextlib.suppress(IndexError):
                return self._return_code_messages[ret]
        return "Unknown return code"

    async def validate(self) -> str:
        """Initialize the proxy object."""
        try:
            _LOGGER.debug("Connecting (async) to %s on port %s", self._host, self._port)
            reader, writer = await asyncio.open_connection(self._host, self._port)
        except OSError as err:
            _LOGGER.exception(
                "Failed to connect to %s on port %s", self._host, self._port
            )
            raise OWServerConnectionError from err

        _LOGGER.info("Validated connection to %s on port %s", self._host, self._port)
        writer.close()
        await writer.wait_closed()
        _LOGGER.debug("Closed connection to %s on port %s", self._host, self._port)

        await self.ping()
        await self.init_error_codes()

        version_bytes = await self.read(OWServerCommonPath.VERSION)
        return version_bytes.decode()

    async def _sendmess(
        self,
        msgtype: OWServerMessageType,
        payload: bytes,
        flags: int = 0,
        size: int = 0,
        offset: int = 0,
        timeout: int = 0,
    ) -> tuple[int, bytes]:
        """Send generic message and returns retcode, data."""

        flags |= self._flags
        assert not (flags & OWServerControlFlag.PERSISTENCE)

        async with OWServerConnection(self._host, self._port) as conn:
            ret, _, data = await conn.request(
                msgtype, payload, flags, size, offset, timeout
            )

        return ret, data

    async def init_error_codes(self) -> None:
        """Fetch error codes array from owserver."""
        with contextlib.suppress(OWServerReturnError):
            return_codes = await self.read(OWServerCommonPath.RETURN_CODES)
            self._return_code_messages = tuple(bytes2str(return_codes).split(","))

    async def ping(self) -> None:
        """Send a NOP packet and wait for response."""

        ret, data = await self._sendmess(OWServerMessageType.NOP, b"")
        if data or ret > 0:
            raise OWServerProtocolError("invalid reply to ping message")
        if ret < 0:
            raise OWServerReturnError(-ret, self._get_return_code_message(-ret))

    async def read_string(self, path: str) -> str:
        """Read data at path."""
        result_bytes = await self.read(path)
        return result_bytes.decode()

    async def read(
        self,
        path: str,
        size: int = MAX_PAYLOAD,
        offset: int = 0,
        timeout: int = 0,
    ) -> bytes:
        """Read data at path."""

        if size > MAX_PAYLOAD:
            raise ValueError(f"Size cannot exceed {MAX_PAYLOAD}")

        ret, data = await self._sendmess(
            OWServerMessageType.READ,
            str2byteszero(path),
            size=size,
            offset=offset,
            timeout=timeout,
        )
        if ret < 0:
            raise OWServerReturnError(-ret, self._get_return_code_message(-ret), path)
        return data

    async def dir(
        self, path: str = "/", slash: bool = True, bus: bool = False, timeout: int = 0
    ) -> list[str]:
        """List entities at path."""

        if slash:
            msg = OWServerMessageType.DIRALLSLASH
        else:
            msg = OWServerMessageType.DIRALL
        if bus:
            flags = self._flags | OWServerControlFlag.BUS_RET
        else:
            flags = self._flags & ~OWServerControlFlag.BUS_RET

        ret, data = await self._sendmess(
            msg, str2byteszero(path), flags, timeout=timeout
        )
        if ret < 0:
            raise OWServerReturnError(-ret, self._get_return_code_message(-ret), path)
        if data:
            return bytes2str(data).split(",")
        return []

    async def write(
        self, path: str, data: bytes, offset: int = 0, timeout: int = 0
    ) -> None:
        """Write data at path."""

        if not isinstance(data, bytes):
            raise TypeError("'data' argument must be binary")

        ret, rdata = await self._sendmess(
            OWServerMessageType.WRITE,
            str2byteszero(path) + data,
            size=len(data),
            offset=offset,
            timeout=timeout,
        )
        assert not rdata, (ret, rdata)
        if ret < 0:
            raise OWServerReturnError(-ret, self._get_return_code_message(-ret), path)
