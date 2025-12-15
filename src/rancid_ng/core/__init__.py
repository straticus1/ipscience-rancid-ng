"""
RANCID-NG Core Module

Contains the fundamental classes and utilities for configuration collection
and processing.
"""

from rancid_ng.core.processor import ProcessHistory
from rancid_ng.core.rancid import Rancid
from rancid_ng.core.device import DeviceModule
from rancid_ng.core.filters import (
    filter_passwords,
    filter_community_strings,
    filter_oscillating_data,
)
from rancid_ng.core.sorting import (
    ipsort,
    keysort,
    keynsort,
    numsort,
    valsort,
    ipaddrval,
    sortbyipaddr,
)
from rancid_ng.core.utils import (
    bytes2human,
    human2bytes,
    diskszsummary,
)

__all__ = [
    "ProcessHistory",
    "Rancid",
    "DeviceModule",
    "filter_passwords",
    "filter_community_strings",
    "filter_oscillating_data",
    "ipsort",
    "keysort",
    "keynsort",
    "numsort",
    "valsort",
    "ipaddrval",
    "sortbyipaddr",
    "bytes2human",
    "human2bytes",
    "diskszsummary",
]
