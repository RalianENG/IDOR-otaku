# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **Risk Scoring**: `score` command assigns risk score (0-100) and level (critical/high/medium/low) to each IDOR candidate based on HTTP method, parameter location, ID type, and usage patterns
- **HAR Import**: `import-har` command parses HAR files (Chrome DevTools, Burp Suite) and generates the same report format as the proxy tracker
- **Diff Analysis**: `diff` command compares two reports (before/after) showing new/removed IDOR candidates, tracked IDs, and flow count changes
- **Auth Context Tracking**: `auth` command detects cross-user access patterns by tracking Authorization headers and session cookies per flow
- **CSV Export**: `csv` command exports IDOR candidates or flow records to CSV for spreadsheet analysis
- **SARIF Export**: `sarif` command exports findings to SARIF 2.1.0 format for GitHub Code Scanning and other security tool integrations
- Programmatic API: all new features are importable (`from idotaku.report import score_all_findings, diff_reports`)

### Changed

- Interactive mode now includes all new commands (score, diff, auth, csv, sarif, import-har)
- Tracker now captures authentication context (Authorization header, session cookies) per flow
- Documentation translated to English (QUICKSTART.md, SPECIFICATION.md)

### Fixed

- Use defensive `dict.get()` access across all modules to prevent KeyError on malformed report data
- Add error handling for HAR file and report file loading with user-friendly error messages
- Add guard clauses for empty ID values in lifeline, sequence, and auth analysis
- Resolve ruff lint errors (unused imports, unused variables, ambiguous variable names)

## [0.1.0] - 2024

### Added

- mitmproxy-based proxy with automatic browser launch
- ID tracking: origin (response) and usage (request) detection
- IDOR candidate detection (IDs used without known origin)
- Parameter chain analysis with cycle detection
- Commands: `report`, `chain`, `sequence`, `lifeline`
- Interactive mode (`idotaku -i`) with guided menus
- Domain filtering (`--domains` option for `chain`)
- YAML configuration file support
- Interactive HTML export for `chain` and `sequence` commands (`--html` option)
  - Chain: card-based tree nodes with CSS connectors, via-parameter banners, inline param chips
  - Sequence: UML sequence diagram with lifelines, ID chip highlighting, IDOR warning badges
