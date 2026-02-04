"""CSS styles for sequence diagram HTML export."""

SEQUENCE_STYLES = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0d1117;
    color: #c9d1d9;
    min-height: 100vh;
}

/* Main container */
.seq-panel {
    padding: 24px;
    max-width: 100%;
    overflow-x: auto;
}
.seq-panel h1 {
    color: #58a6ff;
    font-size: 1.4em;
    margin-bottom: 6px;
}
.seq-panel .subtitle {
    color: #8b949e;
    font-size: 0.85em;
    margin-bottom: 20px;
    border-bottom: 1px solid #30363d;
    padding-bottom: 10px;
}

/* Lifeline header */
.seq-header {
    display: flex;
    position: sticky;
    top: 0;
    z-index: 20;
    background: #0d1117;
    border-bottom: 2px solid #30363d;
    padding-bottom: 8px;
    margin-bottom: 0;
}
.seq-header-cell {
    flex: 0 0 var(--col-width, 160px);
    text-align: center;
    padding: 8px 4px;
    position: relative;
}
.seq-header-cell .lifeline-name {
    font-size: 0.78em;
    font-weight: 600;
    color: #c9d1d9;
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 10px;
    display: inline-block;
    max-width: 150px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.seq-header-cell.client .lifeline-name {
    background: #1c2333;
    border-color: #58a6ff;
    color: #58a6ff;
}

/* Flow rows */
.seq-body {
    position: relative;
}
.seq-row {
    display: flex;
    position: relative;
    min-height: 60px;
    align-items: stretch;
}
.seq-row:hover {
    background: rgba(88, 166, 255, 0.03);
}

/* Lifeline column cells (vertical dashed lines) */
.seq-cell {
    flex: 0 0 var(--col-width, 160px);
    position: relative;
    min-height: 60px;
}
.seq-cell::after {
    content: '';
    position: absolute;
    left: 50%;
    top: 0;
    bottom: 0;
    width: 1px;
    background: repeating-linear-gradient(
        to bottom,
        #30363d 0px,
        #30363d 6px,
        transparent 6px,
        transparent 12px
    );
    pointer-events: none;
}

/* Row index & timestamp */
.seq-row-meta {
    position: absolute;
    left: -4px;
    top: 50%;
    transform: translateY(-50%);
    z-index: 5;
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    pointer-events: none;
}
.seq-row-index {
    font-size: 0.7em;
    color: #3fb950;
    font-weight: bold;
}
.seq-row-time {
    font-size: 0.65em;
    color: #6e7681;
    font-family: monospace;
}

/* Arrow container - positioned over lifeline cells */
.seq-arrow-container {
    position: absolute;
    top: 0;
    bottom: 0;
    display: flex;
    flex-direction: column;
    justify-content: center;
    z-index: 10;
    pointer-events: none;
}

/* Request arrow (solid, right-pointing) */
.seq-arrow {
    position: relative;
    height: 2px;
    pointer-events: auto;
}
.seq-arrow.request {
    background: #58a6ff;
}
.seq-arrow.request::after {
    content: '';
    position: absolute;
    right: -1px;
    top: -5px;
    width: 0;
    height: 0;
    border-left: 8px solid #58a6ff;
    border-top: 6px solid transparent;
    border-bottom: 6px solid transparent;
}

/* Response arrow (dashed, left-pointing) */
.seq-arrow.response {
    background: repeating-linear-gradient(
        to right,
        #8b949e 0px,
        #8b949e 6px,
        transparent 6px,
        transparent 10px
    );
    margin-top: 12px;
}
.seq-arrow.response::after {
    content: '';
    position: absolute;
    left: -1px;
    top: -5px;
    width: 0;
    height: 0;
    border-right: 8px solid #8b949e;
    border-top: 6px solid transparent;
    border-bottom: 6px solid transparent;
}

/* Method badge on arrow */
.seq-arrow-label {
    position: absolute;
    top: -20px;
    white-space: nowrap;
    display: flex;
    align-items: center;
    gap: 6px;
    pointer-events: auto;
}
.seq-arrow.request .seq-arrow-label {
    left: 8px;
}
.seq-arrow.response .seq-arrow-label {
    right: 8px;
}

/* HTTP Method badges */
.method {
    display: inline-block;
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 0.68em;
    font-weight: bold;
}
.method.GET { background: #238636; color: #fff; }
.method.POST { background: #a371f7; color: #fff; }
.method.PUT { background: #f0883e; color: #fff; }
.method.DELETE { background: #f85149; color: #fff; }
.method.PATCH { background: #3fb950; color: #fff; }
.method.HEAD { background: #6e7681; color: #fff; }
.method.OPTIONS { background: #6e7681; color: #fff; }

/* Arrow path label */
.arrow-path {
    font-size: 0.75em;
    color: #8b949e;
    font-family: monospace;
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
}

/* ID chips on arrows */
.seq-chips {
    position: absolute;
    bottom: 4px;
    display: flex;
    gap: 3px;
    flex-wrap: nowrap;
    overflow: hidden;
    pointer-events: auto;
}
.seq-arrow.request .seq-chips {
    left: 8px;
}
.seq-arrow.response .seq-chips {
    right: 8px;
}

.id-chip {
    display: inline-block;
    font-family: monospace;
    font-size: 0.7em;
    padding: 1px 6px;
    border-radius: 3px;
    cursor: pointer;
    white-space: nowrap;
    max-width: 100px;
    overflow: hidden;
    text-overflow: ellipsis;
    transition: opacity 0.2s, box-shadow 0.2s, transform 0.15s;
}
.id-chip.consumes {
    background: rgba(240, 136, 62, 0.2);
    color: #f0883e;
    border: 1px solid rgba(240, 136, 62, 0.4);
}
.id-chip.produces {
    background: rgba(63, 185, 80, 0.2);
    color: #3fb950;
    border: 1px solid rgba(63, 185, 80, 0.4);
}
.id-chip.idor {
    border-color: #f85149;
    box-shadow: 0 0 0 1px rgba(248, 81, 73, 0.3);
}

/* Highlight state */
.id-chip.highlighted {
    opacity: 1 !important;
    box-shadow: 0 0 8px rgba(88, 166, 255, 0.6);
    transform: scale(1.08);
    z-index: 15;
}
.id-chip.highlighted.consumes {
    background: rgba(240, 136, 62, 0.5);
    border-color: #f0883e;
}
.id-chip.highlighted.produces {
    background: rgba(63, 185, 80, 0.5);
    border-color: #3fb950;
}
body.id-dimmed .id-chip:not(.highlighted) {
    opacity: 0.25;
}
body.id-dimmed .seq-row:not(.row-highlighted) {
    opacity: 0.5;
}
body.id-dimmed .seq-row.row-highlighted {
    background: rgba(88, 166, 255, 0.05);
}

/* More chips button */
.chips-more {
    font-size: 0.65em;
    color: #6e7681;
    padding: 1px 4px;
    cursor: pointer;
    white-space: nowrap;
}
.chips-more:hover {
    color: #c9d1d9;
}

/* ID Summary panel (floating) */
.id-summary-panel {
    position: fixed;
    bottom: 24px;
    right: 24px;
    width: 320px;
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 16px;
    z-index: 100;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
    transform: translateY(20px);
    opacity: 0;
    transition: transform 0.2s ease-out, opacity 0.2s;
    pointer-events: none;
}
.id-summary-panel.visible {
    transform: translateY(0);
    opacity: 1;
    pointer-events: auto;
}
.id-summary-panel .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid #30363d;
}
.id-summary-panel .panel-title {
    font-family: monospace;
    font-size: 0.95em;
    color: #79c0ff;
    font-weight: bold;
    max-width: 250px;
    overflow: hidden;
    text-overflow: ellipsis;
}
.id-summary-panel .panel-close {
    cursor: pointer;
    color: #8b949e;
    font-size: 1.2em;
    line-height: 1;
    padding: 2px 6px;
    border-radius: 4px;
}
.id-summary-panel .panel-close:hover {
    background: #30363d;
    color: #c9d1d9;
}
.id-summary-panel .panel-row {
    display: flex;
    justify-content: space-between;
    margin-bottom: 6px;
    font-size: 0.82em;
}
.id-summary-panel .panel-label {
    color: #8b949e;
}
.id-summary-panel .panel-value {
    color: #c9d1d9;
    font-family: monospace;
    text-align: right;
    max-width: 180px;
    overflow: hidden;
    text-overflow: ellipsis;
}
.id-summary-panel .idor-badge {
    display: inline-block;
    background: rgba(248, 81, 73, 0.2);
    color: #f85149;
    border: 1px solid rgba(248, 81, 73, 0.4);
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 0.8em;
    font-weight: bold;
    margin-top: 8px;
}

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

/* Hint bar */
.hint {
    position: fixed;
    bottom: 20px;
    left: 50%;
    transform: translateX(-50%);
    background: #30363d;
    padding: 8px 14px;
    border-radius: 6px;
    font-size: 0.8em;
    color: #8b949e;
    z-index: 50;
    transition: opacity 0.3s;
}
.hint.hidden {
    opacity: 0;
    pointer-events: none;
}

/* Empty state */
.empty-state {
    text-align: center;
    padding: 60px 20px;
    color: #8b949e;
}
.empty-state h2 {
    color: #58a6ff;
    margin-bottom: 8px;
}
"""
