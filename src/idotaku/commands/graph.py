"""Graph command - show API dependency graph (which API produces params used by which)."""

from collections import defaultdict

import click
from rich.console import Console
from rich.tree import Tree

from ..report import load_report, build_param_producer_consumer, build_api_dependencies

console = Console()


@click.command()
@click.argument("report_file", default="id_tracker_report.json", type=click.Path(exists=True))
@click.option("--min-connections", "-m", default=1, help="Minimum connections to show an API")
def graph(report_file, min_connections):
    """Show API dependency graph (which API produces params used by which).

    Visualizes the dependency structure: API-A produces param X,
    which is consumed by API-B, API-C, etc.
    """
    data = load_report(report_file)

    if not data.flows:
        console.print("[yellow]No flows found in report.[/yellow]")
        return

    sorted_flows = data.sorted_flows

    # Build param producer/consumer mappings
    param_producer, param_consumers = build_param_producer_consumer(sorted_flows)

    # Build API dependency graph
    api_deps = build_api_dependencies(param_producer, param_consumers)

    console.print()
    console.print("[bold blue]API Dependency Graph[/bold blue]")
    console.print("[dim]Shows which APIs produce parameters consumed by other APIs[/dim]")
    console.print()

    # Filter and sort by connection count
    api_with_deps = []
    for producer_key, params in api_deps.items():
        total_connections = sum(len(consumers) for consumers in params.values())
        if total_connections >= min_connections:
            api_with_deps.append((producer_key, params, total_connections))

    api_with_deps.sort(key=lambda x: x[2], reverse=True)

    for producer_key, params, total_conn in api_with_deps[:30]:
        tree = Tree(f"[bold green]{producer_key}[/bold green] [dim]({total_conn} connections)[/dim]")

        for param_val, consumers in list(params.items())[:10]:
            short_param = param_val[:16] + "..." if len(param_val) > 16 else param_val
            param_node = tree.add(f"[cyan]{short_param}[/cyan]")

            # Group consumers by API
            consumer_apis = defaultdict(list)
            for c in consumers:
                consumer_apis[c["api"]].append(c["field"])

            for consumer_api, fields in list(consumer_apis.items())[:5]:
                field_str = ", ".join(set(fields))[:20]
                param_node.add(f"[yellow]→[/yellow] [white]{consumer_api}[/white] [dim]@ {field_str}[/dim]")

            if len(consumer_apis) > 5:
                param_node.add(f"[dim]+{len(consumer_apis) - 5} more APIs[/dim]")

        if len(params) > 10:
            tree.add(f"[dim]+{len(params) - 10} more params[/dim]")

        console.print(tree)
        console.print()

    # Also show "orphan" APIs (consume but don't produce dependencies)
    all_consumers = set()
    for params in api_deps.values():
        for consumers in params.values():
            for c in consumers:
                all_consumers.add(c["api"])

    all_producers = set(api_deps.keys())
    leaf_apis = all_consumers - all_producers

    if leaf_apis:
        console.print("[dim]Leaf APIs (consume but don't produce tracked params):[/dim]")
        for api in list(leaf_apis)[:10]:
            console.print(f"  [dim]└─ {api}[/dim]")
        if len(leaf_apis) > 10:
            console.print(f"  [dim]   +{len(leaf_apis) - 10} more[/dim]")

    console.print()
    console.print(f"[dim]Showing {len(api_with_deps)} producer APIs with {min_connections}+ connections[/dim]")
