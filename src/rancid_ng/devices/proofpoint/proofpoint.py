"""
Proofpoint Device Module for RANCID-NG.

NEW DEVICE TYPE - Not in original RANCID!

Supports Proofpoint email security appliances:
- Proofpoint Protection Server (PPS)
- Proofpoint Email Protection

Proofpoint CLI commands:
- version: Show version information
- show config: Display configuration
- show system: System information
- show license: License status
- config export: Export configuration
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from rancid_ng.core.device import DeviceModule
from rancid_ng.devices import register_device

if TYPE_CHECKING:
    from rancid_ng.login.session import LoginSession


@register_device
class Proofpoint(DeviceModule):
    """
    Device module for Proofpoint email security appliances.

    This is a NEW device type added to RANCID-NG.
    """

    name = "proofpoint"
    aliases = ["pps", "proofpoint-pps"]
    login_script = "clogin"
    default_timeout = 120

    def __init__(self, *args, **kwargs):
        """Initialize Proofpoint device module."""
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
            if re.search(r'(Uptime|Started)', line, re.I):
                continue

            # Extract version info
            if re.search(r'(Version|Release|Build|Serial)', line, re.I):
                self.process_history.add(
                    "COMMENTS", "keysort", "V1",
                    f"!{line}\n"
                )

        self.found_version = True
        return 0

    def show_system(self, session: "LoginSession", cmd: str) -> int:
        """Parse system information."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)

            # Skip counters and dynamic data
            if re.search(r'(Messages|Queue|CPU|Memory Usage)', line, re.I):
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

            # Skip expiration dates
            if re.search(r'(Expires|Expiration|Days)', line, re.I):
                continue

            self.process_history.add("COMMENTS", "keysort", "L1", f"!{line}\n")

        return 0

    def show_config(self, session: "LoginSession", cmd: str) -> int:
        """Parse configuration."""
        output = session.run_command(cmd)
        if not output:
            return -1

        for line in output.splitlines():
            line = self._filter_line(line)

            # Filter passwords
            line = re.sub(r'(password\s*=\s*).*', r'\1<FILTERED>', line, flags=re.I)
            line = re.sub(r'(secret\s*=\s*).*', r'\1<FILTERED>', line, flags=re.I)

            self.process_history.add("", "", "", line + "\n")

        self.found_end = True
        return 0

    def config_export(self, session: "LoginSession", cmd: str) -> int:
        """Export full configuration."""
        return self.show_config(session, cmd)

    HANDLERS = {
        "ShowVersion": "show_version",
        "ShowSystem": "show_system",
        "ShowLicense": "show_license",
        "ShowConfig": "show_config",
        "ConfigExport": "config_export",
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


# Default commands for Proofpoint (for rancid.types.conf)
PROOFPOINT_COMMANDS = """
proofpoint;script;rancid -t proofpoint
proofpoint;login;clogin
proofpoint;module;proofpoint
proofpoint;inloop;proofpoint::inloop
proofpoint;command;proofpoint::ShowVersion;version
proofpoint;command;proofpoint::ShowSystem;show system
proofpoint;command;proofpoint::ShowLicense;show license
proofpoint;command;proofpoint::ShowConfig;config export
"""
