from __future__ import annotations

import json
from dataclasses import asdict

import typer
from rich.console import Console
from rich.table import Table

from src.core.models import DetailViewData, ListViewData, ViewData

_console = Console()


def print_json(data: dict | list) -> None:
    typer.echo(json.dumps(data, indent=2, default=str))


def print_view_table(view: ViewData) -> None:
    if isinstance(view, DetailViewData):
        _print_detail_table(view)
    else:
        _print_list_table(view)


def _print_detail_table(view: DetailViewData) -> None:
    if view.record is None:
        typer.echo("Record not found.")
        return
    table = Table(title=view.entity_title, show_header=True)
    table.add_column("Field", style="bold")
    table.add_column("Value")
    for k, v in view.record.items():
        table.add_row(str(k), str(v))
    _console.print(table)


def _print_list_table(view: ListViewData) -> None:
    if not view.records:
        typer.echo("No records found.")
        return
    columns = list(view.records[0].keys())
    table = Table(title=view.entity_title, show_header=True)
    for col in columns:
        table.add_column(col, style="bold" if col == view.detail_key_field else "")
    for rec in view.records:
        table.add_row(*[str(rec.get(c, "")) for c in columns])
    _console.print(table)


def view_to_dict(view: ViewData) -> dict:
    return asdict(view)
