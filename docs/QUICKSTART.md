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

## Try the Demo

The `examples/vulnerable_api/` directory contains a complete demo with a purposely
vulnerable FastAPI server and an automated attack scenario.

### Prerequisites

- Python 3.12+
- idotaku installed (`pip install -e .` from the project root)
- mitmproxy installed (included as a dependency of idotaku)

### Option A: One-Command Demo

```bash
cd examples/vulnerable_api

# Linux/macOS
bash run_demo.sh

# Windows (or any platform)
python run_demo.py
```

This script automatically:
1. Installs demo dependencies (fastapi, uvicorn, requests)
2. Starts the vulnerable API server on port 3000
3. Starts mitmdump proxy on port 8080 with the idotaku tracker
4. Runs an 11-phase attack scenario through the proxy
5. Stops the proxy (generating the report)
6. Runs all analysis commands (report, score, chain, auth)
7. Generates HTML exports (chain.html, sequence.html)

### Option B: Manual Step-by-Step

If you prefer to run each step yourself:

#### Terminal 1: Start the Vulnerable API

```bash
cd examples/vulnerable_api
pip install -r requirements.txt
python server.py
```

The server starts at http://localhost:3000 with 3 test users (alice, bob, charlie)
and intentional IDOR vulnerabilities across 13+ endpoints.

#### Terminal 2: Start the idotaku Proxy

Using the idotaku CLI (launches a browser and web UI):

```bash
cd examples/vulnerable_api
idotaku --port 8080 -o test_report.json -c idotaku.yaml
```

Or using mitmdump directly (headless, no browser):

```bash
cd examples/vulnerable_api
TRACKER=$(python -c "from idotaku.browser import get_tracker_script_path; print(get_tracker_script_path())")
mitmdump -s "$TRACKER" --listen-port 8080 \
    --set idotaku_config="$(pwd)/idotaku.yaml" \
    --set idotaku_output="$(pwd)/test_report.json" \
    --quiet
```

#### Terminal 3: Run the Test Scenario

```bash
cd examples/vulnerable_api
python test_scenario.py
```

The scenario logs each phase as it runs:

```
[Phase 1] Alice login
[Phase 2] Alice accesses own data
[Phase 3] CRITICAL IDOR - Alice attacks Charlie (1003) via admin endpoints
[Phase 4] HIGH IDOR - Alice updates Bob's user via PUT
[Phase 5] MEDIUM IDOR - Alice accesses Bob's profile via UUID in body
[Phase 6] LOW IDOR - Alice accesses Bob's document via header token
[Phase 7] Parameter chain - Order CRUD
[Phase 8] Bob login
[Phase 9] Cross-user detection - Bob accesses Alice's data
[Phase 10] Alice lists her own profiles (producer)
[Phase 11] Alice lists her own documents (producer)
```

#### Stop and Analyze

Stop the proxy (Ctrl+C in Terminal 2), then:

```bash
cd examples/vulnerable_api

# Summary report
idotaku report test_report.json

# Risk scoring (the key output)
idotaku score test_report.json

# Parameter chain tree
idotaku chain test_report.json

# Cross-user access detection
idotaku auth test_report.json

# Generate interactive HTML reports
idotaku chain test_report.json --html chain.html
idotaku sequence test_report.json --html sequence.html
```

### Expected Results

The test scenario produces detections at every severity level:

| Level    | Score | ID                                  | Attack Vector                            |
|----------|-------|-------------------------------------|------------------------------------------|
| CRITICAL | 89    | `1003` (charlie)                    | 3 admin endpoints (delete, role, action) |
| HIGH     | 65    | `1002` (bob)                        | PUT /api/users/1002                      |
| MEDIUM   | 46    | `b2c3d4e5-...` (bob's profile UUID) | POST profiles/view + profiles/update     |
| LOW      | 18    | `doc_YzAbCd...` (bob's doc token)   | GET documents/by-header via header       |

The chain analysis shows how IDs flow through the order CRUD lifecycle:
`POST /api/orders` (creates order_id) → `GET /api/orders/{id}` → `PATCH /api/orders/{id}` → `DELETE /api/orders/{id}`

The auth analysis detects that both Alice and Bob access user ID `1001` with
different auth tokens — a cross-user access pattern.

### HTML Reports

Open the generated HTML files in a browser:

- **chain.html** — Interactive card-based tree showing parameter chains.
  Click nodes to expand/collapse. Shows Consumes/Produces chips for each API call.
- **sequence.html** — UML-style sequence diagram of all API calls.
  Click ID chips to highlight all occurrences across the timeline.
  IDOR candidates are marked with red warning badges.

### Demo Troubleshooting

**Port already in use:**

```bash
# Use custom ports
python run_demo.py --api-port 4000 --proxy-port 9090

# Or for the shell script
API_PORT=4000 PROXY_PORT=9090 bash run_demo.sh
```

**Empty report:** Make sure the proxy is running before the test scenario.
The tracker records traffic in real-time and writes the report on shutdown.

**Windows path issues:** Use `python run_demo.py` instead of `bash run_demo.sh`.
The Python script handles Windows paths and process signals correctly.

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