"""
Proofpoint Device Module for RANCID-NG.

NEW DEVICE TYPE - Not in original RANCID!

Supports Proofpoint email security appliances:
- Proofpoint Protection Server (PPS)
- Proofpoint Email Protection
"""

from rancid_ng.devices.proofpoint.proofpoint import Proofpoint

__all__ = ["Proofpoint"]
