"""davinci-cli ロギング設定。

CLI の --verbose / --debug フラグに応じてログレベルを設定する。
ログは stderr に出力する（stdout は JSON 出力専用）。

使い方:
  from davinci_cli.core.logging import setup_logging, get_logger

  # CLI エントリポイントで1度だけ呼ぶ
  setup_logging(verbose=ctx.obj.get("verbose"), debug=ctx.obj.get("debug"))

  # 各モジュールで
  logger = get_logger(__name__)
  logger.info("Processing project: %s", name)
"""

from __future__ import annotations

import logging
import sys

# ルートロガー名
_ROOT_LOGGER_NAME = "davinci_cli"

# ログフォーマット
_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_LOG_FORMAT_DEBUG = "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s"


def setup_logging(verbose: bool = False, debug: bool = False) -> None:
    """ログレベルとフォーマットを設定する。

    Args:
        verbose: True で INFO レベル
        debug: True で DEBUG レベル（verbose より優先）
    """
    logger = logging.getLogger(_ROOT_LOGGER_NAME)

    # 既存ハンドラをクリア（多重呼び出し対策）
    logger.handlers.clear()

    if debug:
        level = logging.DEBUG
        fmt = _LOG_FORMAT_DEBUG
    elif verbose:
        level = logging.INFO
        fmt = _LOG_FORMAT
    else:
        level = logging.WARNING
        fmt = _LOG_FORMAT

    logger.setLevel(level)

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(fmt))

    logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """指定名のロガーを返す。

    名前は 'davinci_cli.core.connection' のようにドット区切りで指定する。
    """
    return logging.getLogger(name)
