# IDOR-otaku (idotaku) Specification

## Overview

**idotaku** is a vulnerability assessment tool that tracks ID origin (Origin) and usage (Usage) from API calls to detect IDOR (Insecure Direct Object Reference) vulnerability candidates.

It operates as a mitmproxy addon, intercepting and analyzing traffic between the browser and API server.

---

## Architecture

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

## Project Structure

```
idotaku/
├── pyproject.toml          # Package definition
├── idotaku.example.yaml    # Config file template
├── docs/
│   ├── QUICKSTART.md       # Quick start guide
│   └── SPECIFICATION.md    # This document
└── src/
    └── idotaku/
        ├── __init__.py     # Package init, version definition
        ├── tracker.py      # Core logic (mitmproxy addon)
        ├── config.py       # Config file loader
        ├── cli.py          # CLI entry point
        ├── commands/       # Subcommands
        │   ├── run.py      # Proxy launch
        │   ├── report.py   # Summary report
        │   ├── chain.py    # Parameter chain detection
        │   ├── sequence.py # Sequence display
        │   ├── lifeline.py # ID lifeline display
        │   └── interactive_cmd.py  # Interactive mode
        ├── export/         # HTML export
        │   ├── chain_exporter.py    # Chain HTML output
        │   └── sequence_exporter.py # Sequence HTML output
        └── interactive.py  # Interactive mode UI
```

---

## Core Logic (tracker.py)

### Data Structures

```python
@dataclass
class IDOccurrence:
    """Represents a single occurrence of an ID"""
    id_value: str      # ID value (e.g., "12345", "uuid-xxx-xxx")
    id_type: str       # Type: "numeric" | "uuid" | "token"
    location: str      # Location: "url_path" | "query" | "body" | "header"
    field_name: str    # Field name (e.g., "user_id", "items[0].id")
    url: str           # Request URL
    method: str        # HTTP method
    timestamp: str     # ISO8601 timestamp
    direction: str     # "request" | "response"

@dataclass
class TrackedID:
    """A tracked ID"""
    value: str                       # ID value
    id_type: str                     # Type
    first_seen: str                  # First discovery time
    origin: Optional[IDOccurrence]   # First occurrence in a response
    usages: list[IDOccurrence]       # List of occurrences in requests

@dataclass
class FlowRecord:
    """A request-response pair (single communication)"""
    flow_id: str                     # Unique ID assigned by mitmproxy
    url: str                         # Request URL
    method: str                      # HTTP method
    timestamp: str                   # ISO8601 timestamp
    request_ids: list[dict]          # IDs detected in request
    response_ids: list[dict]         # IDs detected in response
```

### ID Detection Patterns

| Type | Regex | Description |
|------|-------|-------------|
| uuid | `[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}` | UUID v1-v5 |
| numeric | `[1-9]\d{2,10}` | 3-11 digit numbers (100 or greater) |
| token | `[A-Za-z0-9_-]{20,}` | Alphanumeric tokens of 20+ characters |

### Exclusion Patterns

| Pattern | Description |
|---------|-------------|
| `^\d{10,13}$` | Unix timestamps (false positive prevention) |
| `^\d+\.\d+\.\d+$` | Version numbers |

### ID Tracking Logic

```
1. ID appears in response
   → Recorded in TrackedID.origin (first occurrence only)
   → This is the "ID origin"

2. ID appears in request
   → Added to TrackedID.usages
   → This is the "ID usage"

3. Analysis at termination
   → usages present && origin absent = IDOR candidate
   (ID used in requests but never originated from a response)
```

---

## IDOR Detection Logic

### Detection Criteria

```
potential_idor = ID where:
  - usages.length > 0  (used in requests)
  - origin == null      (never appeared in any response)
```

### Rationale

1. **Normal flow**: When a user interacts with an API, they first receive an ID in a response (origin), then use it in subsequent requests (usage)

2. **IDOR candidate**: An ID used in requests but never seen in responses may indicate:
   - The user manually guessed or modified the ID
   - An ID obtained from a different session is being used
   - The ID is a target of enumeration attacks

---

## Configuration File (config.py)

### Search Order

When no config file is explicitly specified, the following paths are searched in order:

1. `idotaku.yaml` (current directory)
2. `idotaku.yml`
3. `.idotaku.yaml`
4. `.idotaku.yml`

### Config File Format

```yaml
idotaku:
  # Output file path
  output: id_tracker_report.json

  # Minimum value for numeric IDs (smaller numbers are ignored)
  min_numeric: 100

  # ID detection patterns (name: regex)
  patterns:
    uuid: "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    numeric: "[1-9]\\d{2,10}"
    token: "[A-Za-z0-9_-]{20,}"
    # Custom pattern example:
    # order_id: "ORD-[A-Z]{2}-\\d{8}"

  # Exclusion patterns (regex to exclude from ID candidates)
  exclude_patterns:
    - "^\\d{10,13}$"      # Unix timestamp
    - "^\\d+\\.\\d+\\.\\d+$"  # Version numbers

  # Content-Types to extract IDs from
  trackable_content_types:
    - application/json
    - application/x-www-form-urlencoded
    - text/html
    - text/plain

  # Additional headers to ignore (appended to defaults)
  extra_ignore_headers: []
    # - x-internal-trace-id

  # Target domains (allowlist, empty means all domains)
  # target_domains:
  #   - api.example.com
  #   - "*.example.com"

  # Excluded domains (blocklist, takes priority over target_domains)
  # exclude_domains:
  #   - analytics.example.com
  #   - "*.tracking.com"

  # Excluded extensions (static files)
  # exclude_extensions:
  #   - ".css"
  #   - ".js"
  #   - ".png"
  #   - ".jpg"
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `output` | string | `id_tracker_report.json` | Output file path |
| `min_numeric` | int | `100` | Minimum value for numeric IDs |
| `patterns` | dict | uuid/numeric/token | ID detection patterns |
| `exclude_patterns` | list | timestamp/version | Exclusion patterns |
| `trackable_content_types` | list | json/form/html/text | Content-Types to analyze |
| `ignore_headers` | list | (default set) | Headers to ignore (full override) |
| `extra_ignore_headers` | list | `[]` | Additional headers to ignore |
| `target_domains` | list | `[]` (all domains) | Target domains (allowlist) |
| `exclude_domains` | list | `[]` | Excluded domains (blocklist, takes priority) |
| `exclude_extensions` | list | static file extensions | Extensions to exclude (.css, .js, .png, etc.) |

### Default Excluded Extensions

Static files are automatically excluded:
- **Styles & scripts**: `.css`, `.js`, `.map`
- **Images**: `.png`, `.jpg`, `.jpeg`, `.gif`, `.svg`, `.ico`, `.webp`, `.bmp`
- **Fonts**: `.woff`, `.woff2`, `.ttf`, `.eot`, `.otf`
- **Media**: `.mp3`, `.mp4`, `.webm`, `.ogg`, `.wav`
- **Other**: `.pdf`, `.zip`, `.gz`

### Default Ignored Headers

- **Metadata**: `content-type`, `content-length`, `accept`, `user-agent`, `host`, `origin`, `referer`
- **Cache**: `cache-control`, `etag`, `last-modified`, `if-none-match`
- **CORS**: `access-control-allow-*`
- **Other**: `date`, `server`, `sec-ch-ua`, `sec-fetch-*`

---

## Output Format (JSON)

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

### Report Structure

| Section | Description |
|---------|-------------|
| `summary` | Statistics (unique ID count, flow count, etc.) |
| `flows` | IDs listed per communication unit |
| `tracked_ids` | Per-ID details (where it originated and where it was used) |
| `potential_idor` | List of IDOR vulnerability candidates |

---

## CLI Command Details (cli.py)

### Main Command

```bash
idotaku [OPTIONS]
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--port` | `-p` | 8080 | Proxy port |
| `--web-port` | `-w` | 8081 | Web UI port |
| `--output` | `-o` | `id_tracker_report.json` | Output file |
| `--min-numeric` | | 100 | Minimum value for numeric IDs |
| `--no-browser` | | false | Disable automatic browser launch |
| `--browser` | | auto | Browser to use (chrome/edge/firefox/auto) |
| `--config` | `-c` | none | Config file path |
| `--interactive` | `-i` | false | Launch in interactive mode |

### report - Summary Display

```bash
idotaku report [REPORT_FILE]
```

### chain - Parameter Chain Detection

```bash
idotaku chain [REPORT_FILE] [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--top N` | Number of chains to display (default: 10) |
| `--min-depth N` | Minimum depth (default: 2) |
| `--html FILE` | Export as interactive HTML |
| `--domains PATTERNS` | Filter by domains (comma-separated, wildcards supported) |

**Domain filter examples**:
```bash
# Specific domain only
idotaku chain --domains "api.example.com"

# Multiple domains (with wildcards)
idotaku chain --domains "api.example.com,*.internal.com"
```

**Chain detection algorithm**:
1. Build a dependency graph between flows (response ID → used in request)
2. Identify root nodes (flows with no dependencies)
3. Construct trees via DFS from each root
4. Score = depth × 100 + node count

**Cycle detection**:
- Cycles are detected by API pattern (method + normalized path)
- Example: `GET /users/123` and `GET /users/456` share the same pattern
- When a cycle is detected, a reference node is returned and child nodes are deferred to the original node

### sequence - Sequence Display

```bash
idotaku sequence [REPORT_FILE] [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--limit N` | Number of API calls to display (default: 30) |
| `--html FILE` | Export as interactive HTML |

### lifeline - ID Lifeline Display

```bash
idotaku lifeline [REPORT_FILE] [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--min-uses N` | Minimum usage count (default: 1) |
| `--sort TYPE` | Sort order: lifespan/uses/first |

### version - Version Display

```bash
idotaku version
```

### interactive - Interactive Mode

```bash
idotaku interactive
# or
idotaku -i
```

**Features**:
- Select commands with arrow keys
- Auto-detect and select report files
- Checkbox selection for domain filters
- Press Enter to skip (uses default values)

**Target users**:
- Beginners: Learn commands with guided menus
- Advanced: Quickly skip with Enter

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| mitmproxy | >=10.0.0 | Proxy engine |
| click | >=8.0.0 | CLI framework |
| rich | >=13.0.0 | Terminal output formatting |
| questionary | >=2.0.0 | Interactive prompts |

---

## Limitations

1. **No WebSocket support**: HTTP/HTTPS only
2. **No binary body support**: Only JSON/text is analyzed
3. **No GraphQL support**: Query structure is not parsed (processed as JSON body)
4. **Auth token false positives**: Long tokens may be detected as IDs

---

## Future Enhancements

### Implemented

- [x] Domain filtering
- [x] Custom ID pattern definitions
- [x] Parameter chain detection and visualization
- [x] Sequence display
- [x] ID lifeline display
- [x] Interactive CLI (interactive mode)
- [x] Domain filter option for chain command
- [x] Interactive HTML export for chain / sequence

### Not Yet Implemented

- [ ] Real-time Web UI
- [ ] ID substitution testing (automatic replay)
- [ ] HAR format export
- [ ] GraphQL support
- [ ] WebSocket support
- [ ] Response status code recording