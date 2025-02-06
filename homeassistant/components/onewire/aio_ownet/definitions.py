"""Async owserver protocol implementation."""

from __future__ import annotations

from enum import IntEnum, StrEnum


# for message type classification see
# https://owfs.org/index_php_page_owserver-message-types.html
# and 'enum msg_classification' from module/owlib/src/include/ow_message.h
class OWServerMessageType(IntEnum):
    """OWServer message types."""

    ERROR = 0
    """Note used"""
    NOP = 1
    """No-Op (not used)"""
    READ = 2
    """read from 1-wire bus"""
    WRITE = 3
    """write to 1-wire bua"""
    DIR = 4
    """list 1-wire bus"""
    SIZE = 5
    """get data size (not used)"""
    PRESENCE = 6
    """Is the specified component recognized and known"""
    DIRALL = 7
    """list 1-wire bus, in one packet string"""
    GET = 8
    """dirall or read depending on path"""
    DIRALLSLASH = 9
    """dirall but with directory entries getting a trailing '/'"""
    GETSLASH = 10
    """dirallslash or read depending on path"""


# for owserver flag word definition see
# https://owfs.org/index_php_page_owserver-flag-word.html
# and module/owlib/src/include/ow_parsedname.h
class OWServerControlFlag(IntEnum):
    """OWServer message flags."""

    BUS_RET = 0x00000002
    PERSISTENCE = 0x00000004
    ALIAS = 0x00000008
    SAFEMODE = 0x00000010
    UNCACHED = 0x00000020
    OWNET = 0x00000100


# for owserver flag word definition see
# https://owfs.org/index_php_page_owserver-flag-word.html
# and module/owlib/src/include/ow_temperature.h
class OWServerTemperatureScale(IntEnum):
    """OWServer temperature scale flags."""

    TEMPERATURE_SCALE_CENTIGRAGE = 0x00000000
    TEMPERATURE_SCALE_FAHRENHEIT = 0x00010000
    TEMPERATURE_SCALE_KELVIN = 0x00020000
    TEMPERATURE_SCALE_RANKINE = 0x00030000
    _MASK = 0x00030000


# for owserver flag word definition see
# https://owfs.org/index_php_page_owserver-flag-word.html
# and module/owlib/src/include/ow_pressure.h
class OWServerPressureScale(IntEnum):
    """OWServer pressure scale flags."""

    PRESSURE_SCALE_MILLIBAR = 0x00000000
    PRESSURE_SCALE_ATMOSPHERE = 0x00040000
    PRESSURE_SCALE_MM_MERCURY = 0x00080000
    PRESSURE_SCALE_INCH_MERCURY = 0x000C0000
    PRESSURE_SCALE_POUNDS_PER_SQUARE_INCH = 0x00100000
    PRESSURE_SCALE_PASCAL = 0x00140000
    _MASK = 0x001C0000


# for owserver flag word definition see
# https://owfs.org/index_php_page_owserver-flag-word.html
# and module/owlib/src/include/ow.h
class OWServerDeviceFormat(IntEnum):
    """OWServer pressure scale flags."""

    FDI = 0x00000000
    """ /10.67C6697351FF"""
    FI = 0x01000000
    """ /1067C6697351FF"""
    FDIDC = 0x02000000
    """ /10.67C6697351FF.8D"""
    FDIC = 0x03000000
    """ /10.67C6697351FF8D"""
    FIDC = 0x04000000
    """ /1067C6697351FF.8D"""
    FIC = 0x05000000
    """ /1067C6697351FF8D"""
    _MASK = 0xFF000000


# common OWFS paths
class OWServerCommonPath(StrEnum):
    """OWServer common paths."""

    RETURN_CODES = "/settings/return_codes/text.ALL"
    VERSION = "/system/configuration/version"
    PID = "/system/process/pid"
