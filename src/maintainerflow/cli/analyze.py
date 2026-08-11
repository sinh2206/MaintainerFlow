import asyncio
from pathlib import Path
from typing import Annotated

import typer
from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from maintainerflow.ai.gemini import GeminiProvider
from maintainerflow.core.schemas import PullRequestSource
from maintainerflow.services.analyze_pull_request import analyze_pull_request


class GeminiCliSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("GEMINI_API_KEY", "MAINTAINERFLOW_GEMINI_API_KEY"),
    )
    model: str = Field(
        default="gemini-3.5-flash-lite",
        validation_alias=AliasChoices("GEMINI_MODEL", "MAINTAINERFLOW_GEMINI_MODEL"),
    )


def analyze_command(
    input_file: Annotated[
        Path, typer.Option("--input", exists=True, dir_okay=False, readable=True)
    ],
    use_ai: Annotated[
        bool, typer.Option("--ai", help="Add optional Gemini semantic signals.")
    ] = False,
) -> None:
    """Analyze a local PR fixture and print the versioned JSON report."""
    source = PullRequestSource.model_validate_json(input_file.read_text(encoding="utf-8"))
    provider = None
    model = "static-only"
    if use_ai:
        settings = GeminiCliSettings()
        if settings.api_key is None:
            raise typer.BadParameter("GEMINI_API_KEY is required with --ai")
        provider = GeminiProvider(settings.api_key, model=settings.model)
        model = settings.model
    run = asyncio.run(analyze_pull_request(source, ai_provider=provider, model_version=model))
    typer.echo(run.result.model_dump_json(indent=2))
