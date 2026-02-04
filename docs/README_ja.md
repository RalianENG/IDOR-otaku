# idotaku

[![CI](https://github.com/RalianENG/IDOR-otaku/actions/workflows/ci.yml/badge.svg)](https://github.com/RalianENG/IDOR-otaku/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/idotaku)](https://pypi.org/project/idotaku/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/pypi/pyversions/idotaku)](https://pypi.org/project/idotaku/)

**IDOR-otaku** — mitmproxy ベースの IDOR 検出ツール。通信を傍受し、パラメータの関係性を分析して、安全でない直接オブジェクト参照（IDOR）を検出します。

> **IDOR（Insecure Direct Object Reference）** とは、ユーザーIDや注文番号などの内部オブジェクトIDが適切な認可チェックなしに公開され、攻撃者がIDを操作することで他のユーザーのデータにアクセスできてしまう脆弱性です。

## 仕組み

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Browser   │────>│  mitmproxy  │────>│  API Server  │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
                           v
                    ┌─────────────┐
                    │  idotaku    │
                    │  (tracker)  │
                    └──────┬──────┘
                           │
                           v
                    ┌─────────────┐
                    │   Report    │
                    │   (JSON)    │
                    └─────────────┘
```

1. **傍受** — mitmproxy 経由でブラウザの通信をプロキシ
2. **追跡** — IDがレスポンスで最初に出現した場所（Origin）とリクエストで使用された場所（Usage）を記録
3. **検出** — レスポンスで一度も出現していないのにリクエストで使用されているIDをIDOR候補としてフラグ
4. **可視化** — パラメータチェーンやAPIシーケンス図をインタラクティブHTMLでレンダリング

## 動作要件

- Python 3.10+
- mitmproxy 10.0+

## インストール

```bash
pip install idotaku
```

## クイックスタート

```bash
# 対話モード（初心者におすすめ）
idotaku -i

# プロキシを直接起動
idotaku

# レポート分析
idotaku report id_tracker_report.json
idotaku chain id_tracker_report.json --html chain.html
idotaku sequence id_tracker_report.json --html sequence.html

# HARファイルからレポート生成（Chrome DevTools / Burp Suite）
idotaku import-har capture.har -o report.json
```

## コマンド一覧

### 分析

| コマンド | 説明 |
|----------|------|
| `report` | IDOR検出レポートのサマリー表示 |
| `chain` | パラメータチェーン検出（`--domains` フィルタ、`--html` エクスポート対応） |
| `sequence` | パラメータフロー付きAPIシーケンス表示（`--html` エクスポート対応） |
| `lifeline` | パラメータのライフスパン表示 |
| `score` | IDOR候補のリスクスコアリング（critical / high / medium / low） |
| `auth` | 認証コンテキスト分析（クロスユーザーアクセス検出） |
| `diff` | 2つのレポートの差分比較 |
| `interactive` | 対話モード（メニュー選択式） |

### インポート & エクスポート

| コマンド | 説明 |
|----------|------|
| `import-har` | HARファイルをインポートしてレポート生成 |
| `csv` | IDOR候補またはフロー一覧をCSVエクスポート |
| `sarif` | SARIF 2.1.0形式でエクスポート（GitHub Code Scanning対応） |

## ドキュメント

- [Quick Start Guide](QUICKSTART.md) (English)
- [Specification](SPECIFICATION.md) (English)

## コントリビュート

```bash
# クローンして開発用依存をインストール
git clone https://github.com/RalianENG/IDOR-otaku.git
cd IDOR-otaku
pip install -e ".[dev]"

# テスト実行
pytest

# カバレッジ付きテスト
pytest --cov=idotaku --cov-report=term-missing

# Lint
ruff check src/
```

バグ報告やプルリクエストは [GitHub Issues](https://github.com/RalianENG/IDOR-otaku/issues) にてお待ちしています。

## 免責事項

本ツールは**許可されたセキュリティテストおよび教育目的でのみ**使用してください。所有していないシステムをテストする前に、適切な許可を得る必要があります。本ツールの誤用または損害について、作者は一切の責任を負いません。すべての適用法令を遵守のうえ、自己責任でご利用ください。

## ライセンス

[MIT](../LICENSE)
