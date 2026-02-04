# idotaku クイックスタート

## インストール

```bash
# リポジトリをクローン
git clone https://github.com/RalianENG/IDOR-otaku.git
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

### 1. 起動（対話モード - 初心者向け）

```bash
idotaku -i
```

矢印キーでコマンドを選択できるインタラクティブモードが起動します。
ファイル選択やドメインフィルタも対話形式で設定可能。

### 1. 起動（プロキシモード）

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
# サマリー表示（IDOR候補の確認）
idotaku report

# リスクスコアリング（IDOR候補を重要度順に表示）
idotaku score

# パラメータチェーン検出（ビジネスフロー発見）
idotaku chain

# 特定ドメインのみ分析（ノイズ除去）
idotaku chain --domains "api.example.com,*.internal.com"

# チェーンをHTMLでインタラクティブに可視化
idotaku chain --html chain_report.html

# APIシーケンス図をHTML出力（IDハイライト付き）
idotaku sequence --html sequence_report.html

# パラメータのライフスパン分析
idotaku lifeline

# 認証コンテキスト分析（クロスユーザーアクセス検出）
idotaku auth
```

---

## コマンド早見表

### 基本

| コマンド | 説明 |
|----------|------|
| `idotaku -i` | 対話モード（メニュー選択式） |
| `idotaku` | プロキシ起動 |

### 分析

| コマンド | 説明 |
|----------|------|
| `idotaku report` | IDOR検出レポートのサマリー表示 |
| `idotaku score` | IDOR候補のリスクスコアリング（critical/high/medium/low） |
| `idotaku chain` | パラメータチェーン検出・ランキング（`--html` でHTML出力） |
| `idotaku sequence` | APIシーケンス図（`--html` でHTML出力、IDハイライト付き） |
| `idotaku lifeline` | パラメータのライフスパン分析 |
| `idotaku auth` | 認証コンテキスト分析（クロスユーザーアクセス検出） |
| `idotaku diff A.json B.json` | 2つのレポートの差分比較 |

### インポート・エクスポート

| コマンド | 説明 |
|----------|------|
| `idotaku import-har file.har` | HARファイルからレポート生成 |
| `idotaku csv report.json` | IDOR候補をCSV出力（`-m flows` でフロー一覧） |
| `idotaku sarif report.json` | SARIF 2.1.0形式で出力（GitHub Code Scanning対応） |

詳細は [SPECIFICATION.md](./SPECIFICATION.md) 参照

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

### HTML出力

`chain` と `sequence` コマンドは `--html` オプションでインタラクティブなHTMLレポートを生成できます:

```bash
# チェーンHTMLレポート（カード型ツリー + コネクタライン）
idotaku chain --html chain_report.html

# シーケンスHTMLレポート（UMLシーケンス図 + IDハイライト）
idotaku sequence --html sequence_report.html
```

- **chain HTML**: パラメータチェーンをカード型ノードで表示。展開/折りたたみ、via パラメータ表示、Consumes/Producesチップ
- **sequence HTML**: APIコールをシーケンス図で表示。IDチップをクリックすると同じIDの全出現箇所がハイライト。IDOR候補は赤枠で警告

---

## よく使うオプション

```bash
# 対話モード（おすすめ）
idotaku -i

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

# チェーン分析（ドメインフィルタ）
idotaku chain --domains "api.example.com"

# チェーンをHTMLで出力
idotaku chain --html report.html

# シーケンス図をHTMLで出力
idotaku sequence --html sequence.html

# ライフスパン分析（使用回数順）
idotaku lifeline --sort uses

# HARファイルからレポート生成（Chrome DevTools / Burp Suite）
idotaku import-har capture.har -o report.json

# リスクスコアリング（スコア50以上のみ表示）
idotaku score --min-score 50

# criticalレベルのみ表示
idotaku score --level critical

# レポートの差分比較
idotaku diff old_report.json new_report.json

# 差分をJSONファイルに出力
idotaku diff old.json new.json -o diff_result.json

# 認証コンテキスト分析
idotaku auth

# CSV出力（IDOR候補）
idotaku csv report.json -o idor.csv

# CSV出力（フロー一覧）
idotaku csv report.json -o flows.csv -m flows

# SARIF出力（GitHub Code Scanning用）
idotaku sarif report.json -o findings.sarif.json
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
