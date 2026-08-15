from pathlib import Path
from typing import Annotated

import typer
from pydantic import BaseModel, ConfigDict, Field

from maintainerflow.release.breaking import detect_breaking_candidates
from maintainerflow.release.changelog import DEFAULT_CHANGELOG_CONFIG, generate_changelog
from maintainerflow.release.notes import build_release_draft
from maintainerflow.release.schemas import ChangelogConfig, MergedPullRequest


class ReleasePreviewInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    repository: str = Field(min_length=1, max_length=255)
    from_ref: str = Field(min_length=1, max_length=255)
    to_ref: str = Field(min_length=1, max_length=255)
    compare_url: str = Field(min_length=1, max_length=2_048)
    pull_requests: tuple[MergedPullRequest, ...]
    config: ChangelogConfig = DEFAULT_CHANGELOG_CONFIG
    limitations: tuple[str, ...] = ()


def release_command(
    input_file: Annotated[
        Path, typer.Option("--input", exists=True, dir_okay=False, readable=True)
    ],
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
    publish: Annotated[
        bool,
        typer.Option(
            "--publish",
            help="Reserved for a future reviewed publisher; never enabled in v1.0.",
        ),
    ] = False,
) -> None:
    """Preview or export deterministic release notes without a GitHub write."""
    if publish:
        raise typer.BadParameter(
            "GitHub Release publishing is intentionally unavailable; export and review the draft"
        )
    source = ReleasePreviewInput.model_validate_json(input_file.read_text(encoding="utf-8"))
    changelog = generate_changelog(source.pull_requests, source.config)
    draft = build_release_draft(
        repository=source.repository,
        from_ref=source.from_ref,
        to_ref=source.to_ref,
        compare_url=source.compare_url,
        changelog=changelog,
        breaking_candidates=detect_breaking_candidates(source.pull_requests),
        limitations=source.limitations,
    )
    if output:
        output.write_text(draft.markdown, encoding="utf-8", newline="\n")
    else:
        typer.echo(draft.markdown, nl=False)
