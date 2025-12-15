"""
Cisco IronPort Device Module for RANCID-NG.

NEW DEVICE TYPE - Not in original RANCID!

Supports Cisco IronPort/AsyncOS appliances:
- Email Security Appliance (ESA) / C-Series
- Web Security Appliance (WSA) / S-Series
- Security Management Appliance (SMA) / M-Series

AsyncOS CLI commands used:
- version: Show appliance version and serial
- showconfig: Export full configuration
- displayconfig: Display configuration (may need different format)
- status: System status
- systemsetup: Basic system settings (view mode)
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from rancid_ng.core.device import DeviceModule
from rancid_ng.devices import register_device

if TYPE_CHECKING:
    from rancid_ng.login.session import LoginSession


@register_device
class CiscoIronPort(DeviceModule):
    """
    Device module for Cisco IronPort/AsyncOS appliances.

    This is a NEW device type added to RANCID-NG.
    """

    name = "ironport"
    aliases = ["asyncos", "cisco-ironport", "esa", "wsa", "sma"]
    login_script = "clogin"  # Standard SSH login
    default_timeout = 120

    # AsyncOS prompts are typically: hostname>
    PROMPT_PATTERN = r'[\w\.-]+>\s*$'

    def __init__(self, *args, **kwargs):
        """Initialize IronPort device module."""
        super().__init__(*args, **kwargs)
        self.found_version = False
        self.appliance_type = None  # ESA, WSA, or SMA

    def init(self) -> int:
        """Initialize for a new collection run."""
        self.found_version = False
        self.appliance_type = None

        self.process_history.add("", "", "",
                                 f"!RANCID-CONTENT-TYPE: {self.devtype}\n!\n")
        self.process_history.add("COMMENTS", "keysort", "A0", "!\n")
        return 0

    def inloop(self, session: "LoginSession") -> int:
        """Main parsing loop for IronPort output."""
        if not session:
            return -1

        # Execute all registered commands
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
        """
        Parse 'version' command output.

        Example output:
        Current Version
        ===============
        Product: Cisco C680 Email Security Appliance
        Model: C680
        Version: 14.0.0-698
        Build Date: 2023-01-15
        Serial #: 1234567890AB
        """
        if self.found_version:
            return 0

        output = session.run_command(cmd)
        if not output:
            return -1

        for line in output.splitlines():
            line = self._filter_line(line)

            if not line.strip() or line.startswith("="):
                continue

            # Detect appliance type
            if re.search(r'Email Security Appliance', line, re.I):
                self.appliance_type = "ESA"
            elif re.search(r'Web Security Appliance', line, re.I):
                self.appliance_type = "WSA"
            elif re.search(r'Security Management Appliance', line, re.I):
                self.appliance_type = "SMA"

            # Extract key information
            match = re.match(r'^(Product|Model|Version|Serial\s*#?):\s*(.+)$', line)
            if match:
                key = match.group(1)
                value = match.group(2).strip()
                self.process_history.add(
                    "COMMENTS", "keysort", "A1",
                    f"!{key}: {value}\n"
                )
                continue

            # Skip changing data
            if re.search(r'(Uptime|Build Date|Time)', line, re.I):
                continue

            self.process_history.add("COMMENTS", "keysort", "A2", f"!{line}\n")

        self.found_version = True
        return 0

    def show_status(self, session: "LoginSession", cmd: str) -> int:
        """
        Parse 'status' command output.

        Shows system status including counters - we filter changing data.
        """
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)

            # Skip counters and dynamic data
            if re.search(r'(Messages|Connections|Uptime|Queue)', line, re.I):
                continue

            # Keep hardware/license info
            if re.search(r'(Feature|License|Hardware|Memory)', line, re.I):
                self.process_history.add(
                    "COMMENTS", "keysort", "S1",
                    f"!{line}\n"
                )

        return 0

    def show_license(self, session: "LoginSession", cmd: str) -> int:
        """Parse license information."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)

            # Skip expiration dates - they change
            if re.search(r'(Expires|Expiration)', line, re.I):
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

    def show_config(self, session: "LoginSession", cmd: str) -> int:
        """
        Parse 'showconfig' command output.

        This exports the full AsyncOS configuration in XML format.
        Note: This can be a large output and may take time.
        """
        output = session.run_command(cmd)
        if not output:
            return -1

        in_config = False

        for line in output.splitlines():
            line = self._filter_line(line)

            # Look for start of XML config
            if re.match(r'^<\?xml', line) or re.match(r'^<config', line):
                in_config = True

            if in_config:
                # Filter passwords and secrets in XML
                line = self._filter_xml_secrets(line)
                self.process_history.add("", "", "", line + "\n")

            # Look for end of config
            if re.match(r'^</config>', line):
                in_config = False
                self.found_end = True

        return 0

    def display_config(self, session: "LoginSession", cmd: str) -> int:
        """
        Parse 'displayconfig' command output.

        Alternative configuration display format.
        """
        output = session.run_command(cmd)
        if not output:
            return -1

        for line in output.splitlines():
            line = self._filter_line(line)
            self.process_history.add("", "", "", line + "\n")

        self.found_end = True
        return 0

    def _filter_xml_secrets(self, line: str) -> str:
        """
        Filter secrets from XML configuration.

        AsyncOS config contains encrypted passwords but we still
        filter them for safety.
        """
        # Filter password elements
        patterns = [
            (r'<password>.*?</password>', '<password>FILTERED</password>'),
            (r'<secret>.*?</secret>', '<secret>FILTERED</secret>'),
            (r'<key>.*?</key>', '<key>FILTERED</key>'),
            (r'<passphrase>.*?</passphrase>', '<passphrase>FILTERED</passphrase>'),
            (r'<ldap_password>.*?</ldap_password>', '<ldap_password>FILTERED</ldap_password>'),
        ]

        result = line
        for pattern, replacement in patterns:
            result = re.sub(pattern, replacement, result, flags=re.I)

        return result

    # Command to handler mapping
    HANDLERS = {
        "ShowVersion": "show_version",
        "ShowStatus": "show_status",
        "ShowLicense": "show_license",
        "ShowNetwork": "show_network",
        "ShowConfig": "show_config",
        "DisplayConfig": "display_config",
    }

    def get_handler(self, command: str) -> callable | None:
        """Get handler method for a command."""
        handler_name = self.commands.get(command)
        if not handler_name:
            # Try command directly
            return getattr(self, command.lower().replace(" ", "_"), None)

        if "::" in handler_name:
            handler_name = handler_name.split("::")[-1]

        method_name = self.HANDLERS.get(handler_name)
        if method_name:
            return getattr(self, method_name, None)

        return None


# Define default commands for IronPort
# This would go in rancid.types.conf
IRONPORT_COMMANDS = """
# Cisco IronPort / AsyncOS
ironport;script;rancid -t ironport
ironport;login;clogin
ironport;module;ironport
ironport;inloop;ironport::inloop
ironport;command;ironport::ShowVersion;version
ironport;command;ironport::ShowStatus;status
ironport;command;ironport::ShowLicense;showlicense
ironport;command;ironport::ShowConfig;showconfig
"""
