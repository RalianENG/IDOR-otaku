"""CSS styles for HTML exports."""

# Chain tree export styles
CHAIN_STYLES = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0d1117;
    color: #c9d1d9;
    min-height: 100vh;
}

/* Main Tree Panel - Full Width */
.tree-panel {
    padding: 20px;
    padding-right: 40px;
    max-width: 1200px;
    margin: 0 auto;
}
.tree-panel h1 {
    color: #58a6ff;
    font-size: 1.4em;
    margin-bottom: 20px;
    border-bottom: 1px solid #30363d;
    padding-bottom: 10px;
}

/* Tree Styles */
.tree-root {
    margin-bottom: 30px;
}
.tree-header {
    background: #161b22;
    padding: 12px 16px;
    border-radius: 8px;
    margin-bottom: 8px;
    border-left: 4px solid #58a6ff;
}
.tree-header .rank {
    color: #f0883e;
    font-weight: bold;
    margin-right: 10px;
}
.tree-header .stats {
    color: #8b949e;
    font-size: 0.85em;
    margin-left: 10px;
}

.tree-node {
    margin-left: 24px;
    border-left: 2px solid #30363d;
    padding-left: 16px;
}
.node-item {
    padding: 8px 12px;
    margin: 4px 0;
    background: #161b22;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.15s;
    position: relative;
}
.node-item:hover {
    background: #1f2937;
    border-color: #58a6ff;
}
.node-item.selected {
    background: #1f3a5f;
    border-left: 3px solid #58a6ff;
}
.node-item.highlight-target {
    animation: highlight-pulse 0.5s ease-in-out 3;
}
@keyframes highlight-pulse {
    0%, 100% { background: #1f3a5f; box-shadow: 0 0 0 0 rgba(88, 166, 255, 0.7); }
    50% { background: #2d4a7c; box-shadow: 0 0 0 4px rgba(88, 166, 255, 0); }
}
.cycle-link:hover {
    background: #2d1f1f !important;
}
.cycle-badge:hover {
    background: rgba(248, 81, 73, 0.2);
    border-radius: 4px;
}
.node-item.from-cycle {
    border-left: 2px solid #f0883e;
    padding-left: 10px;
    margin-left: -2px;
}
.node-item::before {
    content: "";
    position: absolute;
    left: -18px;
    top: 50%;
    width: 16px;
    height: 2px;
    background: #30363d;
}

.method {
    display: inline-block;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.75em;
    font-weight: bold;
    margin-right: 8px;
}
.method.GET { background: #238636; color: #fff; }
.method.POST { background: #a371f7; color: #fff; }
.method.PUT { background: #f0883e; color: #fff; }
.method.DELETE { background: #f85149; color: #fff; }
.method.PATCH { background: #3fb950; color: #fff; }

.path { color: #c9d1d9; font-size: 0.9em; }
.param-arrow {
    color: #f0883e;
    margin: 0 6px;
}
.param-value {
    color: #79c0ff;
    font-family: monospace;
    font-size: 0.85em;
    background: #1f2937;
    padding: 2px 6px;
    border-radius: 4px;
}

.toggle-btn {
    display: inline-block;
    width: 18px;
    height: 18px;
    text-align: center;
    line-height: 18px;
    background: #30363d;
    border-radius: 4px;
    margin-right: 8px;
    font-size: 0.8em;
    cursor: pointer;
}
.toggle-btn:hover { background: #484f58; }

/* Slide-in Detail Panel */
.detail-overlay {
    position: fixed;
    top: 0;
    right: 0;
    width: 450px;
    height: 100vh;
    background: #161b22;
    box-shadow: -4px 0 20px rgba(0,0,0,0.5);
    transform: translateX(100%);
    transition: transform 0.25s ease-out;
    z-index: 1000;
    display: flex;
    flex-direction: column;
}
.detail-overlay.open {
    transform: translateX(0);
}
.detail-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    border-bottom: 1px solid #30363d;
    background: #0d1117;
}
.detail-header h2 {
    color: #58a6ff;
    font-size: 1.1em;
    margin: 0;
}
.close-btn {
    background: #30363d;
    border: none;
    color: #c9d1d9;
    width: 32px;
    height: 32px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 1.2em;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background 0.15s;
}
.close-btn:hover {
    background: #484f58;
}
.detail-body {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
}
.detail-section {
    margin-bottom: 20px;
}
.detail-section h3 {
    color: #8b949e;
    font-size: 0.85em;
    text-transform: uppercase;
    margin-bottom: 8px;
}
.detail-url {
    background: #0d1117;
    padding: 12px;
    border-radius: 6px;
    font-family: monospace;
    font-size: 0.9em;
    word-break: break-all;
    color: #79c0ff;
}
.detail-time {
    color: #8b949e;
    font-size: 0.9em;
}

.param-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85em;
}
.param-table th {
    text-align: left;
    padding: 8px;
    background: #0d1117;
    color: #8b949e;
    font-weight: normal;
}
.param-table td {
    padding: 8px;
    border-bottom: 1px solid #30363d;
}
.param-table .value {
    font-family: monospace;
    color: #79c0ff;
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.param-table .type { color: #a371f7; }
.param-table .location { color: #3fb950; }
.param-table .field { color: #f0883e; }

.badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 0.75em;
    margin-right: 4px;
}
.badge.req { background: #f0883e33; color: #f0883e; }
.badge.res { background: #3fb95033; color: #3fb950; }

/* Collapse animation */
.tree-children {
    overflow: hidden;
    transition: max-height 0.2s ease-out;
}
.tree-children.collapsed {
    max-height: 0 !important;
}

/* Keyboard hint */
.hint {
    position: fixed;
    bottom: 20px;
    right: 20px;
    background: #30363d;
    padding: 8px 14px;
    border-radius: 6px;
    font-size: 0.8em;
    color: #8b949e;
}
.hint kbd {
    background: #0d1117;
    padding: 2px 6px;
    border-radius: 4px;
    margin: 0 2px;
}
"""

# Common base styles shared by multiple exports
BASE_STYLES = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0d1117;
    color: #c9d1d9;
    min-height: 100vh;
}

.method {
    display: inline-block;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.75em;
    font-weight: bold;
    margin-right: 8px;
}
.method.GET { background: #238636; color: #fff; }
.method.POST { background: #a371f7; color: #fff; }
.method.PUT { background: #f0883e; color: #fff; }
.method.DELETE { background: #f85149; color: #fff; }
.method.PATCH { background: #3fb950; color: #fff; }
"""
