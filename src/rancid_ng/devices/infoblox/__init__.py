"""
InfoBlox Device Module for RANCID-NG.

NEW DEVICE TYPE - Not in original RANCID!

Supports InfoBlox DDI (DNS, DHCP, IPAM) appliances:
- InfoBlox NIOS appliances
- InfoBlox virtual appliances
"""

from rancid_ng.devices.infoblox.infoblox import InfoBlox

__all__ = ["InfoBlox"]
