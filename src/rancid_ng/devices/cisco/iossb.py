"""
Cisco Small Business Device Module for RANCID-NG.

Supports Cisco Small Business switches and other Marvell-based OEMs:
- Cisco SG/SF series
- PowerConnect 5448
- Some Transition Networks switches
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from rancid_ng.core.device import DeviceModule
from rancid_ng.devices import register_device

if TYPE_CHECKING:
    from rancid_ng.login.session import LoginSession


@register_device
class CiscoIOSSB(DeviceModule):
    """Device module for Cisco Small Business devices."""

    name = "iossb"
    aliases = ["cisco-sb", "ios-sb"]
    login_script = "csblogin"
    default_timeout = 90

    def init(self) -> int:
        """Initialize for a new collection run."""
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
        """Parse 'show version' output."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)

            if re.search(r'Uptime', line, re.I):
                continue

            self.process_history.add("COMMENTS", "keysort", "V1", f"!{line}\n")

        return 0

    def show_system(self, session: "LoginSession", cmd: str) -> int:
        """Parse 'show system' output."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)
            self.process_history.add("COMMENTS", "keysort", "S1", f"!{line}\n")

        return 0

    def write_term(self, session: "LoginSession", cmd: str) -> int:
        """Parse running configuration."""
        output = session.run_command(cmd)
        if not output:
            return -1

        for line in output.splitlines():
            line = self._filter_line(line)
            self.process_history.add("", "", "", line + "\n")

        self.found_end = True
        return 0

    HANDLERS = {
        "ShowVersion": "show_version",
        "ShowSystem": "show_system",
        "WriteTerm": "write_term",
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
