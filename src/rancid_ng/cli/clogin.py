"""
clogin - Cisco Login Script for RANCID-NG

Python replacement for the Expect-based clogin script.
"""

from __future__ import annotations

import sys
from argparse import ArgumentParser

from rancid_ng import __version__


def main() -> int:
    """Main entry point for clogin."""
    parser = ArgumentParser(
        description="Login to Cisco devices",
        prog="clogin",
    )
    parser.add_argument("-V", "--version", action="version",
                        version=f"rancid-ng clogin {__version__}")
    parser.add_argument("-d", "--debug", action="store_true",
                        help="Enable debug output")
    parser.add_argument("-t", "--timeout", type=int, default=90,
                        help="Timeout in seconds")
    parser.add_argument("-c", "--command", dest="commands",
                        help="Commands to execute (semicolon-separated)")
    parser.add_argument("-x", "--execute", dest="script",
                        help="Execute commands from file")
    parser.add_argument("-f", "--file", dest="cloginrc",
                        help="Use alternate .cloginrc file")
    parser.add_argument("-u", "--user", help="Username")
    parser.add_argument("-p", "--password", help="Password")
    parser.add_argument("-e", "--enable", dest="enable_password",
                        help="Enable password")
    parser.add_argument("-noenable", action="store_true",
                        help="Don't enter enable mode")
    parser.add_argument("-autoenable", action="store_true",
                        help="Already in enable mode after login")
    parser.add_argument("hostname", help="Target device hostname")

    args = parser.parse_args()

    from rancid_ng.login.session import LoginSession
    from rancid_ng.config.cloginrc import CloginrcParser

    # Load authentication config
    cloginrc = CloginrcParser()
    if args.cloginrc:
        cloginrc.load_file(args.cloginrc)
    else:
        cloginrc.load_default()

    auth = cloginrc.get_auth(args.hostname)

    # Override with command line args
    if args.user:
        auth.user = args.user
    if args.password:
        auth.password = args.password
    if args.enable_password:
        auth.enable_password = args.enable_password
    if args.noenable:
        auth.noenable = True
    if args.autoenable:
        auth.autoenable = True

    # Create session
    session = LoginSession(
        hostname=args.hostname,
        timeout=args.timeout,
        debug=args.debug,
    )
    session.configure_auth(auth)

    try:
        if not session.connect():
            print(f"Failed to connect to {args.hostname}", file=sys.stderr)
            return 1

        # Execute commands if specified
        if args.commands:
            cmds = args.commands.split(";")
            for cmd in cmds:
                cmd = cmd.strip()
                if cmd:
                    output = session.run_command(cmd)
                    if output:
                        print(output)

        elif args.script:
            with open(args.script) as f:
                for line in f:
                    cmd = line.strip()
                    if cmd and not cmd.startswith("#"):
                        output = session.run_command(cmd)
                        if output:
                            print(output)
        else:
            # Interactive mode - use expect session
            from rancid_ng.login.expect import CloginExpect

            print(f"Connected to {args.hostname}")
            print("Type 'exit' or Ctrl-D to disconnect")

            while True:
                try:
                    cmd = input("> ")
                    if cmd.lower() in ("exit", "quit", "logout"):
                        break
                    output = session.run_command(cmd)
                    if output:
                        print(output)
                except (EOFError, KeyboardInterrupt):
                    break

        return 0

    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
