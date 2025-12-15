"""
Cisco IronPort Device Module for RANCID-NG.

NEW DEVICE TYPE - Not in original RANCID!

Supports Cisco IronPort/AsyncOS appliances:
- Email Security Appliance (ESA) / C-Series
- Web Security Appliance (WSA) / S-Series
- Security Management Appliance (SMA) / M-Series
"""

from rancid_ng.devices.ironport.ironport import CiscoIronPort

__all__ = ["CiscoIronPort"]
