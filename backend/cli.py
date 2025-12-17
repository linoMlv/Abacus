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


if __name__ == "__main__":
    app()
