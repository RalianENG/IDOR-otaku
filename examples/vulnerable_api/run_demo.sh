#!/usr/bin/env bash
# =============================================================================
# idotaku Demo Runner
#
# Starts the vulnerable API, proxies traffic through idotaku, runs the
# automated attack scenario, and generates analysis reports.
#
# Usage:
#   bash run_demo.sh
#   bash run_demo.sh --api-port 4000 --proxy-port 9090
# =============================================================================
set -euo pipefail

# ---------- Configuration ----------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
API_PORT="${API_PORT:-3000}"
PROXY_PORT="${PROXY_PORT:-8080}"
REPORT_FILE="test_report.json"
CONFIG_FILE="idotaku.yaml"
SERVER_PID=""
PROXY_PID=""

# ---------- Parse arguments ----------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --api-port)  API_PORT="$2"; shift 2 ;;
        --proxy-port) PROXY_PORT="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: bash run_demo.sh [--api-port PORT] [--proxy-port PORT]"
            echo ""
            echo "Options:"
            echo "  --api-port PORT    API server port (default: 3000)"
            echo "  --proxy-port PORT  Proxy port (default: 8080)"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# ---------- Color helpers ----------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }
header()  { echo -e "\n${BOLD}===== $* =====${NC}"; }

# ---------- Cleanup ----------
cleanup() {
    if [[ -n "$PROXY_PID" ]] && kill -0 "$PROXY_PID" 2>/dev/null; then
        info "Stopping proxy (PID $PROXY_PID)..."
        kill "$PROXY_PID" 2>/dev/null || true
        wait "$PROXY_PID" 2>/dev/null || true
    fi
    if [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
        info "Stopping API server (PID $SERVER_PID)..."
        kill "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT

# ---------- Step 1: Prerequisites ----------
header "Checking prerequisites"

for cmd in python3 mitmdump idotaku; do
    if command -v "$cmd" &>/dev/null; then
        success "$cmd found: $(command -v "$cmd")"
    else
        error "$cmd not found. Please install it first."
        if [[ "$cmd" == "idotaku" ]]; then
            echo "  pip install -e .  (from the project root)"
        fi
        exit 1
    fi
done

# Check port availability
check_port() {
    local port=$1
    if python3 -c "
import socket, sys
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    s.bind(('127.0.0.1', $port))
    s.close()
except OSError:
    sys.exit(1)
" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

if ! check_port "$API_PORT"; then
    error "Port $API_PORT is already in use. Free it or use --api-port."
    exit 1
fi
if ! check_port "$PROXY_PORT"; then
    error "Port $PROXY_PORT is already in use. Free it or use --proxy-port."
    exit 1
fi
success "Ports $API_PORT and $PROXY_PORT are available"

# ---------- Step 2: Install dependencies ----------
header "Installing demo dependencies"
cd "$SCRIPT_DIR"
pip install -r requirements.txt --quiet
success "Dependencies installed"

# ---------- Step 3: Start API server ----------
header "Starting vulnerable API server (port $API_PORT)"
python3 server.py --port "$API_PORT" &
SERVER_PID=$!
info "Server PID: $SERVER_PID"

# Wait for health check
DEADLINE=$((SECONDS + 15))
while [[ $SECONDS -lt $DEADLINE ]]; do
    if curl -sf "http://localhost:$API_PORT/api/health" >/dev/null 2>&1; then
        success "API server is ready"
        break
    fi
    sleep 0.5
done
if [[ $SECONDS -ge $DEADLINE ]]; then
    error "API server failed to start within 15 seconds"
    exit 1
fi

# ---------- Step 4: Start mitmdump proxy ----------
header "Starting mitmdump proxy (port $PROXY_PORT)"

TRACKER_SCRIPT=$(python3 -c "from idotaku.browser import get_tracker_script_path; print(get_tracker_script_path())")
info "Tracker: $TRACKER_SCRIPT"

mitmdump \
    -s "$TRACKER_SCRIPT" \
    --listen-port "$PROXY_PORT" \
    --set "idotaku_config=$SCRIPT_DIR/$CONFIG_FILE" \
    --set "idotaku_output=$SCRIPT_DIR/$REPORT_FILE" \
    --set connection_strategy=lazy \
    --quiet &
PROXY_PID=$!
info "Proxy PID: $PROXY_PID"

# Wait for proxy to be ready
DEADLINE=$((SECONDS + 15))
while [[ $SECONDS -lt $DEADLINE ]]; do
    if curl -sf --proxy "http://localhost:$PROXY_PORT" "http://localhost:$API_PORT/api/health" >/dev/null 2>&1; then
        success "Proxy is ready"
        break
    fi
    sleep 0.5
done
if [[ $SECONDS -ge $DEADLINE ]]; then
    error "Proxy failed to start within 15 seconds"
    exit 1
fi

# ---------- Step 5: Run test scenario ----------
header "Running test scenario"
python3 test_scenario.py \
    --api "http://localhost:$API_PORT" \
    --proxy "http://localhost:$PROXY_PORT"
success "Test scenario complete"

# ---------- Step 6: Stop proxy (triggers report generation) ----------
header "Stopping proxy (generating report)"
kill "$PROXY_PID" 2>/dev/null || true
wait "$PROXY_PID" 2>/dev/null || true
PROXY_PID=""
sleep 1

if [[ -f "$SCRIPT_DIR/$REPORT_FILE" ]]; then
    success "Report generated: $REPORT_FILE"
else
    error "Report file not found: $REPORT_FILE"
    exit 1
fi

# ---------- Step 7: Stop server ----------
kill "$SERVER_PID" 2>/dev/null || true
wait "$SERVER_PID" 2>/dev/null || true
SERVER_PID=""
success "API server stopped"

# ---------- Step 8: Run analysis ----------
header "Report Summary"
idotaku report "$SCRIPT_DIR/$REPORT_FILE"

header "Risk Scores"
idotaku score "$SCRIPT_DIR/$REPORT_FILE"

header "Parameter Chains"
idotaku chain "$SCRIPT_DIR/$REPORT_FILE"

header "Cross-User Access"
idotaku auth "$SCRIPT_DIR/$REPORT_FILE"

# ---------- Step 9: Generate HTML exports ----------
header "Generating HTML exports"
idotaku chain "$SCRIPT_DIR/$REPORT_FILE" --html "$SCRIPT_DIR/chain.html"
success "Chain HTML: $SCRIPT_DIR/chain.html"

idotaku sequence "$SCRIPT_DIR/$REPORT_FILE" --html "$SCRIPT_DIR/sequence.html"
success "Sequence HTML: $SCRIPT_DIR/sequence.html"

# ---------- Done ----------
echo ""
echo -e "${GREEN}${BOLD}Demo complete!${NC}"
echo ""
echo "Generated files:"
echo "  Report:   $SCRIPT_DIR/$REPORT_FILE"
echo "  Chain:    $SCRIPT_DIR/chain.html"
echo "  Sequence: $SCRIPT_DIR/sequence.html"
echo ""
echo "Open the HTML files in a browser to explore interactive visualizations."
