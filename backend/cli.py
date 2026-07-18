from pathlib import Path

import typer
import uvicorn
from rich.console import Console
from rich.panel import Panel
from sqlmodel import SQLModel

from database import engine

app = typer.Typer()
console = Console()


@app.command()
def start(host: str = "127.0.0.1", port: int = 8000, reload: bool = True):
    """
    Start the FastAPI server.
    """
    console.print(
        Panel(
            f"Starting Abacus Backend on http://{host}:{port}",
            title="Abacus",
            style="bold green",
        )
    )
    uvicorn.run("main:app", host=host, port=port, reload=reload)


@app.command()
def setup_db():
    """
    Create database tables.
    """
    console.print("[bold yellow]Creating tables...[/bold yellow]")
    SQLModel.metadata.create_all(engine)
    console.print("[bold green]Tables created successfully.[/bold green]")


@app.command()
def reset_db():
    """
    Drop and recreate database tables.
    """
    confirm = typer.confirm("Are you sure you want to drop all tables?")
    if not confirm:
        console.print("[bold red]Aborted.[/bold red]")
        raise typer.Abort()

    console.print("[bold red]Dropping all tables...[/bold red]")
    SQLModel.metadata.drop_all(engine)
    console.print("[bold green]Tables dropped.[/bold green]")
    setup_db()


@app.command()
def purge_logs(days: int = typer.Option(None, help="Override LOG_RETENTION_DAYS.")):
    """
    Delete log entries older than the retention window.
    """
    from sqlmodel import Session

    from log_retention import purge_old_logs

    with Session(engine) as session:
        deleted = purge_old_logs(session, retention_days=days)
    console.print(f"[bold green]Purged {deleted} log entries.[/bold green]")


@app.command("migrate-mysql")
def migrate_mysql(
    dump: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        help="Path to the MySQL .sql export (mysqldump / phpMyAdmin).",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Parse, import and validate, then roll back."
    ),
):
    """
    Import a legacy MySQL dump into the PostgreSQL database (one-off migration).

    The schema must already exist ('alembic upgrade head') and the target tables
    must be empty. Everything runs in a single transaction.
    """
    from mysql_import import MysqlImportError, migrate_mysql_dump

    try:
        imported = migrate_mysql_dump(dump, dry_run=dry_run)
    except MysqlImportError as exc:
        console.print(f"[bold red]Migration refused:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc

    total = sum(imported.values())
    for table, rows in imported.items():
        console.print(f"  {rows:>6} rows  ->  {table}")
    if dry_run:
        console.print(
            f"[bold yellow]Dry run:[/bold yellow] {total} rows validated, "
            "rolled back (nothing committed)."
        )
    else:
        console.print(
            f"[bold green]Migration committed:[/bold green] {total} rows imported."
        )


if __name__ == "__main__":
    app()
