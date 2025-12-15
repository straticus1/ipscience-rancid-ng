"""
Cisco IOS-XR Device Module for RANCID-NG.

Supports Cisco devices running IOS-XR:
- ASR 9000 series
- NCS series (5000, 5500, 6000)
- CRS series
- XRv (virtual)

Handles both Classic XR (cXR) and Enhanced XR (eXR/64-bit).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from rancid_ng.core.device import DeviceModule
from rancid_ng.devices import register_device

if TYPE_CHECKING:
    from rancid_ng.login.session import LoginSession


@register_device
class CiscoIOSXR(DeviceModule):
    """Device module for Cisco IOS-XR devices."""

    name = "iosxr"
    aliases = ["cisco-xr", "ios-xr", "ios-exr", "cisco-exr", "ios-xr7", "cisco-xr7"]
    login_script = "clogin"
    default_timeout = 120

    def __init__(self, *args, **kwargs):
        """Initialize IOS-XR device module."""
        super().__init__(*args, **kwargs)
        self.found_version = False
        self.found_inventory = False

    def init(self) -> int:
        """Initialize for a new collection run."""
        self.found_version = False
        self.found_inventory = False

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
        """Parse 'show version' / 'admin show version' output."""
        if self.found_version:
            return 0

        output = session.run_command(cmd)
        if not output:
            return -1

        for line in output.splitlines():
            line = self._filter_line(line)

            if re.search(r'uptime is', line, re.I):
                continue

            if re.search(r'(Software|Version|Copyright)', line, re.I):
                self.process_history.add(
                    "COMMENTS", "keysort", "F1",
                    f"!{line}\n"
                )

        self.found_version = True
        return 0

    def show_install_active(self, session: "LoginSession", cmd: str) -> int:
        """Parse 'show install active' output."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)
            self.process_history.add("COMMENTS", "keysort", "I1", f"!{line}\n")

        return 0

    def show_install_summary(self, session: "LoginSession", cmd: str) -> int:
        """Parse 'admin show install active' output."""
        return self.show_install_active(session, cmd)

    def show_license(self, session: "LoginSession", cmd: str) -> int:
        """Parse 'show license' output."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)
            self.process_history.add("COMMENTS", "keysort", "L1", f"!{line}\n")

        return 0

    def show_boot_var(self, session: "LoginSession", cmd: str) -> int:
        """Parse boot variables."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)
            self.process_history.add("COMMENTS", "keysort", "H1", f"!{line}\n")

        return 0

    def show_hw_fpd(self, session: "LoginSession", cmd: str) -> int:
        """Parse 'show hw-module fpd' output."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)
            self.process_history.add("COMMENTS", "keysort", "P1", f"!{line}\n")

        return 0

    def show_redundancy(self, session: "LoginSession", cmd: str) -> int:
        """Parse 'show redundancy' output."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)

            if re.search(r'uptime', line, re.I):
                continue

            self.process_history.add("COMMENTS", "keysort", "R1", f"!{line}\n")

        return 0

    def show_env(self, session: "LoginSession", cmd: str) -> int:
        """Parse environment output."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)

            if re.search(r'Temperature|Fan', line, re.I):
                continue

            self.process_history.add("COMMENTS", "keysort", "E1", f"!{line}\n")

        return 0

    def dir_slot_n(self, session: "LoginSession", cmd: str) -> int:
        """Parse directory listing."""
        output = session.run_command(cmd)
        if not output:
            return 0

        if re.search(r'No such file', output):
            return 0

        for line in output.splitlines():
            if re.search(r'bytes (total|free)', line, re.I):
                self.process_history.add(
                    "COMMENTS", "keysort", "D1",
                    f"!{line.strip()}\n"
                )

        return 0

    def show_inventory(self, session: "LoginSession", cmd: str) -> int:
        """Parse 'show inventory' output."""
        if self.found_inventory:
            return 0

        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)
            self.process_history.add("COMMENTS", "keysort", "I1", f"!{line}\n")

        self.found_inventory = True
        return 0

    def show_diag(self, session: "LoginSession", cmd: str) -> int:
        """Parse diagnostic info."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)
            self.process_history.add("COMMENTS", "keysort", "D1", f"!{line}\n")

        return 0

    def admin_show_running(self, session: "LoginSession", cmd: str) -> int:
        """Parse admin running config."""
        output = session.run_command(cmd)
        if not output:
            return 0

        self.process_history.add("", "", "", "! Admin Configuration\n")
        for line in output.splitlines():
            line = self._filter_line(line)
            self.process_history.add("", "", "", f"!{line}\n")

        return 0

    def write_term(self, session: "LoginSession", cmd: str) -> int:
        """Parse running configuration."""
        output = session.run_command(cmd)
        if not output:
            return -1

        for line in output.splitlines():
            line = self._filter_line(line)
            self.process_history.add("", "", "", line + "\n")

            if re.match(r'^end\s*$', line):
                self.found_end = True
                break

        return 0

    HANDLERS = {
        "ShowVersion": "show_version",
        "ShowInstallActive": "show_install_active",
        "ShowInstallSummary": "show_install_summary",
        "ShowLicense": "show_license",
        "ShowBootVar": "show_boot_var",
        "ShowHWfpd": "show_hw_fpd",
        "ShowRedundancy": "show_redundancy",
        "ShowEnv": "show_env",
        "ShowMemorySum": "show_version",
        "DirSlotN": "dir_slot_n",
        "ShowContAll": "show_diag",
        "AdminShowDiag": "show_diag",
        "ShowDiag": "show_diag",
        "ShowInventory": "show_inventory",
        "ShowVLAN": "run_command",
        "ShowDebug": "run_command",
        "ShowRPL": "run_command",
        "AdminShowRunning": "admin_show_running",
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
