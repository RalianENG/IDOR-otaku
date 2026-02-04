"""JavaScript code for HTML exports."""

# Chain tree export scripts
# Note: {trees_json} placeholder will be replaced with actual data
CHAIN_SCRIPTS = """
const treesData = {trees_json};

// Configuration
const INDENT_PX = 20;
const MAX_INDENT_PX = 200;
const AUTO_COLLAPSE_DEPTH = 3;
const PARAM_COLLAPSE_THRESHOLD = 5;

function escapeHtml(s) {
    return String(s).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/'/g,'&#39;');
}

function truncatePath(path, max) {
    return path.length > max ? path.substring(0, max - 3) + '...' : path;
}

function truncateValue(val, max) {
    val = String(val);
    return val.length > max ? val.substring(0, max - 2) + '..' : val;
}

function formatParams(params, maxLen) {
    if (!params || params.length === 0) return '';
    if (params.length === 1) return truncateValue(params[0], maxLen);
    const first = truncateValue(params[0], maxLen - 6);
    return first + ' +' + (params.length - 1);
}

// Build a one-line summary of the chain by following the first child at each level
function buildChainSummary(tree) {
    const steps = [];
    let current = tree;
    const maxSteps = 8;
    while (current && current.type !== 'cycle_ref' && steps.length < maxSteps) {
        steps.push({ method: current.method, path: truncatePath(current.path, 25) });
        if (current.children && current.children.length > 0) {
            current = current.children.find(function(c) { return c.type !== 'cycle_ref'; }) || null;
        } else {
            current = null;
        }
    }
    return steps.map(function(s) {
        return '<span class="summary-step"><span class="method ' + s.method + '">' + s.method + '</span> ' + escapeHtml(s.path) + '</span>';
    }).join('<span class="summary-arrow">&#8594;</span>');
}

// Render cycle reference node
function renderCycleRef(node, depth) {
    const indent = Math.min(depth * INDENT_PX, MAX_INDENT_PX);
    let html = '<div class="node-cycle-ref cycle-ref-' + node.flow_idx + '"'
        + ' style="margin-left:' + indent + 'px"'
        + ' onclick="scrollToNode(' + node.target_index + ')">';
    html += '&#8617; <span class="cycle-target">[#' + node.target_index + ']</span>';
    if (node.via_params && node.via_params.length > 0) {
        html += ' <span class="cycle-params">via ' + escapeHtml(formatParams(node.via_params, 20)) + '</span>';
    }
    html += ' <span style="font-size:0.85em">(see above)</span>';
    html += '</div>';
    return html;
}

// Render inline param body (Consumes / Produces)
function renderCardBody(node) {
    const reqIds = node.request_ids || [];
    const resIds = node.response_ids || [];
    if (reqIds.length === 0 && resIds.length === 0) return '';

    // Determine which response values flow to children
    const childViaParams = new Set();
    if (node.children) {
        for (const child of node.children) {
            if (child.via_params) {
                child.via_params.forEach(function(p) { childViaParams.add(p); });
            }
        }
    }

    let html = '<div class="node-card-body">';

    // Consumes section
    if (reqIds.length > 0) {
        const manyParams = reqIds.length > PARAM_COLLAPSE_THRESHOLD;
        html += '<div class="param-section' + (manyParams ? ' params-collapsed' : '') + '">';
        html += '<div class="param-section-title consumes">Consumes (' + reqIds.length + ')</div>';
        for (const id of reqIds) {
            const label = id.field ? id.field : truncateValue(id.value, 20);
            html += '<span class="param-chip consumes" title="' + escapeHtml(id.location + ': ' + id.value) + '">'
                + escapeHtml(truncateValue(label, 24)) + '</span>';
        }
        if (manyParams) {
            html += '<button class="param-expand-btn" onclick="toggleParamExpand(event)">+'
                + (reqIds.length - PARAM_COLLAPSE_THRESHOLD) + ' more</button>';
        }
        html += '</div>';
    }

    // Produces section
    if (resIds.length > 0) {
        const manyParams = resIds.length > PARAM_COLLAPSE_THRESHOLD;
        html += '<div class="param-section' + (manyParams ? ' params-collapsed' : '') + '">';
        html += '<div class="param-section-title produces">Produces (' + resIds.length + ')</div>';
        for (const id of resIds) {
            const flowsToChild = childViaParams.has(id.value);
            const label = id.field ? id.field : truncateValue(id.value, 20);
            html += '<span class="param-chip produces' + (flowsToChild ? ' flows-to-child' : '') + '"'
                + ' title="' + escapeHtml(id.location + ': ' + id.value) + '">'
                + escapeHtml(truncateValue(label, 24)) + '</span>';
        }
        if (manyParams) {
            html += '<button class="param-expand-btn" onclick="toggleParamExpand(event)">+'
                + (resIds.length - PARAM_COLLAPSE_THRESHOLD) + ' more</button>';
        }
        html += '</div>';
    }

    html += '</div>';
    return html;
}

// Render a single node card
function renderNodeCard(node, depth, isRoot) {
    if (node.type === 'cycle_ref') {
        return renderCycleRef(node, depth);
    }

    const indent = Math.min(depth * INDENT_PX, MAX_INDENT_PX);
    const nodeId = 'node-' + node.index + '-' + node.flow_idx;
    const hasChildren = node.children && node.children.length > 0;
    const startCollapsed = !isRoot && depth >= AUTO_COLLAPSE_DEPTH;

    let html = '<div class="node-card' + (node.from_cycle ? ' from-cycle' : '') + '"'
        + ' style="margin-left:' + indent + 'px"'
        + ' data-node-index="' + node.index + '"'
        + ' data-full-url="' + escapeHtml(node.url) + '"'
        + ' id="' + nodeId + '">';

    // Via parameter banner (shows which param connects this card to its parent)
    if (!isRoot && node.via_params && node.via_params.length > 0) {
        html += '<div class="node-via-banner">';
        html += '<span class="via-label">via</span>';
        for (let pi = 0; pi < node.via_params.length; pi++) {
            if (pi > 0) html += '<span class="via-arrow">,</span>';
            html += '<span class="via-param" title="' + escapeHtml(node.via_params[pi]) + '">'
                + escapeHtml(truncateValue(node.via_params[pi], 30)) + '</span>';
        }
        html += '<span class="via-arrow">&#8594;</span>';
        html += '</div>';
    }

    // Card header
    html += '<div class="node-card-header">';
    if (hasChildren) {
        const symbol = startCollapsed ? '+' : '\\u2212';
        html += '<span class="toggle-btn" onclick="toggleChildren(event, \\'' + nodeId + '\\')">' + symbol + '</span>';
    } else {
        html += '<span style="width:18px;display:inline-block"></span>';
    }
    if (node.from_cycle) {
        html += '<span style="color:#f0883e" title="Continued from cycle">\\u21B3</span>';
    }
    html += '<span class="node-index">[#' + node.index + ']</span>';
    html += '<span class="method ' + node.method + '">' + node.method + '</span>';
    html += '<span class="path"'
        + ' onmouseenter="showUrlPopover(event, \\'' + escapeHtml(node.url).replace(/'/g, "\\\\'") + '\\')"'
        + ' onmouseleave="hideUrlPopover()">'
        + escapeHtml(truncatePath(node.path, 40)) + '</span>';
    if (node.domain) {
        html += '<span class="domain">' + escapeHtml(node.domain) + '</span>';
    }
    html += '</div>';

    // Card body (inline params)
    html += renderCardBody(node);

    html += '</div>';

    // Children with CSS tree line variables
    if (hasChildren) {
        const collapsedClass = startCollapsed ? ' collapsed' : '';
        const lineX = indent + 9;
        const childIndent = Math.min((depth + 1) * INDENT_PX, MAX_INDENT_PX);
        html += '<div class="node-children' + collapsedClass + '" id="children-' + nodeId + '"'
            + ' style="--tree-line-x:' + lineX + 'px; --child-indent:' + childIndent + 'px">';
        for (const child of node.children) {
            html += renderNodeCard(child, depth + 1, false);
        }
        html += '</div>';
    }

    return html;
}

// Render all trees
function renderTrees() {
    const container = document.getElementById('trees');
    let html = '';

    for (let i = 0; i < treesData.length; i++) {
        const tree = treesData[i];
        html += '<div class="tree-root">';

        // Header with mini summary
        html += '<div class="tree-header">';
        html += '<span class="rank">#' + tree.rank + '</span>';
        html += '<span class="method ' + tree.method + '">' + tree.method + '</span> ';
        html += '<span class="path" style="cursor:default">' + escapeHtml(truncatePath(tree.path, 50)) + '</span>';
        if (tree.domain) html += '<span class="domain">' + escapeHtml(tree.domain) + '</span>';
        html += '<span class="stats">depth:' + tree.depth + ' nodes:' + tree.nodes + '</span>';
        html += '<div class="chain-summary">' + buildChainSummary(tree) + '</div>';
        html += '</div>';

        // Tree container
        html += '<div class="tree-container" id="tree-container-' + i + '">';

        // Render root node card at depth 0
        html += renderNodeCard(tree, 0, true);

        html += '</div>';
        html += '</div>';
    }

    container.innerHTML = html;
}

// Toggle children collapse/expand
function toggleChildren(event, nodeId) {
    event.stopPropagation();
    const childrenEl = document.getElementById('children-' + nodeId);
    if (!childrenEl) return;
    const toggleBtn = event.target;

    if (childrenEl.classList.contains('collapsed')) {
        childrenEl.classList.remove('collapsed');
        childrenEl.style.maxHeight = childrenEl.scrollHeight + 'px';
        toggleBtn.textContent = '\\u2212';
    } else {
        childrenEl.style.maxHeight = childrenEl.scrollHeight + 'px';
        childrenEl.offsetHeight; // force reflow
        childrenEl.classList.add('collapsed');
        toggleBtn.textContent = '+';
    }
}

// Toggle param expand
function toggleParamExpand(event) {
    event.stopPropagation();
    const section = event.target.closest('.param-section');
    if (!section) return;
    if (section.classList.contains('params-collapsed')) {
        section.classList.remove('params-collapsed');
        event.target.style.display = 'none';
    }
}

// URL popover
function showUrlPopover(event, fullUrl) {
    if (!fullUrl || fullUrl === '?') return;
    let popover = document.getElementById('url-popover');
    if (!popover) {
        popover = document.createElement('div');
        popover.id = 'url-popover';
        popover.className = 'url-popover';
        document.body.appendChild(popover);
    }
    popover.textContent = fullUrl;
    const rect = event.target.getBoundingClientRect();
    popover.style.left = rect.left + 'px';
    popover.style.top = (rect.bottom + 6) + 'px';
    popover.classList.add('visible');
}

function hideUrlPopover() {
    const popover = document.getElementById('url-popover');
    if (popover) popover.classList.remove('visible');
}

// Scroll to a node (for cycle ref clicks)
function scrollToNode(targetIndex) {
    const targetNode = document.querySelector('[data-node-index="' + targetIndex + '"]');
    if (!targetNode) return;

    // Expand all collapsed parents
    let parent = targetNode.parentElement;
    while (parent) {
        if (parent.classList && parent.classList.contains('node-children') && parent.classList.contains('collapsed')) {
            parent.classList.remove('collapsed');
            parent.style.maxHeight = parent.scrollHeight + 'px';
            const prevSibling = parent.previousElementSibling;
            if (prevSibling) {
                const toggleBtn = prevSibling.querySelector('.toggle-btn');
                if (toggleBtn) toggleBtn.textContent = '\\u2212';
            }
        }
        parent = parent.parentElement;
    }

    targetNode.scrollIntoView({ behavior: 'smooth', block: 'center' });
    targetNode.classList.add('highlight-target');
    setTimeout(function() {
        targetNode.classList.remove('highlight-target');
    }, 2000);
}

// Initialize
renderTrees();
"""
