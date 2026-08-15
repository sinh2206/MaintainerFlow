import hashlib
import json
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e
ROOT = Path(__file__).parents[2]


def source_hash() -> str:
    digest = hashlib.sha256()
    for path in sorted((ROOT / "backend/src").rglob("*.py")):
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def test_fresh_wheel_install_and_smoke_do_not_modify_source(tmp_path: Path) -> None:
    before = source_hash()
    distribution = tmp_path / "dist"
    subprocess.run(
        ["uv", "build", "--out-dir", str(distribution)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    environment = tmp_path / "venv"
    subprocess.run(
        ["uv", "venv", "--python", sys.executable, str(environment)],
        check=True,
        capture_output=True,
        text=True,
    )
    python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    wheel = next(distribution.glob("*.whl"))
    source_distribution = next(distribution.glob("*.tar.gz"))
    with tarfile.open(source_distribution, "r:gz") as archive:
        packaged = set(archive.getnames())
    assert any(name.endswith("/README.md") for name in packaged)
    assert any(name.endswith("/benchmarks/datasets/pr-risk/manifest.json") for name in packaged)
    assert any(
        name.endswith("/backend/migrations/versions/0005_release_assistant.py") for name in packaged
    )
    subprocess.run(
        ["uv", "pip", "install", "--python", str(python), str(wheel)],
        check=True,
        capture_output=True,
        text=True,
    )
    fixture = ROOT / "benchmarks/datasets/pr-risk/fixtures/05-authentication.json"
    result = subprocess.run(
        [str(python), "-m", "maintainerflow", "analyze", "--input", str(fixture)],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(result.stdout)
    benchmark = subprocess.run(
        [str(python), "-m", "maintainerflow", "benchmark", "--suite", "all"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    benchmark_report = json.loads(benchmark.stdout)

    assert report["schema_version"] == "1"
    assert report["risk"]["level"] == "high"
    assert benchmark_report["pr_risk"]["evaluation"]["sample_count"] == 30
    assert benchmark_report["pr_risk"]["comparison"]["requirement_met"] is True
    assert benchmark_report["issue_triage"]["classification"]["macro_f1"] >= 0.8
    assert source_hash() == before


def test_smoke_script_static_path_is_deterministic() -> None:
    command = [sys.executable, str(ROOT / "scripts/smoke_test.py"), "--skip-docker"]
    first = subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
    second = subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)

    assert json.loads(first.stdout) == json.loads(second.stdout)
