"""Export command - export report as HTML with interactive tree visualization."""

from datetime import datetime
import html as html_module
from urllib.parse import urlparse

import click
from rich.console import Console

from ..report import load_report

console = Console()


def esc(s):
    """HTML escape helper."""
    return html_module.escape(str(s))


def extract_domain(url):
    """Extract domain from URL."""
    try:
        parsed = urlparse(url)
        return parsed.netloc or ""
    except Exception:
        return ""


def get_base_domain(domain):
    """Get base domain (e.g., api.example.com -> example.com)."""
    parts = domain.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return domain


@click.command()
@click.argument("report_file", default="id_tracker_report.json", type=click.Path(exists=True))
@click.option("--output", "-o", default=None, help="Output HTML file (default: based on section)")
@click.option("--section", "-s", type=click.Choice(["all", "tree", "trace", "timeline"]), default="all",
              help="Section to export: tree (ID flow), trace (API transitions), timeline (flow table), or all")
def export(report_file, output, section):
    """Export report as HTML with interactive tree visualization.

    Sections:
      tree     - ID Flow Tree (origin → usage by ID)
      trace    - API Trace (ID transitions between API calls)
      timeline - Flow Timeline (request/response table)
      all      - All sections in one file
    """
    # Default output filename based on section
    if output is None:
        if section == "all":
            output = "id_report.html"
        else:
            output = f"id_report_{section}.html"

    data = load_report(report_file)

    tracked_ids = data.tracked_ids
    potential_idor = data.potential_idor
    potential_idor_values = data.idor_values
    flows = data.flows
    summary = data.summary

    # Collect all unique domains from tracked IDs
    all_domains = set()
    for id_value, info in tracked_ids.items():
        origin = info.get("origin")
        if origin and origin.get("url"):
            domain = extract_domain(origin["url"])
            if domain:
                all_domains.add(domain)
        for usage in info.get("usages", []):
            if usage.get("url"):
                domain = extract_domain(usage["url"])
                if domain:
                    all_domains.add(domain)

    # Also collect from flows
    for flow in flows:
        if flow.get("url"):
            domain = extract_domain(flow["url"])
            if domain:
                all_domains.add(domain)

    sorted_domains = sorted(all_domains)

    # Build ID tree HTML
    id_trees = []
    sorted_ids = sorted(tracked_ids.items(), key=lambda x: x[1].get("first_seen", ""))

    for id_value, info in sorted_ids:
        is_idor = id_value in potential_idor_values
        id_type_str = info.get("type", "unknown")
        origin = info.get("origin")
        usages = info.get("usages", [])

        idor_class = "idor" if is_idor else ""
        idor_badge = '<span class="badge idor-badge">IDOR</span>' if is_idor else ""

        children = []

        # Origin
        if origin:
            method = origin.get("method", "?")
            url = origin.get("url", "?")
            location = origin.get("location", "?")
            field = origin.get("field_name") or origin.get("field") or ""
            timestamp = origin.get("timestamp", "")
            time_part = timestamp.split("T")[1][:8] if "T" in timestamp else ""
            domain = extract_domain(url)

            # Field name as prominent badge if exists
            field_html = f'<span class="field-name">{esc(field)}</span>' if field else ''
            loc_html = f'<span class="location-type">{esc(location)}</span>'

            children.append(f'''
                <li class="origin" data-domain="{esc(domain)}" data-base-domain="{esc(get_base_domain(domain))}">
                    <span class="label origin-label">ORIGIN</span>
                    <span class="method">{esc(method)}</span>
                    <span class="url" title="{esc(url)}">{esc(url[:60] + '...' if len(url) > 60 else url)}</span>
                    <span class="location-info">→ {loc_html}{field_html}</span>
                    {f'<span class="time">({time_part})</span>' if time_part else ''}
                </li>
            ''')
        else:
            children.append('<li class="no-origin">No origin (not seen in response)</li>')

        # Usages
        for i, usage in enumerate(usages, 1):
            method = usage.get("method", "?")
            url = usage.get("url", "?")
            location = usage.get("location", "?")
            field = usage.get("field_name") or usage.get("field") or ""
            timestamp = usage.get("timestamp", "")
            time_part = timestamp.split("T")[1][:8] if "T" in timestamp else ""
            domain = extract_domain(url)

            # Field name as prominent badge if exists
            field_html = f'<span class="field-name">{esc(field)}</span>' if field else ''
            loc_html = f'<span class="location-type">{esc(location)}</span>'

            children.append(f'''
                <li class="usage" data-domain="{esc(domain)}" data-base-domain="{esc(get_base_domain(domain))}">
                    <span class="label usage-label">USAGE {i}</span>
                    <span class="method">{esc(method)}</span>
                    <span class="url" title="{esc(url)}">{esc(url[:60] + '...' if len(url) > 60 else url)}</span>
                    <span class="location-info">→ {loc_html}{field_html}</span>
                    {f'<span class="time">({time_part})</span>' if time_part else ''}
                </li>
            ''')

        if not usages:
            children.append('<li class="no-usage">No usage (not seen in request)</li>')

        # Collect domains for this ID tree
        tree_domains = set()
        tree_base_domains = set()
        if origin and origin.get("url"):
            d = extract_domain(origin["url"])
            if d:
                tree_domains.add(d)
                tree_base_domains.add(get_base_domain(d))
        for usage in usages:
            if usage.get("url"):
                d = extract_domain(usage["url"])
                if d:
                    tree_domains.add(d)
                    tree_base_domains.add(get_base_domain(d))

        id_trees.append(f'''
            <details class="id-tree {idor_class}" open data-domains="{esc(','.join(tree_domains))}" data-base-domains="{esc(','.join(tree_base_domains))}">
                <summary>
                    <code class="id-value">{esc(id_value)}</code>
                    <span class="id-type">({id_type_str})</span>
                    {idor_badge}
                </summary>
                <ul class="tree-children">
                    {''.join(children)}
                </ul>
            </details>
        ''')

    # Build flow table
    flow_rows = []
    for i, flow in enumerate(flows[:100], 1):
        method = flow.get("method", "?")
        url = flow.get("url", "?")
        req_ids = flow.get("request_ids", [])
        res_ids = flow.get("response_ids", [])

        req_badges = ''.join(f'<span class="id-badge req">{esc(r["value"][:12])}</span>' for r in req_ids[:3])
        if len(req_ids) > 3:
            req_badges += f'<span class="more">+{len(req_ids)-3}</span>'

        res_badges = ''.join(f'<span class="id-badge res">{esc(r["value"][:12])}</span>' for r in res_ids[:3])
        if len(res_ids) > 3:
            res_badges += f'<span class="more">+{len(res_ids)-3}</span>'

        flow_rows.append(f'''
            <tr>
                <td>{i}</td>
                <td><span class="method-badge">{esc(method)}</span></td>
                <td class="url-cell" title="{esc(url)}">{esc(url[:50] + '...' if len(url) > 50 else url)}</td>
                <td>{req_badges or '-'}</td>
                <td>{res_badges or '-'}</td>
            </tr>
        ''')

    # Build API Trace (ID transition tree)
    sorted_flows = sorted(flows, key=lambda x: x.get("timestamp", ""))

    # Build transition map: response ID -> subsequent request usages
    id_to_subsequent_usage = {}
    for i, flow in enumerate(sorted_flows):
        for req_id in flow.get("request_ids", []):
            id_val = req_id["value"]
            if id_val not in id_to_subsequent_usage:
                id_to_subsequent_usage[id_val] = []
            id_to_subsequent_usage[id_val].append({
                "flow_idx": i,
                "location": req_id.get("location", "?"),
                "field": req_id.get("field"),
            })

    # Build origin map: which response first produced each ID (backward tracking)
    id_to_origin_html = {}
    for i, flow in enumerate(sorted_flows):
        for res_id in flow.get("response_ids", []):
            id_val = res_id["value"]
            if id_val not in id_to_origin_html:  # First occurrence only
                id_to_origin_html[id_val] = {
                    "flow_idx": i,
                    "location": res_id.get("location", "?"),
                    "field": res_id.get("field"),
                    "method": flow.get("method", "?"),
                    "url": flow.get("url", "?"),
                    "timestamp": flow.get("timestamp", ""),
                }

    def format_trace_id(id_info, is_idor_id=False):
        """Format ID for trace display."""
        id_val = id_info["value"]
        id_type = id_info.get("type", "?")
        location = id_info.get("location", "?")
        field = id_info.get("field")
        display_val = id_val[:16] + "..." if len(id_val) > 16 else id_val

        idor_class = "idor" if is_idor_id else ""
        field_html = f'<span class="trace-field">{esc(field)}</span>' if field else ''

        return f'''<span class="trace-id {idor_class}">
            <code>{esc(display_val)}</code>
            <span class="trace-id-type">({id_type})</span>
            <span class="trace-loc">{esc(location)}</span>{field_html}
        </span>'''

    api_trace_items = []
    shown_as_child = set()

    for i, flow in enumerate(sorted_flows[:50]):  # Limit to 50 for performance
        if i in shown_as_child:
            continue

        method = flow.get("method", "?")
        url = flow.get("url", "?")
        timestamp = flow.get("timestamp", "")
        time_part = timestamp.split("T")[1][:8] if "T" in timestamp else ""
        request_ids = flow.get("request_ids", [])
        response_ids = flow.get("response_ids", [])

        short_url = url[:50] + "..." if len(url) > 50 else url

        # Build request IDs HTML with origin tracking
        req_html = ""
        if request_ids:
            req_items = []
            for req_id in request_ids[:10]:
                id_val = req_id["value"]
                is_idor_id = id_val in potential_idor_values
                id_html = format_trace_id(req_id, is_idor_id)

                # Check for origin (where this ID came from)
                origin_html = ""
                if id_val in id_to_origin_html:
                    origin = id_to_origin_html[id_val]
                    origin_idx = origin["flow_idx"]
                    if origin_idx < i:  # Only show if from a previous flow
                        origin_method = origin["method"]
                        origin_url = origin["url"]
                        origin_short_url = origin_url[:35] + "..." if len(origin_url) > 35 else origin_url
                        origin_loc = origin["location"]
                        if origin["field"]:
                            origin_loc += f".{origin['field']}"
                        origin_html = f'''
                            <div class="trace-origin">
                                <span class="trace-arrow-back">←</span>
                                <span class="trace-origin-label">from</span>
                                <span class="method-badge">{esc(origin_method)}</span>
                                <span class="trace-origin-url" title="{esc(origin_url)}">{esc(origin_short_url)}</span>
                                <span class="trace-at">@ {esc(origin_loc)}</span>
                            </div>
                        '''

                req_items.append(f'<li>{id_html}{origin_html}</li>')

            if len(request_ids) > 10:
                req_items.append(f'<li class="more">+{len(request_ids) - 10} more</li>')
            req_html = f'<div class="trace-section req"><span class="trace-label">REQ</span><ul>{"".join(req_items)}</ul></div>'

        # Build response IDs HTML with transitions
        res_html = ""
        if response_ids:
            res_items = []
            for res_id in response_ids[:15]:
                id_val = res_id["value"]
                is_idor_id = id_val in potential_idor_values
                id_html = format_trace_id(res_id, is_idor_id)

                # Check for transitions
                transitions_html = ""
                if id_val in id_to_subsequent_usage:
                    trans_items = []
                    for usage in id_to_subsequent_usage[id_val]:
                        next_idx = usage["flow_idx"]
                        if next_idx <= i:
                            continue
                        shown_as_child.add(next_idx)
                        next_flow = sorted_flows[next_idx]
                        next_method = next_flow.get("method", "?")
                        next_url = next_flow.get("url", "?")
                        next_short_url = next_url[:35] + "..." if len(next_url) > 35 else next_url
                        next_time = next_flow.get("timestamp", "").split("T")[1][:8] if "T" in next_flow.get("timestamp", "") else ""

                        loc_str = usage["location"]
                        if usage["field"]:
                            loc_str += f".{usage['field']}"

                        # Get response IDs from the transitioned flow
                        next_res_ids = next_flow.get("response_ids", [])
                        next_res_html = ""
                        if next_res_ids:
                            next_res_items = ''.join(
                                f'<span class="trace-next-id">{format_trace_id(nr, nr["value"] in potential_idor_values)}</span>'
                                for nr in next_res_ids[:3]
                            )
                            if len(next_res_ids) > 3:
                                next_res_items += f'<span class="more">+{len(next_res_ids) - 3}</span>'
                            next_res_html = f'<div class="trace-next-res">→ {next_res_items}</div>'

                        trans_items.append(f'''
                            <div class="trace-transition">
                                <span class="trace-arrow">→</span>
                                <span class="trace-next-api">
                                    <span class="method-badge">{esc(next_method)}</span>
                                    <span class="trace-next-url" title="{esc(next_url)}">{esc(next_short_url)}</span>
                                    <span class="trace-time">{next_time}</span>
                                    <span class="trace-at">@ {esc(loc_str)}</span>
                                </span>
                                {next_res_html}
                            </div>
                        ''')

                    if trans_items:
                        transitions_html = f'<div class="trace-transitions">{"".join(trans_items[:5])}</div>'
                        if len(trans_items) > 5:
                            transitions_html += f'<div class="more">+{len(trans_items) - 5} more transitions</div>'

                res_items.append(f'<li>{id_html}{transitions_html}</li>')

            if len(response_ids) > 15:
                res_items.append(f'<li class="more">+{len(response_ids) - 15} more</li>')
            res_html = f'<div class="trace-section res"><span class="trace-label">RES</span><ul>{"".join(res_items)}</ul></div>'

        api_trace_items.append(f'''
            <details class="api-trace-item" open>
                <summary>
                    <span class="method-badge">{esc(method)}</span>
                    <span class="trace-url" title="{esc(url)}">{esc(short_url)}</span>
                    <span class="trace-time">{time_part}</span>
                </summary>
                <div class="trace-body">
                    {req_html}
                    {res_html}
                </div>
            </details>
        ''')

    # Build section HTML blocks
    section_titles = {
        "tree": "ID Flow Tree",
        "trace": "API Trace",
        "timeline": "Flow Timeline",
        "all": "ID Tracking Report",
    }

    tree_section_html = f'''
        <h2>ID Flow Tree</h2>
        <div class="filter-bar">
            <label>Filter:</label>
            <input type="text" id="search" placeholder="Search ID..." oninput="filterIDs()">
            <select id="typeFilter" onchange="filterIDs()">
                <option value="all">All Types</option>
                <option value="numeric">Numeric</option>
                <option value="uuid">UUID</option>
                <option value="token">Token</option>
            </select>
            <select id="domainFilter" onchange="filterIDs()">
                <option value="all">All Domains</option>
                {''.join(f'<option value="{esc(d)}">{esc(d)}</option>' for d in sorted_domains)}
            </select>
            <label><input type="checkbox" id="includeSubdomains" onchange="filterIDs()" checked> Include Subdomains</label>
            <label><input type="checkbox" id="idorOnly" onchange="filterIDs()"> IDOR Only</label>
            <button onclick="toggleAll(true)">Expand All</button>
            <button onclick="toggleAll(false)">Collapse All</button>
        </div>
        <div id="id-trees">
            {''.join(id_trees)}
        </div>
    '''

    trace_section_html = f'''
        <h2>API Trace (ID Transitions)</h2>
        <p style="color: #888; margin-bottom: 15px;">Shows how IDs flow from API responses to subsequent requests. Click to expand/collapse.</p>
        <div id="api-trace">
            {''.join(api_trace_items)}
        </div>
        {f'<p style="color: #666; text-align: center;">Showing first 50 of {len(sorted_flows)} API calls</p>' if len(sorted_flows) > 50 else ''}
    '''

    timeline_section_html = f'''
        <h2>Flow Timeline</h2>
        <table class="flow-table">
            <thead>
                <tr>
                    <th>#</th>
                    <th>Method</th>
                    <th>URL</th>
                    <th>Request IDs</th>
                    <th>Response IDs</th>
                </tr>
            </thead>
            <tbody>
                {''.join(flow_rows)}
            </tbody>
        </table>
        {f'<p style="color: #666; text-align: center;">Showing first 100 of {len(flows)} flows</p>' if len(flows) > 100 else ''}
    '''

    # Select sections based on parameter
    if section == "tree":
        body_sections = tree_section_html
    elif section == "trace":
        body_sections = trace_section_html
    elif section == "timeline":
        body_sections = timeline_section_html
    else:  # all
        body_sections = tree_section_html + trace_section_html + timeline_section_html

    # Only include tree-specific JS if tree section is included
    tree_js = '''
        function getBaseDomain(domain) {
            const parts = domain.split('.');
            if (parts.length >= 2) {
                return parts.slice(-2).join('.');
            }
            return domain;
        }

        function filterIDs() {
            const search = document.getElementById('search').value.toLowerCase();
            const typeFilter = document.getElementById('typeFilter').value;
            const domainFilter = document.getElementById('domainFilter').value;
            const includeSubdomains = document.getElementById('includeSubdomains').checked;
            const idorOnly = document.getElementById('idorOnly').checked;

            document.querySelectorAll('.id-tree').forEach(tree => {
                const idValue = tree.querySelector('.id-value').textContent.toLowerCase();
                const idType = tree.querySelector('.id-type').textContent;
                const isIdor = tree.classList.contains('idor');
                const treeDomains = (tree.dataset.domains || '').split(',').filter(d => d);
                const treeBaseDomains = (tree.dataset.baseDomains || '').split(',').filter(d => d);

                let show = true;
                if (search && !idValue.includes(search)) show = false;
                if (typeFilter !== 'all' && !idType.includes(typeFilter)) show = false;
                if (idorOnly && !isIdor) show = false;

                // Domain filtering
                if (domainFilter !== 'all') {
                    if (includeSubdomains) {
                        const filterBaseDomain = getBaseDomain(domainFilter);
                        const hasMatchingDomain = treeBaseDomains.some(bd => bd === filterBaseDomain) ||
                                                   treeDomains.some(d => d === domainFilter || d.endsWith('.' + domainFilter));
                        if (!hasMatchingDomain) show = false;
                    } else {
                        if (!treeDomains.includes(domainFilter)) show = false;
                    }
                }

                tree.style.display = show ? 'block' : 'none';
            });
        }

        function toggleAll(open) {
            document.querySelectorAll('.id-tree').forEach(tree => {
                tree.open = open;
            });
        }
    ''' if section in ("tree", "all") else ''

    html_content = _build_html_content(
        section, section_titles, summary, potential_idor, body_sections, tree_js
    )

    with open(output, "w", encoding="utf-8") as f:
        f.write(html_content)

    console.print(f"[green]Report exported to:[/green] {output}")


def _build_html_content(section, section_titles, summary, potential_idor, body_sections, tree_js):
    """Build the complete HTML content."""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>idotaku - {section_titles[section]}</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #eee;
            margin: 0;
            padding: 20px;
            line-height: 1.6;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #00d9ff; border-bottom: 2px solid #00d9ff; padding-bottom: 10px; }}
        h2 {{ color: #ff6b6b; margin-top: 30px; }}

        /* Summary Cards */
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }}
        .card {{
            background: #16213e;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
        }}
        .card.danger {{ background: #4a1942; border: 2px solid #ff6b6b; }}
        .card-value {{ font-size: 2em; font-weight: bold; color: #00d9ff; }}
        .card.danger .card-value {{ color: #ff6b6b; }}
        .card-label {{ color: #888; font-size: 0.9em; }}

        /* ID Trees */
        .id-tree {{
            background: #16213e;
            border-radius: 8px;
            margin: 10px 0;
            overflow: hidden;
        }}
        .id-tree.idor {{ border-left: 4px solid #ff6b6b; }}
        .id-tree summary {{
            padding: 12px 15px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 10px;
            background: #1f2b47;
        }}
        .id-tree summary:hover {{ background: #2a3a5e; }}
        .id-value {{ color: #00d9ff; font-size: 1.1em; }}
        .id-tree.idor .id-value {{ color: #ff6b6b; }}
        .id-type {{ color: #888; }}
        .badge {{ padding: 2px 8px; border-radius: 4px; font-size: 0.75em; font-weight: bold; }}
        .idor-badge {{ background: #ff6b6b; color: #fff; }}

        .tree-children {{
            list-style: none;
            margin: 0;
            padding: 0 15px 15px 30px;
        }}
        .tree-children li {{
            padding: 8px 12px;
            margin: 5px 0;
            border-left: 2px solid #333;
            background: #0f1729;
            border-radius: 0 6px 6px 0;
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 8px;
        }}
        .tree-children li.origin {{ border-left-color: #4ade80; }}
        .tree-children li.usage {{ border-left-color: #fbbf24; }}
        .tree-children li.no-origin {{ border-left-color: #ff6b6b; color: #ff6b6b; font-style: italic; }}
        .tree-children li.no-usage {{ color: #666; font-style: italic; }}

        .label {{
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 0.75em;
            font-weight: bold;
        }}
        .origin-label {{ background: #166534; color: #4ade80; }}
        .usage-label {{ background: #78350f; color: #fbbf24; }}
        .method {{ font-weight: bold; color: #a78bfa; }}
        .url {{ color: #94a3b8; font-size: 0.9em; word-break: break-all; }}
        .location-info {{ display: flex; align-items: center; gap: 4px; }}
        .location-type {{ color: #67e8f9; font-style: italic; }}
        .field-name {{
            background: #7c3aed;
            color: #fff;
            padding: 2px 8px;
            border-radius: 4px;
            font-family: monospace;
            font-size: 0.85em;
            font-weight: bold;
            margin-left: 4px;
        }}
        .tree-children li.origin .field-name {{ background: #15803d; }}
        .tree-children li.usage .field-name {{ background: #b45309; }}
        .time {{ color: #666; font-size: 0.85em; }}

        /* Flow Table */
        .flow-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            font-size: 0.9em;
        }}
        .flow-table th {{
            background: #1f2b47;
            padding: 12px;
            text-align: left;
            color: #00d9ff;
        }}
        .flow-table td {{
            padding: 10px 12px;
            border-bottom: 1px solid #2a3a5e;
        }}
        .flow-table tr:hover {{ background: #1f2b47; }}
        .url-cell {{ max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #94a3b8; }}
        .method-badge {{ background: #4c1d95; color: #c4b5fd; padding: 2px 6px; border-radius: 3px; font-weight: bold; }}
        .id-badge {{ font-family: monospace; font-size: 0.85em; padding: 2px 5px; border-radius: 3px; margin: 1px; display: inline-block; }}
        .id-badge.req {{ background: #78350f; color: #fbbf24; }}
        .id-badge.res {{ background: #166534; color: #4ade80; }}
        .more {{ color: #666; font-size: 0.85em; }}

        /* Filter */
        .filter-bar {{
            background: #16213e;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: flex;
            gap: 15px;
            align-items: center;
            flex-wrap: wrap;
        }}
        .filter-bar label {{ color: #888; }}
        .filter-bar input, .filter-bar select {{
            background: #0f1729;
            border: 1px solid #333;
            color: #eee;
            padding: 8px 12px;
            border-radius: 5px;
        }}
        .filter-bar button {{
            background: #00d9ff;
            color: #000;
            border: none;
            padding: 8px 16px;
            border-radius: 5px;
            cursor: pointer;
            font-weight: bold;
        }}
        .filter-bar button:hover {{ background: #00b8d9; }}

        /* API Trace */
        .api-trace-item {{
            background: #16213e;
            border-radius: 8px;
            margin: 10px 0;
            overflow: hidden;
        }}
        .api-trace-item summary {{
            padding: 12px 15px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 10px;
            background: #1f2b47;
        }}
        .api-trace-item summary:hover {{ background: #2a3a5e; }}
        .trace-url {{ color: #94a3b8; font-size: 0.9em; }}
        .trace-time {{ color: #666; font-size: 0.85em; }}
        .trace-body {{ padding: 10px 15px 15px 15px; }}
        .trace-section {{ margin: 8px 0; }}
        .trace-section ul {{ list-style: none; margin: 5px 0 5px 20px; padding: 0; }}
        .trace-section li {{ margin: 4px 0; padding: 6px 10px; background: #0f1729; border-radius: 4px; }}
        .trace-section.req .trace-label {{ background: #78350f; color: #fbbf24; padding: 2px 6px; border-radius: 3px; font-size: 0.75em; font-weight: bold; }}
        .trace-section.res .trace-label {{ background: #166534; color: #4ade80; padding: 2px 6px; border-radius: 3px; font-size: 0.75em; font-weight: bold; }}
        .trace-id {{ display: inline-flex; align-items: center; gap: 6px; flex-wrap: wrap; }}
        .trace-id code {{ color: #00d9ff; font-size: 0.95em; }}
        .trace-id.idor code {{ color: #ff6b6b; }}
        .trace-id-type {{ color: #666; font-size: 0.8em; }}
        .trace-loc {{ color: #67e8f9; font-size: 0.85em; font-style: italic; }}
        .trace-field {{ background: #7c3aed; color: #fff; padding: 1px 6px; border-radius: 3px; font-family: monospace; font-size: 0.8em; }}
        .trace-transitions {{ margin-left: 20px; margin-top: 8px; border-left: 2px solid #4c1d95; padding-left: 12px; }}
        .trace-transition {{ margin: 6px 0; padding: 6px 10px; background: #1a1a3e; border-radius: 4px; }}
        .trace-arrow {{ color: #fbbf24; font-weight: bold; margin-right: 6px; }}
        .trace-next-api {{ display: inline-flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
        .trace-next-url {{ color: #94a3b8; font-size: 0.85em; }}
        .trace-at {{ color: #67e8f9; font-size: 0.8em; }}
        .trace-next-res {{ margin-top: 4px; margin-left: 20px; padding: 4px 8px; background: #0f1729; border-radius: 4px; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }}
        .trace-next-id {{ display: inline-flex; align-items: center; gap: 4px; }}
        .more {{ color: #666; font-size: 0.85em; font-style: italic; }}

        /* Origin tracking (backward trace for REQ IDs) */
        .trace-origin {{ margin-top: 6px; margin-left: 16px; padding: 4px 10px; background: #1e293b; border-left: 2px solid #3b82f6; border-radius: 0 4px 4px 0; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
        .trace-arrow-back {{ color: #3b82f6; font-weight: bold; }}
        .trace-origin-label {{ color: #94a3b8; font-size: 0.85em; }}
        .trace-origin-url {{ color: #94a3b8; font-size: 0.85em; }}

        footer {{ margin-top: 40px; text-align: center; color: #666; font-size: 0.9em; }}
        footer a {{ color: #00d9ff; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>idotaku {section_titles[section]}</h1>
        <p style="color: #666;">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

        <div class="summary">
            <div class="card">
                <div class="card-value">{summary.total_unique_ids}</div>
                <div class="card-label">Unique IDs</div>
            </div>
            <div class="card">
                <div class="card-value">{summary.ids_with_origin}</div>
                <div class="card-label">With Origin</div>
            </div>
            <div class="card">
                <div class="card-value">{summary.ids_with_usage}</div>
                <div class="card-label">With Usage</div>
            </div>
            <div class="card">
                <div class="card-value">{summary.total_flows}</div>
                <div class="card-label">Total Flows</div>
            </div>
            <div class="card danger">
                <div class="card-value">{len(potential_idor)}</div>
                <div class="card-label">Potential IDOR</div>
            </div>
        </div>

        {body_sections}

        <footer>
            Generated by <a href="https://github.com/yourname/idotaku">idotaku</a>
        </footer>
    </div>

    <script>
        {tree_js}
    </script>
</body>
</html>
'''
