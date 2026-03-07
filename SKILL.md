---
name: davinci-cli
version: 1.0.0
description: DaVinci Resolve CLI / MCP — agent-first interface
---

# davinci-cli Skill

DaVinci Resolve をコマンドラインから操作する CLI / MCP サーバー。

## AGENT RULES

1. **破壊的操作は必ず `--dry-run` で事前確認** してからユーザーに提示し、承認を得て実行する
2. **`--fields` で出力フィールドを絞る** — コンテキストウィンドウの消費を最小化する
3. **`--json` で構造化入力** — エージェントからの入力は `--json '{"key": "value"}'` 形式を推奨
4. **エラーは JSON で返る** — `{"error": "...", "error_type": "...", "exit_code": N}`

## 使用パターン

### 接続確認パターン

```bash
dr system ping
dr system info
```

### 読み取りパターン

```bash
dr project list --fields name
dr timeline list --fields name,fps
dr clip list --fields index,name
dr media list --fields clip_name
dr schema list
dr schema show project.open
```

### 書き込みパターン（--dry-run 必須）

```bash
# Step 1: dry-run で確認
dr project open "MyProject" --dry-run
# Step 2: ユーザー承認後に実行
dr project open "MyProject"
```

## コマンド一覧

### dr system
- `dr system ping` — 接続確認
- `dr system version` — バージョン情報
- `dr system edition` — エディション（Free/Studio）
- `dr system info` — 総合情報

### dr schema
- `dr schema list` — 登録コマンド一覧
- `dr schema show <command>` — コマンドの JSON Schema

### dr project
- `dr project list [--fields]` — プロジェクト一覧
- `dr project info [--fields]` — 現在のプロジェクト情報
- `dr project open <name> [--dry-run]` — プロジェクトを開く
- `dr project close [--dry-run]` — プロジェクトを閉じる
- `dr project create --name <name> [--dry-run]` — 新規作成
- `dr project delete <name> [--dry-run]` — 削除
- `dr project save` — 保存
- `dr project settings get <key>` — 設定取得
- `dr project settings set <key> <value> [--dry-run]` — 設定変更

### dr timeline
- `dr timeline list [--fields]` — タイムライン一覧
- `dr timeline current [--fields]` — 現在のタイムライン
- `dr timeline switch <name> [--dry-run]` — 切り替え
- `dr timeline create --name <name> [--dry-run]` — 新規作成
- `dr timeline delete <name> [--dry-run]` — 削除
- `dr timeline export --json '...' [--dry-run]` — エクスポート
- `dr timeline marker list` — マーカー一覧
- `dr timeline marker add --json '...' [--dry-run]` — マーカー追加
- `dr timeline marker delete <frame_id> [--dry-run]` — マーカー削除

### dr clip
- `dr clip list [--fields] [--timeline]` — クリップ一覧
- `dr clip info <index> [--fields]` — クリップ詳細
- `dr clip select <index>` — クリップ選択
- `dr clip property get <index> <key>` — プロパティ取得
- `dr clip property set <index> <key> <value> [--dry-run]` — プロパティ設定

### dr color
- `dr color apply-lut <clip_index> <lut_path> [--dry-run]` — LUT 適用
- `dr color reset <clip_index> [--dry-run]` — グレードリセット
- `dr color copy-grade --from <index>` — グレードコピー
- `dr color paste-grade --to <index> [--dry-run]` — グレードペースト
- `dr color node list <clip_index>` — ノード一覧
- `dr color node add <clip_index> [--dry-run]` — ノード追加
- `dr color node delete <clip_index> <node_index> [--dry-run]` — ノード削除
- `dr color still list` — スチル一覧
- `dr color still grab <clip_index> [--dry-run]` — スチル取得
- `dr color still apply <clip_index> <still_index> [--dry-run]` — スチル適用

### dr media
- `dr media list [--folder] [--fields]` — メディア一覧
- `dr media import <paths...>` — メディアインポート
- `dr media folder list` — フォルダ一覧
- `dr media folder create <name>` — フォルダ作成
- `dr media folder delete <name> [--dry-run]` — フォルダ削除

### dr deliver
- `dr deliver preset list` — プリセット一覧
- `dr deliver preset load <name>` — プリセット読み込み
- `dr deliver add-job --json '...' [--dry-run]` — ジョブ追加
- `dr deliver list-jobs [--fields]` — ジョブ一覧
- `dr deliver start [--job-ids] [--dry-run]` — レンダー開始（**--dry-run 必須**）
- `dr deliver stop` — レンダー停止
- `dr deliver status` — 進捗確認

## MCP サーバー

```bash
dr-mcp
```

MCP サーバーでは全ての破壊的操作の `dry_run` デフォルトが `True`。
エージェントは明示的に `dry_run=False` を指定しない限り、事前確認モードで動作する。

## Exit Codes

| Code | 意味 |
|------|------|
| 1 | DaVinci Resolve 未起動 |
| 2 | プロジェクト未オープン |
| 3 | バリデーションエラー |
| 4 | 環境設定エラー |
| 5 | エディション不一致 |
