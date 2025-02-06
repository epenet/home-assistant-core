"""Async owserver protocol implementation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import struct
from time import monotonic
from types import TracebackType
from typing import Self

from .definitions import OWServerControlFlag, OWServerMessageType
from .exceptions import (
    OWServerConnectionError,
    OWServerMalformedHeaderError,
    OWServerShortReadError,
    OWServerTimeoutError,
)

_LOGGER = logging.getLogger(__name__)

# do not attempt to read messages bigger than this (bytes)
MAX_PAYLOAD = 65536


@dataclass
class OWServerTxHeader:
    """OWServer header for messages sent to the server."""

    version: int = 0
    """'0' from client 0x10000 + # of tags from owserver"""
    payload: int = 0
    """length in bytes of payload field"""
    type: OWServerMessageType = OWServerMessageType.NOP
    """type of message: read, write, directory, present?"""
    control_flags: int = OWServerControlFlag.OWNET
    """various flags"""
    size: int = 0
    """expected size of data read or written"""
    offset: int = 0
    """location in read or write field that data starts"""

    def pack(self) -> bytes:
        """Parse the header from a byte string."""
        return struct.pack(
            ">iiiiii",
            self.version,
            self.payload,
            self.type,
            self.control_flags,
            self.size,
            self.offset,
        )


@dataclass
class OWServerRxHeader:
    """OWServer header for messages received from the server."""

    HEADER_SIZE = 6 * 4

    version: int = 0
    """'0'"""
    payload: int = 0
    """length in bytes of payload field"""
    ret: int = 0
    """return value"""
    control_flags: int = OWServerControlFlag.OWNET
    """various flags"""
    size: int = 0
    """expected size of data read or written"""
    offset: int = 0
    """location in read or write field that data starts"""

    @staticmethod
    def from_packed(data: bytes) -> OWServerRxHeader:
        """Parse the header from a byte string."""
        unpack = struct.unpack(">iiiiii", data)
        return OWServerRxHeader(
            version=unpack[0],
            payload=unpack[1],
            ret=unpack[2],
            control_flags=unpack[3],
            size=unpack[4],
            offset=unpack[5],
        )


class OWServerConnection:
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

    async def _read_msg(self) -> tuple[OWServerRxHeader, bytes]:
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
                raise OWServerConnectionError from err

            if not buf:
                raise OWServerShortReadError(0, nbytes)

            while len(buf) < nbytes:
                try:
                    tmp = await self._reader.read(nbytes - len(buf))
                except OSError as err:
                    raise OWServerConnectionError from err

                if not tmp:
                    _LOGGER.debug("ee %s", repr(buf))
                    raise OWServerShortReadError(len(buf), nbytes)

                buf += tmp

            assert len(buf) == nbytes, (buf, len(buf), nbytes)
            return buf

        data = await _recv_socket(OWServerRxHeader.HEADER_SIZE)
        header = OWServerRxHeader.from_packed(data)
        _LOGGER.debug("<- %s", header)

        # error conditions
        if header.version != 0:
            raise OWServerMalformedHeaderError("bad version", header)
        if header.payload > MAX_PAYLOAD:
            raise OWServerMalformedHeaderError(
                "huge payload, unwilling to read", header
            )

        if header.payload > 0:
            payload = await _recv_socket(header.payload)
            _LOGGER.debug("<-.. %s %s", header, payload)
            assert header.size <= header.payload
            payload = payload[: header.size]
        else:
            payload = b""
        return header, payload

    async def _send_msg(self, header: OWServerTxHeader, payload: bytes) -> None:
        """Send message to server."""

        _LOGGER.debug("-> %s %s", repr(header), payload)
        assert header.payload == len(payload)
        try:
            self._writer.write(header.pack() + payload)
            await self._writer.drain()
        except OSError as err:
            raise OWServerConnectionError from err

    async def request(
        self,
        msgtype: OWServerMessageType,
        payload: bytes,
        flags: int,
        size: int = 0,
        offset: int = 0,
        timeout: int = 0,
    ) -> tuple[int, int, bytes]:
        """Send message to server and return response."""

        if timeout < 0:
            raise ValueError("timeout cannot be negative!")

        tohead = OWServerTxHeader(
            payload=len(payload),
            type=msgtype,
            control_flags=flags,
            size=size,
            offset=offset,
        )

        tstartcom = monotonic()  # set timer when communication begins
        await self._send_msg(tohead, payload)

        while True:
            fromhead, data = await self._read_msg()

            if fromhead.payload >= 0:
                # we received a valid answer and return the result
                return fromhead.ret, fromhead.control_flags, data

            assert msgtype != OWServerMessageType.NOP

            # we did not exit the loop because payload is negative
            # Server said PING to keep connection alive during lengthy op

            # check if timeout has expired
            if timeout:
                tcom = monotonic() - tstartcom
                if tcom > timeout:
                    raise OWServerTimeoutError(tcom, timeout)
