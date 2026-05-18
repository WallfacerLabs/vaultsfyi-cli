"""CLI output helpers."""

from __future__ import annotations

import json
import sys
from enum import Enum
from typing import Any

import typer
from tabulate import tabulate


class OutputFormat(str, Enum):
    table = "table"
    json = "json"


def echo_json(data: Any) -> None:
    typer.echo(json.dumps(data, indent=2, default=str))


def echo_error(error: Exception | str, output: OutputFormat) -> None:
    message = str(error)
    if output == OutputFormat.json:
        typer.echo(json.dumps({"error": message}, indent=2))
    else:
        typer.echo(f"Error: {message}", err=True)


def format_usd(value: float, decimals: int = 2) -> str:
    return f"${value:.{decimals}f}"


def format_apy(value: float) -> str:
    return f"{value * 100:.2f}%"


def print_table(rows: list[dict[str, Any]], headers: dict[str, str] | None = None) -> None:
    if not rows:
        typer.echo("No results")
        return
    if headers:
        table_rows = [{headers.get(k, k): v for k, v in row.items()} for row in rows]
    else:
        table_rows = rows
    typer.echo(tabulate(table_rows, headers="keys", tablefmt="simple"))


def confirm_or_abort(message: str, yes: bool, output: OutputFormat) -> None:
    if yes:
        return
    if output == OutputFormat.json:
        raise typer.BadParameter("transaction commands in JSON mode require --yes")
    if not typer.confirm(message):
        raise typer.Abort()
