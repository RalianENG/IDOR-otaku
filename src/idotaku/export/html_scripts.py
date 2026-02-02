"""JavaScript code for HTML exports."""

# Chain tree export scripts
# Note: {trees_json} placeholder will be replaced with actual data
CHAIN_SCRIPTS = """
const treesData = {trees_json};
let selectedNode = null;

function truncatePath(path, max) {
    return path.length > max ? path.substring(0, max - 3) + '...' : path;
}

function truncateValue(val, max) {
    return val.length > max ? val.substring(0, max - 2) + '..' : val;
}

function formatParams(params, maxLen) {
    // Format array of params for display
    if (!params || params.length === 0) return '';
    if (params.length === 1) {
        return truncateValue(params[0], maxLen);
    }
    // Multiple params: show count
    const first = truncateValue(params[0], maxLen - 6);
    return first + ' +' + (params.length - 1);
}

function renderNode(node, isRoot = false) {
    // Handle cycle reference nodes (max path visits, children deferred to target)
    if (node.type === 'cycle_ref') {
        let html = '<div class="node-item" style="color: #8b949e; font-style: italic;">';
        html += '<span style="width: 26px; display: inline-block;"></span>';
        html += '↩ <span style="color: #3fb950;">[#' + node.target_index + ']</span>';
        if (node.via_params && node.via_params.length > 0) {
            html += ' <span style="color: #6e7681;">via </span><span class="param-value" style="color: #6e7681;">' + formatParams(node.via_params, 16) + '</span>';
        }
        html += ' <span style="color: #6e7681; font-size: 0.85em;">(continues below)</span>';
        html += '</div>';
        return html;
    }

    const hasChildren = node.children && node.children.length > 0;
    const nodeId = 'node-' + node.flow_idx + '-' + Math.random().toString(36).substr(2, 9);

    let html = '<div class="node-item' + (node.from_cycle ? ' from-cycle' : '') + '" data-flow=\\'' + JSON.stringify(node).replace(/'/g, "\\\\'") + '\\' data-node-index="' + node.index + '" id="' + nodeId + '">';

    if (hasChildren) {
        html += '<span class="toggle-btn" onclick="toggleChildren(event, \\'' + nodeId + '\\')">−</span>';
    } else {
        html += '<span style="width: 26px; display: inline-block;"></span>';
    }

    // Show cycle continuation indicator
    if (node.from_cycle) {
        html += '<span style="color: #f0883e; margin-right: 4px;" title="Continued from cycle">↳</span>';
    }

    // Display index
    html += '<span style="color: #3fb950; font-weight: bold; margin-right: 6px;">[#' + node.index + ']</span>';

    html += '<span class="method ' + node.method + '">' + node.method + '</span>';

    if (node.via_params && node.via_params.length > 0 && !isRoot) {
        html += '<span class="param-value">' + formatParams(node.via_params, 16) + '</span>';
        html += '<span class="param-arrow">→</span>';
    }

    html += '<span class="path">' + truncatePath(node.path, 40) + '</span>';
    if (node.domain) {
        html += '<span class="domain">' + node.domain + '</span>';
    }
    html += '</div>';

    if (hasChildren) {
        html += '<div class="tree-children" id="children-' + nodeId + '">';
        html += '<div class="tree-node">';
        for (const child of node.children) {
            html += renderNode(child);
        }
        html += '</div></div>';
    }

    return html;
}

function renderTrees() {
    const container = document.getElementById('trees');
    let html = '';

    for (const tree of treesData) {
        html += '<div class="tree-root">';
        html += '<div class="tree-header">';
        html += '<span class="rank">#' + tree.rank + '</span>';
        html += '<span style="color: #3fb950; font-weight: bold; margin-right: 6px;">[#' + tree.index + ']</span>';
        html += '<span class="method ' + tree.method + '">' + tree.method + '</span> ';
        html += '<span class="path">' + truncatePath(tree.path, 50) + '</span>';
        if (tree.domain) {
            html += '<span class="domain">' + tree.domain + '</span>';
        }
        html += '<span class="stats">depth:' + tree.depth + ' nodes:' + tree.nodes + '</span>';
        html += '</div>';
        html += '<div class="tree-node">';
        for (const child of tree.children) {
            html += renderNode(child);
        }
        html += '</div></div>';
    }

    container.innerHTML = html;

    // Add click handlers
    document.querySelectorAll('.node-item').forEach(item => {
        item.addEventListener('click', (e) => {
            if (e.target.classList.contains('toggle-btn')) return;
            selectNode(item);
        });
    });

    // Also make tree headers clickable
    document.querySelectorAll('.tree-header').forEach((header, idx) => {
        header.style.cursor = 'pointer';
        header.addEventListener('click', () => {
            showDetails(treesData[idx]);
        });
    });
}

function toggleChildren(event, nodeId) {
    event.stopPropagation();
    const childrenEl = document.getElementById('children-' + nodeId);
    const toggleBtn = event.target;

    if (childrenEl.classList.contains('collapsed')) {
        childrenEl.classList.remove('collapsed');
        childrenEl.style.maxHeight = childrenEl.scrollHeight + 'px';
        toggleBtn.textContent = '−';
    } else {
        childrenEl.style.maxHeight = childrenEl.scrollHeight + 'px';
        childrenEl.offsetHeight; // Force reflow
        childrenEl.classList.add('collapsed');
        toggleBtn.textContent = '+';
    }
}

function selectNode(item) {
    document.querySelectorAll('.node-item').forEach(n => n.classList.remove('selected'));
    item.classList.add('selected');
    const data = JSON.parse(item.dataset.flow);
    showDetails(data);
}

function openPanel() {
    document.getElementById('detailPanel').classList.add('open');
}

function closePanel() {
    document.getElementById('detailPanel').classList.remove('open');
    document.querySelectorAll('.node-item').forEach(n => n.classList.remove('selected'));
}

function scrollToNode(targetIndex) {
    // Find the node with the target index
    const targetNode = document.querySelector('[data-node-index="' + targetIndex + '"]');
    if (!targetNode) return;

    // Expand all parent tree-children to make target visible
    let parent = targetNode.parentElement;
    while (parent) {
        if (parent.classList && parent.classList.contains('tree-children') && parent.classList.contains('collapsed')) {
            parent.classList.remove('collapsed');
            parent.style.maxHeight = parent.scrollHeight + 'px';
            // Update toggle button
            const prevSibling = parent.previousElementSibling;
            if (prevSibling) {
                const toggleBtn = prevSibling.querySelector('.toggle-btn');
                if (toggleBtn) toggleBtn.textContent = '−';
            }
        }
        parent = parent.parentElement;
    }

    // Scroll to the node
    targetNode.scrollIntoView({ behavior: 'smooth', block: 'center' });

    // Highlight the node temporarily
    targetNode.classList.add('highlight-target');
    setTimeout(() => {
        targetNode.classList.remove('highlight-target');
    }, 2000);

    // Select the node and show details
    selectNode(targetNode);
}

// Esc key to close
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closePanel();
});

function showDetails(node) {
    const container = document.getElementById('details');
    openPanel();

    let html = '';

    // URL
    html += '<div class="detail-section">';
    html += '<h3>URL</h3>';
    html += '<div class="detail-url">' + node.url + '</div>';
    html += '</div>';

    // Timestamp
    if (node.timestamp) {
        html += '<div class="detail-section">';
        html += '<h3>Timestamp</h3>';
        html += '<div class="detail-time">' + node.timestamp + '</div>';
        html += '</div>';
    }

    // Via Parameters (connection params)
    if (node.via_params && node.via_params.length > 0) {
        html += '<div class="detail-section">';
        html += '<h3>Connected via Parameter' + (node.via_params.length > 1 ? 's (' + node.via_params.length + ')' : '') + '</h3>';
        html += '<div class="detail-url">';
        for (const p of node.via_params) {
            html += '<div style="font-family: monospace; margin: 4px 0;">' + p + '</div>';
        }
        html += '</div>';
        html += '</div>';
    }

    // From Cycle indicator
    if (node.from_cycle) {
        html += '<div class="detail-section">';
        html += '<h3 style="color: #f0883e;">↳ Continued from Cycle</h3>';
        html += '<div class="detail-url" style="background: #f0883e22; border: 1px solid #f0883e;">';
        html += '<div>This node was added as a continuation from a cycle.</div>';
        html += '</div>';
        html += '</div>';
    }

    // Cycle Information
    if (node.is_cycle && node.cycle_to_index !== undefined) {
        html += '<div class="detail-section">';
        html += '<h3 style="color: #f85149;">⟳ Cycle Detected</h3>';
        html += '<div class="detail-url" style="background: #f8514922; border: 1px solid #f85149;">';
        html += '<div>Same API as <span style="color: #3fb950; font-weight: bold;">[#' + node.cycle_to_index + ']</span></div>';
        if (node.via_params && node.via_params.length > 0) {
            html += '<div style="color: #8b949e; margin-top: 8px;">via parameter' + (node.via_params.length > 1 ? 's' : '') + ':</div>';
            for (const p of node.via_params) {
                html += '<div style="color: #79c0ff; font-family: monospace; margin-left: 8px;">' + p + '</div>';
            }
        }
        html += '</div>';
        html += '</div>';
    }

    // Request IDs
    if (node.request_ids && node.request_ids.length > 0) {
        html += '<div class="detail-section">';
        html += '<h3><span class="badge req">REQ</span> Request Parameters (' + node.request_ids.length + ')</h3>';
        html += '<table class="param-table"><thead><tr>';
        html += '<th>Value</th><th>Type</th><th>Location</th><th>Field</th>';
        html += '</tr></thead><tbody>';
        for (const id of node.request_ids) {
            html += '<tr>';
            html += '<td class="value" title="' + id.value + '">' + truncateValue(id.value, 24) + '</td>';
            html += '<td class="type">' + (id.type || '-') + '</td>';
            html += '<td class="location">' + (id.location || '-') + '</td>';
            html += '<td class="field">' + (id.field || '-') + '</td>';
            html += '</tr>';
        }
        html += '</tbody></table></div>';
    }

    // Response IDs
    if (node.response_ids && node.response_ids.length > 0) {
        html += '<div class="detail-section">';
        html += '<h3><span class="badge res">RES</span> Response Parameters (' + node.response_ids.length + ')</h3>';
        html += '<table class="param-table"><thead><tr>';
        html += '<th>Value</th><th>Type</th><th>Location</th><th>Field</th>';
        html += '</tr></thead><tbody>';
        for (const id of node.response_ids) {
            html += '<tr>';
            html += '<td class="value" title="' + id.value + '">' + truncateValue(id.value, 24) + '</td>';
            html += '<td class="type">' + (id.type || '-') + '</td>';
            html += '<td class="location">' + (id.location || '-') + '</td>';
            html += '<td class="field">' + (id.field || '-') + '</td>';
            html += '</tr>';
        }
        html += '</tbody></table></div>';
    }

    container.innerHTML = html;
}

// Initialize
renderTrees();
"""
