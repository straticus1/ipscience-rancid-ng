"""
Main RANCID-NG orchestration class.

This module provides the main Rancid class that orchestrates the
configuration collection process:
- Loading device type definitions
- Instantiating the appropriate device module
- Managing the login session
- Coordinating output processing
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

from rancid_ng.config.types import DeviceTypeRegistry
from rancid_ng.core.processor import ProcessHistory

if TYPE_CHECKING:
    from rancid_ng.core.device import DeviceModule
    from rancid_ng.login.session import LoginSession


class Rancid:
    """
    Main RANCID-NG collection orchestrator.

    This class coordinates the configuration collection process:
    1. Load device type configuration
    2. Instantiate the appropriate device module
    3. Establish connection via login script
    4. Execute commands and collect output
    5. Process and filter output
    6. Write to output file

    Example:
        >>> rancid = Rancid(hostname="router1", devtype="cisco")
        >>> rancid.collect()
    """

    # Default paths for configuration files
    DEFAULT_SYSCONFDIR = "/etc/rancid"
    DEFAULT_BASEDIR = "/var/rancid"

    def __init__(
        self,
        hostname: str,
        devtype: str,
        output: TextIO | None = None,
        debug: bool = False,
        log: bool = False,
        file_mode: bool = False,
    ):
        """
        Initialize the RANCID collector.

        Args:
            hostname: Target device hostname
            devtype: Device type name (e.g., "cisco", "junos")
            output: Output stream (defaults to stdout)
            debug: Enable debug output
            log: Enable logging
            file_mode: Read from file instead of connecting
        """
        self.hostname = hostname
        self.devtype = devtype.lower()
        self.output = output or sys.stdout
        self.debug = debug
        self.log = log
        self.file_mode = file_mode

        # Configuration paths
        self.sysconfdir = os.environ.get("RANCID_SYSCONFDIR", self.DEFAULT_SYSCONFDIR)
        self.basedir = os.environ.get("BASEDIR", self.DEFAULT_BASEDIR)

        # State
        self.device_module: DeviceModule | None = None
        self.session: LoginSession | None = None
        self.clean_run = False
        self.timeout = 90  # Default timeout

        # Load device type registry
        self.type_registry = DeviceTypeRegistry()
        self._load_type_configs()

    def _load_type_configs(self) -> None:
        """Load device type configuration files."""
        # Try standard locations
        config_paths = [
            Path(self.sysconfdir) / "rancid.types.base",
            Path(self.sysconfdir) / "rancid.types.conf",
            Path(__file__).parent.parent.parent.parent / "etc" / "rancid.types.base",
            Path(__file__).parent.parent.parent.parent / "etc" / "rancid.types.conf",
        ]

        for path in config_paths:
            if path.exists():
                self.type_registry.load_file(path)
                if self.debug:
                    print(f"Loaded type config: {path}", file=sys.stderr)

    def collect(self) -> int:
        """
        Run the configuration collection.

        Returns:
            0 on success (clean run), non-zero on error
        """
        # Get device type configuration
        type_config = self.type_registry.get_type(self.devtype)
        if not type_config:
            print(f"Unknown device type: {self.devtype}", file=sys.stderr)
            return 1

        # Handle aliases
        if type_config.alias:
            if self.debug:
                print(
                    f"Device type {self.devtype} aliased to {type_config.alias}",
                    file=sys.stderr
                )
            return Rancid(
                hostname=self.hostname,
                devtype=type_config.alias,
                output=self.output,
                debug=self.debug,
                log=self.log,
                file_mode=self.file_mode,
            ).collect()

        # Set timeout from config
        if type_config.timeout:
            self.timeout = type_config.timeout

        # Load the device module
        self.device_module = self._load_device_module(type_config)
        if not self.device_module:
            print(f"Failed to load module for: {self.devtype}", file=sys.stderr)
            return 1

        # Register commands from type configuration
        for cmd, handler in type_config.commands:
            self.device_module.register_command(cmd, handler)

        # Initialize the device module
        result = self.device_module.init()
        if result != 0:
            return result

        # Establish connection (unless in file mode)
        if not self.file_mode:
            self.session = self._create_session(type_config)
            if not self.session:
                print(f"Failed to connect to: {self.hostname}", file=sys.stderr)
                return 1

        # Run the collection loop
        try:
            result = self.device_module.inloop(self.session)
        except Exception as e:
            print(f"Collection error: {e}", file=sys.stderr)
            if self.debug:
                import traceback
                traceback.print_exc()
            return 1
        finally:
            # Cleanup
            if self.session:
                self.session.close()

        # Finalize output
        self.device_module.finalize()

        # Check for clean run
        self.clean_run = self.device_module.clean_run
        return 0 if self.clean_run else 1

    def _load_device_module(self, type_config) -> DeviceModule | None:
        """
        Load the appropriate device module.

        Args:
            type_config: Device type configuration

        Returns:
            Instantiated device module or None
        """
        from rancid_ng.devices import get_device_module

        module_name = type_config.module
        if not module_name:
            # Try to use device type name as module name
            module_name = self.devtype

        module_class = get_device_module(module_name)
        if module_class:
            return module_class(
                hostname=self.hostname,
                devtype=self.devtype,
                output=self.output,
                debug=self.debug,
            )

        return None

    def _create_session(self, type_config) -> LoginSession | None:
        """
        Create a login session to the device.

        Args:
            type_config: Device type configuration

        Returns:
            Active LoginSession or None
        """
        from rancid_ng.login.session import LoginSession
        from rancid_ng.config.cloginrc import CloginrcParser

        # Load authentication configuration
        cloginrc = CloginrcParser()
        auth_config = cloginrc.get_auth(self.hostname)

        # Create session
        session = LoginSession(
            hostname=self.hostname,
            login_script=type_config.login or "clogin",
            timeout=self.timeout,
            debug=self.debug,
        )

        # Apply authentication
        if auth_config:
            session.configure_auth(auth_config)

        # Connect
        if session.connect():
            return session

        return None

    def get_command_string(self) -> str:
        """
        Get the command string for the login script.

        This is used with the -C option to output the command
        that would be passed to the login script.

        Returns:
            Semicolon-separated command string
        """
        type_config = self.type_registry.get_type(self.devtype)
        if not type_config:
            return ""

        commands = [cmd for cmd, _ in type_config.commands]
        return ";".join(commands)

    def print_command_line(self) -> None:
        """
        Print the command line that would be used to collect config.

        This is the -C option behavior from the original rancid.
        """
        type_config = self.type_registry.get_type(self.devtype)
        if not type_config:
            print(f"Unknown device type: {self.devtype}", file=sys.stderr)
            return

        login_script = type_config.login or "clogin"
        cmd_string = self.get_command_string()

        cmd = f"{login_script}"
        if self.timeout != 90:
            cmd += f" -t {self.timeout}"
        cmd += f" -c '{cmd_string}' {self.hostname}"

        print(cmd)
