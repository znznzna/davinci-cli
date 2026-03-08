from pathlib import Path

SKILL_MD = Path("SKILL.md")


def test_skill_md_exists():
    assert SKILL_MD.exists(), "SKILL.md must exist in project root"


def test_skill_md_has_frontmatter():
    content = SKILL_MD.read_text(encoding="utf-8")
    assert content.startswith("---"), "Must have YAML frontmatter"
    assert "name: davinci-cli" in content
    assert "version: 1.0.0" in content


def test_skill_md_has_agent_rules():
    content = SKILL_MD.read_text(encoding="utf-8")
    assert "Agent Quick Contract" in content
    assert "--dry-run" in content


def test_skill_md_has_all_command_groups():
    content = SKILL_MD.read_text(encoding="utf-8")
    for group in [
        "dr system",
        "dr schema",
        "dr project",
        "dr timeline",
        "dr clip",
        "dr color",
        "dr media",
        "dr deliver",
    ]:
        assert group in content, f"Missing command group: {group}"


def test_skill_md_has_usage_patterns():
    content = SKILL_MD.read_text(encoding="utf-8")
    assert "Workflow" in content or "Pattern" in content


def test_skill_md_deliver_has_mandatory_dry_run():
    content = SKILL_MD.read_text(encoding="utf-8")
    deliver_section_start = content.find("dr deliver")
    assert deliver_section_start != -1
    deliver_section = content[deliver_section_start:]
    assert "必須" in deliver_section or "required" in deliver_section.lower()
