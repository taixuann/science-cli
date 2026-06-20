"""Instrument model registry — hardware/instrument model management."""

from science_cli.core.instruments.registry import (
    BUILTIN_INSTRUMENTS,
    get_all_instruments,
    get_instrument,
    get_instruments_by_technique,
    register_instrument,
    remove_instrument,
    edit_instrument,
)
from science_cli.core.instruments.models import Instrument, InstrumentConfig
from science_cli.core.instruments.types import (
    INSTRUMENT_TYPES,
    describe_type,
    list_types,
)

__all__ = [
    "BUILTIN_INSTRUMENTS",
    "get_all_instruments",
    "get_instrument",
    "get_instruments_by_technique",
    "register_instrument",
    "remove_instrument",
    "edit_instrument",
    "Instrument",
    "InstrumentConfig",
    "INSTRUMENT_TYPES",
    "describe_type",
    "list_types",
]
