# IDOR-otaku (idotaku) 仕様書

## 概要

**idotaku** は、APIコールからIDの発生（Origin）と使用（Usage）を追跡し、IDOR（Insecure Direct Object Reference）脆弱性の候補を検出する脆弱性診断支援ツール。

mitmproxy のアドオンとして動作し、ブラウザとAPIサーバー間の通信を傍受・解析する。

---

## アーキテクチャ

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Browser   │────▶│  mitmproxy  │────▶│  API Server │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  idotaku    │
                    │  (tracker)  │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   Report    │
                    │   (JSON)    │
                    └─────────────┘
```

---

## プロジェクト構成

```
idotaku/
├── pyproject.toml          # パッケージ定義
├── idotaku.example.yaml    # 設定ファイルテンプレート
├── docs/
│   ├── QUICKSTART.md       # クイックスタートガイド
│   └── SPECIFICATION.md    # 本ドキュメント
└── src/
    └── idotaku/
        ├── __init__.py     # パッケージ初期化、バージョン定義
        ├── tracker.py      # コアロジック（mitmproxyアドオン）
        ├── config.py       # 設定ファイルローダー
        ├── cli.py          # CLIエントリーポイント
        ├── commands/       # サブコマンド群
        │   ├── run.py      # プロキシ起動
        │   ├── report.py   # サマリーレポート
        │   ├── chain.py    # パラメータチェーン検出
        │   ├── sequence.py # シーケンス表示
        │   ├── lifeline.py # IDライフライン表示
        │   └── interactive_cmd.py  # 対話モード
        ├── export/         # HTMLエクスポート
        │   ├── chain_exporter.py    # chainのHTML出力
        │   └── sequence_exporter.py # sequenceのHTML出力
        └── interactive.py  # 対話モードUI
```

---

## コアロジック（tracker.py）

### データ構造

```python
@dataclass
class IDOccurrence:
    """IDの出現1回分を表す"""
    id_value: str      # ID値 (例: "12345", "uuid-xxx-xxx")
    id_type: str       # 種別: "numeric" | "uuid" | "token"
    location: str      # 出現場所: "url_path" | "query" | "body" | "header"
    field_name: str    # フィールド名 (例: "user_id", "items[0].id")
    url: str           # リクエストURL
    method: str        # HTTPメソッド
    timestamp: str     # ISO8601形式タイムスタンプ
    direction: str     # "request" | "response"

@dataclass
class TrackedID:
    """追跡対象のID"""
    value: str                       # ID値
    id_type: str                     # 種別
    first_seen: str                  # 最初に発見した時刻
    origin: Optional[IDOccurrence]   # レスポンスで最初に出現した場所
    usages: list[IDOccurrence]       # リクエストで使用された場所のリスト

@dataclass
class FlowRecord:
    """リクエスト-レスポンスのペア（1回の通信）"""
    flow_id: str                     # mitmproxyが付与する一意ID
    url: str                         # リクエストURL
    method: str                      # HTTPメソッド
    timestamp: str                   # ISO8601形式タイムスタンプ
    request_ids: list[dict]          # リクエストで検出されたID一覧
    response_ids: list[dict]         # レスポンスで検出されたID一覧
```

### ID検出パターン

| 種別 | 正規表現 | 説明 |
|------|----------|------|
| uuid | `[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}` | UUID v1-v5 |
| numeric | `[1-9]\d{2,10}` | 3〜11桁の数値（100以上） |
| token | `[A-Za-z0-9_-]{20,}` | 20文字以上の英数字トークン |

### 除外パターン

| パターン | 説明 |
|----------|------|
| `^\d{10,13}$` | Unixタイムスタンプ（誤検出防止） |
| `^\d+\.\d+\.\d+$` | バージョン番号 |

### ID追跡ロジック

```
1. レスポンスでIDが出現
   → TrackedID.origin に記録（最初の1回のみ）
   → これが「IDの発生源」

2. リクエストでIDが出現
   → TrackedID.usages に追加
   → これが「IDの使用」

3. 終了時に分析
   → usages あり && origin なし = IDOR候補
   （リクエストで使われているが、レスポンスで発生していないID）
```

---

## IDOR検出ロジック

### 検出条件

```
potential_idor = ID where:
  - usages.length > 0  （リクエストで使われている）
  - origin == null     （レスポンスで一度も発生していない）
```

### 検出理由

1. **正規フロー**: ユーザーがAPIを使うと、まずレスポンスでIDを受け取り（origin）、それを使って後続リクエストを送る（usage）

2. **IDOR候補**: リクエストで使われているが、レスポンスで発生していないIDは以下の可能性がある：
   - ユーザーが手動でIDを推測・変更した
   - 別セッションで取得したIDを使っている
   - 列挙攻撃のターゲットになっている

---

## 設定ファイル（config.py）

### 検索順序

設定ファイルが明示的に指定されていない場合、以下の順序で自動検索される：

1. `idotaku.yaml`（カレントディレクトリ）
2. `idotaku.yml`
3. `.idotaku.yaml`
4. `.idotaku.yml`

### 設定ファイル形式

```yaml
idotaku:
  # 出力ファイルパス
  output: id_tracker_report.json

  # 数値IDの最小値（これより小さい数値は無視）
  min_numeric: 100

  # ID検出パターン（名前: 正規表現）
  patterns:
    uuid: "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    numeric: "[1-9]\\d{2,10}"
    token: "[A-Za-z0-9_-]{20,}"
    # カスタムパターン例：
    # order_id: "ORD-[A-Z]{2}-\\d{8}"

  # 除外パターン（ID候補から除外する正規表現）
  exclude_patterns:
    - "^\\d{10,13}$"      # Unix timestamp
    - "^\\d+\\.\\d+\\.\\d+$"  # Version numbers

  # ID抽出対象のContent-Type
  trackable_content_types:
    - application/json
    - application/x-www-form-urlencoded
    - text/html
    - text/plain

  # 追加で除外するヘッダー（デフォルトに追加）
  extra_ignore_headers: []
    # - x-internal-trace-id

  # ターゲットドメイン（ホワイトリスト、空なら全ドメイン）
  # target_domains:
  #   - api.example.com
  #   - "*.example.com"

  # 除外ドメイン（ブラックリスト、target_domainsより優先）
  # exclude_domains:
  #   - analytics.example.com
  #   - "*.tracking.com"

  # 除外拡張子（静的ファイル）
  # exclude_extensions:
  #   - ".css"
  #   - ".js"
  #   - ".png"
  #   - ".jpg"
```

### 設定項目一覧

| 項目 | 型 | デフォルト | 説明 |
|------|-----|------------|------|
| `output` | string | `id_tracker_report.json` | 出力ファイルパス |
| `min_numeric` | int | `100` | 数値IDの最小値 |
| `patterns` | dict | uuid/numeric/token | ID検出パターン |
| `exclude_patterns` | list | timestamp/version | 除外パターン |
| `trackable_content_types` | list | json/form/html/text | 解析対象Content-Type |
| `ignore_headers` | list | (デフォルトセット) | 除外ヘッダー（完全上書き） |
| `extra_ignore_headers` | list | `[]` | 追加除外ヘッダー |
| `target_domains` | list | `[]`（全ドメイン） | 追跡対象ドメイン（ホワイトリスト） |
| `exclude_domains` | list | `[]` | 除外ドメイン（ブラックリスト、優先） |
| `exclude_extensions` | list | 静的ファイル拡張子 | 除外する拡張子（.css, .js, .png 等） |

### デフォルト除外拡張子

静的ファイルを自動的に除外:
- **スタイル・スクリプト**: `.css`, `.js`, `.map`
- **画像**: `.png`, `.jpg`, `.jpeg`, `.gif`, `.svg`, `.ico`, `.webp`, `.bmp`
- **フォント**: `.woff`, `.woff2`, `.ttf`, `.eot`, `.otf`
- **メディア**: `.mp3`, `.mp4`, `.webm`, `.ogg`, `.wav`
- **その他**: `.pdf`, `.zip`, `.gz`

### デフォルト除外ヘッダー

- **メタデータ系**: `content-type`, `content-length`, `accept`, `user-agent`, `host`, `origin`, `referer`
- **キャッシュ系**: `cache-control`, `etag`, `last-modified`, `if-none-match`
- **CORS系**: `access-control-allow-*`
- **その他**: `date`, `server`, `sec-ch-ua`, `sec-fetch-*`

---

## 出力フォーマット（JSON）

### id_tracker_report.json

```json
{
  "summary": {
    "total_unique_ids": 15,
    "ids_with_origin": 10,
    "ids_with_usage": 8,
    "total_flows": 25
  },
  "flows": [
    {
      "flow_id": "abc123-def456",
      "method": "GET",
      "url": "https://api.example.com/users",
      "timestamp": "2024-01-01T12:00:00",
      "request_ids": [],
      "response_ids": [
        {"value": "12345", "type": "numeric", "location": "body", "field": "data.id"}
      ]
    }
  ],
  "tracked_ids": {
    "12345": {
      "type": "numeric",
      "first_seen": "2024-01-01T12:00:00",
      "origin": {
        "url": "https://api.example.com/users",
        "method": "GET",
        "location": "body",
        "field_name": "data.id",
        "timestamp": "2024-01-01T12:00:00"
      },
      "usage_count": 1,
      "usages": [...]
    }
  },
  "potential_idor": [
    {
      "id_value": "99999",
      "id_type": "numeric",
      "usages": [...],
      "reason": "ID used in request but never seen in response"
    }
  ]
}
```

### レポート構造

| セクション | 説明 |
|------------|------|
| `summary` | 統計情報（ユニークID数、フロー数など） |
| `flows` | 通信単位のID一覧 |
| `tracked_ids` | ID単位の詳細（どこで発生し、どこで使われたか） |
| `potential_idor` | IDOR脆弱性候補のリスト |

---

## CLIコマンド詳細（cli.py）

### メインコマンド

```bash
idotaku [OPTIONS]
```

| オプション | 短縮 | デフォルト | 説明 |
|------------|------|------------|------|
| `--port` | `-p` | 8080 | プロキシポート |
| `--web-port` | `-w` | 8081 | Web UIポート |
| `--output` | `-o` | `id_tracker_report.json` | 出力ファイル |
| `--min-numeric` | | 100 | 数値IDの最小値 |
| `--no-browser` | | false | ブラウザ自動起動を無効化 |
| `--browser` | | auto | 使用ブラウザ (chrome/edge/firefox/auto) |
| `--config` | `-c` | なし | 設定ファイルパス |
| `--interactive` | `-i` | false | 対話モードで起動 |

### report - サマリー表示

```bash
idotaku report [REPORT_FILE]
```

### chain - パラメータチェーン検出

```bash
idotaku chain [REPORT_FILE] [OPTIONS]
```

| オプション | 説明 |
|------------|------|
| `--top N` | 表示するチェーン数（デフォルト: 10） |
| `--min-depth N` | 最小深さ（デフォルト: 2） |
| `--html FILE` | インタラクティブHTMLとしてエクスポート |
| `--domains PATTERNS` | ドメインでフィルタ（カンマ区切り、ワイルドカード対応） |

**ドメインフィルタ例**:
```bash
# 特定ドメインのみ
idotaku chain --domains "api.example.com"

# 複数ドメイン（ワイルドカード対応）
idotaku chain --domains "api.example.com,*.internal.com"
```

**チェーン検出のアルゴリズム**:
1. Flow間の依存関係をグラフ化（レスポンスのID → リクエストで使用）
2. ルートノード（依存先がないFlow）を特定
3. 各ルートからDFSでツリーを構築
4. スコア = 深さ × 100 + ノード数

**サイクル検出**:
- APIパターン（メソッド + 正規化パス）でサイクルを検出
- 例: `GET /users/123` と `GET /users/456` は同じパターン
- サイクル検出時は参照ノードを返し、子ノードは元ノードにdefer

### sequence - シーケンス表示

```bash
idotaku sequence [REPORT_FILE] [OPTIONS]
```

| オプション | 説明 |
|------------|------|
| `--limit N` | 表示するAPIコール数（デフォルト: 30） |
| `--html FILE` | インタラクティブHTMLとしてエクスポート |

### lifeline - IDライフライン表示

```bash
idotaku lifeline [REPORT_FILE] [OPTIONS]
```

| オプション | 説明 |
|------------|------|
| `--min-uses N` | 最低使用回数（デフォルト: 1） |
| `--sort TYPE` | ソート順: lifespan/uses/first |

### version - バージョン表示

```bash
idotaku version
```

### interactive - 対話モード

```bash
idotaku interactive
# または
idotaku -i
```

**機能**:
- 矢印キーでコマンド選択
- レポートファイルの自動検出・選択
- ドメインフィルタのチェックボックス選択
- Enterでスキップ可能（デフォルト値使用）

**対象ユーザー**:
- 初心者: ガイド付きでコマンドを学べる
- シニア: Enterで素早くスキップ可能

---

## 依存関係

| パッケージ | バージョン | 用途 |
|------------|------------|------|
| mitmproxy | >=10.0.0 | プロキシエンジン |
| click | >=8.0.0 | CLIフレームワーク |
| rich | >=13.0.0 | ターミナル出力装飾 |
| questionary | >=2.0.0 | 対話式プロンプト |

---

## 制限事項

1. **WebSocket非対応**: HTTP/HTTPSのみ
2. **バイナリボディ非対応**: JSON/テキストのみ解析
3. **GraphQL非対応**: クエリ構造は解析しない（JSON bodyとしては処理）
4. **認証トークンの誤検出**: 長いトークンがIDとして検出される場合あり

---

## 今後の拡張候補

### 実装済み

- [x] ドメインフィルタリング
- [x] カスタムIDパターン定義
- [x] パラメータチェーン検出・可視化
- [x] シーケンス表示
- [x] IDライフライン表示
- [x] 対話式CLI（インタラクティブモード）
- [x] chainコマンドのドメインフィルタオプション
- [x] chain / sequence のインタラクティブHTMLエクスポート

### 未実装

- [ ] リアルタイムWeb UI
- [ ] ID置換テスト（自動リプレイ）
- [ ] HAR形式エクスポート
- [ ] GraphQL対応
- [ ] WebSocket対応
- [ ] レスポンスステータスコードの記録
