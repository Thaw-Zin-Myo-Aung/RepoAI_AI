import typer
from rich import print as rprint

app = typer.Typer(no_args_is_help=True)


@app.command()
def hello(name: str = "world") -> None:
    """Say hi to verify the CLI works."""
    rprint(f"[bold green]Hello, {name}![/bold green] RepoAI is alive.")


@app.command()
def plan(intent: str) -> None:
    """Stub for later: accept a refactor intent and echo it."""
    rprint(f"[cyan]Planning…[/cyan] intent = {intent}")


def main() -> None:
    """Entry point for the CLI."""
    app()
