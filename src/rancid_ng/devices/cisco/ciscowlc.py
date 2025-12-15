"""
Cisco WLC Device Module for RANCID-NG.

Supports Cisco Wireless LAN Controllers:
- WLC 2504
- WLC 5508
- WLC 5520
- WLC 8540
- vWLC
- Catalyst 9800 WLC
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from rancid_ng.core.device import DeviceModule
from rancid_ng.devices import register_device

if TYPE_CHECKING:
    from rancid_ng.login.session import LoginSession


@register_device
class CiscoWLC(DeviceModule):
    """Device module for Cisco Wireless LAN Controllers."""

    name = "ciscowlc"
    aliases = ["cisco-wlc4", "cisco-wlc5", "cisco-wlc8"]
    login_script = "wlogin"
    default_timeout = 120

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

    def show_udi(self, session: "LoginSession", cmd: str) -> int:
        """Parse 'show udi' output."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)
            self.process_history.add("COMMENTS", "keysort", "U1", f"!{line}\n")

        return 0

    def show_sysinfo(self, session: "LoginSession", cmd: str) -> int:
        """Parse 'show sysinfo' output."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)

            # Skip uptime
            if re.search(r'Uptime', line, re.I):
                continue

            self.process_history.add("COMMENTS", "keysort", "S1", f"!{line}\n")

        return 0

    def show_config(self, session: "LoginSession", cmd: str) -> int:
        """Parse configuration output."""
        output = session.run_command(cmd)
        if not output:
            return -1

        for line in output.splitlines():
            line = self._filter_line(line)
            self.process_history.add("", "", "", line + "\n")

        self.found_end = True
        return 0

    HANDLERS = {
        "ShowUdi": "show_udi",
        "ShowSysinfo": "show_sysinfo",
        "ShowConfig": "show_config",
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
