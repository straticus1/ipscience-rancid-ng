"""
Sorting utilities for RANCID-NG.

Direct port of the sorting functions from rancid.pm:
- keysort: Alphabetical sort on hash keys
- keynsort: Numerical sort on hash keys
- numsort: Numerical sort (ascending)
- valsort: Sort on hash values
- ipsort: Sort on IPv4/IPv6 address keys
- ipaddrval: Convert IP address to sortable string
- sortbyipaddr: Comparison function for IP addresses
"""

from __future__ import annotations

import ipaddress
import re
from typing import Any


def keysort(lines: dict[str, str]) -> list[str]:
    """
    Sort alpha-numerically on the keys of the dict.

    This is the Python equivalent of the Perl keysort() function.

    Args:
        lines: Dictionary with string keys and string values

    Returns:
        List of values sorted by their keys alphabetically
    """
    return [lines[key] for key in sorted(lines.keys())]


def keynsort(lines: dict[str, str]) -> list[str]:
    """
    Sort numerically on the keys of the dict.

    This is the Python equivalent of the Perl keynsort() function.
    Keys are converted to integers for numerical comparison.

    Args:
        lines: Dictionary with numeric string keys and string values

    Returns:
        List of values sorted by their keys numerically
    """
    def numeric_key(k: str) -> int:
        try:
            return int(k)
        except ValueError:
            return 0

    return [lines[key] for key in sorted(lines.keys(), key=numeric_key)]


def numsort(lines: dict[str | int, str]) -> list[str]:
    """
    Numerical sort (ascending) on dict keys.

    Args:
        lines: Dictionary with numeric keys and string values

    Returns:
        List of values sorted numerically by key
    """
    def numeric_key(k: str | int) -> float:
        try:
            return float(k)
        except (ValueError, TypeError):
            return 0.0

    return [lines[key] for key in sorted(lines.keys(), key=numeric_key)]


def valsort(lines: dict[str, str]) -> list[str]:
    """
    Sort on the values of the dict.

    Args:
        lines: Dictionary with string values

    Returns:
        List of values sorted alphabetically
    """
    return sorted(lines.values())


def ipaddrval(addr: str) -> str:
    """
    Convert an IPv4/IPv6 address to a string suitable for comparison.

    This handles:
    - IPv4 addresses (with optional /prefix)
    - IPv6 addresses (with optional /prefix)
    - Addresses with port numbers
    - Mixed/embedded IPv4-in-IPv6

    Args:
        addr: IP address string (may include prefix length)

    Returns:
        Normalized string suitable for lexicographic sorting
    """
    # Remove any prefix length for now
    addr_part = addr.split("/")[0]

    # Handle port notation (addr:port for IPv4)
    if addr_part.count(":") == 1 and "." in addr_part:
        addr_part = addr_part.split(":")[0]

    try:
        # Try parsing as IPv6 first
        if ":" in addr_part:
            ip = ipaddress.IPv6Address(addr_part)
            # Return as zero-padded hex string (32 chars for IPv6)
            return f"6{ip.exploded.replace(':', '')}"
        else:
            # Parse as IPv4
            ip = ipaddress.IPv4Address(addr_part)
            # Return as zero-padded decimal octets (12 chars for IPv4)
            octets = str(ip).split(".")
            return "4" + "".join(f"{int(o):03d}" for o in octets)
    except (ValueError, ipaddress.AddressValueError):
        # If parsing fails, return original for string sorting
        return addr


def sortbyipaddr(a: str, b: str) -> int:
    """
    Comparison function for sorting IP addresses.

    Args:
        a: First IP address
        b: Second IP address

    Returns:
        -1 if a < b, 0 if a == b, 1 if a > b
    """
    val_a = ipaddrval(a)
    val_b = ipaddrval(b)

    if val_a < val_b:
        return -1
    elif val_a > val_b:
        return 1
    return 0


def ipsort(lines: dict[str, str]) -> list[str]:
    """
    Sort on the IPv4/IPv6 address keys of the dict.

    This is the Python equivalent of the Perl ipsort() function.

    Args:
        lines: Dictionary with IP address keys and string values

    Returns:
        List of values sorted by their IP address keys
    """
    from functools import cmp_to_key
    return [lines[key] for key in sorted(lines.keys(), key=ipaddrval)]


def aclsort(lines: list[str], aclfilterseq: bool = True) -> list[str]:
    """
    Sort access control list entries.

    Handles sorting of ACL entries, optionally filtering sequence numbers.

    Args:
        lines: List of ACL entry strings
        aclfilterseq: Whether to filter sequence numbers

    Returns:
        Sorted list of ACL entries
    """
    # Extract IP addresses or sequence numbers for sorting
    result = []

    for line in lines:
        # Try to extract an IP address for sorting
        ip_match = re.search(
            r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})',
            line
        )
        if ip_match:
            sort_key = ipaddrval(ip_match.group(1))
        else:
            sort_key = line

        result.append((sort_key, line))

    # Sort by key
    result.sort(key=lambda x: x[0])

    return [item[1] for item in result]
