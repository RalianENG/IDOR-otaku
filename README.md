# idotaku

[![CI](https://github.com/RalianENG/IDOR-otaku/actions/workflows/ci.yml/badge.svg)](https://github.com/RalianENG/IDOR-otaku/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/idotaku)](https://pypi.org/project/idotaku/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/pypi/pyversions/idotaku)](https://pypi.org/project/idotaku/)

**IDOR-otaku** — mitmproxy-based IDOR detection tool that intercepts traffic and analyzes parameter relationships to find insecure direct object references.

> **IDOR (Insecure Direct Object Reference)** is a vulnerability where an application exposes internal object IDs (user IDs, order numbers, etc.) without proper authorization checks, allowing attackers to access other users' data by manipulating these IDs.

## How It Works

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

1. **Intercept** — Proxies browser traffic via mitmproxy
2. **Track** — Records where IDs first appear (response) and where they are used (request)
3. **Detect** — Flags IDs used in requests that never appeared in any response (IDOR candidates)
4. **Visualize** — Renders parameter chains and API sequence diagrams as interactive HTML

## Requirements

- Python 3.10+
- mitmproxy 10.0+

## Installation

```bash
pip install idotaku
```

## Quick Start

```bash
# Interactive mode (recommended for beginners)
idotaku -i

# Start proxy directly
idotaku

# Analyze report
idotaku report id_tracker_report.json
idotaku chain id_tracker_report.json --html chain.html
idotaku sequence id_tracker_report.json --html sequence.html

# Import HAR file (from Chrome DevTools, Burp Suite, etc.)
idotaku import-har capture.har -o report.json
```

## Commands

### Analysis

| Command | Description |
|---------|-------------|
| `report` | View IDOR detection report summary |
| `chain` | Detect parameter chains with `--html` export and `--domains` filter |
| `sequence` | API sequence diagram with `--html` export and ID highlighting |
| `lifeline` | Show parameter lifespan analysis |
| `score` | Risk-score IDOR candidates (critical / high / medium / low) |
| `auth` | Detect cross-user access patterns via auth context |
| `diff` | Compare two reports and show changes |
| `interactive` | Launch interactive mode with guided menus |

### Import & Export

| Command | Description |
|---------|-------------|
| `import-har` | Import HAR file and generate idotaku report |
| `csv` | Export IDOR candidates or flows to CSV |
| `sarif` | Export findings to SARIF 2.1.0 (GitHub Code Scanning) |

## Programmatic API

```python
from idotaku.report import load_report, score_all_findings, diff_reports
from idotaku.export import export_csv, export_sarif
from idotaku.import_har import import_har

# Load and score
data = load_report("report.json")
scored = score_all_findings(data.potential_idor)

# Export
export_csv("idor.csv", data, mode="idor")
export_sarif("findings.sarif.json", data)

# Import HAR
report = import_har("capture.har")

# Diff two reports
from idotaku.report import diff_reports
diff = diff_reports(load_report("old.json"), load_report("new.json"))
```

## Documentation

- **[日本語ドキュメント / Japanese README](docs/README_ja.md)**
- [Quick Start Guide (Japanese)](docs/QUICKSTART.md)
- [Specification (Japanese)](docs/SPECIFICATION.md)

## Contributing

```bash
# Clone and install with dev dependencies
git clone https://github.com/RalianENG/IDOR-otaku.git
cd idotaku
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=idotaku

# Lint
ruff check src/
```

Bug reports and pull requests are welcome on [GitHub Issues](https://github.com/RalianENG/IDOR-otaku/issues).

## Disclaimer

This tool is intended for **authorized security testing and educational purposes only**. You must obtain proper authorization before testing any systems you do not own. The authors are not responsible for any misuse or damage caused by this tool. Use at your own risk and in compliance with all applicable laws.

## License

[MIT](LICENSE)