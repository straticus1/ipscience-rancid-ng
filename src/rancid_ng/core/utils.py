"""
Utility functions for RANCID-NG.

Direct ports of utility functions from rancid.pm:
- bytes2human: Convert bytes to human-readable format
- human2bytes: Convert human-readable format to bytes
- diskszsummary: Summarize disk size with free percentage
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path


def bytes2human(count: int) -> str:
    """
    Convert bytes to human-readable format (GB/MB/KB).

    This is a direct port of the Perl bytes2human() function.

    Args:
        count: Number of bytes

    Returns:
        Human-readable string (e.g., "256 MB", "1 GB")
    """
    if count >= 1024 * 1024 * 1024:
        value = count // (1024 * 1024 * 1024)
        return f"{value} GB"
    elif count >= 1024 * 1024:
        value = count // (1024 * 1024)
        return f"{value} MB"
    elif count >= 1024:
        value = count // 1024
        return f"{value} KB"
    elif count > 0:
        return "<1KB"
    else:
        return "0 KB"


def human2bytes(value: str | int) -> int:
    """
    Convert human-readable format to bytes.

    This is a direct port of the Perl human2bytes() function.

    Args:
        value: Human-readable string (e.g., "256 MB", "1,024 KB")

    Returns:
        Number of bytes
    """
    if isinstance(value, int):
        return value

    # Remove commas
    value = value.replace(",", "")

    # Determine multiplier
    value_upper = value.upper()
    if "GB" in value_upper:
        multiplier = 1024 * 1024 * 1024
    elif "MB" in value_upper:
        multiplier = 1024 * 1024
    elif "KB" in value_upper:
        multiplier = 1024
    else:
        multiplier = 1

    # Extract numeric value
    match = re.search(r"(\d+)", value)
    if match:
        return int(match.group(1)) * multiplier
    return 0


def diskszsummary(
    total: int | str | None = None,
    free: int | str | None = None,
    used: int | str | None = None,
) -> str:
    """
    Summarize total disk/flash space as human-readable form with free percentage.

    This is a direct port of the Perl diskszsummary() function.

    Args:
        total: Total space (bytes or human-readable)
        free: Free space (bytes or human-readable)
        used: Used space (bytes or human-readable)

    Returns:
        Summary string like "256 MB total (75% free)"
    """
    # Convert to bytes
    total_bytes = human2bytes(total) if total else None
    free_bytes = human2bytes(free) if free else None
    used_bytes = human2bytes(used) if used else None

    # Calculate percentage
    if free_bytes is not None and total_bytes:
        pcnt = int(free_bytes / total_bytes * 100)
    elif used_bytes is not None and total_bytes:
        pcnt = int((total_bytes - used_bytes) / total_bytes * 100)
    elif free_bytes is not None and used_bytes is not None:
        total_bytes = free_bytes + used_bytes
        pcnt = int(free_bytes / total_bytes * 100)
    else:
        return "unknown"

    # Format output
    total_human = bytes2human(total_bytes) if total_bytes else "unknown"
    return f"{total_human} total ({pcnt}% free)"


def which(program: str) -> str | None:
    """
    Find the full path to an executable.

    This is similar to the Unix 'which' command and the Perl which() function.

    Args:
        program: Name of the program to find

    Returns:
        Full path to the program, or None if not found
    """
    return shutil.which(program)


def ensure_dir(path: str | Path) -> Path:
    """
    Ensure a directory exists, creating it if necessary.

    Args:
        path: Directory path

    Returns:
        Path object for the directory
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_filename(name: str) -> str:
    """
    Convert a string to a safe filename.

    Replaces characters that are unsafe in filenames.

    Args:
        name: Original name

    Returns:
        Safe filename string
    """
    # Replace unsafe characters with underscores
    unsafe = r'[<>:"/\\|?*\x00-\x1f]'
    return re.sub(unsafe, "_", name)


def parse_interface_name(name: str) -> tuple[str, str, int | None]:
    """
    Parse an interface name into components.

    Handles common interface naming conventions:
    - GigabitEthernet0/0/1 -> ("GigabitEthernet", "0/0/", 1)
    - Ethernet1 -> ("Ethernet", "", 1)
    - ge-0/0/0 -> ("ge", "0/0/", 0)

    Args:
        name: Interface name string

    Returns:
        Tuple of (type, slot_path, port_number)
    """
    # Try common patterns
    patterns = [
        # Cisco style: GigabitEthernet0/0/1
        r"^([A-Za-z]+)(\d+(?:/\d+)*/)(\d+)$",
        # Juniper style: ge-0/0/0
        r"^([a-z]+-?)(\d+(?:/\d+)*/)(\d+)$",
        # Simple style: Ethernet1
        r"^([A-Za-z]+)()(\d+)$",
    ]

    for pattern in patterns:
        match = re.match(pattern, name)
        if match:
            iface_type, slot_path, port = match.groups()
            return (iface_type, slot_path, int(port))

    return (name, "", None)


def normalize_mac(mac: str) -> str:
    """
    Normalize a MAC address to a consistent format.

    Accepts various formats:
    - 00:11:22:33:44:55
    - 0011.2233.4455
    - 00-11-22-33-44-55

    Returns:
    - Lowercase colon-separated format: 00:11:22:33:44:55

    Args:
        mac: MAC address in any format

    Returns:
        Normalized MAC address
    """
    # Remove all separators and convert to lowercase
    clean = re.sub(r"[:\-.]", "", mac.lower())

    # Validate length
    if len(clean) != 12:
        return mac  # Return original if invalid

    # Format with colons
    return ":".join(clean[i:i+2] for i in range(0, 12, 2))


def strip_carriage_returns(line: str) -> str:
    """
    Strip carriage returns from a line.

    This replicates the common Perl pattern: tr/\015//d

    Args:
        line: Input line

    Returns:
        Line with carriage returns removed
    """
    return line.replace("\r", "")


def get_env_int(name: str, default: int = 0) -> int:
    """
    Get an integer environment variable.

    Args:
        name: Environment variable name
        default: Default value if not set or invalid

    Returns:
        Integer value
    """
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def get_env_bool(name: str, default: bool = False) -> bool:
    """
    Get a boolean environment variable.

    Recognizes: yes, true, 1, on (case-insensitive) as True

    Args:
        name: Environment variable name
        default: Default value if not set

    Returns:
        Boolean value
    """
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in ("yes", "true", "1", "on")
