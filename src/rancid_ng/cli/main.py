"""
RANCID-NG Main CLI Entry Point

Provides the main 'rancid-ng' command with subcommands for
various operations.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from rancid_ng import __version__


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="rancid-ng")
@click.option("--debug", "-d", is_flag=True, help="Enable debug output")
@click.pass_context
def main(ctx: click.Context, debug: bool) -> None:
    """
    RANCID-NG: Really Awesome New Cisco confIg Differ - Next Generation

    A Python 3 rewrite of the classic RANCID network configuration
    backup tool.

    Brought to you by ipscience.io, a service from After Dark Systems, LLC
    """
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command()
@click.argument("hostname")
@click.option("-t", "--type", "devtype", required=True, help="Device type")
@click.option("-f", "--file", "input_file", type=click.Path(exists=True),
              help="Read from file instead of connecting")
@click.option("-o", "--output", "output_file", type=click.Path(),
              help="Output file (default: stdout)")
@click.option("-C", "--print-command", is_flag=True,
              help="Print the login command instead of running")
@click.option("-l", "--log", is_flag=True, help="Enable logging")
@click.pass_context
def collect(
    ctx: click.Context,
    hostname: str,
    devtype: str,
    input_file: str | None,
    output_file: str | None,
    print_command: bool,
    log: bool,
) -> None:
    """
    Collect configuration from a device.

    HOSTNAME is the target device hostname or IP address.
    """
    from rancid_ng.core.rancid import Rancid

    debug = ctx.obj.get("debug", False)

    # Open output file if specified
    output = None
    if output_file:
        output = open(output_file, "w")

    try:
        rancid = Rancid(
            hostname=hostname,
            devtype=devtype,
            output=output or sys.stdout,
            debug=debug,
            log=log,
            file_mode=bool(input_file),
        )

        if print_command:
            rancid.print_command_line()
            return

        result = rancid.collect()
        sys.exit(result)

    finally:
        if output:
            output.close()


@main.command()
@click.pass_context
def list_types(ctx: click.Context) -> None:
    """List all supported device types."""
    from rancid_ng.devices import list_device_modules
    from rancid_ng.config.types import load_default_types

    click.echo("Registered device modules:")
    for name in list_device_modules():
        click.echo(f"  {name}")

    click.echo("\nDevice types from configuration:")
    registry = load_default_types()
    for devtype in sorted(registry.list_types()):
        config = registry.get_type(devtype)
        alias_str = f" -> {config.alias}" if config.alias else ""
        click.echo(f"  {devtype}{alias_str}")


@main.command()
@click.argument("hostname")
@click.option("-c", "--command", "commands", multiple=True,
              help="Command(s) to execute")
@click.option("-t", "--type", "devtype", help="Device type")
@click.option("-x", "--execute", "script", help="Execute commands from file")
@click.option("--enable", "-e", is_flag=True, help="Enter enable mode")
@click.option("--noenable", is_flag=True, help="Don't enter enable mode")
@click.pass_context
def login(
    ctx: click.Context,
    hostname: str,
    commands: tuple[str, ...],
    devtype: str | None,
    script: str | None,
    enable: bool,
    noenable: bool,
) -> None:
    """
    Login to a device interactively or run commands.

    HOSTNAME is the target device hostname or IP address.
    """
    from rancid_ng.login.session import LoginSession
    from rancid_ng.config.cloginrc import load_cloginrc

    debug = ctx.obj.get("debug", False)

    # Load authentication
    cloginrc = load_cloginrc()
    auth = cloginrc.get_auth(hostname)

    if noenable:
        auth.noenable = True

    # Create session
    session = LoginSession(
        hostname=hostname,
        timeout=90,
        debug=debug,
    )
    session.configure_auth(auth)

    try:
        if not session.connect():
            click.echo(f"Failed to connect to {hostname}", err=True)
            sys.exit(1)

        # Run commands if specified
        if commands or script:
            cmd_list = list(commands)

            # Load commands from file
            if script:
                with open(script) as f:
                    cmd_list.extend(line.strip() for line in f if line.strip())

            # Execute commands
            for cmd in cmd_list:
                output = session.run_command(cmd)
                if output:
                    click.echo(output)
        else:
            # Interactive mode
            click.echo(f"Connected to {hostname}")
            click.echo("Type 'exit' or Ctrl-D to disconnect")

            while True:
                try:
                    cmd = click.prompt("", prompt_suffix="> ")
                    if cmd.lower() in ("exit", "quit", "logout"):
                        break
                    output = session.run_command(cmd)
                    if output:
                        click.echo(output)
                except (EOFError, KeyboardInterrupt):
                    break

    finally:
        session.close()


@main.command()
@click.option("-g", "--group", "groups", multiple=True,
              help="Group(s) to process")
@click.option("-m", "--mail", "mail_to", help="Send diffs to this address")
@click.option("-r", "--max-rounds", type=int, default=4,
              help="Maximum retry rounds")
@click.pass_context
def run(
    ctx: click.Context,
    groups: tuple[str, ...],
    mail_to: str | None,
    max_rounds: int,
) -> None:
    """
    Run configuration collection for device groups.

    This is the main batch collection command.
    """
    click.echo("rancid-run: Not yet fully implemented")
    click.echo("Use 'rancid-ng collect' for individual device collection")
    # TODO: Implement full rancid-run functionality


@main.command()
@click.option("-g", "--group", "groups", multiple=True,
              help="Group(s) to initialize")
@click.pass_context
def init(ctx: click.Context, groups: tuple[str, ...]) -> None:
    """
    Initialize RANCID repository for groups.

    Creates the directory structure and version control repository.
    """
    from rancid_ng.config.rancid_conf import load_rancid_conf

    config = load_rancid_conf()

    if not groups:
        groups = tuple(config.list_of_groups)

    if not groups:
        click.echo("No groups specified. Use -g or set LIST_OF_GROUPS in rancid.conf")
        sys.exit(1)

    for group in groups:
        click.echo(f"Initializing group: {group}")
        # TODO: Implement repository initialization


if __name__ == "__main__":
    main()
