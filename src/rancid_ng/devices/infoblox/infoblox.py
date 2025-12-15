"""
InfoBlox Device Module for RANCID-NG.

NEW DEVICE TYPE - Not in original RANCID!

Supports InfoBlox DDI (DNS, DHCP, IPAM) appliances:
- InfoBlox NIOS appliances
- InfoBlox virtual appliances

InfoBlox NIOS CLI commands:
- show version: Version and serial number
- show hardware: Hardware information
- show network: Network configuration
- show status: System status
- show license: License information
- show onedb: Database information
- export: Export configuration backup
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from rancid_ng.core.device import DeviceModule
from rancid_ng.devices import register_device

if TYPE_CHECKING:
    from rancid_ng.login.session import LoginSession


@register_device
class InfoBlox(DeviceModule):
    """
    Device module for InfoBlox NIOS appliances.

    This is a NEW device type added to RANCID-NG.
    """

    name = "infoblox"
    aliases = ["nios", "infoblox-nios"]
    login_script = "clogin"
    default_timeout = 120

    def __init__(self, *args, **kwargs):
        """Initialize InfoBlox device module."""
        super().__init__(*args, **kwargs)
        self.found_version = False

    def init(self) -> int:
        """Initialize for a new collection run."""
        self.found_version = False

        self.process_history.add("", "", "",
                                 f"!RANCID-CONTENT-TYPE: {self.devtype}\n!\n")
        return 0

    def inloop(self, session: "LoginSession") -> int:
        """Main parsing loop."""
        if not session:
            return -1

        for cmd, _ in self.command_table:
            if cmd in self._commands_run:
                continue

            handler = self.get_handler(cmd)
            if handler:
                result = handler(session, cmd)
                if result < 0:
                    return result

            self._commands_run.add(cmd)

        self.clean_run = True
        return 0

    def show_version(self, session: "LoginSession", cmd: str) -> int:
        """Parse version information."""
        if self.found_version:
            return 0

        output = session.run_command(cmd)
        if not output:
            return -1

        for line in output.splitlines():
            line = self._filter_line(line)

            # Skip dynamic data
            if re.search(r'(Uptime|Time)', line, re.I):
                continue

            self.process_history.add("COMMENTS", "keysort", "V1", f"!{line}\n")

        self.found_version = True
        return 0

    def show_hardware(self, session: "LoginSession", cmd: str) -> int:
        """Parse hardware information."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)
            self.process_history.add("COMMENTS", "keysort", "H1", f"!{line}\n")

        return 0

    def show_network(self, session: "LoginSession", cmd: str) -> int:
        """Parse network configuration."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)
            self.process_history.add("COMMENTS", "keysort", "N1", f"!{line}\n")

        return 0

    def show_status(self, session: "LoginSession", cmd: str) -> int:
        """Parse system status."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)

            # Skip dynamic counters
            if re.search(r'(Queries|Cache|CPU|Memory)', line, re.I):
                continue

            self.process_history.add("COMMENTS", "keysort", "S1", f"!{line}\n")

        return 0

    def show_license(self, session: "LoginSession", cmd: str) -> int:
        """Parse license information."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)

            # Skip expiration info
            if re.search(r'(Expir|Days)', line, re.I):
                continue

            self.process_history.add("COMMENTS", "keysort", "L1", f"!{line}\n")

        return 0

    def show_onedb(self, session: "LoginSession", cmd: str) -> int:
        """Parse database information."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)

            # Skip size/count info that changes
            if re.search(r'(Records|Size|Objects)', line, re.I):
                continue

            self.process_history.add("COMMENTS", "keysort", "D1", f"!{line}\n")

        return 0

    def show_config(self, session: "LoginSession", cmd: str) -> int:
        """Parse/export configuration."""
        output = session.run_command(cmd)
        if not output:
            return -1

        for line in output.splitlines():
            line = self._filter_line(line)

            # Filter passwords/secrets
            line = re.sub(r'(password\s*[=:]\s*).*', r'\1<FILTERED>', line, flags=re.I)
            line = re.sub(r'(secret\s*[=:]\s*).*', r'\1<FILTERED>', line, flags=re.I)
            line = re.sub(r'(key\s*[=:]\s*).*', r'\1<FILTERED>', line, flags=re.I)
            line = re.sub(r'(community\s*[=:]\s*).*', r'\1<FILTERED>', line, flags=re.I)

            self.process_history.add("", "", "", line + "\n")

        self.found_end = True
        return 0

    HANDLERS = {
        "ShowVersion": "show_version",
        "ShowHardware": "show_hardware",
        "ShowNetwork": "show_network",
        "ShowStatus": "show_status",
        "ShowLicense": "show_license",
        "ShowOneDB": "show_onedb",
        "ShowConfig": "show_config",
        "Export": "show_config",
    }

    def get_handler(self, command: str) -> callable | None:
        """Get handler method for a command."""
        handler_name = self.commands.get(command)
        if not handler_name:
            return None

        if "::" in handler_name:
            handler_name = handler_name.split("::")[-1]

        method_name = self.HANDLERS.get(handler_name)
        if method_name:
            return getattr(self, method_name, None)

        return None


# Default commands for InfoBlox (for rancid.types.conf)
INFOBLOX_COMMANDS = """
infoblox;script;rancid -t infoblox
infoblox;login;clogin
infoblox;module;infoblox
infoblox;inloop;infoblox::inloop
infoblox;command;infoblox::ShowVersion;show version
infoblox;command;infoblox::ShowHardware;show hardware
infoblox;command;infoblox::ShowNetwork;show network
infoblox;command;infoblox::ShowStatus;show status
infoblox;command;infoblox::ShowLicense;show license
infoblox;command;infoblox::ShowConfig;show running-config
"""
