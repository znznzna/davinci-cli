# HANDOVER.md — davinci-cli

**日付:** 2026-03-07
**セッション:** 初回（プロジェクト立ち上げ・設計・計画策定）

---

## 1. 今回やったこと

- davinci-cli プロジェクトの実装計画ドキュメント3つ（Phase 1-3）を精査・改善
- Opus サブエージェントで既存計画の設計レビュー → Critical 5件 + Important 9件の問題を発見
- 修正済み実装計画を3ファイル作成（`docs/plans/` 配下）
- Codex レビューを3回実施し、全指摘を解消
- CLAUDE.md を作成
- git リポジトリを初期化

**達成:** 実装計画の策定・レビュー完了。コードの実装はまだ未着手。

---

## 2. 決定事項

| 項目 | 決定内容 |
|------|----------|
| エントリポイント名 | `dr`（Phase 1 から統一） |
| 例外クラス名 | `DavinciEnvironmentError`（Python 組み込み衝突回避） |
| exit_code 正規定義 | `exceptions.py` に集約（1-5） |
| validate_path | `core/validation.py` に統合。`Path.resolve()` + `..` 拒絶のみ。許可ディレクトリリスト不要 |
| Resolve 接続モジュール | `davinci_cli.core.connection`（`resolve_bridge` は使わない） |
| dry_run デフォルト | CLI: `False`、MCP: `True` |
| --fields の位置づけ | 表示フィルタ。schema は常にフルレスポンス型を定義 |
| deliver --dry-run | 必須ではない（他コマンドと一貫性優先） |
| Linux サポート | 不要 |
| 設定ファイル | 不要（環境変数 + CLI フラグで完結） |
| CI/CD | GitHub Actions（pytest + ruff + mypy） |
| ロギング | `core/logging.py` で `--verbose`/`--debug` 対応 |
| アーキテクチャ | 現行の `_impl` 純粋関数パターンを維持。Service Layer は v0.2 以降 |
| コマンド登録方式 | 段階的登録（各コマンド実装時に cli.py へ追加） |
| グローバルエラーハンドリング | `DavinciCLIGroup.invoke()` オーバーライド + Exception フォールバック |

---

## 3. 捨てた選択肢と理由

| 選択肢 | 理由 |
|--------|------|
| Service Layer（案2） | 計画の大幅書き直しが必要。まず動くものを作ることを優先し v0.2 以降に検討 |
| Repository Pattern（案3） | 中間案だが _impl 関数シグネチャが全て変わるため、現段階では過剰 |
| validate_path の許可ディレクトリリスト | DaVinci Resolve のメディアは外付け SSD/NAS 等の任意パスに存在するため、制限すると正当なワークフローが壊れる |
| deliver --dry-run 必須化 | 人間が使うとき毎回 `--no-dry-run` が必要になり不便。エージェント安全性は MCP 側の `dry_run=True` デフォルトで担保 |
| 設定ファイル (`~/.davinci-cli/config.toml`) | エージェントは毎回 CLI フラグで明示指定するため永続設定不要。デバッグの複雑化要因 |
| Pydantic モデルの全フィールド Optional 化 | `--fields` 対応のためだが、schema の意味が薄れる。表示フィルタとして扱う方が自然 |

---

## 4. ハマりどころ

- **codex exec が git リポジトリ外で動かない**: `Not inside a trusted directory` エラー → `git init` で解決
- **Schema 不整合が3回のレビューサイクルで段階的に発見された**: 1回目は構造的問題、2回目は型の使い回し、3回目は `--fields` との相互作用。Schema 設計は _impl 戻り値と1:1対応を徹底すべき
- **Opus の修正が一部不完全**: 指摘を渡しても広範囲の修正は漏れが出る。Codex での再検証は必須

---

## 5. 学び

- 実装計画レベルでの Opus 精査 → Codex レビューの2段階チェックが有効
- Schema 登録は `_impl` 関数の戻り値と厳密に1:1対応させないと、MCP/エージェント駆動で破綻する
- 計画ドキュメント間の横断的整合性（モジュール参照、例外名、exit_code）は最初に統一ルールを決めて全 Phase に反映すべき
- `--fields` のような表示層の機能は型システム（schema）とは分離して設計すべき

---

## 6. 次にやること

1. **Phase 1 実装**: `docs/plans/2026-03-07-davinci-cli-phase1-revised.md` を `superpowers:executing-plans` で実行（Task 1-10）
2. **Phase 2 実装**: `docs/plans/2026-03-07-davinci-cli-phase2-revised.md`（Task 11-17）
3. **Phase 3 実装**: `docs/plans/2026-03-07-davinci-cli-phase3-revised.md`（Task 18-23）

各 Phase は別セッションで実行可能。Phase 1 から順番に。

---

## 7. 関連ファイル

### 新規作成
- `CLAUDE.md` — Claude Code 用プロジェクト説明
- `HANDOVER.md` — このファイル
- `docs/plans/2026-03-07-davinci-cli-phase1-revised.md` — Phase 1 実装計画（修正版）
- `docs/plans/2026-03-07-davinci-cli-phase2-revised.md` — Phase 2 実装計画（修正版）
- `docs/plans/2026-03-07-davinci-cli-phase3-revised.md` — Phase 3 実装計画（修正版）

### 既存（参考用・旧版）
- `2026-03-07-davinci-cli-phase1.md` — Phase 1 旧計画
- `2026-03-07-davinci-cli-commands-a.md` — Phase 2 旧計画
- `2026-03-07-davinci-cli-commands-b.md` — Phase 3 旧計画
