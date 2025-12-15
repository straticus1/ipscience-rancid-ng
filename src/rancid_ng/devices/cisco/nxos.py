"""
Cisco NX-OS Device Module for RANCID-NG.

Supports Cisco Nexus switches running NX-OS:
- Nexus 2000 (FEX)
- Nexus 3000/3500
- Nexus 5000/5500/5600
- Nexus 6000
- Nexus 7000/7700
- Nexus 9000

This is a port of the Perl nxos.pm module from RANCID.
"""

from __future__ import annotations

import re
import sys
from typing import TYPE_CHECKING

from rancid_ng.core.device import DeviceModule
from rancid_ng.devices import register_device

if TYPE_CHECKING:
    from rancid_ng.login.session import LoginSession


@register_device
class CiscoNXOS(DeviceModule):
    """
    Device module for Cisco NX-OS devices.

    Handles configuration collection from Cisco Nexus switches.
    """

    name = "nxos"
    aliases = ["cisco-nx", "ios-nx"]
    login_script = "clogin"
    default_timeout = 90

    def __init__(self, *args, **kwargs):
        """Initialize NX-OS device module."""
        super().__init__(*args, **kwargs)

        # State variables
        self.found_version = False
        self.found_license = False
        self.found_env = False
        self.found_module = False
        self.found_inventory = False

    def init(self) -> int:
        """Initialize for a new collection run."""
        self.found_version = False
        self.found_license = False
        self.found_env = False
        self.found_module = False
        self.found_inventory = False

        # Output content type header
        self.process_history.add("", "", "",
                                 f"!RANCID-CONTENT-TYPE: {self.devtype}\n!\n")
        self.process_history.add("COMMENTS", "keysort", "B0", "!\n")
        self.process_history.add("COMMENTS", "keysort", "D0", "!\n")
        self.process_history.add("COMMENTS", "keysort", "F0", "!\n")

        return 0

    def inloop(self, session: "LoginSession") -> int:
        """Main parsing loop for NX-OS output."""
        if not session:
            return -1

        # Process all registered commands
        for cmd, handler_name in self.command_table:
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
        if self.found_version:
            return 0

        output = session.run_command(cmd)
        if not output:
            return -1

        for line in output.splitlines():
            line = self._filter_line(line)

            # Skip uptime - it changes
            if re.search(r'uptime is', line, re.I):
                continue

            # Extract key information
            match = re.search(r'^\s+system:\s+version\s+(\S+)', line)
            if match:
                self.process_history.add(
                    "COMMENTS", "keysort", "F1",
                    f"!Software: NX-OS version {match.group(1)}\n"
                )
                continue

            match = re.search(r'^\s+kickstart:\s+version\s+(\S+)', line)
            if match:
                self.process_history.add(
                    "COMMENTS", "keysort", "F2",
                    f"!Software: Kickstart version {match.group(1)}\n"
                )
                continue

            match = re.search(r'Hardware', line):
            if match:
                self.process_history.add(
                    "COMMENTS", "keysort", "A1",
                    f"!{line}\n"
                )
                continue

            match = re.search(r'(cisco Nexus\S*)', line):
            if match:
                self.process_history.add(
                    "COMMENTS", "keysort", "A1",
                    f"!Chassis: {match.group(1)}\n"
                )
                continue

        self.found_version = True
        return 0

    def show_license(self, session: "LoginSession", cmd: str) -> int:
        """Parse 'show license' output."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)

            # Skip date/time info
            if re.search(r'(expires|Expiry)', line, re.I):
                continue

            self.process_history.add("COMMENTS", "keysort", "L1", f"!{line}\n")

        return 0

    def show_redundancy(self, session: "LoginSession", cmd: str) -> int:
        """Parse 'show system redundancy status' output."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)
            self.process_history.add("COMMENTS", "keysort", "R1", f"!{line}\n")

        return 0

    def show_env(self, session: "LoginSession", cmd: str) -> int:
        """Parse 'show environment' output."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)

            # Skip temperature readings - they change
            if re.search(r'Temperature|Fan Speed', line, re.I):
                continue

            self.process_history.add("COMMENTS", "keysort", "E1", f"!{line}\n")

        return 0

    def show_env_temp(self, session: "LoginSession", cmd: str) -> int:
        """Parse 'show environment temperature' - skip for oscillating data."""
        return 0

    def show_env_power(self, session: "LoginSession", cmd: str) -> int:
        """Parse 'show environment power' output."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)

            # Skip wattage readings
            if re.search(r'\d+\.\d+\s+W', line):
                continue

            self.process_history.add("COMMENTS", "keysort", "P1", f"!{line}\n")

        return 0

    def show_boot(self, session: "LoginSession", cmd: str) -> int:
        """Parse 'show boot' output."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)
            self.process_history.add("COMMENTS", "keysort", "H1", f"!{line}\n")

        return 0

    def dir_slot_n(self, session: "LoginSession", cmd: str) -> int:
        """Parse 'dir' command output."""
        output = session.run_command(cmd)
        if not output:
            return 0

        if re.search(r'(No such file|Invalid)', output):
            return 0

        # Extract size summary
        for line in output.splitlines():
            if re.search(r'bytes (used|free|total)', line, re.I):
                slot = cmd.split()[-1].rstrip(":")
                self.process_history.add(
                    "COMMENTS", "keysort", "B4",
                    f"!{slot}: {line.strip()}\n"
                )

        return 0

    def show_module(self, session: "LoginSession", cmd: str) -> int:
        """Parse 'show module' output."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)

            # Skip uptime
            if re.search(r'uptime', line, re.I):
                continue

            self.process_history.add("COMMENTS", "keysort", "M1", f"!{line}\n")

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

    def show_int_transceiver(self, session: "LoginSession", cmd: str) -> int:
        """Parse 'show interface transceiver' output."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)

            # Skip readings that change
            if re.search(r'(Temperature|Voltage|Current|Power)', line, re.I):
                continue

            self.process_history.add("COMMENTS", "keysort", "T1", f"!{line}\n")

        return 0

    def show_vlan(self, session: "LoginSession", cmd: str) -> int:
        """Parse 'show vlan' output."""
        output = session.run_command(cmd)
        if not output:
            return 0

        vlan_count = 0
        for line in output.splitlines():
            if re.match(r'^\d+\s+\S+\s+active', line):
                vlan_count += 1

        if vlan_count > 0:
            self.process_history.add(
                "COMMENTS", "keysort", "V1",
                f"!VLANs: {vlan_count} active\n"
            )

        return 0

    def show_fex(self, session: "LoginSession", cmd: str) -> int:
        """Parse 'show fex' output."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)
            self.process_history.add("COMMENTS", "keysort", "X1", f"!{line}\n")

        return 0

    def write_term(self, session: "LoginSession", cmd: str) -> int:
        """Parse 'show running-config' output."""
        output = session.run_command(cmd)
        if not output:
            return -1

        config_started = False

        for line in output.splitlines():
            line = self._filter_line(line)

            # Wait for config to start
            if not config_started:
                if re.match(r'^!Command:|^version ', line):
                    config_started = True
                else:
                    continue

            # Output line
            self.process_history.add("", "", "", line + "\n")

            # Check for end
            if re.match(r'^end\s*$', line):
                self.found_end = True
                break

        return 0

    # Handler mapping
    HANDLERS = {
        "ShowVersion": "show_version",
        "ShowVersionBuild": "show_version",
        "ShowLicense": "show_license",
        "ShowRedundancy": "show_redundancy",
        "ShowEnv": "show_env",
        "ShowEnvTemp": "show_env_temp",
        "ShowEnvPower": "show_env_power",
        "ShowBoot": "show_boot",
        "DirSlotN": "dir_slot_n",
        "ShowModule": "show_module",
        "ShowInventory": "show_inventory",
        "ShowIntTransceiver": "show_int_transceiver",
        "ShowVTP": "show_vlan",
        "ShowVLAN": "show_vlan",
        "ShowDebug": "run_command",
        "ShowCores": "run_command",
        "ShowProcLog": "run_command",
        "ShowFex": "show_fex",
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
