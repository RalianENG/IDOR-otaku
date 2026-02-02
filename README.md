# idotaku

API ID tracking tool for security testing - tracks ID generation and usage patterns to detect potential IDOR vulnerabilities.

## Installation

```bash
pip install idotaku
```

## Usage

### Interactive Mode (Recommended for beginners)

```bash
idotaku -i
# or
idotaku interactive
```

Menu-driven interface with arrow key navigation.

### Start tracking proxy

```bash
idotaku
```

This launches mitmweb proxy and a browser configured to use it.

### Analyze report

```bash
# View summary
idotaku report id_tracker_report.json

# Visualize ID flow
idotaku tree id_tracker_report.json

# Show API trace
idotaku trace id_tracker_report.json

# Detect parameter chains
idotaku chain id_tracker_report.json

# Filter by domain
idotaku chain id_tracker_report.json --domains "api.example.com"

# Export to HTML
idotaku export id_tracker_report.json -o report.html
```

## Commands

| Command | Description |
|---------|-------------|
| `interactive` | Launch interactive mode with guided menus |
| `report` | View ID tracking report summary |
| `tree` | Visualize IDs as origin → usage tree |
| `flow` | Show ID flow timeline |
| `trace` | Show API call transitions |
| `sequence` | Show API sequence with parameter flow |
| `lifeline` | Show parameter lifespan |
| `graph` | Show API dependency graph |
| `chain` | Detect parameter chains (supports `--domains` filter) |
| `export` | Export to interactive HTML |

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=idotaku
```

## License

MIT
