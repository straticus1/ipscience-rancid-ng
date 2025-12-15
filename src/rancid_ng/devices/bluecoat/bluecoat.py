"""
Bluecoat/Symantec Device Module for RANCID-NG.

NEW DEVICE TYPE - Not in original RANCID!

Supports Bluecoat/Symantec proxy appliances:
- ProxySG (SGOS)
- PacketShaper
- Advanced Secure Gateway (ASG)

SGOS CLI commands:
- show version: Version and serial information
- show hardware-info: Hardware details
- show license: License information
- show configuration: Running configuration
- show policy: Policy configuration
- show attack-detection: Security settings
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from rancid_ng.core.device import DeviceModule
from rancid_ng.devices import register_device

if TYPE_CHECKING:
    from rancid_ng.login.session import LoginSession


@register_device
class Bluecoat(DeviceModule):
    """
    Device module for Bluecoat/Symantec proxy appliances.

    This is a NEW device type added to RANCID-NG.
    """

    name = "bluecoat"
    aliases = ["proxysg", "sgos", "symantec-proxy", "bluecoat-sg"]
    login_script = "clogin"
    default_timeout = 120

    # SGOS prompt typically: ProxySG#
    PROMPT_PATTERN = r'[\w\.-]+[#>]\s*$'

    def __init__(self, *args, **kwargs):
        """Initialize Bluecoat device module."""
        super().__init__(*args, **kwargs)
        self.found_version = False
        self.found_hardware = False

    def init(self) -> int:
        """Initialize for a new collection run."""
        self.found_version = False
        self.found_hardware = False

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
            if re.search(r'(Uptime|Started|Time)', line, re.I):
                continue

            # Extract key info
            if re.search(r'(Version|Release|Serial|Model)', line, re.I):
                self.process_history.add(
                    "COMMENTS", "keysort", "V1",
                    f"!{line}\n"
                )

        self.found_version = True
        return 0

    def show_hardware_info(self, session: "LoginSession", cmd: str) -> int:
        """Parse hardware information."""
        if self.found_hardware:
            return 0

        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)

            # Skip temperature/sensor readings
            if re.search(r'(Temperature|Fan|Sensor)', line, re.I):
                continue

            self.process_history.add("COMMENTS", "keysort", "H1", f"!{line}\n")

        self.found_hardware = True
        return 0

    def show_license(self, session: "LoginSession", cmd: str) -> int:
        """Parse license information."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)

            # Skip expiration dates
            if re.search(r'(Expir|Days remaining)', line, re.I):
                continue

            self.process_history.add("COMMENTS", "keysort", "L1", f"!{line}\n")

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

    def show_policy(self, session: "LoginSession", cmd: str) -> int:
        """Parse policy configuration."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)
            self.process_history.add("COMMENTS", "keysort", "P1", f"!{line}\n")

        return 0

    def show_config(self, session: "LoginSession", cmd: str) -> int:
        """Parse/export configuration."""
        output = session.run_command(cmd)
        if not output:
            return -1

        for line in output.splitlines():
            line = self._filter_line(line)

            # Filter passwords and secrets
            line = re.sub(r'(password\s+).*', r'\1<FILTERED>', line, flags=re.I)
            line = re.sub(r'(secret\s+).*', r'\1<FILTERED>', line, flags=re.I)
            line = re.sub(r'(credential\s+).*', r'\1<FILTERED>', line, flags=re.I)
            line = re.sub(r'(key\s+).*', r'\1<FILTERED>', line, flags=re.I)
            line = re.sub(r'(community\s+).*', r'\1<FILTERED>', line, flags=re.I)

            # Filter encrypted strings (often in format $1$xxx or similar)
            line = re.sub(r'\$\d+\$[A-Za-z0-9./]+', '<ENCRYPTED>', line)

            self.process_history.add("", "", "", line + "\n")

        self.found_end = True
        return 0

    def show_attack_detection(self, session: "LoginSession", cmd: str) -> int:
        """Parse attack detection settings."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)
            self.process_history.add("COMMENTS", "keysort", "A1", f"!{line}\n")

        return 0

    HANDLERS = {
        "ShowVersion": "show_version",
        "ShowHardwareInfo": "show_hardware_info",
        "ShowLicense": "show_license",
        "ShowNetwork": "show_network",
        "ShowPolicy": "show_policy",
        "ShowConfig": "show_config",
        "ShowAttackDetection": "show_attack_detection",
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


# Default commands for Bluecoat (for rancid.types.conf)
BLUECOAT_COMMANDS = """
bluecoat;script;rancid -t bluecoat
bluecoat;login;clogin
bluecoat;module;bluecoat
bluecoat;inloop;bluecoat::inloop
bluecoat;command;bluecoat::ShowVersion;show version
bluecoat;command;bluecoat::ShowHardwareInfo;show hardware-info
bluecoat;command;bluecoat::ShowLicense;show license
bluecoat;command;bluecoat::ShowNetwork;show interface
bluecoat;command;bluecoat::ShowConfig;show configuration
"""
