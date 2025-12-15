"""
Cisco IOS Device Module for RANCID-NG.

Supports Cisco IOS, IOS-XE, ASA/PIX, and compatible devices including:
- Catalyst switches (2960, 3560, 3750, 3850, 9000 series)
- ISR routers (1900, 2900, 4000 series)
- ASR routers (1000, 920 series)
- ASA firewalls
- PIX firewalls (legacy)
- Allied Telesis AW+ (compatible)

This is a port of the Perl ios.pm module from RANCID.
"""

from __future__ import annotations

import re
import sys
from typing import TYPE_CHECKING

from rancid_ng.core.device import DeviceModule
from rancid_ng.core.processor import ProcessHistory
from rancid_ng.devices import register_device

if TYPE_CHECKING:
    from rancid_ng.login.session import LoginSession


@register_device
class CiscoIOS(DeviceModule):
    """
    Device module for Cisco IOS and IOS-XE devices.

    Handles configuration collection from Cisco routers, switches,
    and firewalls running IOS, IOS-XE, ASA, or PIX software.
    """

    name = "ios"
    aliases = ["cisco"]
    login_script = "clogin"
    default_timeout = 90

    # Device type detection
    DEVICE_TYPES = {
        "CE": "Content Engine",
        "SAN": "SAN OS",
        "NXOS": "Nexus OS",
        "3750": "Catalyst 3750",
        "PIX": "PIX Firewall",
        "ASA": "ASA Firewall",
        "IOS": "IOS",
        "XE": "IOS-XE",
    }

    def __init__(self, *args, **kwargs):
        """Initialize IOS device module."""
        super().__init__(*args, **kwargs)

        # State variables (matching ios.pm)
        self.proc = ""
        self.ios = "IOS"
        self.found_version = False
        self.found_env = False
        self.found_diag = False
        self.found_inventory = False
        self.config_register = None
        self.supbootdisk = False
        self.type = None
        self.ssp = 0
        self.sspmem = None

        # Output formatting control
        self.C0 = 0
        self.E0 = 0
        self.H0 = 0
        self.I0 = 0
        self.DO_SHOW_VLAN = False
        self.vss_show_module = False

    def init(self) -> int:
        """
        Initialize for a new collection run.

        Returns:
            0 on success
        """
        # Reset state
        self.proc = ""
        self.ios = "IOS"
        self.found_version = False
        self.found_env = False
        self.found_diag = False
        self.found_inventory = False
        self.config_register = None
        self.supbootdisk = False
        self.type = None
        self.ssp = 0
        self.sspmem = None
        self.C0 = 0
        self.E0 = 0
        self.H0 = 0
        self.I0 = 0
        self.DO_SHOW_VLAN = False
        self.vss_show_module = False

        # Output content type header and separators
        self.process_history.add("", "", "",
                                 f"!RANCID-CONTENT-TYPE: {self.devtype}\n!\n")
        self.process_history.add("COMMENTS", "keysort", "B0", "!\n")
        self.process_history.add("COMMENTS", "keysort", "D0", "!\n")
        self.process_history.add("COMMENTS", "keysort", "F0", "!\n")
        self.process_history.add("COMMENTS", "keysort", "G0", "!\n")

        return 0

    def inloop(self, session: "LoginSession") -> int:
        """
        Main parsing loop for IOS device output.

        Args:
            session: Active login session

        Returns:
            0 on success, non-zero on error
        """
        if not session:
            return -1

        # Build command regex pattern
        cmds_pattern = "|".join(re.escape(cmd) for cmd in self.commands.keys())
        if not cmds_pattern:
            return -1

        # Process commands
        while True:
            # Read a line from the session
            line = self._read_line(session)
            if line is None:
                break

            # Strip carriage returns
            line = line.replace("\r", "")

            # Check for errors
            if line.startswith("Error:"):
                print(f"{self.hostname} clogin error: {line}", file=sys.stdout)
                if self.debug:
                    print(f"{self.hostname} clogin error: {line}", file=sys.stderr)
                self.clean_run = False
                break

            # Check for command prompts
            match = re.search(f'[>#]\\s*({cmds_pattern})\\s*$', line)
            if match:
                cmd = match.group(1)

                # Detect prompt if not already set
                if not self.prompt:
                    prompt_match = re.match(r'^([^#>]+[#>])', line)
                    if prompt_match:
                        self.prompt = re.escape(prompt_match.group(1))
                        self.debug_print(f"PROMPT MATCH: {self.prompt}")

                self.debug_print(f"HIT COMMAND: {line}")

                # Get handler
                handler = self.get_handler(cmd)
                if not handler:
                    print(f"{self.hostname}: undefined function for {cmd}",
                          file=sys.stderr)
                    self.clean_run = False
                    break

                # Execute handler
                result = handler(session, cmd)
                if result < 0:
                    self.clean_run = False
                    break

                # Mark command as run
                self._commands_run.add(cmd)

            # Check for exit
            if re.search(r'[>#]\s*exit$', line):
                self.clean_run = True
                break

        return 0 if self.clean_run else -1

    def _read_line(self, session: "LoginSession") -> str | None:
        """
        Read a line from the session.

        This is a simplified implementation - the actual implementation
        would need to handle the expect-like reading.

        Args:
            session: Login session

        Returns:
            Line of output or None
        """
        # This is a placeholder - actual implementation depends on
        # how we integrate with the session
        pass

    # =========================================================================
    # Command Handlers
    # =========================================================================

    def show_version(self, session: "LoginSession", cmd: str) -> int:
        """
        Parse 'show version' output.

        This is one of the most important parsers - it extracts:
        - Software version and image
        - Hardware model
        - Memory
        - Serial number
        - Boot information
        """
        self.debug_print(f"    In ShowVersion: processing")

        if self.found_version:
            return 0

        # Read until next prompt
        output = session.run_command(cmd)
        if not output:
            return -1

        slave = ""
        slaveslot = ""

        for line in output.splitlines():
            line = self._filter_line(line)

            # Skip noise lines
            if re.match(r'^\s*$', line):
                continue
            if re.match(r'^Load for five', line):
                continue
            if re.match(r'^Time source is', line):
                continue

            # Check for errors
            if re.search(r'invalid (input|command) detected', line, re.I):
                return 1
            if re.search(r'authorization failed', line, re.I):
                return -1

            # Handle pager
            if re.match(r'^<-+ More -+>', line):
                line = re.sub(r'^<-+ More -+>\s*', '', line)

            # Detect slave slot
            match = re.search(r'^Slave in slot (\d+) is running', line)
            if match:
                slave = " Slave:"
                slaveslot = f", slot {match.group(1)}"
                continue

            # Detect IOS-XE
            if re.search(r'cisco ios.*(IOS-)?XE', line, re.I):
                self.ios = "XE"

            # Detect device type
            if re.search(r'^Application and Content Networking .*Software', line):
                self.type = "CE"
            if re.search(r'^Cisco Application Control Software', line):
                self.type = "CE"
            if re.search(r'^Cisco Storage Area Networking Operating System', line):
                self.type = "SAN"
            if re.search(r'^Cisco Nexus Operating System', line):
                self.type = "NXOS"

            # Extract image info
            match = re.search(
                r'^Application and Content Networking Software Release (.+)',
                line, re.I
            )
            if match:
                self.process_history.add(
                    "COMMENTS", "keysort", "F1",
                    f"!Image: {line}\n"
                )
                continue

            # Extract PIX info
            if re.search(r'^Cisco Secure PIX', line, re.I):
                self.process_history.add(
                    "COMMENTS", "keysort", "F1",
                    f"!Image: {line}\n"
                )
                continue

            # Extract IOS version
            match = re.search(
                r'^(Cisco )?IOS .* Software,? \(([A-Za-z0-9_-]*)\), .*Version\s+(.*)$',
                line
            )
            if match:
                software = match.group(2)
                version = match.group(3)
                self.process_history.add(
                    "COMMENTS", "keysort", "F1",
                    f"!Image:{slave} Software: {software}, {version}\n"
                )
                continue

            # Extract compiled info
            match = re.search(r'^Compiled (.*)$', line)
            if match:
                self.process_history.add(
                    "COMMENTS", "keysort", "F3",
                    f"!Image:{slave} Compiled: {match.group(1)}\n"
                )
                continue

            # Extract ROM info
            match = re.search(
                r'^ROM: (IOS \S+ )?(System )?Bootstrap.*(Version.*)$',
                line
            )
            if match:
                self.process_history.add(
                    "COMMENTS", "keysort", "G1",
                    f"!ROM Bootstrap: {match.group(3)}\n"
                )
                continue

            # Extract hardware info (PIX style)
            match = re.search(
                r'^Hardware:\s+(.*), (.* RAM), CPU (.*)$',
                line
            )
            if match:
                self.process_history.add(
                    "COMMENTS", "keysort", "A1",
                    f"!Chassis type: {match.group(1)} - a PIX\n"
                )
                self.process_history.add(
                    "COMMENTS", "keysort", "A2",
                    f"!CPU: {match.group(3)}\n"
                )
                self.process_history.add(
                    "COMMENTS", "keysort", "B1",
                    f"!Memory: {match.group(2)}\n"
                )
                continue

            # Extract serial number
            match = re.search(r'^serial number:\s+(.*)$', line, re.I)
            if match:
                self.process_history.add(
                    "COMMENTS", "keysort", "C1",
                    f"!Serial Number: {match.group(1)}\n"
                )
                continue

            # Extract system image
            match = re.search(r'^System image file is "([^"]*)"', line)
            if match:
                self.process_history.add(
                    "COMMENTS", "keysort", "F5",
                    f"!Image: {match.group(1)}\n"
                )
                continue

            # Extract processor/memory info
            match = re.search(
                r'(\S+(?:\sseries)?)\s+(?:\(([^)]+)\)\s+processor|\(revision[^)]+\)).*\s+with (\S+k) bytes',
                line, re.I
            )
            if match:
                self.proc = match.group(1)
                cpu = match.group(2) or ""
                mem = match.group(3)

                self.process_history.add(
                    "COMMENTS", "keysort", "A1",
                    f"!Chassis type:{slave} {self.proc}{slaveslot}\n"
                )
                if cpu:
                    self.process_history.add(
                        "COMMENTS", "keysort", "A2",
                        f"!CPU:{slave} {cpu}\n"
                    )
                self.process_history.add(
                    "COMMENTS", "keysort", "B1",
                    f"!Memory:{slave} main {mem}\n"
                )
                continue

        self.found_version = True
        return 0

    def show_redundancy(self, session: "LoginSession", cmd: str) -> int:
        """Parse 'show redundancy' output."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)
            self.process_history.add("COMMENTS", "keysort", "A4", f"!{line}\n")

        return 0

    def show_env(self, session: "LoginSession", cmd: str) -> int:
        """Parse 'show env' output."""
        if self.found_env:
            return 0

        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)

            # Skip certain lines for reduced churn
            if re.search(r'(Fan Speed|Temperature|SYSTEM TEMPERATURE)', line):
                continue

            self.process_history.add("COMMENTS", "keysort", "E1", f"!{line}\n")

        self.found_env = True
        return 0

    def show_boot(self, session: "LoginSession", cmd: str) -> int:
        """Parse 'show boot' output."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)

            # Filter oscillating data
            if re.search(r'(BOOT path-list|Config file|Private Config file)', line):
                continue

            self.process_history.add("COMMENTS", "keysort", "H1", f"!{line}\n")

        return 0

    def show_flash(self, session: "LoginSession", cmd: str) -> int:
        """Parse 'show flash' output."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)

            # Summarize flash size instead of showing all files
            if re.search(r'bytes (total|used|available|free)', line, re.I):
                self.process_history.add(
                    "COMMENTS", "keysort", "B3",
                    f"!Flash: {line}\n"
                )

        return 0

    def dir_slot_n(self, session: "LoginSession", cmd: str) -> int:
        """Parse 'dir' command output for various slots."""
        output = session.run_command(cmd)
        if not output:
            return 0

        # Check for errors (directory doesn't exist)
        if re.search(r'(No such file|Invalid input|Error opening)', output):
            return 0

        # Extract directory name and size summary
        total = None
        free = None

        for line in output.splitlines():
            line = self._filter_line(line)

            # Look for size summary
            match = re.search(r'(\d+)\s+bytes\s+total', line)
            if match:
                total = int(match.group(1))
            match = re.search(r'(\d+)\s+bytes\s+free', line)
            if match:
                free = int(match.group(1))

        if total and free:
            from rancid_ng.core.utils import diskszsummary
            summary = diskszsummary(total, free)
            slot = cmd.split()[-1].rstrip(":")

            self.process_history.add(
                "COMMENTS", "keysort", "B4",
                f"!{slot}: {summary}\n"
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

            if not line.strip():
                continue

            self.process_history.add("COMMENTS", "keysort", "I1", f"!{line}\n")

        self.found_inventory = True
        return 0

    def show_vlan(self, session: "LoginSession", cmd: str) -> int:
        """Parse 'show vlan' output."""
        output = session.run_command(cmd)
        if not output:
            return 0

        # Output VLAN summary
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

    def write_term(self, session: "LoginSession", cmd: str) -> int:
        """
        Parse 'show running-config' / 'write term' output.

        This is the main configuration output handler.
        """
        output = session.run_command(cmd)
        if not output:
            return -1

        in_acl = False
        acl_name = ""
        config_started = False

        for line in output.splitlines():
            # Apply standard filters
            line = self._filter_line(line)

            # Skip empty lines before config starts
            if not config_started:
                if re.match(r'^!', line) or re.match(r'^version ', line):
                    config_started = True
                else:
                    continue

            # Track ACL context for filtering
            acl_match = re.match(r'^ip access-list (standard|extended) (\S+)', line)
            if acl_match:
                in_acl = True
                acl_name = acl_match.group(2)

            if in_acl and re.match(r'^!|^[^ ]', line) and not line.startswith('ip access-list'):
                in_acl = False
                acl_name = ""

            # Output the line
            self.process_history.add("", "", "", line + "\n")

            # Check for end marker
            if re.match(r'^end\s*$', line):
                self.found_end = True
                break

        return 0

    def show_diag(self, session: "LoginSession", cmd: str) -> int:
        """Parse 'show diag' output."""
        if self.found_diag:
            return 0

        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)
            self.process_history.add("COMMENTS", "keysort", "D1", f"!{line}\n")

        self.found_diag = True
        return 0

    def show_module(self, session: "LoginSession", cmd: str) -> int:
        """Parse 'show module' output."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)

            # Skip status lines that change frequently
            if re.search(r'(Uptime|Temperature)', line):
                continue

            self.process_history.add("COMMENTS", "keysort", "M1", f"!{line}\n")

        return 0

    def show_license(self, session: "LoginSession", cmd: str) -> int:
        """Parse 'show license' output."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)

            # Skip changing data
            if re.search(r'(Period left|Usage count)', line):
                continue

            self.process_history.add("COMMENTS", "keysort", "L1", f"!{line}\n")

        return 0

    def run_command_comment(self, session: "LoginSession", cmd: str) -> int:
        """Run a command and output as comments."""
        output = session.run_command(cmd)
        if not output:
            return 0

        for line in output.splitlines():
            line = self._filter_line(line)
            self.process_history.add("", "", "", f"!{line}\n")

        return 0

    # Register handler method names for command mapping
    HANDLERS = {
        "ShowVersion": "show_version",
        "ShowRedundancy": "show_redundancy",
        "ShowEnv": "show_env",
        "ShowBoot": "show_boot",
        "ShowFlash": "show_flash",
        "DirSlotN": "dir_slot_n",
        "ShowInventory": "show_inventory",
        "ShowVLAN": "show_vlan",
        "WriteTerm": "write_term",
        "ShowDiag": "show_diag",
        "ShowModule": "show_module",
        "ShowLicense": "show_license",
        "RunCommandComment": "run_command_comment",
    }

    def get_handler(self, command: str) -> callable | None:
        """
        Get handler method for a command.

        Maps handler names from rancid.types.base to methods.
        """
        handler_name = self.commands.get(command)
        if not handler_name:
            return None

        # Extract method name from module::method format
        if "::" in handler_name:
            handler_name = handler_name.split("::")[-1]

        # Map to Python method name
        method_name = self.HANDLERS.get(handler_name)
        if method_name:
            return getattr(self, method_name, None)

        return None
