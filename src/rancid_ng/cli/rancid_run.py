"""rancid-run - Batch Collection Script for RANCID-NG"""
from rancid_ng.cli.main import run as main_run

def main():
    """Entry point for rancid-run."""
    import click
    from rancid_ng.cli.main import main as cli_main
    ctx = click.Context(cli_main)
    ctx.invoke(main_run)

if __name__ == "__main__":
    main()
