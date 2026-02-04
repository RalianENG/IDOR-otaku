"""JavaScript code for sequence diagram HTML export."""

# Note: {sequence_json} placeholder will be replaced with actual data
SEQUENCE_SCRIPTS = """
const seqData = {sequence_json};

const COL_WIDTH = 160;
const MAX_CHIP_DISPLAY = 4;

let activeIdValue = null;

function escapeHtml(s) {
    return String(s).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/'/g,'&#39;');
}

function truncate(s, max) {
    s = String(s);
    return s.length > max ? s.substring(0, max - 2) + '..' : s;
}

// Render lifeline headers
function renderHeaders() {
    const header = document.getElementById('seq-header');
    let html = '';
    for (let i = 0; i < seqData.lifelines.length; i++) {
        const ll = seqData.lifelines[i];
        const isClient = (i === 0);
        html += '<div class="seq-header-cell' + (isClient ? ' client' : '') + '">';
        html += '<span class="lifeline-name" title="' + escapeHtml(ll) + '">' + escapeHtml(truncate(ll, 22)) + '</span>';
        html += '</div>';
    }
    header.innerHTML = html;
}

// Render a single flow row
function renderFlowRow(flow, idx) {
    const lifelineCount = seqData.lifelines.length;
    const targetCol = seqData.flow_lifeline_map[idx];

    // Build cells for lifeline columns
    let cellsHtml = '';
    for (let c = 0; c < lifelineCount; c++) {
        cellsHtml += '<div class="seq-cell"></div>';
    }

    // Request arrow: Client (col 0) -> Endpoint (col targetCol)
    const arrowLeft = COL_WIDTH / 2;
    const arrowRight = targetCol * COL_WIDTH + COL_WIDTH / 2;
    const arrowWidth = Math.abs(arrowRight - arrowLeft);
    const arrowStart = Math.min(arrowLeft, arrowRight);

    // Request IDs chips
    const reqIds = flow.request_ids || [];
    let reqChipsHtml = '';
    if (reqIds.length > 0) {
        reqChipsHtml = renderChips(reqIds, 'consumes', idx);
    }

    // Response IDs chips
    const resIds = flow.response_ids || [];
    let resChipsHtml = '';
    if (resIds.length > 0) {
        resChipsHtml = renderChips(resIds, 'produces', idx);
    }

    // Method badge + path label
    const method = flow.method || '?';
    const path = flow.path || '/';
    const labelHtml = '<span class="method ' + method + '">' + method + '</span>'
        + '<span class="arrow-path" title="' + escapeHtml(flow.url || '') + '">' + escapeHtml(truncate(path, 30)) + '</span>';

    // Timestamp
    const ts = flow.timestamp || '';
    const timePart = ts.indexOf('T') >= 0 ? ts.split('T')[1].substring(0, 8) : '';

    // Build arrow HTML
    let arrowHtml = '';

    // Request arrow (solid, right-pointing)
    if (targetCol > 0) {
        arrowHtml += '<div class="seq-arrow-container" style="left:' + arrowStart + 'px;width:' + arrowWidth + 'px;">';
        arrowHtml += '<div class="seq-arrow request" style="width:100%">';
        arrowHtml += '<div class="seq-arrow-label">' + labelHtml + '</div>';
        if (reqChipsHtml) {
            arrowHtml += '<div class="seq-chips">' + reqChipsHtml + '</div>';
        }
        arrowHtml += '</div>';

        // Response arrow (dashed, left-pointing)
        arrowHtml += '<div class="seq-arrow response" style="width:100%">';
        if (resChipsHtml) {
            arrowHtml += '<div class="seq-chips">' + resChipsHtml + '</div>';
        }
        arrowHtml += '</div>';
        arrowHtml += '</div>';
    } else {
        // Self-call (rare edge case): render as a small loop
        arrowHtml += '<div class="seq-arrow-container" style="left:' + (COL_WIDTH / 2) + 'px;width:60px;">';
        arrowHtml += '<div class="seq-arrow request" style="width:100%">';
        arrowHtml += '<div class="seq-arrow-label">' + labelHtml + '</div>';
        arrowHtml += '</div>';
        arrowHtml += '</div>';
    }

    // Row meta (index + time)
    let metaHtml = '<div class="seq-row-meta">'
        + '<span class="seq-row-index">#' + (idx + 1) + '</span>'
        + '<span class="seq-row-time">' + escapeHtml(timePart) + '</span>'
        + '</div>';

    return '<div class="seq-row" data-row-idx="' + idx + '">'
        + metaHtml + cellsHtml + arrowHtml
        + '</div>';
}

// Render ID chips
function renderChips(ids, chipClass, rowIdx) {
    let html = '';
    const display = ids.slice(0, MAX_CHIP_DISPLAY);
    const remaining = ids.length - display.length;

    for (let i = 0; i < display.length; i++) {
        const id = display[i];
        const val = id.value || '';
        const label = id.field ? id.field : truncate(val, 12);
        const isIdor = seqData.idor_values && seqData.idor_values.indexOf(val) >= 0;
        const idorClass = isIdor ? ' idor' : '';
        html += '<span class="id-chip ' + chipClass + idorClass + '"'
            + ' data-id-value="' + escapeHtml(val) + '"'
            + ' data-row-idx="' + rowIdx + '"'
            + ' title="' + escapeHtml(val) + ' (' + escapeHtml(id.location || '') + ')"'
            + ' onclick="onChipClick(event, \\'' + escapeHtml(val).replace(/'/g, "\\\\'") + '\\')">'
            + escapeHtml(truncate(label, 12))
            + '</span>';
    }

    if (remaining > 0) {
        html += '<span class="chips-more">+' + remaining + '</span>';
    }

    return html;
}

// Render full sequence diagram
function renderSequence() {
    if (!seqData.flows || seqData.flows.length === 0) {
        document.getElementById('seq-body').innerHTML =
            '<div class="empty-state"><h2>No API flows</h2><p>No flows found in report data.</p></div>';
        return;
    }

    // Set CSS variable for column width
    document.documentElement.style.setProperty('--col-width', COL_WIDTH + 'px');

    // Set minimum width for horizontal scroll
    const totalWidth = seqData.lifelines.length * COL_WIDTH + 40;
    const body = document.getElementById('seq-body');
    const header = document.getElementById('seq-header');
    body.style.minWidth = totalWidth + 'px';
    header.style.minWidth = totalWidth + 'px';

    renderHeaders();

    let rowsHtml = '';
    for (let i = 0; i < seqData.flows.length; i++) {
        rowsHtml += renderFlowRow(seqData.flows[i], i);
    }
    body.innerHTML = rowsHtml;
}

// ID chip click handler
function onChipClick(event, idValue) {
    event.stopPropagation();

    if (activeIdValue === idValue) {
        clearHighlight();
        return;
    }

    highlightId(idValue);
}

// Highlight all chips with the same ID value
function highlightId(idValue) {
    activeIdValue = idValue;
    document.body.classList.add('id-dimmed');

    // Remove all previous highlights
    var allChips = document.querySelectorAll('.id-chip');
    for (var i = 0; i < allChips.length; i++) {
        allChips[i].classList.remove('highlighted');
    }
    var allRows = document.querySelectorAll('.seq-row');
    for (var i = 0; i < allRows.length; i++) {
        allRows[i].classList.remove('row-highlighted');
    }

    // Highlight matching chips and rows
    var matchingChips = document.querySelectorAll('.id-chip[data-id-value="' + CSS.escape(idValue) + '"]');
    for (var i = 0; i < matchingChips.length; i++) {
        matchingChips[i].classList.add('highlighted');
        var row = matchingChips[i].closest('.seq-row');
        if (row) row.classList.add('row-highlighted');
    }

    // Show summary panel
    showIdSummary(idValue);

    // Hide hint
    var hint = document.getElementById('hint');
    if (hint) hint.classList.add('hidden');
}

// Clear all highlights
function clearHighlight() {
    activeIdValue = null;
    document.body.classList.remove('id-dimmed');

    var allChips = document.querySelectorAll('.id-chip');
    for (var i = 0; i < allChips.length; i++) {
        allChips[i].classList.remove('highlighted');
    }
    var allRows = document.querySelectorAll('.seq-row');
    for (var i = 0; i < allRows.length; i++) {
        allRows[i].classList.remove('row-highlighted');
    }

    hideIdSummary();
}

// Show ID summary panel
function showIdSummary(idValue) {
    var panel = document.getElementById('id-summary');
    if (!panel) return;

    var info = seqData.id_info[idValue];
    if (!info) {
        // Minimal info if not in tracked_ids
        panel.querySelector('.panel-title').textContent = idValue;
        panel.querySelector('#summary-type').textContent = '?';
        panel.querySelector('#summary-origin').textContent = 'Unknown';
        panel.querySelector('#summary-usage').textContent = '?';
        var idorEl = panel.querySelector('#summary-idor');
        idorEl.style.display = 'none';
        panel.classList.add('visible');
        return;
    }

    panel.querySelector('.panel-title').textContent = idValue;
    panel.querySelector('#summary-type').textContent = info.type || '?';

    // Origin info
    if (info.origin_flow !== null && info.origin_flow !== undefined) {
        var originFlow = seqData.flows[info.origin_flow];
        if (originFlow) {
            var originText = (originFlow.method || '?') + ' ' + truncate(originFlow.path || '/', 25);
            panel.querySelector('#summary-origin').textContent = originText;
        } else {
            panel.querySelector('#summary-origin').textContent = 'Flow #' + (info.origin_flow + 1);
        }
    } else {
        panel.querySelector('#summary-origin').textContent = 'No origin found';
    }

    panel.querySelector('#summary-usage').textContent = (info.usage_count || 0) + ' time(s)';

    // IDOR badge
    var isIdor = seqData.idor_values && seqData.idor_values.indexOf(idValue) >= 0;
    var idorEl = panel.querySelector('#summary-idor');
    idorEl.style.display = isIdor ? 'inline-block' : 'none';

    panel.classList.add('visible');
}

// Hide ID summary panel
function hideIdSummary() {
    var panel = document.getElementById('id-summary');
    if (panel) panel.classList.remove('visible');
}

// Background click to clear
document.addEventListener('click', function(e) {
    if (activeIdValue && !e.target.closest('.id-chip') && !e.target.closest('.id-summary-panel')) {
        clearHighlight();
    }
});

// Initialize
renderSequence();
"""
