#!/usr/bin/env python3
"""One-command local smoke gate; it never writes repository source files."""

import argparse
import json
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "benchmarks/datasets/pr-risk/fixtures/05-authentication.json"


def run(*command: str, timeout: int = 120) -> str:
    result = subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.stdout.strip()


def json_url(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.load(response)


def compose_services() -> dict[str, str]:
    output = run("docker", "compose", "ps", "--format", "json")
    rows = [json.loads(line) for line in output.splitlines() if line]
    return {str(row["Service"]): str(row["State"]) for row in rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-docker", action="store_true")
    parser.add_argument("--start", action="store_true", help="Build and start Compose first.")
    args = parser.parse_args()

    report: dict[str, object] = {"python": sys.version.split()[0]}
    run(sys.executable, "-m", "maintainerflow", "--help")
    analysis = json.loads(
        run(
            sys.executable,
            "-m",
            "maintainerflow",
            "analyze",
            "--input",
            str(FIXTURE),
        )
    )
    report["fixture"] = {
        "status": analysis["status"],
        "risk_level": analysis["risk"]["level"],
        "schema_version": analysis["schema_version"],
    }
    if not args.skip_docker:
        if args.start:
            run("docker", "compose", "up", "--build", "-d", "--wait", timeout=600)
        services = compose_services()
        required = {"api", "db", "redis", "worker", "recovery", "frontend"}
        missing = required - services.keys()
        if missing or any(services[item] != "running" for item in required):
            raise RuntimeError(
                f"Compose services not ready: missing={sorted(missing)} states={services}"
            )
        if json_url("http://localhost:8000/health") != {"status": "ok"}:
            raise RuntimeError("health endpoint failed")
        if json_url("http://localhost:8000/ready") != {"status": "ready"}:
            raise RuntimeError("ready endpoint failed")
        with urllib.request.urlopen("http://localhost:3000/", timeout=10) as response:
            if b"MaintainerFlow" not in response.read():
                raise RuntimeError("frontend smoke check failed")
        if json_url("http://localhost:3000/api/health") != {"status": "ok"}:
            raise RuntimeError("frontend health proxy failed")
        if json_url("http://localhost:3000/api/ready") != {"status": "ready"}:
            raise RuntimeError("frontend readiness proxy failed")
        openapi = json_url("http://localhost:3000/api/openapi.json")
        if openapi.get("info", {}).get("title") != "MaintainerFlow":
            raise RuntimeError("frontend OpenAPI proxy failed")
        run("docker", "compose", "run", "--rm", "--no-deps", "migrate", "alembic", "check")
        revision = run(
            "docker",
            "compose",
            "exec",
            "-T",
            "db",
            "psql",
            "-U",
            "maintainerflow",
            "-d",
            "maintainerflow",
            "-Atc",
            "SELECT version_num FROM alembic_version;",
        )
        report["compose"] = {"services": services, "migration": revision}
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
