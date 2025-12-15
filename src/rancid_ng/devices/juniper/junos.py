"""
Juniper JunOS Device Module for RANCID-NG.

Supports Juniper devices running JunOS:
- MX series routers
- EX series switches
- SRX series firewalls
- QFX series switches
- PTX series routers
- ACX series routers
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from rancid_ng.core.device import DeviceModule
from rancid_ng.devices import register_device

if TYPE_CHECKING:
    from rancid_ng.login.session import LoginSession


@register_device
class JunOS(DeviceModule):
    """Device module for Juniper JunOS devices."""

    name = "junos"
    aliases = ["juniper", "junos-evo", "juniper-srx"]
    login_script = "jlogin"
    default_timeout = 120

    def init(self) -> int:
        self.process_history.add("", "", "",
                                 f"!RANCID-CONTENT-TYPE: {self.devtype}\n!\n")
        return 0

    def inloop(self, session: "LoginSession") -> int:
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

    def show_chassis_hardware(self, session: "LoginSession", cmd: str) -> int:
        """Parse 'show chassis hardware' output."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)
            self.process_history.add("COMMENTS", "keysort", "H1", f"!{line}\n")

        return 0

    def show_version(self, session: "LoginSession", cmd: str) -> int:
        """Parse 'show version' output."""
        output = session.run_command(cmd)
        if not output:
            return -1

        for line in output.splitlines():
            line = self._filter_line(line)
            self.process_history.add("COMMENTS", "keysort", "V1", f"!{line}\n")

        return 0

    def show_configuration(self, session: "LoginSession", cmd: str) -> int:
        """Parse 'show configuration' output."""
        output = session.run_command(cmd)
        if not output:
            return -1

        for line in output.splitlines():
            line = self._filter_line(line)

            # Filter secrets
            line = re.sub(r'(encrypted-password\s+)"[^"]+"', r'\1"<removed>"', line)
            line = re.sub(r'(secret\s+)"[^"]+"', r'\1"<removed>"', line)

            self.process_history.add("", "", "", line + "\n")

        self.found_end = True
        return 0

    HANDLERS = {
        "ShowChassisHardware": "show_chassis_hardware",
        "ShowChassisEnvironment": "show_chassis_hardware",
        "ShowChassisFirmware": "show_chassis_hardware",
        "ShowChassisFpcDetail": "show_chassis_hardware",
        "ShowChassisRoutingEngine": "show_chassis_hardware",
        "ShowChassisSCB": "show_chassis_hardware",
        "ShowChassisClocks": "show_chassis_hardware",
        "ShowChassisAlarms": "show_chassis_hardware",
        "ShowSystemLicense": "show_version",
        "ShowSystemBootMessages": "show_version",
        "ShowSystemCoreDumps": "show_version",
        "ShowVersion": "show_version",
        "ShowConfiguration": "show_configuration",
    }

    def get_handler(self, command: str) -> callable | None:
        handler_name = self.commands.get(command)
        if not handler_name:
            return None

        if "::" in handler_name:
            handler_name = handler_name.split("::")[-1]

        method_name = self.HANDLERS.get(handler_name)
        if method_name:
            return getattr(self, method_name, None)

        return None
