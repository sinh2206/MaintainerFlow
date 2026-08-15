import re
from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).parents[2]
PINNED_ACTION = re.compile(r"^\s*uses:\s*[^\s@]+@([0-9a-f]{40})(?:\s|$)", re.MULTILINE)


def workflow(name: str) -> tuple[dict[str, Any], str]:
    text = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
    parsed = yaml.load(text, Loader=yaml.BaseLoader)
    return cast(dict[str, Any], parsed), text


def test_release_publish_is_unreachable_until_quality_compose_and_package_gates_pass() -> None:
    release, text = workflow("release.yml")
    jobs = release["jobs"]

    assert release["permissions"] == {"contents": "read"}
    assert jobs["package"]["needs"] == ["gate", "compose-gate"]
    assert jobs["publish"]["needs"] == "package"
    assert jobs["publish"]["permissions"] == {"contents": "write"}
    assert all(
        job.get("permissions", {}).get("contents") != "write"
        for name, job in jobs.items()
        if name != "publish"
    )
    assert text.count("gh release create") == 1
    assert 'test "$(git cat-file -t "$GITHUB_REF_NAME")" = tag' in text
    assert 'test "$GITHUB_REF_NAME" = "v$version"' in text
    assert "ruff format --check ." in text
    assert 'pytest -m "not e2e"' in text
    assert 'RUN_E2E: "1"' in text
    assert "alembic check" in text
    assert "sha256sum --check SHA256SUMS" in text
    assert "--verify-tag" in text


def test_workflows_pin_every_third_party_action_to_a_full_commit() -> None:
    for name in ("ci.yml", "release.yml", "security.yml"):
        _, text = workflow(name)
        uses = [line for line in text.splitlines() if "uses:" in line]

        assert uses
        assert len(PINNED_ACTION.findall(text)) == len(uses)
