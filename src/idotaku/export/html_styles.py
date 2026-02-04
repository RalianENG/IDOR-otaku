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

/* Main Tree Panel */
.tree-panel {
    padding: 24px;
    max-width: 1400px;
    margin: 0 auto;
}
.tree-panel h1 {
    color: #58a6ff;
    font-size: 1.4em;
    margin-bottom: 20px;
    border-bottom: 1px solid #30363d;
    padding-bottom: 10px;
}

/* Tree Root & Header */
.tree-root {
    margin-bottom: 40px;
}
.tree-header {
    background: #161b22;
    padding: 14px 18px;
    border-radius: 8px;
    margin-bottom: 16px;
    border-left: 4px solid #58a6ff;
}
.tree-header .rank {
    color: #f0883e;
    font-weight: bold;
    font-size: 1.1em;
    margin-right: 12px;
}
.tree-header .stats {
    color: #8b949e;
    font-size: 0.85em;
    margin-left: 12px;
}

/* Chain Summary (mini flow) */
.chain-summary {
    margin-top: 8px;
    font-size: 0.82em;
    color: #8b949e;
    font-family: monospace;
    white-space: nowrap;
    overflow-x: auto;
    padding: 4px 0;
}
.chain-summary .summary-step {
    color: #c9d1d9;
}
.chain-summary .summary-arrow {
    color: #484f58;
    margin: 0 6px;
}
.chain-summary .method {
    font-size: 0.9em;
}

/* Tree Container */
.tree-container {
    position: relative;
    padding-left: 0;
}

/* HTTP Method Badges */
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

/* Card Node */
.node-card {
    position: relative;
    z-index: 2;
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 0;
    margin: 8px 0;
    max-width: 700px;
    transition: border-color 0.15s, box-shadow 0.15s;
}
.node-card:hover {
    border-color: #58a6ff;
    box-shadow: 0 0 0 1px rgba(88, 166, 255, 0.3);
}
.node-card.from-cycle {
    border-left: 3px solid #f0883e;
}
.node-card.highlight-target {
    animation: highlight-pulse 0.5s ease-in-out 3;
}
@keyframes highlight-pulse {
    0%, 100% { border-color: #58a6ff; box-shadow: 0 0 0 0 rgba(88, 166, 255, 0.7); }
    50% { border-color: #79c0ff; box-shadow: 0 0 0 4px rgba(88, 166, 255, 0); }
}

/* Via Parameter Banner - shows which param connects this card to its parent */
.node-via-banner {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 5px 14px;
    background: rgba(121, 192, 255, 0.08);
    border-bottom: 1px solid rgba(121, 192, 255, 0.15);
    border-radius: 8px 8px 0 0;
    font-size: 0.78em;
    color: #8b949e;
    flex-wrap: wrap;
}
.node-via-banner .via-label {
    color: #6e7681;
    font-style: italic;
}
.node-via-banner .via-param {
    font-family: monospace;
    color: #79c0ff;
    background: rgba(121, 192, 255, 0.12);
    padding: 1px 8px;
    border-radius: 4px;
    border: 1px solid rgba(121, 192, 255, 0.25);
}
.node-via-banner .via-arrow {
    color: #484f58;
}

/* Card Header */
.node-card-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 14px;
    cursor: default;
}
.node-index {
    color: #3fb950;
    font-weight: bold;
    font-size: 0.85em;
    min-width: 32px;
}
.path {
    color: #c9d1d9;
    font-size: 0.9em;
    cursor: pointer;
}
.path:hover {
    color: #79c0ff;
    text-decoration: underline;
}
.domain {
    color: #8b949e;
    font-size: 0.8em;
    margin-left: 8px;
    padding: 2px 6px;
    background: #21262d;
    border-radius: 4px;
}

/* Card Body - Inline Params */
.node-card-body {
    border-top: 1px solid #21262d;
    padding: 8px 14px 10px;
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
}
.param-section {
    flex: 1;
    min-width: 180px;
}
.param-section-title {
    font-size: 0.72em;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 4px;
    font-weight: 600;
}
.param-section-title.consumes { color: #f0883e; }
.param-section-title.produces { color: #3fb950; }

.param-chip {
    display: inline-block;
    font-family: monospace;
    font-size: 0.78em;
    padding: 2px 8px;
    border-radius: 4px;
    margin: 2px 4px 2px 0;
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    vertical-align: middle;
}
.param-chip.consumes {
    background: rgba(240, 136, 62, 0.15);
    color: #f0883e;
    border: 1px solid rgba(240, 136, 62, 0.3);
}
.param-chip.produces {
    background: rgba(63, 185, 80, 0.15);
    color: #3fb950;
    border: 1px solid rgba(63, 185, 80, 0.3);
}
.param-chip.produces.flows-to-child {
    background: rgba(63, 185, 80, 0.25);
    border-color: rgba(63, 185, 80, 0.5);
    font-weight: bold;
}

/* Param expand/collapse */
.param-expand-btn {
    color: #8b949e;
    font-size: 0.75em;
    cursor: pointer;
    padding: 2px 6px;
    border-radius: 4px;
    background: #21262d;
    border: none;
    margin-top: 4px;
    display: inline-block;
}
.param-expand-btn:hover { background: #30363d; color: #c9d1d9; }
.params-collapsed .param-chip:nth-child(n+7) { display: none; }

/* Toggle button */
.toggle-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    background: #30363d;
    border-radius: 4px;
    font-size: 0.8em;
    cursor: pointer;
    color: #c9d1d9;
    flex-shrink: 0;
    user-select: none;
}
.toggle-btn:hover { background: #484f58; }

/* Cycle Reference Node */
.node-cycle-ref {
    position: relative;
    z-index: 2;
    background: transparent;
    border: 1px dashed #f85149;
    border-radius: 8px;
    padding: 8px 14px;
    margin: 8px 0;
    color: #8b949e;
    font-style: italic;
    cursor: pointer;
    max-width: 700px;
    transition: background 0.15s;
}
.node-cycle-ref:hover {
    background: rgba(248, 81, 73, 0.08);
}
.node-cycle-ref .cycle-target {
    color: #3fb950;
    font-weight: bold;
    font-style: normal;
}
.node-cycle-ref .cycle-params {
    color: #6e7681;
    font-family: monospace;
    font-size: 0.85em;
}

/* Children container with tree lines and collapse animation */
.node-children {
    position: relative;
    overflow: hidden;
    transition: max-height 0.25s ease-out, opacity 0.2s;
}
.node-children.collapsed {
    max-height: 0 !important;
    opacity: 0;
}

/* Vertical tree line */
.node-children::before {
    content: '';
    position: absolute;
    left: var(--tree-line-x, 9px);
    top: 0;
    bottom: 0;
    width: 2px;
    background: #3d444d;
    z-index: 3;
    pointer-events: none;
}

/* Horizontal branch line on each child card */
.node-children > .node-card::after,
.node-children > .node-cycle-ref::after {
    content: '';
    position: absolute;
    left: calc(var(--tree-line-x, 9px) - var(--child-indent, 20px));
    top: 18px;
    width: calc(var(--child-indent, 20px) - var(--tree-line-x, 9px) - 1px);
    height: 2px;
    background: #3d444d;
    z-index: 3;
    pointer-events: none;
}

/* Branch dot at the connection point */
.node-children > .node-card::before,
.node-children > .node-cycle-ref::before {
    content: '';
    position: absolute;
    left: calc(var(--tree-line-x, 9px) - var(--child-indent, 20px) - 2px);
    top: 15px;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #3d444d;
    z-index: 4;
    pointer-events: none;
}

/* URL Popover */
.url-popover {
    position: fixed;
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 8px 12px;
    font-family: monospace;
    font-size: 0.82em;
    color: #79c0ff;
    word-break: break-all;
    max-width: 500px;
    z-index: 100;
    box-shadow: 0 4px 12px rgba(0,0,0,0.4);
    pointer-events: none;
    opacity: 0;
    transition: opacity 0.15s;
}
.url-popover.visible { opacity: 1; }

/* Security warning banner */
.security-warning {
    background: rgba(240, 136, 62, 0.12);
    border: 1px solid rgba(240, 136, 62, 0.4);
    border-radius: 8px;
    padding: 12px 18px;
    margin-bottom: 20px;
    font-size: 0.85em;
    color: #f0883e;
    line-height: 1.5;
}
.security-warning strong {
    color: #f0883e;
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
