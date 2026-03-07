import json

import pytest
from click.testing import CliRunner
from pydantic import BaseModel

from davinci_cli.cli import dr
from davinci_cli.commands.schema import schema_list_impl, schema_show_impl
from davinci_cli.core.exceptions import SchemaNotFoundError
from davinci_cli.schema_registry import SCHEMA_REGISTRY, register_schema


class _TestOutput(BaseModel):
    name: str
    value: int


class _TestInput(BaseModel):
    name: str


@pytest.fixture(autouse=True)
def _register_test_schemas():
    """テスト用スキーマを登録し、テスト後にクリアする"""
    original = dict(SCHEMA_REGISTRY)
    register_schema("test.command", output_model=_TestOutput)
    register_schema("test.with_input", output_model=_TestOutput, input_model=_TestInput)
    yield
    SCHEMA_REGISTRY.clear()
    SCHEMA_REGISTRY.update(original)


class TestSchemaShowImpl:
    def test_returns_output_schema(self):
        result = schema_show_impl("test.command")
        assert result["command"] == "test.command"
        assert "output_schema" in result
        assert result["output_schema"]["type"] == "object"

    def test_returns_input_schema_when_present(self):
        result = schema_show_impl("test.with_input")
        assert "input_schema" in result
        assert "name" in result["input_schema"]["properties"]

    def test_unknown_command_raises_schema_not_found(self):
        with pytest.raises(SchemaNotFoundError):
            schema_show_impl("nonexistent.command")


class TestSchemaListImpl:
    def test_lists_registered_commands(self):
        result = schema_list_impl()
        commands = [r["command"] for r in result]
        assert "test.command" in commands
        assert "test.with_input" in commands


class TestSchemaCLI:
    def test_dr_schema_show(self):
        result = CliRunner().invoke(dr, ["schema", "show", "test.command"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "output_schema" in data

    def test_dr_schema_list(self):
        result = CliRunner().invoke(dr, ["schema", "list"])
        assert result.exit_code == 0

    def test_dr_schema_show_not_found(self):
        result = CliRunner().invoke(dr, ["schema", "show", "nonexistent"])
        assert result.exit_code == 3
