"""IDOR verification command."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import click
import questionary
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..interactive import STYLE
from ..report import load_report
from ..report.scoring import score_all_findings
from ..verify import (
    ComparisonResult,
    Modification,
    RequestData,
    ResponseData,
    VerifyHttpClient,
    VerifyResult,
    compare_responses,
    suggest_modifications,
)
from ..verify.suggestions import CUSTOM_INPUT

console = Console()

LEVEL_COLORS = {
    "critical": "red",
    "high": "yellow",
    "medium": "blue",
    "low": "dim",
}

VERDICT_COLORS = {
    "VULNERABLE": "bold red",
    "LIKELY_VULNERABLE": "bold yellow",
    "INCONCLUSIVE": "bold blue",
    "NOT_VULNERABLE": "bold green",
}


@click.command("verify")
@click.argument(
    "report_file",
    default="id_tracker_report.json",
    type=click.Path(exists=True),
)
@click.option(
    "--output", "-o",
    default="verify_results.json",
    help="Output file for verification results",
)
@click.option("--no-save", is_flag=True, help="Don't save results to file")
@click.option("--timeout", default=30.0, help="Request timeout in seconds")
@click.option(
    "--no-verify-ssl", is_flag=True,
    help="Disable SSL certificate verification",
)
@click.option(
    "--proxy", default=None,
    help="HTTP proxy for requests (e.g., http://127.0.0.1:8080)",
)
@click.option(
    "--min-score", default=0,
    help="Minimum risk score to show (0-100)",
)
@click.option(
    "--level", "-l",
    type=click.Choice(["critical", "high", "medium", "low"]),
    default=None,
    help="Filter by risk level",
)
def verify(
    report_file: str,
    output: str,
    no_save: bool,
    timeout: float,
    no_verify_ssl: bool,
    proxy: Optional[str],
    min_score: int,
    level: Optional[str],
) -> None:
    """Verify IDOR candidates by sending modified requests.

    Loads IDOR findings from a report, suggests parameter modifications,
    and lets you send verification requests with explicit confirmation.

    \b
    Examples:
        idotaku verify report.json
        idotaku verify report.json --proxy http://127.0.0.1:8080
        idotaku verify report.json --min-score 50
    """
    # Load and score
    data = load_report(report_file)

    if not data.potential_idor:
        console.print("[green]No IDOR candidates to verify.[/green]")
        return

    scored = score_all_findings(data.potential_idor)
    if min_score > 0:
        scored = [s for s in scored if s.get("risk_score", 0) >= min_score]
    if level:
        scored = [s for s in scored if s.get("risk_level") == level]

    if not scored:
        console.print("[dim]No findings match the filter criteria.[/dim]")
        return

    # Authorization warning
    _display_legal_warning()

    proceed = questionary.confirm(
        "Do you have authorization to test this target?",
        default=False,
        style=STYLE,
    ).ask()
    if not proceed:
        console.print("[dim]Aborted.[/dim]")
        return

    # Initialize HTTP client
    client = VerifyHttpClient(
        timeout=timeout,
        verify_ssl=not no_verify_ssl,
        proxy=proxy,
    )

    # Verification loop
    results: list[VerifyResult] = []

    while True:
        # Select finding
        finding = _prompt_select_finding(scored)
        if finding is None:
            break

        # Select specific usage
        usage = _prompt_select_usage(finding)
        if usage is None:
            continue

        # Build original request from report data
        original_request = _build_request_from_report(
            finding, usage, data.flows
        )
        original_response = _build_original_response(finding, usage, data.flows)

        # Display original request
        _display_request(original_request, "Original Request")

        # If no headers in report (old format), prompt for auth
        if not original_request.headers:
            original_request = _prompt_auth_headers(original_request)

        # Suggest modifications
        suggestions = suggest_modifications(
            finding["id_value"], finding["id_type"]
        )
        modification = _prompt_select_modification(
            finding, suggestions, original_request, usage
        )
        if modification is None:
            continue

        # Apply modification
        modified_request = _apply_modification(original_request, modification)

        # Display modified request
        _display_request(modified_request, "Modified Request")

        # Final confirmation
        send_confirm = questionary.confirm(
            "Send this request?",
            default=False,
            style=STYLE,
        ).ask()
        if not send_confirm:
            console.print("[dim]Skipped.[/dim]")
            continue

        # Send request
        try:
            response = client.send(modified_request)
        except Exception as e:
            console.print(f"[red]Request failed:[/red] {e}")
            continue

        # Compare and display
        comparison = compare_responses(response, original_response)
        _display_response(response)
        _display_comparison(comparison)

        result = VerifyResult(
            finding_id_value=finding["id_value"],
            finding_id_type=finding["id_type"],
            original_request=original_request,
            modified_request=modified_request,
            modification=modification,
            response=response,
            original_response=original_response,
            comparison=comparison,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        results.append(result)

        # Continue?
        cont = questionary.confirm(
            "Test another finding?",
            default=True,
            style=STYLE,
        ).ask()
        if not cont:
            break

    # Save results
    if results and not no_save:
        _save_results(results, output, report_file)
        console.print(f"\n[green]Results saved:[/green] {output}")

    if results:
        _display_summary(results)


# --- Display helpers ---


def _display_legal_warning() -> None:
    """Display authorization warning."""
    console.print()
    console.print(Panel(
        "[bold red]AUTHORIZATION WARNING[/bold red]\n\n"
        "This tool sends real HTTP requests to the target server.\n"
        "Only use this on systems you are authorized to test.\n\n"
        "By proceeding, you confirm that:\n"
        "  1. You have written authorization to test this target\n"
        "  2. You understand the requests will be sent to a live server\n"
        "  3. You accept responsibility for all requests sent",
        title="[bold red]WARNING[/bold red]",
        border_style="red",
    ))
    console.print()


def _display_request(request: RequestData, title: str) -> None:
    """Display request details."""
    lines = [
        f"[bold]{request.method}[/bold] {request.url}",
    ]
    if request.headers:
        for name, value in list(request.headers.items())[:10]:
            display_value = value[:80] + "..." if len(value) > 80 else value
            lines.append(f"  [dim]{name}:[/dim] {display_value}")
        if len(request.headers) > 10:
            lines.append(f"  [dim]... ({len(request.headers) - 10} more)[/dim]")
    if request.body:
        body_preview = request.body[:200]
        if len(request.body) > 200:
            body_preview += "..."
        lines.append(f"\n  [dim]Body:[/dim] {body_preview}")

    console.print(Panel("\n".join(lines), title=title, border_style="cyan"))


def _display_response(response: ResponseData) -> None:
    """Display response details."""
    status_color = "green" if response.status_code < 400 else "red"
    lines = [
        f"Status: [{status_color}]{response.status_code}[/{status_color}]",
        f"Content-Length: {response.content_length}",
        f"Time: {response.elapsed_ms:.0f}ms",
    ]
    if response.body:
        body_preview = response.body[:300]
        if len(response.body) > 300:
            body_preview += "..."
        lines.append(f"\n[dim]{body_preview}[/dim]")

    console.print(Panel("\n".join(lines), title="Response", border_style="cyan"))


def _display_comparison(comparison: ComparisonResult) -> None:
    """Display comparison result."""
    color = VERDICT_COLORS.get(comparison.verdict, "white")
    console.print(f"\nVerdict: [{color}]{comparison.verdict}[/{color}]")
    for detail in comparison.details:
        console.print(f"  {detail}")
    console.print()


def _display_summary(results: list[VerifyResult]) -> None:
    """Display verification session summary."""
    table = Table(title="Verification Summary")
    table.add_column("ID", style="cyan")
    table.add_column("Modification")
    table.add_column("Status")
    table.add_column("Verdict")

    for r in results:
        color = VERDICT_COLORS.get(r.comparison.verdict, "white")
        table.add_row(
            r.finding_id_value[:20],
            r.modification.description,
            str(r.response.status_code),
            f"[{color}]{r.comparison.verdict}[/{color}]",
        )

    console.print(table)


# --- Prompt helpers ---


def _prompt_select_finding(
    scored: list[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """Prompt user to select an IDOR finding."""
    choices = []
    for i, item in enumerate(scored):
        score_val = item.get("risk_score", 0)
        level_val = item.get("risk_level", "?")
        id_val = item.get("id_value", "?")[:30]
        id_type = item.get("id_type", "?")
        choices.append({
            "value": str(i),
            "name": f"[{score_val:3d}] {level_val:8s} {id_val} ({id_type})",
        })
    choices.append({"value": "__quit__", "name": "Quit"})

    result = questionary.select(
        "Select IDOR candidate to verify:",
        choices=choices,
        style=STYLE,
    ).ask()

    if result is None or result == "__quit__":
        return None

    return scored[int(result)]


def _prompt_select_usage(
    finding: dict[str, Any],
) -> Optional[dict[str, Any]]:
    """Prompt user to select a specific usage if multiple exist."""
    usages = finding.get("usages", [])
    if not usages:
        console.print("[red]No usages found for this finding.[/red]")
        return None

    if len(usages) == 1:
        return usages[0]

    choices = []
    for i, u in enumerate(usages):
        method = u.get("method", "?")
        url = u.get("url", "?")
        location = u.get("location", "?")
        choices.append({
            "value": str(i),
            "name": f"{method} {url[:60]} ({location})",
        })

    result = questionary.select(
        "Select usage to verify:",
        choices=choices,
        style=STYLE,
    ).ask()

    if result is None:
        return None

    return usages[int(result)]


def _prompt_auth_headers(request: RequestData) -> RequestData:
    """Prompt user to provide authentication headers."""
    console.print(
        "[yellow]No headers found in report (old format). "
        "Please provide authentication.[/yellow]"
    )

    auth = questionary.text(
        "Authorization header value (empty to skip):",
        default="",
        style=STYLE,
    ).ask()
    if auth:
        request.headers["Authorization"] = auth

    cookie = questionary.text(
        "Cookie header value (empty to skip):",
        default="",
        style=STYLE,
    ).ask()
    if cookie:
        request.headers["Cookie"] = cookie

    return request


def _prompt_select_modification(
    finding: dict[str, Any],
    suggestions: list[Any],
    request: RequestData,
    usage: dict[str, Any],
) -> Optional[Modification]:
    """Prompt user to select a parameter modification."""
    from ..verify.models import SuggestedValue

    choices = []
    for i, s in enumerate(suggestions):
        if isinstance(s, SuggestedValue):
            display_val = s.value if s.value != CUSTOM_INPUT else ""
            choices.append({
                "value": str(i),
                "name": f"{s.description}" + (
                    f" -> {display_val}" if display_val else ""
                ),
            })

    result = questionary.select(
        "Select parameter modification:",
        choices=choices,
        style=STYLE,
    ).ask()

    if result is None:
        return None

    selected = suggestions[int(result)]

    if selected.value == CUSTOM_INPUT:
        custom = questionary.text(
            "Enter custom value:",
            style=STYLE,
        ).ask()
        if custom is None:
            return None
        new_value = custom
        description = f"Custom: {custom}"
    else:
        new_value = selected.value
        description = selected.description

    return Modification(
        original_value=finding["id_value"],
        modified_value=new_value,
        location=usage.get("location", "url_path"),
        field_name=usage.get("field_name"),
        description=description,
    )


# --- Request building ---


def _build_request_from_report(
    finding: dict[str, Any],
    usage: dict[str, Any],
    flows: list[dict[str, Any]],
) -> RequestData:
    """Build a RequestData from report data."""
    url = usage.get("url", "")
    method = usage.get("method", "GET")

    # Try to find the matching flow for full request data
    headers: dict[str, str] = {}
    body: Optional[str] = None

    for flow in flows:
        if flow.get("url") == url and flow.get("method") == method:
            headers = dict(flow.get("request_headers", {}))
            body = flow.get("request_body")
            break

    return RequestData(
        method=method,
        url=url,
        headers=headers,
        body=body,
    )


def _build_original_response(
    finding: dict[str, Any],
    usage: dict[str, Any],
    flows: list[dict[str, Any]],
) -> Optional[ResponseData]:
    """Build original ResponseData from report flow data."""
    url = usage.get("url", "")
    method = usage.get("method", "GET")

    for flow in flows:
        if flow.get("url") == url and flow.get("method") == method:
            status_code = flow.get("status_code", 0)
            if status_code == 0:
                return None
            response_body = flow.get("response_body", "")
            return ResponseData(
                status_code=status_code,
                headers=dict(flow.get("response_headers", {})),
                body=response_body or "",
                content_length=len(response_body) if response_body else 0,
            )

    return None


def _apply_modification(
    original: RequestData,
    modification: Modification,
) -> RequestData:
    """Apply a modification to create a new request."""
    request = RequestData(
        method=original.method,
        url=original.url,
        headers=dict(original.headers),
        body=original.body,
    )

    old = modification.original_value
    new = modification.modified_value
    location = modification.location
    field_name = modification.field_name

    if location == "url_path":
        request.url = request.url.replace(old, new)

    elif location == "query":
        parsed = urlparse(request.url)
        params = parse_qs(parsed.query, keep_blank_values=True)
        if field_name and field_name in params:
            params[field_name] = [new]
        else:
            # Fallback: replace in query string
            new_query = parsed.query.replace(old, new)
            request.url = urlunparse(parsed._replace(query=new_query))
            return request
        new_query = urlencode(params, doseq=True)
        request.url = urlunparse(parsed._replace(query=new_query))

    elif location == "body":
        if request.body:
            content_type = request.headers.get(
                "content-type", request.headers.get("Content-Type", "")
            )
            if "application/json" in content_type:
                request.body = _replace_in_json(
                    request.body, old, new, field_name
                )
            else:
                request.body = request.body.replace(old, new)

    elif location == "header":
        if field_name:
            header_key = _find_header_key(request.headers, field_name)
            if header_key:
                request.headers[header_key] = request.headers[
                    header_key
                ].replace(old, new)

    return request


def _replace_in_json(
    body: str,
    old_value: str,
    new_value: str,
    field_name: Optional[str],
) -> str:
    """Replace a value in a JSON body."""
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return body.replace(old_value, new_value)

    if field_name:
        _set_nested_value(data, field_name, old_value, new_value)
    else:
        return body.replace(old_value, new_value)

    return json.dumps(data, ensure_ascii=False)


def _set_nested_value(
    data: Any,
    field_path: str,
    old_value: str,
    new_value: str,
) -> None:
    """Set a value in a nested dict using a dotted field path."""
    parts = field_path.split(".")
    current = data

    for part in parts[:-1]:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return

    final_key = parts[-1]
    if isinstance(current, dict) and final_key in current:
        if str(current[final_key]) == old_value:
            # Preserve type if possible
            if isinstance(current[final_key], int):
                try:
                    current[final_key] = int(new_value)
                except ValueError:
                    current[final_key] = new_value
            else:
                current[final_key] = new_value


def _find_header_key(
    headers: dict[str, str],
    field_name: str,
) -> Optional[str]:
    """Find the actual header key (case-insensitive match)."""
    # Handle special field_name formats from tracker
    # e.g., "cookie:session_id", "authorization:bearer"
    if ":" in field_name:
        prefix = field_name.split(":")[0]
    else:
        prefix = field_name

    for key in headers:
        if key.lower() == prefix.lower():
            return key

    return None


# --- Results saving ---


def _save_results(
    results: list[VerifyResult],
    output: str,
    report_file: str,
) -> None:
    """Save verification results to JSON."""
    output_data = {
        "session": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source_report": report_file,
        },
        "results": [_result_to_dict(r) for r in results],
    }

    with open(output, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)


def _result_to_dict(result: VerifyResult) -> dict[str, Any]:
    """Convert a VerifyResult to a serializable dict."""
    return {
        "finding_id": result.finding_id_value,
        "finding_type": result.finding_id_type,
        "modification": {
            "original": result.modification.original_value,
            "modified": result.modification.modified_value,
            "location": result.modification.location,
            "description": result.modification.description,
        },
        "request": {
            "method": result.modified_request.method,
            "url": result.modified_request.url,
        },
        "response": {
            "status_code": result.response.status_code,
            "content_length": result.response.content_length,
            "elapsed_ms": result.response.elapsed_ms,
        },
        "original_response": {
            "status_code": result.original_response.status_code,
            "content_length": result.original_response.content_length,
        } if result.original_response else None,
        "verdict": result.comparison.verdict,
        "timestamp": result.timestamp,
    }
