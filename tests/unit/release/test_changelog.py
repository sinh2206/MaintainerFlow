from itertools import permutations

from maintainerflow.release.changelog import classify_pull_request, generate_changelog
from maintainerflow.release.schemas import CategoryRule, ChangelogConfig
from tests.unit.release.conftest import make_pull_request


def test_classifies_twelve_prs_without_loss_or_duplication() -> None:
    pulls = (
        make_pull_request(1, "feat: one"),
        make_pull_request(2, "feat(ui): two"),
        make_pull_request(3, "New thing", labels=("enhancement",)),
        make_pull_request(4, "fix: four"),
        make_pull_request(5, "Repair five", labels=("bug",)),
        make_pull_request(6, "perf: six"),
        make_pull_request(7, "Speed seven", labels=("performance",)),
        make_pull_request(8, "docs: eight"),
        make_pull_request(9, "Guide nine", labels=("documentation",)),
        make_pull_request(10, "chore: ten"),
        make_pull_request(11, "build(ci): eleven"),
        make_pull_request(12, "Unclassified twelve"),
    )

    result = generate_changelog(pulls)

    assert len(result.entries) == 12
    assert {item.pull_request.github_id for item in result.entries} == {
        pull.github_id for pull in pulls
    }
    assert [item.category for item in result.entries].count("feature") == 3
    assert [item.category for item in result.entries].count("fix") == 2
    assert [item.category for item in result.entries].count("performance") == 2
    assert [item.category for item in result.entries].count("docs") == 2
    assert [item.category for item in result.entries].count("chore") == 3


def test_multi_label_uses_configured_precedence() -> None:
    config = ChangelogConfig(
        rules=(
            CategoryRule(category="docs", labels=("docs",)),
            CategoryRule(category="fix", labels=("bug",)),
            CategoryRule(category="feature", labels=("feature",)),
        )
    )
    pull = make_pull_request(1, "feat: conflicting title", labels=("FEATURE", "bug", " docs "))

    result = classify_pull_request(pull, config)

    assert result.category == "docs"
    assert result.matched_by == "label:docs"


def test_label_precedes_title_within_same_rule_order() -> None:
    pull = make_pull_request(1, "docs: update API", labels=("bug",))

    result = classify_pull_request(pull)

    assert result.category == "fix"
    assert result.matched_by == "label:bug"


def test_title_prefix_requires_conventional_boundary() -> None:
    assert classify_pull_request(make_pull_request(1, "fixture update")).category == "chore"
    assert (
        classify_pull_request(make_pull_request(2, "performance anxiety notes")).category == "chore"
    )


def test_duplicate_github_id_is_deterministically_collapsed() -> None:
    first = make_pull_request(8, "fix: zulu", github_id=800)
    canonical = make_pull_request(8, "fix: alpha", github_id=800)
    unique = make_pull_request(2, "feat: unique")

    forward = generate_changelog((first, unique, canonical))
    reverse = generate_changelog((canonical, unique, first))

    assert forward == reverse
    assert forward.duplicate_github_ids == (800,)
    assert len(forward.entries) == 2
    assert (
        next(
            item for item in forward.entries if item.pull_request.github_id == 800
        ).pull_request.title
        == "fix: alpha"
    )


def test_every_input_permutation_has_identical_output() -> None:
    pulls = (
        make_pull_request(12, "docs: guide"),
        make_pull_request(3, "fix: crash"),
        make_pull_request(7, "feat: search"),
        make_pull_request(4, "perf: cache"),
    )
    expected = generate_changelog(pulls)

    assert all(generate_changelog(order) == expected for order in permutations(pulls))


def test_repeated_generation_is_idempotent() -> None:
    pulls = (make_pull_request(1, "feat: stable"), make_pull_request(2, "docs: stable"))

    first = generate_changelog(pulls)
    second = generate_changelog(entry.pull_request for entry in first.entries)

    assert second == first
