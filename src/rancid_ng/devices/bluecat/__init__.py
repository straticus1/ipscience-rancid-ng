"""
BlueCat Device Module for RANCID-NG.

NEW DEVICE TYPE - Not in original RANCID!

Supports BlueCat DDI (DNS, DHCP, IPAM) appliances:
- BlueCat Address Manager (BAM)
- BlueCat DNS/DHCP Server (BDDS)
"""

from rancid_ng.devices.bluecat.bluecat import BlueCat

__all__ = ["BlueCat"]
