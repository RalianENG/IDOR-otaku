"""Chain command - detect and rank parameter chains as trees (main business flows)."""

from urllib.parse import urlparse

import click
from rich.console import Console
from rich.tree import Tree

from ..report import load_report, build_param_flow_mappings, build_flow_graph
from ..export import export_chain_html
from ..utils import normalize_api_path

console = Console()


def escape_rich(text):
    """Escape Rich markup characters in text."""
    return str(text).replace("[", "\\[")


def format_param(params):
    """Format param(s) for display. Accepts single param or list."""
    if isinstance(params, list):
        if len(params) == 0:
            return "[dim]none[/dim]"
        if len(params) == 1:
            param = params[0]
        else:
            # Multiple params - show count and first few
            short_list = [escape_rich(p[:12] + ".." if len(p) > 12 else p) for p in params[:3]]
            suffix = f"+{len(params)-3}" if len(params) > 3 else ""
            return f"[cyan]{', '.join(short_list)}{suffix}[/cyan]"
    else:
        param = params
    short = param[:20] + ".." if len(param) > 20 else param
    return f"[cyan]{escape_rich(short)}[/cyan]"


@click.command()
@click.argument("report_file", default="id_tracker_report.json", type=click.Path(exists=True))
@click.option("--top", "-n", default=10, help="Number of top root chains to show")
@click.option("--min-depth", "-m", default=2, help="Minimum tree depth")
@click.option("--html", "-o", "html_output", default=None, help="Export to interactive HTML file")
def chain(report_file, top, min_depth, html_output):
    """Detect and rank parameter chains as trees (main business flows).

    Finds parameter flow trees where:
    API-A produces params → multiple APIs use them → they produce more params → ...

    Shows branching structure when one API's params feed multiple downstream APIs.
    """
    data = load_report(report_file)

    if not data.flows:
        console.print("[yellow]No flows found in report.[/yellow]")
        return

    sorted_flows = data.sorted_flows

    # Build mappings using shared analysis functions
    param_origins, param_usages, flow_produces = build_param_flow_mappings(sorted_flows)

    # Build flow graph
    flow_graph = build_flow_graph(param_origins, param_usages)

    def format_api(flow_idx):
        """Format API for display."""
        flow = sorted_flows[flow_idx]
        method = flow.get("method", "?")
        url = flow.get("url", "?")
        path = urlparse(url).path or "/"
        if len(path) > 45:
            path = path[:42] + "..."
        # Escape [ in path to prevent Rich markup parsing
        path = path.replace("[", "\\[")
        return f"[bold magenta]{method}[/bold magenta] [white]{path}[/white]"

    def calc_tree_depth(flow_idx, visited):
        """Calculate max depth from this flow."""
        if flow_idx in visited:
            return 0
        visited.add(flow_idx)
        edges = flow_graph.get(flow_idx, [])
        if not edges:
            return 1
        max_child_depth = 0
        for next_idx, _ in edges:
            child_depth = calc_tree_depth(next_idx, visited.copy())
            max_child_depth = max(max_child_depth, child_depth)
        return 1 + max_child_depth

    def count_tree_nodes(flow_idx, visited):
        """Count total nodes in tree."""
        if flow_idx in visited:
            return 0
        visited.add(flow_idx)
        count = 1
        for next_idx, _ in flow_graph.get(flow_idx, []):
            count += count_tree_nodes(next_idx, visited.copy())
        return count

    def get_api_key(flow_idx):
        """Get API key (method + normalized path) for cycle detection."""
        flow = sorted_flows[flow_idx]
        method = flow.get("method", "?")
        url = flow.get("url", "")
        return f"{method} {normalize_api_path(url)}"

    def build_tree_data(flow_idx, via_params, visited_apis, node_index_map, index_counter,
                        deferred_children, first_occurrence):
        """Build tree data structure with cycle continuation.

        Cycle detection is based on API pattern (method + normalized path), not flow_idx.
        """
        api_key = get_api_key(flow_idx)
        is_cycle = api_key in visited_apis

        # Already visited this API pattern? Return ref
        if is_cycle:
            first_idx = first_occurrence.get(api_key, flow_idx)
            target_index = node_index_map.get(first_idx, "?")
            return {"type": "ref", "target_index": target_index, "via_params": via_params, "api_key": api_key}

        # Mark this API pattern as visited
        new_visited = visited_apis | {api_key}
        first_occurrence[api_key] = flow_idx

        # Assign index
        current_index = index_counter[0]
        index_counter[0] += 1
        node_index_map[flow_idx] = current_index

        children = []
        for next_idx, next_params in flow_graph.get(flow_idx, []):
            child = build_tree_data(
                next_idx, next_params, new_visited,
                node_index_map, index_counter, deferred_children, first_occurrence
            )
            if child:
                # If child is a ref, defer its grandchildren to the cycle target
                if child.get("type") == "ref":
                    target_index = child.get("target_index")
                    target_idx = next_idx  # The skipped node's flow_idx
                    for gc_idx, gc_params in flow_graph.get(target_idx, []):
                        gc_api = get_api_key(gc_idx)
                        if gc_idx != target_idx and gc_api not in new_visited:
                            if target_index not in deferred_children:
                                deferred_children[target_index] = []
                            gc = build_tree_data(gc_idx, gc_params, new_visited, node_index_map,
                                               index_counter, deferred_children, first_occurrence)
                            if gc:
                                gc["from_cycle"] = True
                                deferred_children[target_index].append(gc)
                children.append(child)

        return {
            "flow_idx": flow_idx,
            "index": current_index,
            "via_params": via_params,
            "is_cycle": False,
            "api_key": api_key,
            "children": children,
        }

    def inject_deferred(node, deferred_children):
        """Inject deferred children into target nodes."""
        if not node or node.get("type") == "ref":
            return
        idx = node.get("index")
        if idx in deferred_children:
            node["children"].extend(deferred_children[idx])
            del deferred_children[idx]
        for child in node.get("children", []):
            inject_deferred(child, deferred_children)

    def render_tree_node(node, parent_tree, is_root=False):
        """Render tree data to Rich Tree."""
        if node.get("type") == "ref":
            target = node.get("target_index", "?")
            via = format_param(node.get("via_params")) if node.get("via_params") else ""
            parent_tree.add(f"[dim]↩ \\[#{target}] via {via} [italic](continues below)[/italic][/dim]")
            return

        flow_idx = node["flow_idx"]
        current_index = node["index"]
        via_params = node.get("via_params")
        from_cycle = node.get("from_cycle", False)
        children = node.get("children", [])

        # Build label
        from_cycle_mark = "[bold yellow]↳[/bold yellow] " if from_cycle else ""
        index_label = f"[bold green]\\[#{current_index}][/bold green]"

        if via_params and not is_root:
            label = f"{from_cycle_mark}{index_label} [yellow]→[/yellow] {format_param(via_params)} [yellow]→[/yellow] {format_api(flow_idx)}"
        else:
            label = f"{from_cycle_mark}{index_label} {format_api(flow_idx)}"

        if children:
            child_node = parent_tree.add(label)
            for child in children:
                render_tree_node(child, child_node)
        else:
            parent_tree.add(label)

    # Find root candidates (flows that produce params used by others)
    # and rank by tree size/depth
    root_candidates = []
    for flow_idx in flow_produces.keys():
        if flow_graph.get(flow_idx):  # Has outgoing edges
            depth = calc_tree_depth(flow_idx, set())
            nodes = count_tree_nodes(flow_idx, set())
            if depth >= min_depth:
                # Score: prioritize depth, then breadth
                score = depth * 100 + nodes
                root_candidates.append((score, depth, nodes, flow_idx))

    root_candidates.sort(key=lambda x: x[0], reverse=True)

    # Deduplicate: remove roots that are subtrees of higher-ranked roots
    covered_flows = set()
    selected_roots = []

    for score, depth, nodes, flow_idx in root_candidates:
        if flow_idx not in covered_flows:
            selected_roots.append((score, depth, nodes, flow_idx))
            # Mark all flows in this tree as covered
            def mark_covered(idx, visited):
                if idx in visited:
                    return
                visited.add(idx)
                covered_flows.add(idx)
                for next_idx, _ in flow_graph.get(idx, []):
                    mark_covered(next_idx, visited)
            mark_covered(flow_idx, set())

            if len(selected_roots) >= top:
                break

    if not selected_roots:
        console.print("[yellow]No parameter chains found.[/yellow]")
        console.print(f"[dim]Try lowering --min-depth (current: {min_depth})[/dim]")
        return

    console.print()
    console.print("[bold blue]Parameter Chain Trees[/bold blue]")
    console.print("[dim]Showing parameter flow from API responses to subsequent requests[/dim]")
    console.print()

    for rank, (score, depth, nodes, root_idx) in enumerate(selected_roots, 1):
        # Initialize tracking for this tree
        node_index_map = {}
        index_counter = [1]
        deferred_children = {}
        visited_apis = set()
        first_occurrence = {}

        # Build tree data with cycle continuation
        tree_data = build_tree_data(root_idx, None, visited_apis, node_index_map, index_counter,
                                   deferred_children, first_occurrence)

        # Inject deferred children into their targets
        inject_deferred(tree_data, deferred_children)

        # Create Rich Tree for display
        # Note: \[ escapes the bracket in Rich markup to display literal [#N]
        tree = Tree(
            f"[bold yellow]#{rank}[/bold yellow] [bold green]\\[#1][/bold green] {format_api(root_idx)} "
            f"[dim](depth:{depth}, nodes:{nodes})[/dim]"
        )

        # Render children to Rich Tree
        for child in tree_data.get("children", []):
            render_tree_node(child, tree)

        console.print(tree)
        console.print()

    # Summary
    total_roots = len([r for r in root_candidates if r[1] >= min_depth])
    console.print(f"[dim]Showing {len(selected_roots)} of {total_roots} root chains (min depth: {min_depth})[/dim]")
    if selected_roots:
        max_depth = max(d for _, d, _, _ in selected_roots)
        max_nodes = max(n for _, _, n, _ in selected_roots)
        console.print(f"[dim]Max depth: {max_depth}, Max nodes: {max_nodes}[/dim]")

    # HTML export
    if html_output:
        export_chain_html(html_output, sorted_flows, flow_graph, flow_produces, selected_roots)
        console.print(f"\n[green]HTML exported to:[/green] {html_output}")
