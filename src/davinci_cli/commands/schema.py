import click


@click.group()
def schema() -> None:
    """Runtime schema resolution."""
