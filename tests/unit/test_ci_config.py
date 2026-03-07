from pathlib import Path


CI_CONFIG = Path(".github/workflows/ci.yml")


def test_ci_config_exists():
    """CI設定ファイルが存在すること"""
    assert CI_CONFIG.exists(), ".github/workflows/ci.yml must exist"


def test_ci_config_is_valid_yaml_structure():
    """CI設定ファイルが基本的なYAML構造を持つこと（pyyaml不要、文字列パターンで検証）"""
    content = CI_CONFIG.read_text()
    # YAML の基本構造: "name:" と "jobs:" が存在する
    assert "name:" in content
    assert "jobs:" in content


def test_ci_has_test_job():
    """pytest ジョブが含まれていること"""
    content = CI_CONFIG.read_text()
    assert "pytest" in content


def test_ci_has_lint_job():
    """ruff ジョブが含まれていること"""
    content = CI_CONFIG.read_text()
    assert "ruff" in content


def test_ci_has_type_check_job():
    """mypy ジョブが含まれていること"""
    content = CI_CONFIG.read_text()
    assert "mypy" in content


def test_ci_triggers_on_push_and_pr():
    """push と pull_request でトリガーされること（文字列パターンマッチで検証）"""
    content = CI_CONFIG.read_text()
    assert "push:" in content
    assert "pull_request:" in content
