"""davinci-cli 例外階層。

全例外は DavinciCLIError を継承し、exit_code を持つ。
エージェントはこの exit_code を使ってエラー種別を判別できる。

exit_code 体系（正規定義）:
  1: ResolveNotRunningError — DaVinci Resolve が起動していない
  2: ProjectNotOpenError / ProjectNotFoundError — プロジェクト未オープン/未発見
  3: ValidationError — 入力バリデーションエラー
  4: DavinciEnvironmentError — 環境変数・パス設定エラー
  5: EditionError — エディション不一致

cli.py はこの定義を参照する。独自に exit_code を再定義しない。
"""
from __future__ import annotations


class DavinciCLIError(Exception):
    """基底例外。"""

    exit_code: int = 1

    def __init__(self, message: str = "") -> None:
        self.message = message
        super().__init__(message)

    def __str__(self) -> str:
        return self.message


class ResolveNotRunningError(DavinciCLIError):
    """DaVinci Resolve が起動していない。"""

    exit_code = 1

    def __init__(self) -> None:
        super().__init__(
            "DaVinci Resolve is not running. Please launch DaVinci Resolve first."
        )


class ProjectNotOpenError(DavinciCLIError):
    """プロジェクトが開かれていない。"""

    exit_code = 2

    def __init__(self) -> None:
        super().__init__("No project is currently open in DaVinci Resolve.")


class ProjectNotFoundError(DavinciCLIError):
    """指定されたプロジェクトが見つからない。"""

    exit_code = 2

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Project not found: {name}")


class ValidationError(DavinciCLIError):
    """入力値バリデーションエラー。"""

    exit_code = 3

    def __init__(self, field: str, reason: str) -> None:
        self.field = field
        super().__init__(f"Validation failed for '{field}': {reason}")


class DavinciEnvironmentError(DavinciCLIError):
    """環境変数・パス設定エラー。

    Python 組み込みの EnvironmentError (= OSError) との衝突を避けるため、
    'Davinci' プレフィックス付きの名前にしている。
    """

    exit_code = 4

    def __init__(self, detail: str) -> None:
        super().__init__(f"Environment configuration error: {detail}")


class EditionError(DavinciCLIError):
    """DaVinci Resolve エディション不一致エラー。"""

    exit_code = 5

    def __init__(self, required: str, actual: str) -> None:
        self.required = required
        self.actual = actual
        super().__init__(
            f"This feature requires DaVinci Resolve {required}, "
            f"but {actual} edition is running."
        )
