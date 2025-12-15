"""
RANCID CLI Entry Point

Direct replacement for the 'rancid' command.
"""

from __future__ import annotations

import sys
from argparse import ArgumentParser

from rancid_ng import __version__


def main() -> int:
    """Main entry point for rancid command."""
    parser = ArgumentParser(
        description="RANCID-NG: Configuration collection for network devices",
        prog="rancid",
    )
    parser.add_argument("-V", "--version", action="version",
                        version=f"rancid-ng {__version__}")
    parser.add_argument("-d", "--debug", action="store_true",
                        help="Enable debug output")
    parser.add_argument("-l", "--log", action="store_true",
                        help="Enable logging")
    parser.add_argument("-f", "--file", dest="input_file",
                        help="Read from file instead of connecting")
    parser.add_argument("-t", "--type", dest="devtype", required=True,
                        help="Device type")
    parser.add_argument("-C", action="store_true", dest="print_cmd",
                        help="Print login command")
    parser.add_argument("hostname", nargs="?",
                        help="Target device hostname")

    args = parser.parse_args()

    if not args.hostname and not args.print_cmd:
        parser.error("hostname is required")

    from rancid_ng.core.rancid import Rancid

    rancid = Rancid(
        hostname=args.hostname or "",
        devtype=args.devtype,
        debug=args.debug,
        log=args.log,
        file_mode=bool(args.input_file),
    )

    if args.print_cmd:
        rancid.print_command_line()
        return 0

    return rancid.collect()


if __name__ == "__main__":
    sys.exit(main())
