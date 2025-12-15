"""
Cisco Device Modules for RANCID-NG

Supports:
- IOS (Catalyst, ISR, ASR, etc.)
- NX-OS (Nexus)
- IOS-XR (ASR 9000, NCS, etc.)
- FX-OS (Firepower)
- ASA/PIX
- WLC (Wireless LAN Controllers)
- Small Business switches
"""

from rancid_ng.devices.cisco.ios import CiscoIOS
from rancid_ng.devices.cisco.nxos import CiscoNXOS
from rancid_ng.devices.cisco.iosxr import CiscoIOSXR
from rancid_ng.devices.cisco.fxos import CiscoFXOS
from rancid_ng.devices.cisco.ciscowlc import CiscoWLC
from rancid_ng.devices.cisco.iossb import CiscoIOSSB

__all__ = [
    "CiscoIOS",
    "CiscoNXOS",
    "CiscoIOSXR",
    "CiscoFXOS",
    "CiscoWLC",
    "CiscoIOSSB",
]
