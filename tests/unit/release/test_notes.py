from itertools import permutations

import pytest
from pydantic import ValidationError

from maintainerflow.release.breaking import detect_breaking_candidate
from maintainerflow.release.changelog import generate_changelog
from maintainerflow.release.notes import build_release_draft, contributors, render_release_notes
from maintainerflow.release.schemas import Changelog, MergedPullRequest
from tests.unit.release.conftest import make_pull_request


def _render(changelog: Changelog, **kwargs: object) -> str:
    return render_release_notes(
        repository="acme/widgets",
        from_ref="v0.4.0",
        to_ref="v1.0.0",
        compare_url="https://github.com/acme/widgets/compare/v0.4.0...v1.0.0",
        changelog=changelog,
        **kwargs,  # type: ignore[arg-type]
    )


def test_markdown_has_compare_range_and_omits_empty_categories() -> None:
    markdown = _render(generate_changelog((make_pull_request(2, "fix: crash"),)))

    assert "[v0.4.0...v1.0.0]" in markdown
    assert "## Fixes" in markdown
    assert "## Features" not in markdown
    assert markdown.endswith("\n")


def test_contributors_are_case_insensitive_unique_sorted_and_exclude_bots() -> None:
    changelog = generate_changelog(
        (
            make_pull_request(1, "fix: a", author="Zoë"),
            make_pull_request(2, "fix: b", author="ana"),
            make_pull_request(3, "fix: c", author="Ana"),
            make_pull_request(4, "fix: d", author="dependabot[bot]"),
            make_pull_request(5, "fix: e", author="GitHub-Actions"),
            make_pull_request(6, "fix: f", author="renovate-bot"),
        )
    )

    assert contributors(changelog) == ("Ana", "Zoë")
    markdown = _render(changelog)
    assert "@Ana, @Zoë" in markdown
    assert "dependabot" not in markdown.split("## Contributors", 1)[1]


def test_unicode_and_multiline_malicious_title_cannot_inject_heading_or_html() -> None:
    pull = make_pull_request(
        1,
        "fix: hỗ trợ tiếng Việt ](https://evil.test)\n## Injected <script>alert(1)</script>",
    )

    markdown = _render(generate_changelog((pull,)))

    assert "\n## Injected" not in markdown
    assert "\\](https://evil.test)" in markdown
    assert "<script>" not in markdown
    assert "&lt;script&gt;" in markdown


def test_breaking_candidates_and_limitations_are_stable_and_deduplicated() -> None:
    first = make_pull_request(8, "feat!: remove X")
    second = make_pull_request(2, "fix!: change Y")
    candidates = tuple(
        item
        for item in (detect_breaking_candidate(first), detect_breaking_candidate(second))
        if item
    )
    changelog = generate_changelog((first, second))

    forward = _render(
        changelog,
        breaking_candidates=(*candidates, candidates[0]),
        limitations=("No signed tags", " No   signed tags ", "Offline data"),
    )
    reverse = _render(
        changelog,
        breaking_candidates=reversed(candidates),
        limitations=("Offline data", "No signed tags"),
    )

    assert forward == reverse
    assert forward.count("[#8]") == 1
    assert forward.index("[#2]") < forward.index("[#8]")
    assert "maintainer confirmation" in forward
    assert forward.count("No signed tags") == 1


def test_render_is_identical_for_every_entry_permutation() -> None:
    pulls = (
        make_pull_request(3, "docs: ba", author="c"),
        make_pull_request(1, "feat: một", author="a"),
        make_pull_request(2, "fix: hai", author="b"),
    )
    categorized = generate_changelog(pulls).entries
    expected = _render(Changelog(entries=categorized))

    assert all(_render(Changelog(entries=order)) == expected for order in permutations(categorized))


def test_build_draft_matches_renderer_and_normalizes_metadata() -> None:
    changelog = generate_changelog((make_pull_request(1, "feat: search", author="alice"),))

    draft = build_release_draft(
        repository=" acme/widgets ",
        from_ref=" v0.4.0 ",
        to_ref=" v1.0.0 ",
        compare_url="https://github.com/acme/widgets/compare/v0.4.0...v1.0.0",
        changelog=changelog,
        limitations=("  Preview only  ",),
    )

    assert draft.repository == "acme/widgets"
    assert draft.contributors == ("alice",)
    assert draft.limitations == ("Preview only",)
    assert draft.markdown == _render(changelog, limitations=("Preview only",))


@pytest.mark.parametrize(
    "url",
    (
        "javascript:alert(1)",
        "ftp://github.com/acme/widgets/pull/1",
        "https://github.com/a b",
        "https://github.com/acme/>injected",
        "https://github.com/acme/widgets\x00hidden",
    ),
)
def test_pull_request_rejects_non_http_or_injectable_url(url: str) -> None:
    with pytest.raises(ValidationError):
        MergedPullRequest(
            github_id=1,
            number=1,
            title="fix: safe",
            url=url,
            author="safe",
        )


def test_renderer_rejects_untrusted_compare_url_before_emitting_markdown() -> None:
    with pytest.raises(ValueError, match="HTTP"):
        render_release_notes(
            repository="acme/widgets",
            from_ref="v0.4.0",
            to_ref="v1.0.0",
            compare_url="javascript:alert(1)",
            changelog=Changelog(),
        )
