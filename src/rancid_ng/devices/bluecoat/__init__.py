"""
Bluecoat/Symantec Device Module for RANCID-NG.

NEW DEVICE TYPE - Not in original RANCID!

Supports Bluecoat/Symantec proxy appliances:
- ProxySG (SGOS)
- PacketShaper
- Advanced Secure Gateway
"""

from rancid_ng.devices.bluecoat.bluecoat import Bluecoat

__all__ = ["Bluecoat"]
