"""入力バリデーション — エージェントが生成する典型的な誤りを拒絶する。

validate_path() は Phase 3 の security.py に分離していた版を統合済み。
- Path.resolve() でシンボリックリンクを解決
- allowed_extensions で拡張子チェック
- パストラバーサル検出（URLデコード後も検査）

security.py は作らない。パス検証はこのモジュールに一元化する。

設計判断: validate_path() はパストラバーサル防止（Path.resolve() + '..' 拒絶）のみ。
許可ディレクトリリスト（allowed_directories）は意図的に実装しない。
理由: DaVinci Resolve のメディアファイルは外付け SSD、NAS、ネットワークドライブ等の
任意パスに存在するため、許可ディレクトリを事前に列挙することが不可能。
パストラバーサル防止のみで十分なセキュリティを確保できる。
"""
from __future__ import annotations

import re
import urllib.parse
from pathlib import Path

from davinci_cli.core.exceptions import ValidationError

# パストラバーサルパターン（デコード後に検査）
# パスセグメントとしての ".." のみ検出。"clip..v2.mov" 等の正当な名前は許可する。
_PATH_TRAVERSAL_RE = re.compile(r"(?:^|[/\\])\.\.[/\\]|(?:^|[/\\])\.\.$")

# リソースID禁止文字
_RESOURCE_ID_INVALID_CHARS_RE = re.compile(r"[?#%\s]")

# 許可するコントロール文字（タブ=0x09、LF=0x0A、CR=0x0D）
_ALLOWED_CONTROLS = {"\t", "\n", "\r"}


def validate_path(
    path: str | None,
    allowed_extensions: list[str] | None = None,
) -> Path:
    """ファイルパスを検証し、resolve() された Path オブジェクトを返す。

    - None または空文字を拒絶
    - パストラバーサル（../ など）を拒絶（URLデコード後も検査）
    - シンボリックリンクは resolve() で実体パスに解決
    - allowed_extensions 指定時は拡張子を検査（大文字小文字区別なし）

    Returns:
        Path: resolve() 済みの Path オブジェクト
    """
    if path is None or not isinstance(path, str):
        raise ValidationError(field="path", reason="must be a non-null string")
    if not path.strip():
        raise ValidationError(field="path", reason="empty path is not allowed")

    # URLデコードを最大2回施してから検査（ダブルエンコード対策）
    decoded = path
    for _ in range(2):
        decoded = urllib.parse.unquote(decoded)

    if _PATH_TRAVERSAL_RE.search(decoded):
        raise ValidationError(field="path", reason="path traversal detected")

    resolved = Path(path).resolve()

    # 拡張子チェック
    if allowed_extensions is not None:
        normalized_extensions = [ext.lower() for ext in allowed_extensions]
        if resolved.suffix.lower() not in normalized_extensions:
            raise ValidationError(
                field="path",
                reason=(
                    f"extension '{resolved.suffix}' not allowed. "
                    f"Allowed: {allowed_extensions}"
                ),
            )

    return resolved


def validate_resource_id(resource_id: str | None) -> str:
    """リソースIDを検証する。

    - None または空文字を拒絶
    - ?、#、%、空白を含む値を拒絶（クエリパラム混入・エンコードインジェクション対策）
    """
    if resource_id is None or not isinstance(resource_id, str):
        raise ValidationError(field="resource_id", reason="must be a non-null string")
    if not resource_id.strip():
        raise ValidationError(field="resource_id", reason="empty resource ID is not allowed")
    if _RESOURCE_ID_INVALID_CHARS_RE.search(resource_id):
        raise ValidationError(
            field="resource_id",
            reason="invalid character detected (?, #, %, or whitespace)",
        )
    return resource_id


def validate_string(value: str | None) -> str:
    """汎用文字列を検証する。

    - None または空文字を拒絶
    - 0x20未満のコントロール文字（タブ・LF・CR を除く）を拒絶
    """
    if value is None or not isinstance(value, str):
        raise ValidationError(field="value", reason="must be a non-null string")
    if not value:
        raise ValidationError(field="value", reason="empty string is not allowed")

    for ch in value:
        code = ord(ch)
        if code < 0x20 and ch not in _ALLOWED_CONTROLS:
            raise ValidationError(
                field="value",
                reason=f"control character detected (U+{code:04X})",
            )
    return value
