import json

import click
from click.testing import CliRunner

from davinci_cli.decorators import dry_run_option, fields_option, json_input_option


@click.command()
@json_input_option
@click.pass_context
def cmd_with_json(ctx, json_input):
    """テスト用コマンド: --json オプション"""
    if json_input:
        click.echo(json.dumps({"received": json_input}))
    else:
        click.echo(json.dumps({"received": None}))


@click.command()
@fields_option
@click.pass_context
def cmd_with_fields(ctx, fields):
    """テスト用コマンド: --fields オプション"""
    click.echo(json.dumps({"fields": fields}))


@click.command()
@dry_run_option
@click.pass_context
def cmd_with_dry_run(ctx, dry_run):
    """テスト用コマンド: --dry-run オプション"""
    click.echo(json.dumps({"dry_run": dry_run}))


class TestJsonInputOption:
    def test_json_input_provided(self):
        runner = CliRunner()
        result = runner.invoke(cmd_with_json, ["--json", '{"name": "Test"}'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["received"] == {"name": "Test"}

    def test_json_input_not_provided(self):
        runner = CliRunner()
        result = runner.invoke(cmd_with_json, [])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["received"] is None

    def test_json_input_invalid_json(self):
        runner = CliRunner()
        result = runner.invoke(cmd_with_json, ["--json", "not-json"])
        assert result.exit_code != 0


class TestFieldsOption:
    def test_fields_provided(self):
        runner = CliRunner()
        result = runner.invoke(cmd_with_fields, ["--fields", "name,id,fps"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["fields"] == ["name", "id", "fps"]

    def test_fields_not_provided(self):
        runner = CliRunner()
        result = runner.invoke(cmd_with_fields, [])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["fields"] is None


class TestDryRunOption:
    def test_dry_run_flag(self):
        runner = CliRunner()
        result = runner.invoke(cmd_with_dry_run, ["--dry-run"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True

    def test_dry_run_default_false(self):
        runner = CliRunner()
        result = runner.invoke(cmd_with_dry_run, [])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is False
