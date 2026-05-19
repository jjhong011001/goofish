"""CLI entry point for Xianyu scraper."""

import asyncio
import sys

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from scraper import auth, exporter
from scraper.parser import parse_items
from scraper.search import search_keyword, ALL_FIELDS

console = Console()


@click.group()
def cli():
    """Xianyu (goofish.com) product search & price comparison tool."""


@cli.command()
def login():
    """Open browser for login and save session."""
    asyncio.run(_login())


async def _login():
    console.print("[bold cyan]Opening browser for login...[/bold cyan]")
    await auth.login_and_save()
    console.print("[bold green]Session saved successfully.[/bold green]")


@cli.command()
@click.argument("keyword")
@click.option("--pages", default=3, show_default=True, help="Number of pages to scrape.")
@click.option(
    "--format", "fmt", default="csv", show_default=True,
    type=click.Choice(["csv", "excel"], case_sensitive=False),
    help="Export format.",
)
@click.option(
    "--fields",
    default=None,
    help=(
        "Comma-separated fields to export. "
        f"Available: {', '.join(ALL_FIELDS)}. "
        "Default: all fields."
    ),
)
@click.option(
    "--delay-min", default=1.5, show_default=True,
    help="Minimum seconds between pages.",
)
@click.option(
    "--delay-max", default=3.0, show_default=True,
    help="Maximum seconds between pages.",
)
@click.option(
    "--location", default=None,
    help="Filter by location (comma-separated). e.g. '北京,上海,广东'",
)
@click.option("--debug", is_flag=True, help="Print raw API JSON responses.")
def search(keyword: str, pages: int, fmt: str, fields: str | None,
           delay_min: float, delay_max: float, location: str | None, debug: bool):
    """Search KEYWORD on Xianyu and export results.

    \b
    Examples:
      python main.py search "iPhone 15"
      python main.py search "MacBook" --pages 10 --delay-min 3 --delay-max 6
      python main.py search "AirPods" --fields "title,price,condition,location"
      python main.py search "Switch" --format excel --fields "title,price,seller_nick"
      python main.py search "iPhone" --location "北京,上海"
    """
    field_list = [f.strip() for f in fields.split(",")] if fields else None
    if field_list:
        invalid = [f for f in field_list if f not in ALL_FIELDS]
        if invalid:
            console.print(f"[red]Unknown fields: {', '.join(invalid)}[/red]")
            console.print(f"Available: {', '.join(ALL_FIELDS)}")
            sys.exit(1)

    location_list = [l.strip() for l in location.split(",")] if location else None

    asyncio.run(_search(keyword, pages, fmt, field_list, delay_min, delay_max, location_list, debug))

async def _search(
    keyword: str,
    pages: int,
    fmt: str,
    fields: list[str] | None,
    delay_min: float,
    delay_max: float,
    locations: list[str] | None,
    debug: bool,
):
    if not auth.session_exists():
        console.print(
            "[bold red]No session found. Run `python main.py login` first.[/bold red]"
        )
        sys.exit(1)

    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Loading session...", total=None)

            context = await auth.load_context(p)

            progress.update(task, description="Checking session validity...")
            valid = await auth.check_session_valid(context)
            if not valid:
                console.print(
                    "[bold red]Session expired. Run `python main.py login` to refresh.[/bold red]"
                )
                await context.browser.close()
                sys.exit(1)

            progress.update(
                task,
                description=(
                    f'Searching "{keyword}" ({pages} page(s), '
                    f'delay {delay_min}~{delay_max}s)...'
                ),
            )
            raw_responses = await search_keyword(
                context, keyword,
                pages=pages,
                debug=debug,
                delay_min=delay_min,
                delay_max=delay_max,
            )

            progress.update(task, description="Parsing results...")
            items = parse_items(raw_responses)

            await context.browser.close()

    if not items:
        console.print(
            "[yellow]No items found. Try --debug to inspect raw API responses.[/yellow]"
        )
        sys.exit(0)

    # Location filter
    if locations:
        before = len(items)
        items = [
            item for item in items
            if any(loc in item.get("location", "") for loc in locations)
        ]
        console.print(
            f"[cyan]Location filter {locations}: {before} → {len(items)} items[/cyan]"
        )

    console.print(f"[green]Found {len(items)} items.[/green]")
    _print_preview(items[:5], fields)
    _print_stats(items)

    out_path = exporter.export(items, keyword, fmt=fmt, fields=fields)
    exported_fields = fields or ALL_FIELDS
    console.print(
        f"[bold green]Exported {len(items)} items "
        f"({len(exported_fields)} fields) to:[/bold green] {out_path}"
    )


def _print_stats(items: list[dict]):
    prices = sorted(p for p in (item.get("price") for item in items) if p is not None)
    if not prices:
        return

    count = len(prices)
    avg   = sum(prices) / count
    low   = prices[0]
    high  = prices[-1]
    mid   = prices[count // 2] if count % 2 else (prices[count // 2 - 1] + prices[count // 2]) / 2
    total_want = sum(item.get("want_count") or 0 for item in items)

    from rich.table import Table as RichTable
    t = RichTable(title="价格统计", show_header=True, header_style="bold magenta")
    t.add_column("指标", style="cyan", width=10)
    t.add_column("数值", justify="right", style="bold yellow")

    t.add_row("商品数量", str(len(items)))
    t.add_row("有价格数", str(count))
    t.add_row("均  价", f"¥{avg:.2f}")
    t.add_row("最低价", f"¥{low:.2f}")
    t.add_row("最高价", f"¥{high:.2f}")
    t.add_row("中位价", f"¥{mid:.2f}")
    t.add_row("总想要数", str(total_want))
    console.print(t)


def _print_preview(items: list[dict], fields: list[str] | None):
    preview_cols = fields[:6] if fields else ["item_id", "title", "price", "condition", "seller_nick", "location"]
    table = Table(title="Preview (first 5 items)", show_lines=True)
    for col in preview_cols:
        table.add_column(col, overflow="fold", max_width=30)
    for item in items:
        table.add_row(*[str(item.get(c, "")) for c in preview_cols])
    console.print(table)


if __name__ == "__main__":
    cli()
