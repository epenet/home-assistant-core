"""Async owserver protocol implementation."""

from __future__ import annotations

import asyncio
import logging
import socket
from time import monotonic
from types import TracebackType
from typing import Self

from pyownet import protocol

_LOGGER = logging.getLogger(__name__)


class _Connection:
    """Private connection class."""

    _reader: asyncio.StreamReader
    _writer: asyncio.StreamWriter

    def __init__(self, host: str, port: int) -> None:
        """Initialize."""
        self._host = host
        self._port = port

    # enter the async context manager
    async def __aenter__(self) -> Self:
        """Open a connection."""
        self._reader, self._writer = await asyncio.open_connection(
            self._host, self._port
        )
        return self

    # exit the async context manager
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        """Close the connection."""
        self._writer.close()
        await self._writer.wait_closed()
        return None

    async def _read_msg(self) -> tuple[protocol._FromServerHeader, bytes]:
        """Read message from server."""

        async def _recv_socket(nbytes: int) -> bytes:
            """Read nbytes bytes from self.socket."""

            #
            # code below is written under the assumption that
            # 'nbytes' is smallish so that the 'while len(buf) < nbytes' loop
            # is entered rarerly
            #
            try:
                buf = await self._reader.read(nbytes)
            except OSError as err:
                raise protocol.ConnError from err

            if not buf:
                raise protocol.ShortRead(0, nbytes)

            while len(buf) < nbytes:
                try:
                    tmp = await self._reader.read(nbytes - len(buf))
                except OSError as err:
                    raise protocol.ConnError from err

                if not tmp:
                    _LOGGER.debug("ee %s", repr(buf))
                    raise protocol.ShortRead(len(buf), nbytes)

                buf += tmp

            assert len(buf) == nbytes, (buf, len(buf), nbytes)
            return buf

        data = await _recv_socket(protocol._FromServerHeader.header_size)  # noqa: SLF001
        header = protocol._FromServerHeader(data)  # noqa: SLF001
        _LOGGER.debug("<- %s", repr(header))

        # error conditions
        if header.version != 0:
            raise protocol.MalformedHeader("bad version", header)
        if header.payload > protocol.MAX_PAYLOAD:
            raise protocol.MalformedHeader("huge payload, unwilling to read", header)

        if header.payload > 0:
            payload = await _recv_socket(header.payload)
            _LOGGER.debug(".. %s", repr(payload))
            assert header.size <= header.payload
            payload = payload[: header.size]
        else:
            payload = b""
        return header, payload

    async def _send_msg(self, header: protocol._ToServerHeader, payload: bytes) -> None:
        """Send message to server."""

        _LOGGER.debug("-> %s", repr(header))
        _LOGGER.debug(".. %s", repr(payload))
        assert header.payload == len(payload)
        try:
            self._writer.write(header + payload)
            await self._writer.drain()
            sent = len(header + payload)
        except OSError as err:
            raise protocol.ConnError from err

        if sent < len(header + payload):
            raise protocol.ShortWrite(sent, len(header + payload))
        assert sent == len(header + payload), sent

    async def request(
        self,
        msgtype: int,
        payload: bytes,
        flags: int,
        size: int = 0,
        offset: int = 0,
        timeout: int = 0,
    ) -> tuple[int, int, bytes]:
        """Send message to server and return response."""

        if timeout < 0:
            raise ValueError("timeout cannot be negative!")

        tohead = protocol._ToServerHeader(  # noqa: SLF001
            payload=len(payload), type=msgtype, flags=flags, size=size, offset=offset
        )

        tstartcom = monotonic()  # set timer when communication begins
        await self._send_msg(tohead, payload)

        while True:
            fromhead, data = await self._read_msg()

            if fromhead.payload >= 0:
                # we received a valid answer and return the result
                return fromhead.ret, fromhead.flags, data

            assert msgtype != protocol.MSG_NOP

            # we did not exit the loop because payload is negative
            # Server said PING to keep connection alive during lengthy op

            # check if timeout has expired
            if timeout:
                tcom = monotonic() - tstartcom
                if tcom > timeout:
                    raise protocol.OwnetTimeout(tcom, timeout)


class AsyncProxy:
    """A proxy object for an owserver."""

    def __init__(self, host: str, port: int) -> None:
        """Initialize the proxy object."""
        self._host = host
        self._port = port
        self._flags = 0
        self._errmess = protocol._errtuple()  # noqa: SLF001

    async def validate(self) -> str:
        """Initialize the proxy object."""
        try:
            _LOGGER.debug("Connecting (async) to %s on port %s", self._host, self._port)
            reader, writer = await asyncio.open_connection(self._host, self._port)
        except (socket.gaierror, OSError) as err:
            _LOGGER.exception(
                "Failed to connect to %s on port %s", self._host, self._port
            )
            raise protocol.ConnError from err

        _LOGGER.info("Validated connection to %s on port %s", self._host, self._port)
        writer.close()
        await writer.wait_closed()
        _LOGGER.debug("Closed connection to %s on port %s", self._host, self._port)

        await self.ping()

        version_bytes = await self.read(protocol.PTH_VERSION)
        return version_bytes.decode()

    async def _sendmess(
        self,
        msgtype: int,
        payload: bytes,
        flags: int = 0,
        size: int = 0,
        offset: int = 0,
        timeout: int = 0,
    ) -> tuple[int, bytes]:
        """Send generic message and returns retcode, data."""

        flags |= self._flags
        assert not (flags & protocol.FLG_PERSISTENCE)

        async with _Connection(self._host, self._port) as conn:
            ret, _, data = await conn.request(
                msgtype, payload, flags, size, offset, timeout
            )

        return ret, data

    async def ping(self) -> None:
        """Send a NOP packet and wait for response."""

        ret, data = await self._sendmess(protocol.MSG_NOP, b"")
        if data or ret > 0:
            raise protocol.ProtocolError("invalid reply to ping message")
        if ret < 0:
            raise protocol.OwnetError(-ret, self._errmess[-ret])

    async def read_string(self, path: str) -> str:
        """Read data at path."""
        result_bytes = await self.read(path)
        return result_bytes.decode()

    async def read(
        self,
        path: str,
        size: int = protocol.MAX_PAYLOAD,
        offset: int = 0,
        timeout: int = 0,
    ) -> bytes:
        """Read data at path."""

        if size > protocol.MAX_PAYLOAD:
            raise ValueError(f"Size cannot exceed {protocol.MAX_PAYLOAD}")

        ret, data = await self._sendmess(
            protocol.MSG_READ,
            protocol.str2bytez(path),
            size=size,
            offset=offset,
            timeout=timeout,
        )
        if ret < 0:
            raise protocol.OwnetError(-ret, self._errmess[-ret], path)
        return data

    async def dir(
        self, path: str = "/", slash: bool = True, bus: bool = False, timeout: int = 0
    ) -> list[str]:
        """List entities at path."""

        if slash:
            msg = protocol.MSG_DIRALLSLASH
        else:
            msg = protocol.MSG_DIRALL
        if bus:
            flags = self._flags | protocol.FLG_BUS_RET
        else:
            flags = self._flags & ~protocol.FLG_BUS_RET

        ret, data = await self._sendmess(
            msg, protocol.str2bytez(path), flags, timeout=timeout
        )
        if ret < 0:
            raise protocol.OwnetError(-ret, self._errmess[-ret], path)
        if data:
            str_data: str = protocol.bytes2str(data)
            return str_data.split(",")
        return []

    async def write(
        self, path: str, data: bytes, offset: int = 0, timeout: int = 0
    ) -> None:
        """Write data at path."""

        if not isinstance(data, bytes):
            raise TypeError("'data' argument must be binary")

        ret, rdata = await self._sendmess(
            protocol.MSG_WRITE,
            protocol.str2bytez(path) + data,
            size=len(data),
            offset=offset,
            timeout=timeout,
        )
        assert not rdata, (ret, rdata)
        if ret < 0:
            raise protocol.OwnetError(-ret, self._errmess[-ret], path)
