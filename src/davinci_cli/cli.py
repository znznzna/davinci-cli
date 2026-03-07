"""CLIエントリポイント。エントリポイント名は 'dr' に統一。"""

import click


@click.group()
@click.version_option()
def dr() -> None:
    """DaVinci Resolve CLI — agent-first."""
