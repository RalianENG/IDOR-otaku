# idotaku クイックスタート

## インストール

```bash
# リポジトリをクローン
git clone https://github.com/yourname/idotaku.git
cd idotaku

# 仮想環境作成（推奨）
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

# インストール
pip install -e .
```

---

## 基本的な使い方

### 1. 起動

```bash
idotaku
```

これだけで:
- mitmproxy が起動（ポート8080）
- Web UI が起動（http://127.0.0.1:8081）
- ブラウザが自動起動（プロキシ設定済み）

### 2. テスト対象を操作

起動したブラウザでテスト対象のWebアプリを操作します。
APIコールが自動的に記録されます。

### 3. 終了してレポート生成

`Ctrl+C` で終了すると `id_tracker_report.json` が生成されます。

### 4. レポート確認

```bash
# サマリー表示
idotaku report

# ID別ツリー形式で可視化
idotaku tree

# パラメータチェーン検出（ビジネスフロー発見）
idotaku chain

# HTMLでインタラクティブに可視化
idotaku chain --html chain_report.html
```

---

## コマンド早見表

| コマンド | 説明 |
|----------|------|
| `idotaku` | プロキシ起動 |
| `idotaku report` | レポートサマリー表示 |
| `idotaku tree` | ID別ツリー形式で可視化 |
| `idotaku flow` | ID別タイムライン形式で可視化 |
| `idotaku trace` | API遷移を可視化（ID連鎖を表示） |
| `idotaku chain` | パラメータチェーン検出・ランキング |
| `idotaku export` | HTMLレポート出力 |

その他: `sequence`, `lifeline`, `graph` - 詳細は [SPECIFICATION.md](./SPECIFICATION.md) 参照

---

## 出力の見方

### report - サマリー表示

```
=== ID Tracker Summary ===
Unique IDs: 15
IDs with Origin: 10      ← レスポンスで発生したID
IDs with Usage: 8        ← リクエストで使用されたID
Total Flows: 25          ← 記録されたAPI呼び出し数

⚠ Potential IDOR: 3      ← IDOR候補（要確認）
```

- **Origin**: レスポンスでIDが最初に出現した場所（正規の発生源）
- **Usage**: リクエストでIDが使用された場所
- **IDOR候補**: Usageはあるが Originがない = どこから来たか不明なID

### tree - IDツリー表示

```
user_123 (token)
├── [ORIGIN] GET /api/login → body.user_id (12:00:00)
├── [USAGE] GET /api/users/user_123 → url_path (12:00:05)
└── [USAGE] PUT /api/users/user_123 → url_path (12:00:10)

99999 (numeric) ⚠ IDOR candidate
└── [USAGE] GET /api/orders/99999 → url_path (12:00:15)
```

- `[ORIGIN]`: IDの発生源（レスポンスで受け取った）
- `[USAGE]`: IDの使用箇所（リクエストで送信した）
- `⚠ IDOR candidate`: Originなし = 外部から持ち込まれた可能性

### flow - IDタイムライン表示

```
user_123 [token]
  ◉ GET /login (res.body) → GET /users (req.url) → PUT /users (req.url)

99999 [numeric] ⚠
  → GET /orders (req.url)
```

- `◉`: Origin（レスポンスで発生）
- `→`: Usage（リクエストで使用）
- `⚠`: IDOR候補

### chain - パラメータチェーン

```
#1 [Score: 502] 深さ5 / 8ノード
└── [#1] GET /api/auth/login
    ├── via: user_id, session_token
    ├── [#2] GET /api/users/{id}
    │   ├── via: org_id
    │   ├── [#3] GET /api/orgs/{id}
    │   │   └── ...
    │   └── ↩ [#1] via org_id (continues below)  ← サイクル参照
    └── [#4] GET /api/dashboard
        └── ...
```

- `[#N]`: ノード番号（API呼び出しの識別子）
- `via: xxx`: このAPIを呼ぶために使われたパラメータ
- `↩ [#N]`: サイクル参照（同じAPIパターンに戻った）
- `(continues below)`: サイクル先の子ノードは親にぶら下がる

**スコアの意味**:
- `深さ × 100 + ノード数 × 1`
- 深いチェーン = 複雑なビジネスフロー = 重点的にテストすべき箇所

### trace - API遷移表示

```
[1] GET /api/login
    Response IDs:
      user_id: abc123 (body.data.id)
      session: xyz789 (header.set-cookie)
    ↓ user_id → [2], session → [2]

[2] GET /api/users/abc123
    Request IDs:
      abc123 (url_path) ← from [1]
      xyz789 (header.cookie) ← from [1]
    Response IDs:
      org_id: org456 (body.organization_id)
```

- `← from [N]`: どのAPIから流れてきたパラメータか
- `↓ param → [N]`: このパラメータがどのAPIに流れるか

---

## よく使うオプション

```bash
# ポート変更
idotaku --port 9090

# 出力ファイル指定
idotaku --output result.json

# ブラウザ自動起動なし
idotaku --no-browser

# 特定ブラウザ指定
idotaku --browser chrome

# 設定ファイル指定
idotaku --config ./my-config.yaml
idotaku -c idotaku.yaml

# IDOR候補のみ表示
idotaku tree --idor-only

# チェーンをHTMLで出力
idotaku chain --html report.html
```

---

## 設定ファイル

カスタマイズしたい場合は設定ファイルを作成:

```bash
cp idotaku.example.yaml idotaku.yaml
```

または、任意の場所の設定ファイルを指定:

```bash
idotaku -c /path/to/config.yaml
```

設定ファイルが指定されていない場合、カレントディレクトリの `idotaku.yaml` または `.idotaku.yaml` を自動検索します。

### 設定例: カスタムIDパターン追加

```yaml
idotaku:
  patterns:
    order_id: "ORD-[A-Z]{2}-\\d{8}"
    session: "sess_[a-zA-Z0-9]{32}"
```

### 設定例: 特定ドメインのみ追跡（ホワイトリスト）

```yaml
idotaku:
  target_domains:
    - api.example.com
    - "*.example.com"
```

### 設定例: 特定ドメインを除外（ブラックリスト）

```yaml
idotaku:
  exclude_domains:
    - "*.google-analytics.com"
    - "*.doubleclick.net"
    - analytics.example.com
```

ブラックリストはホワイトリストより優先されます。

### 設定例: 静的ファイル除外のカスタマイズ

```yaml
idotaku:
  exclude_extensions:
    - ".css"
    - ".js"
    - ".png"
    - ".jpg"
    - ".svg"
```

デフォルトでは一般的な静的ファイル（CSS, JS, 画像, フォント等）が除外されます。

詳細は [SPECIFICATION.md](./SPECIFICATION.md) 参照

---

## トラブルシューティング

### mitmweb が見つからない

```bash
pip install mitmproxy
```

### HTTPS通信が見れない

ブラウザで http://mitm.it にアクセスし、CA証明書をインストールしてください。
（`idotaku` コマンドで起動したブラウザは `--ignore-certificate-errors` 付きなので不要）

### レポートが空

- プロキシ設定が正しいか確認
- テスト対象がAPIを呼んでいるか確認（Web UIで通信を確認）

---

## 次のステップ

- [SPECIFICATION.md](./SPECIFICATION.md) - 詳細仕様・全コマンドオプション
- 設定ファイルの全オプションは `idotaku.example.yaml` を参照
