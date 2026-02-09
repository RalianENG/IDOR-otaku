# idotaku Quick Start

## Installation

```bash
# Clone the repository
git clone https://github.com/RalianENG/IDOR-otaku.git
cd idotaku

# Create a virtual environment (recommended)
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

# Install
pip install -e .
```

---

## Basic Usage

### 1. Launch (Interactive Mode - Recommended for Beginners)

```bash
idotaku -i
```

Starts an interactive mode where you can select commands with arrow keys.
File selection and domain filters can also be configured interactively.

### 2. Launch (Proxy Mode)

```bash
idotaku
```

This single command:
- Starts mitmproxy (port 8080)
- Starts the Web UI (http://127.0.0.1:8081)
- Auto-launches a browser (with proxy configured)

### 3. Interact with the Target

Use the launched browser to interact with the target web application.
API calls are automatically recorded.

### 4. Stop and Generate Report

Press `Ctrl+C` to stop. An `id_tracker_report.json` file will be generated.

### 5. Analyze the Report

```bash
# View summary (check IDOR candidates)
idotaku report

# Risk scoring (show IDOR candidates by severity)
idotaku score

# Detect parameter chains (discover business flows)
idotaku chain

# Filter by specific domains (reduce noise)
idotaku chain --domains "api.example.com,*.internal.com"

# Visualize chains as interactive HTML
idotaku chain --html chain_report.html

# Export API sequence diagram as HTML (with ID highlighting)
idotaku sequence --html sequence_report.html

# Parameter lifespan analysis
idotaku lifeline

# Auth context analysis (detect cross-user access)
idotaku auth
```

---

## Command Reference

### Basic

| Command | Description |
|---------|-------------|
| `idotaku -i` | Interactive mode (menu-driven) |
| `idotaku` | Start proxy |

### Analysis

| Command | Description |
|---------|-------------|
| `idotaku report` | View IDOR detection report summary |
| `idotaku score` | Risk-score IDOR candidates (critical/high/medium/low) |
| `idotaku chain` | Detect and rank parameter chains (`--html` for HTML export) |
| `idotaku sequence` | API sequence diagram (`--html` for HTML export with ID highlighting) |
| `idotaku lifeline` | Parameter lifespan analysis |
| `idotaku auth` | Auth context analysis (cross-user access detection) |
| `idotaku diff A.json B.json` | Compare two reports |

### Configuration

| Command | Description |
|---------|-------------|
| `idotaku config init` | Create default `idotaku.yaml` in the current directory |
| `idotaku config show` | Show effective configuration (defaults + config file) |
| `idotaku config get <key>` | Get a single config value (e.g. `patterns.uuid`) |
| `idotaku config set <key> <value>` | Set a config value in the YAML file |
| `idotaku config validate` | Validate config file for errors |
| `idotaku config path` | Print path to the active config file |

### Import & Export

| Command | Description |
|---------|-------------|
| `idotaku import-har file.har` | Generate report from HAR file |
| `idotaku csv report.json` | Export IDOR candidates to CSV (`-m flows` for flow list) |
| `idotaku sarif report.json` | Export to SARIF 2.1.0 (GitHub Code Scanning compatible) |

See [SPECIFICATION.md](./SPECIFICATION.md) for details.

---

## Understanding the Output

### report - Summary

```
=== ID Tracker Summary ===
Unique IDs: 15
IDs with Origin: 10      <- IDs originating from responses
IDs with Usage: 8        <- IDs used in requests
Total Flows: 25          <- Number of recorded API calls

⚠ Potential IDOR: 3      <- IDOR candidates (requires review)
```

- **Origin**: Where an ID first appeared in a response (legitimate source)
- **Usage**: Where an ID was used in a request
- **IDOR candidate**: Has Usage but no Origin = unknown source of ID

### chain - Parameter Chains

```
#1 [Score: 502] Depth 5 / 8 nodes
└── [#1] GET /api/auth/login
    ├── via: user_id, session_token
    ├── [#2] GET /api/users/{id}
    │   ├── via: org_id
    │   ├── [#3] GET /api/orgs/{id}
    │   │   └── ...
    │   └── ↩ [#1] via org_id (continues below)  <- Cycle reference
    └── [#4] GET /api/dashboard
        └── ...
```

- `[#N]`: Node number (API call identifier)
- `via: xxx`: Parameters used to make this API call
- `↩ [#N]`: Cycle reference (returns to the same API pattern)
- `(continues below)`: Child nodes of the cycle target are deferred to the parent

**Score meaning**:
- `depth × 100 + node_count × 1`
- Deeper chains = more complex business flows = areas that need thorough testing

### HTML Output

The `chain` and `sequence` commands can generate interactive HTML reports with the `--html` option:

```bash
# Chain HTML report (card-based tree + connector lines)
idotaku chain --html chain_report.html

# Sequence HTML report (UML sequence diagram + ID highlighting)
idotaku sequence --html sequence_report.html
```

- **chain HTML**: Displays parameter chains as card-based nodes. Expand/collapse, via-parameter display, Consumes/Produces chips
- **sequence HTML**: Displays API calls as a sequence diagram. Click ID chips to highlight all occurrences. IDOR candidates shown with red warning badges

---

## Common Options

```bash
# Interactive mode (recommended)
idotaku -i

# Change port
idotaku --port 9090

# Specify output file
idotaku --output result.json

# Disable auto browser launch
idotaku --no-browser

# Specify browser
idotaku --browser chrome

# Specify config file
idotaku --config ./my-config.yaml
idotaku -c idotaku.yaml

# Configuration management
idotaku config init                    # Create default idotaku.yaml
idotaku config show                    # Show current settings
idotaku config get min_numeric         # Get a single value
idotaku config set min_numeric 50      # Set a value
idotaku config set target_domains "api.example.com,*.test.com"
idotaku config validate                # Check for errors

# Chain analysis (domain filter)
idotaku chain --domains "api.example.com"

# Export chain as HTML
idotaku chain --html report.html

# Export sequence diagram as HTML
idotaku sequence --html sequence.html

# Lifespan analysis (sort by usage count)
idotaku lifeline --sort uses

# Generate report from HAR file (Chrome DevTools / Burp Suite)
idotaku import-har capture.har -o report.json

# Risk scoring (show only scores 50+)
idotaku score --min-score 50

# Show only critical level
idotaku score --level critical

# Compare two reports
idotaku diff old_report.json new_report.json

# Export diff as JSON
idotaku diff old.json new.json -o diff_result.json

# Auth context analysis
idotaku auth

# CSV export (IDOR candidates)
idotaku csv report.json -o idor.csv

# CSV export (flow list)
idotaku csv report.json -o flows.csv -m flows

# SARIF export (for GitHub Code Scanning)
idotaku sarif report.json -o findings.sarif.json
```

---

## Configuration File

To customize settings, create a config file:

```bash
idotaku config init
```

Or manually:

Or specify a config file at any location:

```bash
idotaku -c /path/to/config.yaml
```

If no config file is specified, `idotaku.yaml` or `.idotaku.yaml` in the current directory will be auto-detected.

### Example: Add Custom ID Patterns

```yaml
idotaku:
  patterns:
    order_id: "ORD-[A-Z]{2}-\\d{8}"
    session: "sess_[a-zA-Z0-9]{32}"
```

### Example: Track Specific Domains Only (Allowlist)

```yaml
idotaku:
  target_domains:
    - api.example.com
    - "*.example.com"
```

### Example: Exclude Specific Domains (Blocklist)

```yaml
idotaku:
  exclude_domains:
    - "*.google-analytics.com"
    - "*.doubleclick.net"
    - analytics.example.com
```

The blocklist takes priority over the allowlist.

### Example: Customize Static File Exclusions

```yaml
idotaku:
  exclude_extensions:
    - ".css"
    - ".js"
    - ".png"
    - ".jpg"
    - ".svg"
```

By default, common static files (CSS, JS, images, fonts, etc.) are excluded.

See [SPECIFICATION.md](./SPECIFICATION.md) for details.

---

## Troubleshooting

### mitmweb not found

```bash
pip install mitmproxy
```

### Cannot see HTTPS traffic

Visit http://mitm.it in the browser and install the CA certificate.
(Browsers launched by the `idotaku` command have `--ignore-certificate-errors` enabled, so this is not needed.)

### Empty report

- Verify proxy settings are correct
- Confirm the target application is making API calls (check traffic in the Web UI)

---

## Next Steps

- [SPECIFICATION.md](./SPECIFICATION.md) - Full specification and all command options
- See `idotaku.example.yaml` for all configuration options