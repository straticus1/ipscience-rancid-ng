"""
Cisco FX-OS Device Module for RANCID-NG.

Supports Cisco Firepower devices running FX-OS:
- Firepower 4100 series
- Firepower 9300 series
- FTD on Firepower hardware
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from rancid_ng.core.device import DeviceModule
from rancid_ng.devices import register_device

if TYPE_CHECKING:
    from rancid_ng.login.session import LoginSession


@register_device
class CiscoFXOS(DeviceModule):
    """Device module for Cisco FX-OS devices."""

    name = "fxos"
    aliases = []
    login_script = "fxlogin"
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

    def show_model(self, session: "LoginSession", cmd: str) -> int:
        """Parse 'show model' output."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)
            self.process_history.add("COMMENTS", "keysort", "A1", f"!{line}\n")

        return 0

    def show_inventory(self, session: "LoginSession", cmd: str) -> int:
        """Parse 'show inventory' output."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)
            self.process_history.add("COMMENTS", "keysort", "I1", f"!{line}\n")

        return 0

    def dir_slot_n(self, session: "LoginSession", cmd: str) -> int:
        """Parse directory listing."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            if re.search(r'bytes (total|free)', line, re.I):
                self.process_history.add(
                    "COMMENTS", "keysort", "D1",
                    f"!{line.strip()}\n"
                )

        return 0

    def show_mode(self, session: "LoginSession", cmd: str) -> int:
        """Parse 'show mode' output."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)
            self.process_history.add("COMMENTS", "keysort", "M1", f"!{line}\n")

        return 0

    def show_managers(self, session: "LoginSession", cmd: str) -> int:
        """Parse 'show managers' output."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)
            self.process_history.add("COMMENTS", "keysort", "M2", f"!{line}\n")

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

    def write_term_ftd(self, session: "LoginSession", cmd: str) -> int:
        """Parse FTD running config."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)
            self.process_history.add("", "", "", line + "\n")

        return 0

    def show_firmware(self, session: "LoginSession", cmd: str) -> int:
        """Parse firmware information."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)
            self.process_history.add("COMMENTS", "keysort", "F1", f"!{line}\n")

        return 0

    def show_chassis(self, session: "LoginSession", cmd: str) -> int:
        """Parse chassis information."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)

            # Skip temperature readings
            if re.search(r'Temperature', line, re.I):
                continue

            self.process_history.add("COMMENTS", "keysort", "C1", f"!{line}\n")

        return 0

    def write_term(self, session: "LoginSession", cmd: str) -> int:
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
        "ShowModel": "show_model",
        "ShowInventory": "show_inventory",
        "DirSlotN": "dir_slot_n",
        "ShowMode": "show_mode",
        "ShowManagers": "show_managers",
        "ShowNetwork": "show_network",
        "WriteTermFTD": "write_term_ftd",
        "RunCommand": "run_command",
        "ShowFirmware": "show_firmware",
        "ShowChassis": "show_chassis",
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
