"""
Device Type Registry Parser for RANCID-NG.

Parses rancid.types.base and rancid.types.conf files to build
the device type registry.

File format:
    devtype;directive;value[;optional_value]

Directives:
    - alias: Maps this type to another type
    - script: Collection script to use
    - login: Login script to use
    - module: Python module to load
    - inloop: Main loop function
    - command: Command and handler (command;handler;actual_command)
    - timeout: Connection timeout
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


@dataclass
class DeviceTypeConfig:
    """Configuration for a device type."""

    name: str
    alias: str | None = None
    script: str | None = None
    login: str | None = None
    module: str | None = None
    inloop: str | None = None
    timeout: int | None = None
    commands: list[tuple[str, str]] = field(default_factory=list)

    def add_command(self, command: str, handler: str) -> None:
        """Add a command to the command list."""
        self.commands.append((command, handler))


class DeviceTypeRegistry:
    """
    Registry of device types loaded from configuration files.

    This class parses rancid.types.base and rancid.types.conf files
    and maintains a registry of device type configurations.
    """

    def __init__(self):
        """Initialize the registry."""
        self._types: dict[str, DeviceTypeConfig] = {}

    def load_file(self, path: str | Path) -> int:
        """
        Load device type definitions from a file.

        Args:
            path: Path to the configuration file

        Returns:
            Number of types loaded
        """
        path = Path(path)
        if not path.exists():
            return 0

        count = 0
        line_num = 0

        with open(path) as f:
            for line in f:
                line_num += 1
                line = line.strip()

                # Skip comments and empty lines
                if not line or line.startswith("#"):
                    continue

                # Parse the line
                parts = line.split(";")
                if len(parts) < 3:
                    continue

                devtype = parts[0].lower()
                directive = parts[1].lower()
                value = parts[2] if len(parts) > 2 else ""

                # Get or create the device type config
                if devtype not in self._types:
                    self._types[devtype] = DeviceTypeConfig(name=devtype)
                    count += 1

                config = self._types[devtype]

                # Process directive
                if directive == "alias":
                    config.alias = value.lower()
                elif directive == "script":
                    config.script = value
                elif directive == "login":
                    config.login = value
                elif directive == "module":
                    config.module = value
                elif directive == "inloop":
                    config.inloop = value
                elif directive == "timeout":
                    try:
                        config.timeout = int(value)
                    except ValueError:
                        pass
                elif directive == "command":
                    # command;handler;actual_command[;comment]
                    if len(parts) >= 4:
                        handler = value
                        command = parts[3]
                        config.add_command(command, handler)

        return count

    def load_directory(self, directory: str | Path) -> int:
        """
        Load all type configuration files from a directory.

        Args:
            directory: Directory containing type files

        Returns:
            Total number of types loaded
        """
        directory = Path(directory)
        count = 0

        # Load base first, then conf (conf can override)
        for filename in ["rancid.types.base", "rancid.types.conf"]:
            path = directory / filename
            if path.exists():
                count += self.load_file(path)

        return count

    def get_type(self, devtype: str) -> DeviceTypeConfig | None:
        """
        Get configuration for a device type.

        Args:
            devtype: Device type name

        Returns:
            DeviceTypeConfig or None if not found
        """
        return self._types.get(devtype.lower())

    def resolve_type(self, devtype: str) -> DeviceTypeConfig | None:
        """
        Get configuration for a device type, resolving aliases.

        Args:
            devtype: Device type name

        Returns:
            DeviceTypeConfig with aliases resolved, or None
        """
        config = self.get_type(devtype)
        if not config:
            return None

        # Follow alias chain (with loop protection)
        seen = {devtype.lower()}
        while config and config.alias:
            if config.alias in seen:
                # Circular alias - return what we have
                break
            seen.add(config.alias)
            config = self.get_type(config.alias)

        return config

    def list_types(self) -> list[str]:
        """
        List all registered device types.

        Returns:
            Sorted list of device type names
        """
        return sorted(self._types.keys())

    def __iter__(self) -> Iterator[DeviceTypeConfig]:
        """Iterate over all device type configurations."""
        return iter(self._types.values())

    def __len__(self) -> int:
        """Return number of registered types."""
        return len(self._types)

    def __contains__(self, devtype: str) -> bool:
        """Check if a device type is registered."""
        return devtype.lower() in self._types


def load_default_types() -> DeviceTypeRegistry:
    """
    Load device types from default locations.

    Searches:
    1. RANCID_SYSCONFDIR environment variable
    2. /etc/rancid
    3. Package etc directory

    Returns:
        Populated DeviceTypeRegistry
    """
    import os

    registry = DeviceTypeRegistry()

    # Try various locations
    locations = [
        os.environ.get("RANCID_SYSCONFDIR", ""),
        "/etc/rancid",
        "/usr/local/etc/rancid",
        str(Path(__file__).parent.parent.parent.parent / "etc"),
    ]

    for location in locations:
        if location and Path(location).is_dir():
            registry.load_directory(location)

    return registry
