import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_backend_has_one_canonical_python_source_tree() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert not (ROOT / "src").exists()
    assert (ROOT / "backend/src/maintainerflow/__init__.py").is_file()
    assert project["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == [
        "backend/src/maintainerflow"
    ]
    assert project["tool"]["mypy"]["mypy_path"] == "backend/src"


def test_backend_owns_migrations_and_both_container_builds() -> None:
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    alembic = (ROOT / "alembic.ini").read_text(encoding="utf-8")

    assert (ROOT / "backend/migrations/versions/0005_release_assistant.py").is_file()
    assert "script_location = %(here)s/backend/migrations" in alembic
    assert "dockerfile: backend/Dockerfile" in compose
    assert "dockerfile: frontend/Dockerfile" in compose
