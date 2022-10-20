"""Unit system helper class and methods."""
from __future__ import annotations

from numbers import Number
from typing import Final

import voluptuous as vol

from homeassistant.backports.enum import StrEnum
from homeassistant.const import (
    ACCUMULATED_PRECIPITATION,
    LENGTH,
    LENGTH_INCHES,
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    LENGTH_MILLIMETERS,
    MASS,
    MASS_GRAMS,
    MASS_POUNDS,
    PRESSURE,
    PRESSURE_PA,
    PRESSURE_PSI,
    SPEED_METERS_PER_SECOND,
    SPEED_MILES_PER_HOUR,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    TEMPERATURE,
    UNIT_NOT_RECOGNIZED_TEMPLATE,
    VOLUME,
    VOLUME_GALLONS,
    VOLUME_LITERS,
    WIND_SPEED,
)
from homeassistant.helpers.frame import report

from .unit_conversion import (
    DistanceConverter,
    PressureConverter,
    SpeedConverter,
    TemperatureConverter,
    VolumeConverter,
)

_CONF_UNIT_SYSTEM_IMPERIAL: Final = "imperial"
_CONF_UNIT_SYSTEM_METRIC: Final = "metric"
_CONF_UNIT_SYSTEM_US_CUSTOMARY: Final = "us_customary"


class PrecipitationIntensityUnit(StrEnum):
    """Precipitation intensity units.

    The derivation of these units is a volume of rain amassing in a container
    with constant cross section in a given time
    """

    INCHES_PER_DAY = "in/d"
    """Derived from in³/(in².d)"""

    INCHES_PER_HOUR = "in/h"
    """Derived from in³/(in².h)"""

    MILLIMETERS_PER_DAY = "mm/d"
    """Derived from mm³/(mm².d)"""

    MILLIMETERS_PER_HOUR = "mm/h"
    """Derived from mm³/(mm².h)"""


class PrecipitationUnit(StrEnum):
    """Precipitation units.

    The derivation of these units is a volume of rain amassing in a container
    with constant cross section
    """

    INCHES = "in"
    """Derived from in³/in²"""

    MILLIMETERS = "mm"
    """Derived from mm³/mm²"""


class LengthUnit(StrEnum):
    """Length units."""

    MILLIMETERS = "mm"
    """Note: for precipitation, please use PrecipitationUnit.MILLIMETERS"""

    CENTIMETERS = "cm"
    METERS = "m"
    KILOMETERS = "km"

    INCHES = "in"
    """Note: for precipitation, please use PrecipitationUnit.INCHES"""

    FEET = "ft"
    YARD = "yd"
    MILES = "mi"


class MassUnit(StrEnum):
    """Mass units."""

    GRAMS = "g"
    KILOGRAMS = "kg"
    MILLIGRAMS = "mg"
    MICROGRAMS = "µg"

    OUNCES = "oz"
    POUNDS = "lb"


class PressureUnit(StrEnum):
    """Pressure units."""

    PA = "Pa"
    HPA = "hPa"
    KPA = "kPa"
    BAR = "bar"
    CBAR = "cbar"
    MBAR = "mbar"
    MMHG = "mmHg"
    INHG = "inHg"
    PSI = "psi"


class VolumeUnit(StrEnum):
    """Volume units."""

    LITERS = "L"
    MILLILITERS = "mL"
    CUBIC_METERS = "m³"
    CUBIC_FEET = "ft³"

    GALLONS = "gal"
    """US gallon (British gallon is not yet supported)"""

    FLUID_OUNCE = "fl. oz."
    """US fluid ounce (British fluid ounce is not yet supported)"""


class SpeedUnit(StrEnum):
    """Speed units."""

    FEET_PER_SECOND = "ft/s"
    METERS_PER_SECOND = "m/s"
    KILOMETERS_PER_HOUR = "km/h"
    KNOTS = "kn"
    MILES_PER_HOUR = "mph"


class TemperatureUnit(StrEnum):
    """Temperature units."""

    CELSIUS = "°C"
    FAHRENHEIT = "°F"
    KELVIN = "K"


LENGTH_UNITS = {unit.value for unit in LengthUnit}

MASS_UNITS = {unit.value for unit in MassUnit}

PRESSURE_UNITS = {unit.value for unit in PressureUnit}

VOLUME_UNITS = {unit.value for unit in VolumeUnit}

WIND_SPEED_UNITS = {unit.value for unit in SpeedUnit}

TEMPERATURE_UNITS = {unit.value for unit in TemperatureUnit}


def _is_valid_unit(unit: str, unit_type: str) -> bool:
    """Check if the unit is valid for it's type."""
    if unit_type == LENGTH:
        units = LENGTH_UNITS
    elif unit_type == ACCUMULATED_PRECIPITATION:
        units = LENGTH_UNITS
    elif unit_type == WIND_SPEED:
        units = WIND_SPEED_UNITS
    elif unit_type == TEMPERATURE:
        units = TEMPERATURE_UNITS
    elif unit_type == MASS:
        units = MASS_UNITS
    elif unit_type == VOLUME:
        units = VOLUME_UNITS
    elif unit_type == PRESSURE:
        units = PRESSURE_UNITS
    else:
        return False

    return unit in units


class UnitSystem:
    """A container for units of measure."""

    def __init__(
        self,
        name: str,
        temperature: str,
        length: str,
        wind_speed: str,
        volume: str,
        mass: str,
        pressure: str,
        accumulated_precipitation: str,
    ) -> None:
        """Initialize the unit system object."""
        errors: str = ", ".join(
            UNIT_NOT_RECOGNIZED_TEMPLATE.format(unit, unit_type)
            for unit, unit_type in (
                (accumulated_precipitation, ACCUMULATED_PRECIPITATION),
                (temperature, TEMPERATURE),
                (length, LENGTH),
                (wind_speed, WIND_SPEED),
                (volume, VOLUME),
                (mass, MASS),
                (pressure, PRESSURE),
            )
            if not _is_valid_unit(unit, unit_type)
        )

        if errors:
            raise ValueError(errors)

        self._name = name
        self.accumulated_precipitation_unit = accumulated_precipitation
        self.temperature_unit = temperature
        self.length_unit = length
        self.mass_unit = mass
        self.pressure_unit = pressure
        self.volume_unit = volume
        self.wind_speed_unit = wind_speed

    @property
    def name(self) -> str:
        """Return the name of the unit system."""
        report(
            "accesses the `name` property of the unit system. "
            "This is deprecated and will stop working in Home Assistant 2023.1. "
            "Please adjust to use instance check instead.",
            error_if_core=False,
        )
        if self is IMPERIAL_SYSTEM:
            # kept for compatibility reasons, with associated warning above
            return _CONF_UNIT_SYSTEM_IMPERIAL
        return self._name

    @property
    def is_metric(self) -> bool:
        """Determine if this is the metric unit system."""
        report(
            "accesses the `is_metric` property of the unit system. "
            "This is deprecated and will stop working in Home Assistant 2023.1. "
            "Please adjust to use instance check instead.",
            error_if_core=False,
        )
        return self is METRIC_SYSTEM

    def temperature(self, temperature: float, from_unit: str) -> float:
        """Convert the given temperature to this unit system."""
        if not isinstance(temperature, Number):
            raise TypeError(f"{temperature!s} is not a numeric value.")

        return TemperatureConverter.convert(
            temperature, from_unit, self.temperature_unit
        )

    def length(self, length: float | None, from_unit: str) -> float:
        """Convert the given length to this unit system."""
        if not isinstance(length, Number):
            raise TypeError(f"{length!s} is not a numeric value.")

        # type ignore: https://github.com/python/mypy/issues/7207
        return DistanceConverter.convert(  # type: ignore[unreachable]
            length, from_unit, self.length_unit
        )

    def accumulated_precipitation(self, precip: float | None, from_unit: str) -> float:
        """Convert the given length to this unit system."""
        if not isinstance(precip, Number):
            raise TypeError(f"{precip!s} is not a numeric value.")

        # type ignore: https://github.com/python/mypy/issues/7207
        return DistanceConverter.convert(  # type: ignore[unreachable]
            precip, from_unit, self.accumulated_precipitation_unit
        )

    def pressure(self, pressure: float | None, from_unit: str) -> float:
        """Convert the given pressure to this unit system."""
        if not isinstance(pressure, Number):
            raise TypeError(f"{pressure!s} is not a numeric value.")

        # type ignore: https://github.com/python/mypy/issues/7207
        return PressureConverter.convert(  # type: ignore[unreachable]
            pressure, from_unit, self.pressure_unit
        )

    def wind_speed(self, wind_speed: float | None, from_unit: str) -> float:
        """Convert the given wind_speed to this unit system."""
        if not isinstance(wind_speed, Number):
            raise TypeError(f"{wind_speed!s} is not a numeric value.")

        # type ignore: https://github.com/python/mypy/issues/7207
        return SpeedConverter.convert(wind_speed, from_unit, self.wind_speed_unit)  # type: ignore[unreachable]

    def volume(self, volume: float | None, from_unit: str) -> float:
        """Convert the given volume to this unit system."""
        if not isinstance(volume, Number):
            raise TypeError(f"{volume!s} is not a numeric value.")

        # type ignore: https://github.com/python/mypy/issues/7207
        return VolumeConverter.convert(volume, from_unit, self.volume_unit)  # type: ignore[unreachable]

    def as_dict(self) -> dict[str, str]:
        """Convert the unit system to a dictionary."""
        return {
            LENGTH: self.length_unit,
            ACCUMULATED_PRECIPITATION: self.accumulated_precipitation_unit,
            MASS: self.mass_unit,
            PRESSURE: self.pressure_unit,
            TEMPERATURE: self.temperature_unit,
            VOLUME: self.volume_unit,
            WIND_SPEED: self.wind_speed_unit,
        }


def get_unit_system(key: str) -> UnitSystem:
    """Get unit system based on key."""
    if key == _CONF_UNIT_SYSTEM_US_CUSTOMARY:
        return US_CUSTOMARY_SYSTEM
    if key == _CONF_UNIT_SYSTEM_METRIC:
        return METRIC_SYSTEM
    raise ValueError(f"`{key}` is not a valid unit system key")


def _deprecated_unit_system(value: str) -> str:
    """Convert deprecated unit system."""

    if value == _CONF_UNIT_SYSTEM_IMPERIAL:
        # need to add warning in 2023.1
        return _CONF_UNIT_SYSTEM_US_CUSTOMARY
    return value


validate_unit_system = vol.All(
    vol.Lower,
    _deprecated_unit_system,
    vol.Any(_CONF_UNIT_SYSTEM_METRIC, _CONF_UNIT_SYSTEM_US_CUSTOMARY),
)

METRIC_SYSTEM = UnitSystem(
    _CONF_UNIT_SYSTEM_METRIC,
    TEMP_CELSIUS,
    LENGTH_KILOMETERS,
    SPEED_METERS_PER_SECOND,
    VOLUME_LITERS,
    MASS_GRAMS,
    PRESSURE_PA,
    LENGTH_MILLIMETERS,
)

US_CUSTOMARY_SYSTEM = UnitSystem(
    _CONF_UNIT_SYSTEM_US_CUSTOMARY,
    TEMP_FAHRENHEIT,
    LENGTH_MILES,
    SPEED_MILES_PER_HOUR,
    VOLUME_GALLONS,
    MASS_POUNDS,
    PRESSURE_PSI,
    LENGTH_INCHES,
)

IMPERIAL_SYSTEM = US_CUSTOMARY_SYSTEM
"""IMPERIAL_SYSTEM is deprecated. Please use US_CUSTOMARY_SYSTEM instead."""
