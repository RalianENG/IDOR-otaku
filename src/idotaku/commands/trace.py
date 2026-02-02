"""Trace command - visualize API call transitions showing how IDs flow between requests."""

import click
from rich.console import Console
from rich.tree import Tree

from ..report import load_report, build_id_transition_map

console = Console()


@click.command()
@click.argument("report_file", default="id_tracker_report.json", type=click.Path(exists=True))
@click.option("--compact", is_flag=True, help="Compact view (hide IDs not used in subsequent requests)")
def trace(report_file, compact):
    """Visualize API call transitions showing how IDs flow between requests.

    Shows a tree where each API response's IDs connect to subsequent requests that use them.
    """
    data = load_report(report_file)

    potential_idor_values = data.idor_values

    if not data.flows:
        console.print("[yellow]No flows found in report.[/yellow]")
        return

    sorted_flows = data.sorted_flows

    console.print()
    console.print("[bold blue]API Call Trace - ID Transition Tree[/bold blue]")
    console.print()

    # Build ID transition maps using shared analysis function
    id_to_origin, id_to_subsequent_usage = build_id_transition_map(sorted_flows)

    # Track which flows have been shown as children
    shown_as_child = set()

    def format_id(id_info, show_arrow=False):
        """Format an ID for display."""
        id_val = id_info["value"]
        id_type = id_info.get("type", "?")
        location = id_info.get("location", "?")
        field = id_info.get("field")
        is_idor = id_val in potential_idor_values

        # Shorten long IDs
        display_val = id_val[:16] + "..." if len(id_val) > 16 else id_val

        style = "red" if is_idor else "cyan"
        idor_mark = " [red]⚠[/red]" if is_idor else ""

        loc_str = f"{location}"
        if field:
            loc_str += f".{field}"

        arrow = "→ " if show_arrow else ""
        return f"{arrow}[{style}]{display_val}[/{style}] [dim]({id_type})[/dim] @ {loc_str}{idor_mark}"

    def get_id_transitions(response_ids):
        """Get subsequent API calls that use these response IDs."""
        transitions = {}  # id_value -> list of (flow_idx, usage_info)
        for res_id in response_ids:
            id_val = res_id["value"]
            if id_val in id_to_subsequent_usage:
                transitions[id_val] = id_to_subsequent_usage[id_val]
        return transitions

    # Display the trace tree
    for i, flow in enumerate(sorted_flows):
        # Skip if this flow was already shown as a child transition
        if compact and i in shown_as_child:
            continue

        method = flow.get("method", "?")
        url = flow.get("url", "?")
        timestamp = flow.get("timestamp", "")
        time_part = timestamp.split("T")[1][:8] if "T" in timestamp else ""
        request_ids = flow.get("request_ids", [])
        response_ids = flow.get("response_ids", [])

        # Shorten URL
        if len(url) > 50:
            url = url[:47] + "..."

        # Create tree for this API call
        tree = Tree(
            f"[bold magenta]({method})[/bold magenta] [white]{url}[/white] [dim]{time_part}[/dim]"
        )

        # Add request IDs (inputs to this API) with origin tracking
        if request_ids:
            req_branch = tree.add("[yellow]REQ[/yellow]")
            for req_id in request_ids:
                id_val = req_id["value"]
                req_node = req_branch.add(format_id(req_id))

                # Show where this ID came from (origin)
                if id_val in id_to_origin:
                    origin_info = id_to_origin[id_val]
                    origin_flow_idx = origin_info["flow_idx"]
                    if origin_flow_idx < i:  # Only show if from a previous flow
                        origin_flow = sorted_flows[origin_flow_idx]
                        origin_method = origin_flow.get("method", "?")
                        origin_url = origin_flow.get("url", "?")
                        origin_time = origin_flow.get("timestamp", "").split("T")[1][:8] if "T" in origin_flow.get("timestamp", "") else ""

                        if len(origin_url) > 35:
                            origin_url = origin_url[:32] + "..."

                        origin_loc = origin_info["location"]
                        if origin_info["field"]:
                            origin_loc += f".{origin_info['field']}"

                        req_node.add(
                            f"[green]← from[/green] [bold magenta]({origin_method})[/bold magenta] [dim]{origin_url}[/dim] [dim]{origin_time}[/dim] @ {origin_loc}"
                        )

        # Add response IDs and their transitions
        if response_ids:
            res_branch = tree.add("[green]RES[/green]")

            # Get transitions for response IDs
            transitions = get_id_transitions(response_ids)

            for res_id in response_ids:
                id_val = res_id["value"]
                id_node = res_branch.add(format_id(res_id))

                # Show subsequent usages of this ID
                if id_val in transitions:
                    for usage in transitions[id_val]:
                        next_flow_idx = usage["flow_idx"]
                        if next_flow_idx <= i:
                            continue  # Only show forward transitions

                        shown_as_child.add(next_flow_idx)
                        next_flow = sorted_flows[next_flow_idx]
                        next_method = next_flow.get("method", "?")
                        next_url = next_flow.get("url", "?")
                        next_time = next_flow.get("timestamp", "").split("T")[1][:8] if "T" in next_flow.get("timestamp", "") else ""

                        if len(next_url) > 40:
                            next_url = next_url[:37] + "..."

                        loc_str = usage["location"]
                        if usage["field"]:
                            loc_str += f".{usage['field']}"

                        # Add the transition arrow and subsequent API call
                        transition_node = id_node.add(
                            f"[yellow]→[/yellow] [bold magenta]({next_method})[/bold magenta] [white]{next_url}[/white] [dim]{next_time}[/dim] @ {loc_str}"
                        )

                        # Show what IDs this subsequent call produced
                        next_response_ids = next_flow.get("response_ids", [])
                        if next_response_ids:
                            for next_res_id in next_response_ids[:5]:  # Limit to 5
                                transition_node.add(format_id(next_res_id, show_arrow=True))
                            if len(next_response_ids) > 5:
                                transition_node.add(f"[dim]... +{len(next_response_ids) - 5} more[/dim]")
                elif compact:
                    # In compact mode, mark IDs that aren't used later
                    pass  # Already shown, just no children

        console.print(tree)
        console.print()

    # Summary
    console.print(f"[dim]Total: {len(sorted_flows)} API calls[/dim]")
    if potential_idor_values:
        console.print(f"[red]⚠ {len(potential_idor_values)} potential IDOR IDs marked[/red]")
