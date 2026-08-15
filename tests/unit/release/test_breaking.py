from maintainerflow.release.breaking import detect_breaking_candidate, detect_breaking_candidates
from tests.unit.release.conftest import make_pull_request


def test_exact_breaking_label_creates_evidence_backed_candidate() -> None:
    result = detect_breaking_candidate(
        make_pull_request(1, "feat: new API", labels=("BREAKING_CHANGE",))
    )

    assert result is not None
    assert result.requires_maintainer_confirmation is True
    assert [(item.kind, item.text) for item in result.evidence] == [("label", "BREAKING_CHANGE")]


def test_conventional_bang_after_scope_is_detected() -> None:
    result = detect_breaking_candidate(make_pull_request(1, "feat(api)!: remove legacy field"))

    assert result is not None
    assert result.evidence[0].kind == "conventional_marker"
    assert result.evidence[0].source == "pull_request.title"


def test_structured_breaking_footer_is_detected_but_prose_is_not() -> None:
    positive = make_pull_request(
        1, "feat: auth", body="Details\n\nBREAKING CHANGE: Tokens expire sooner"
    )
    negative = make_pull_request(2, "docs: wording", body="This is not a BREAKING CHANGE at all.")

    result = detect_breaking_candidate(positive)

    assert result is not None
    assert result.evidence[0].text == "Tokens expire sooner"
    assert detect_breaking_candidate(negative) is None


def test_public_api_and_migration_evidence_keep_provenance() -> None:
    pull = make_pull_request(
        1,
        "refactor: explicit evidence",
        body=(
            "Public API change: remove Widget.open\n"
            "Migration required: rename `token` to `api_token`"
        ),
    )

    result = detect_breaking_candidate(
        pull,
        public_api_evidence=("Symbol Widget.close was removed",),
        migration_evidence=("Migration 004 drops old_name",),
    )

    assert result is not None
    assert {item.kind for item in result.evidence} == {"public_api", "migration"}
    assert {item.source for item in result.evidence} == {
        "pull_request.body:public-api",
        "pull_request.body:migration",
        "repository-analysis",
    }


def test_unstructured_breaking_words_and_migration_path_are_false_positives() -> None:
    pull = make_pull_request(
        1,
        "Breaking news for migration docs",
        body="No public API is removed and no migration is required.",
        labels=("not-breaking", "migration"),
        changed_files=("migrations/004_index.py", "src/public_api.py"),
    )

    assert detect_breaking_candidate(pull) is None


def test_duplicate_external_evidence_is_collapsed() -> None:
    result = detect_breaking_candidate(
        make_pull_request(1, "refactor: API"),
        public_api_evidence=("Removed X", "Removed X", "  Removed   X  "),
    )

    assert result is not None
    assert len(result.evidence) == 1


def test_collection_is_order_invariant_and_deduplicates_provider_retries() -> None:
    first = make_pull_request(9, "fix!: nine", github_id=900)
    second = make_pull_request(2, "feat!: two", github_id=200)

    assert detect_breaking_candidates((first, second, first)) == detect_breaking_candidates(
        (second, first)
    )


def test_maximum_title_and_long_repository_evidence_are_bounded_not_crashing() -> None:
    pull = make_pull_request(1, f"feat!: {'x' * 992}")

    result = detect_breaking_candidate(
        pull,
        public_api_evidence=(f"Public export changed: {'p' * 4_096}",),
    )

    assert result is not None
    assert all(0 < len(item.text) <= 500 for item in result.evidence)
