"""
RANCID-NG Login Module

Provides SSH/Telnet connection handling with expect-like prompt matching.
This replaces the Expect/Tcl-based login scripts (clogin, jlogin, etc.)
with pure Python implementations using paramiko and pexpect.
"""

from rancid_ng.login.session import LoginSession
from rancid_ng.login.ssh import SSHConnection
from rancid_ng.login.telnet import TelnetConnection
from rancid_ng.login.expect import ExpectSession

__all__ = [
    "LoginSession",
    "SSHConnection",
    "TelnetConnection",
    "ExpectSession",
]
