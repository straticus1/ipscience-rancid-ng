"""rancid-cvs - Repository Initialization Script for RANCID-NG"""
from rancid_ng.cli.main import init as main_init

def main():
    """Entry point for rancid-cvs."""
    import click
    from rancid_ng.cli.main import main as cli_main
    ctx = click.Context(cli_main)
    ctx.invoke(main_init)

if __name__ == "__main__":
    main()
