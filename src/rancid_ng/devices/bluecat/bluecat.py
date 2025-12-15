"""
BlueCat Device Module for RANCID-NG.

NEW DEVICE TYPE - Not in original RANCID!

Supports BlueCat DDI (DNS, DHCP, IPAM) appliances:
- BlueCat Address Manager (BAM)
- BlueCat DNS/DHCP Server (BDDS)

BlueCat CLI commands (Proteus Shell / PSM):
- show version: Version information
- show system: System status
- show network: Network configuration
- show configuration: Running configuration
- configure export: Export configuration
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from rancid_ng.core.device import DeviceModule
from rancid_ng.devices import register_device

if TYPE_CHECKING:
    from rancid_ng.login.session import LoginSession


@register_device
class BlueCat(DeviceModule):
    """
    Device module for BlueCat DDI appliances.

    This is a NEW device type added to RANCID-NG.
    """

    name = "bluecat"
    aliases = ["bluecat-bam", "bluecat-bdds", "proteus"]
    login_script = "clogin"
    default_timeout = 120

    def __init__(self, *args, **kwargs):
        """Initialize BlueCat device module."""
        super().__init__(*args, **kwargs)
        self.found_version = False
        self.appliance_type = None  # BAM or BDDS

    def init(self) -> int:
        """Initialize for a new collection run."""
        self.found_version = False
        self.appliance_type = None

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

            # Detect appliance type
            if re.search(r'Address Manager', line, re.I):
                self.appliance_type = "BAM"
            elif re.search(r'DNS.*DHCP Server', line, re.I):
                self.appliance_type = "BDDS"

            # Skip dynamic data
            if re.search(r'(Uptime|Started)', line, re.I):
                continue

            self.process_history.add("COMMENTS", "keysort", "V1", f"!{line}\n")

        self.found_version = True
        return 0

    def show_system(self, session: "LoginSession", cmd: str) -> int:
        """Parse system information."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)

            # Skip counters
            if re.search(r'(Queries|Cache|Memory Usage)', line, re.I):
                continue

            self.process_history.add("COMMENTS", "keysort", "S1", f"!{line}\n")

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

    def show_dns_config(self, session: "LoginSession", cmd: str) -> int:
        """Parse DNS configuration."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)
            self.process_history.add("COMMENTS", "keysort", "D1", f"!{line}\n")

        return 0

    def show_dhcp_config(self, session: "LoginSession", cmd: str) -> int:
        """Parse DHCP configuration."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)
            self.process_history.add("COMMENTS", "keysort", "H1", f"!{line}\n")

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

            self.process_history.add("", "", "", line + "\n")

        self.found_end = True
        return 0

    HANDLERS = {
        "ShowVersion": "show_version",
        "ShowSystem": "show_system",
        "ShowNetwork": "show_network",
        "ShowDNSConfig": "show_dns_config",
        "ShowDHCPConfig": "show_dhcp_config",
        "ShowConfig": "show_config",
        "ConfigExport": "show_config",
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


# Default commands for BlueCat (for rancid.types.conf)
BLUECAT_COMMANDS = """
bluecat;script;rancid -t bluecat
bluecat;login;clogin
bluecat;module;bluecat
bluecat;inloop;bluecat::inloop
bluecat;command;bluecat::ShowVersion;show version
bluecat;command;bluecat::ShowSystem;show system
bluecat;command;bluecat::ShowNetwork;show network
bluecat;command;bluecat::ShowConfig;configure export
"""
