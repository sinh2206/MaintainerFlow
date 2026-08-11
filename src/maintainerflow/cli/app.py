import typer

from maintainerflow import __version__
from maintainerflow.cli.analyze import analyze_command
from maintainerflow.config import get_settings

app = typer.Typer(no_args_is_help=True)
app.command("analyze")(analyze_command)


@app.callback()
def main() -> None:
    """MaintainerFlow utilities."""


@app.command("config-check")
def config_check() -> None:
    """Validate configuration without printing secrets."""
    settings = get_settings()
    typer.echo(f"MaintainerFlow {__version__}: configuration valid ({settings.environment})")


if __name__ == "__main__":
    app()
