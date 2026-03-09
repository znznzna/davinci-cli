#!/usr/bin/env python3
"""Check that all version files match pyproject.toml."""

import json
import re
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

ROOT = Path(__file__).resolve().parent.parent


def read_pyproject_version() -> str:
    with open(ROOT / "pyproject.toml", "rb") as f:
        data = tomllib.load(f)
    return data["project"]["version"]


def read_init_py_version() -> str | None:
    path = ROOT / "src" / "davinci_cli" / "__init__.py"
    m = re.search(r'__version__\s*=\s*"([^"]*)"', path.read_text())
    return m.group(1) if m else None


def read_skill_md_version() -> str | None:
    path = ROOT / "plugin" / "skills" / "davinci-cli" / "SKILL.md"
    m = re.search(r"^version:\s*(.+)$", path.read_text(), re.MULTILINE)
    return m.group(1).strip() if m else None


def read_json_version(path: Path) -> str | None:
    data = json.loads(path.read_text())
    return data.get("version")


def read_marketplace_plugin_version() -> str | None:
    path = ROOT / ".claude-plugin" / "marketplace.json"
    data = json.loads(path.read_text())
    plugins = data.get("plugins", [])
    return plugins[0].get("version") if plugins else None


def main() -> int:
    source = read_pyproject_version()
    checks = {
        "src/davinci_cli/__init__.py": read_init_py_version(),
        "plugin/skills/davinci-cli/SKILL.md": read_skill_md_version(),
        "plugin/.claude-plugin/plugin.json": read_json_version(
            ROOT / "plugin" / ".claude-plugin" / "plugin.json"
        ),
        ".claude-plugin/marketplace.json": read_marketplace_plugin_version(),
    }

    mismatches = []
    for file, version in checks.items():
        if version != source:
            mismatches.append((file, version))

    if mismatches:
        print(f"Version mismatch! Source (pyproject.toml): {source}")
        for file, version in mismatches:
            print(f"  {file}: {version or 'NOT FOUND'}")
        print("\nRun: python scripts/sync_version.py")
        return 1

    print(f"All versions in sync: {source}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
