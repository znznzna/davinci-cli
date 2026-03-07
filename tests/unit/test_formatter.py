import json
from unittest.mock import patch

from davinci_cli.output.formatter import (
    filter_fields,
    is_tty,
    output,
)


class TestIsTty:
    def test_returns_false_when_not_tty(self):
        # pytest実行中はTTYではない
        assert is_tty() is False

    def test_returns_true_when_tty(self):
        with patch("sys.stdout") as mock_stdout:
            mock_stdout.isatty.return_value = True
            assert is_tty() is True


class TestFilterFields:
    def test_filters_dict(self):
        data = {"name": "MyProject", "fps": 24, "secret": "hidden"}
        result = filter_fields(data, ["name", "fps"])
        assert result == {"name": "MyProject", "fps": 24}
        assert "secret" not in result

    def test_filters_list_of_dicts(self):
        data = [
            {"id": 1, "name": "A", "extra": "x"},
            {"id": 2, "name": "B", "extra": "y"},
        ]
        result = filter_fields(data, ["id", "name"])
        assert result == [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]

    def test_missing_fields_skipped(self):
        data = {"name": "MyProject"}
        result = filter_fields(data, ["name", "nonexistent"])
        assert result == {"name": "MyProject"}
        assert "nonexistent" not in result

    def test_none_fields_returns_original(self):
        data = {"name": "MyProject", "fps": 24}
        result = filter_fields(data, None)
        assert result == data


class TestOutput:
    def test_dict_outputs_json_line(self, capsys):
        with patch("davinci_cli.output.formatter.is_tty", return_value=False):
            output({"name": "MyProject", "fps": 24})
        captured = capsys.readouterr()
        parsed = json.loads(captured.out.strip())
        assert parsed == {"name": "MyProject", "fps": 24}

    def test_list_outputs_ndjson(self, capsys):
        data = [{"id": 1}, {"id": 2}]
        with patch("davinci_cli.output.formatter.is_tty", return_value=False):
            output(data)
        captured = capsys.readouterr()
        lines = [line for line in captured.out.strip().split("\n") if line]
        assert len(lines) == 2
        assert json.loads(lines[0]) == {"id": 1}
        assert json.loads(lines[1]) == {"id": 2}

    def test_fields_filtering_applied(self, capsys):
        with patch("davinci_cli.output.formatter.is_tty", return_value=False):
            output(
                {"name": "MyProject", "fps": 24, "secret": "hidden"},
                fields=["name"],
            )
        captured = capsys.readouterr()
        parsed = json.loads(captured.out.strip())
        assert "name" in parsed
        assert "secret" not in parsed
        assert "fps" not in parsed

    def test_pretty_mode_tty(self, capsys):
        with patch("davinci_cli.output.formatter.is_tty", return_value=True):
            output({"name": "MyProject"}, pretty=True)
        captured = capsys.readouterr()
        assert "MyProject" in captured.out

    def test_non_tty_ignores_pretty_flag(self, capsys):
        with patch("davinci_cli.output.formatter.is_tty", return_value=False):
            output({"name": "MyProject"}, pretty=True)
        captured = capsys.readouterr()
        parsed = json.loads(captured.out.strip())
        assert parsed["name"] == "MyProject"
