"""CLI エントリポイント。

エントリポイント名は 'dr' に統一。'cli' は使わない。
グローバルエラーハンドリングは DavinciCLIGroup.invoke() オーバーライドで実装。
各コマンドに手動でデコレータを付ける必要はない。

exit_code は core/exceptions.py の定義を参照する:
  1: ResolveNotRunningError
  2: ProjectNotOpenError / ProjectNotFoundError
  3: ValidationError
  4: DavinciEnvironmentError
  5: EditionError
"""

from __future__ import annotations

import json

import click

from davinci_cli.core.exceptions import DavinciCLIError
from davinci_cli.core.logging import setup_logging


class DavinciCLIGroup(click.Group):
    """カスタム Click Group — invoke オーバーライドでグローバルエラーハンドリング。"""

    def invoke(self, ctx: click.Context) -> None:
        try:
            super().invoke(ctx)
        except DavinciCLIError as exc:
            error_response = {
                "error": str(exc),
                "error_type": type(exc).__name__,
                "exit_code": exc.exit_code,
            }
            click.echo(json.dumps(error_response, ensure_ascii=False))
            ctx.exit(exc.exit_code)
        except click.exceptions.ClickException:
            raise  # Click の UsageError/BadParameter 等はそのまま伝播
        except Exception as exc:
            error_response = {
                "error": str(exc),
                "error_type": type(exc).__name__,
                "exit_code": 1,
            }
            click.echo(json.dumps(error_response, ensure_ascii=False))
            ctx.exit(1)


@click.group(cls=DavinciCLIGroup)
@click.version_option()
@click.option(
    "--pretty",
    is_flag=True,
    default=False,
    help="Human-readable output (TTY only)",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Enable verbose logging (INFO level)",
)
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    help="Enable debug logging (DEBUG level)",
)
@click.pass_context
def dr(ctx: click.Context, pretty: bool, verbose: bool, debug: bool) -> None:
    """DaVinci Resolve CLI — agent-first interface."""
    ctx.ensure_object(dict)
    ctx.obj["pretty"] = pretty
    ctx.obj["verbose"] = verbose
    ctx.obj["debug"] = debug

    setup_logging(verbose=verbose, debug=debug)


def _register_commands() -> None:
    from davinci_cli.commands import project, schema, system

    dr.add_command(system.system)
    dr.add_command(schema.schema)
    dr.add_command(project.project)


_register_commands()
