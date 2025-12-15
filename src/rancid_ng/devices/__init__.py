"""
RANCID-NG Device Modules

Device-specific configuration collection modules for various
network equipment vendors and platforms.

Supported device families:
- Cisco: IOS, NX-OS, IOS-XR, FX-OS, ASA, WLC
- Juniper: JunOS, JunOS-EVO, SRX
- Arista: EOS
- Palo Alto: PAN-OS
- Fortinet: FortiGate
- F5: BIG-IP
- Nokia: SR OS
- Foundry/Brocade
- Dell: OS9, OS10
- Extreme: EXOS
- Mikrotik: RouterOS
- And more...

NEW device types (not in original RANCID):
- Cisco IronPort
- Proofpoint
- BlueCat
- InfoBlox
- Bluecoat
"""

from typing import Type

from rancid_ng.core.device import DeviceModule

# Registry of device modules
_device_modules: dict[str, Type[DeviceModule]] = {}


def register_device(cls: Type[DeviceModule]) -> Type[DeviceModule]:
    """
    Decorator to register a device module.

    Args:
        cls: Device module class

    Returns:
        The class unchanged
    """
    if cls.name:
        _device_modules[cls.name.lower()] = cls
    for alias in getattr(cls, "aliases", []):
        _device_modules[alias.lower()] = cls
    return cls


def get_device_module(name: str) -> Type[DeviceModule] | None:
    """
    Get a device module class by name.

    Args:
        name: Device type name

    Returns:
        Device module class or None
    """
    return _device_modules.get(name.lower())


def list_device_modules() -> list[str]:
    """
    List all registered device module names.

    Returns:
        Sorted list of device type names
    """
    return sorted(_device_modules.keys())


# Import device modules to trigger registration
# These imports must be at the end to avoid circular imports
from rancid_ng.devices.cisco import ios, nxos, iosxr, fxos, ciscowlc, iossb
from rancid_ng.devices.juniper import junos
from rancid_ng.devices.arista import aeos
from rancid_ng.devices.paloalto import panos
from rancid_ng.devices.fortinet import fortigate
from rancid_ng.devices.f5 import bigip
from rancid_ng.devices.nokia import sros
from rancid_ng.devices.foundry import foundry
from rancid_ng.devices.dell import dnos9, dnos10
from rancid_ng.devices.extreme import exos
from rancid_ng.devices.mikrotik import routeros
from rancid_ng.devices.edgerouter import edgerouter
from rancid_ng.devices.riverbed import rbt

# New device types
from rancid_ng.devices.ironport import ironport
from rancid_ng.devices.proofpoint import proofpoint
from rancid_ng.devices.bluecat import bluecat
from rancid_ng.devices.infoblox import infoblox
from rancid_ng.devices.bluecoat import bluecoat

__all__ = [
    "register_device",
    "get_device_module",
    "list_device_modules",
    "DeviceModule",
]
