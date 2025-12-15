"""
RANCID-NG: Really Awesome New Cisco confIg Differ - Next Generation

A Python 3 rewrite of the classic RANCID network configuration backup tool.

Brought to you by ipscience.io, a service from After Dark Systems, LLC

Copyright (c) 2024 After Dark Systems, LLC
"""

__version__ = "4.0.0"
__author__ = "After Dark Systems, LLC"
__email__ = "engineering@ipscience.io"

from rancid_ng.core.processor import ProcessHistory
from rancid_ng.core.rancid import Rancid
from rancid_ng.core.device import DeviceModule

__all__ = [
    "__version__",
    "ProcessHistory",
    "Rancid",
    "DeviceModule",
]
