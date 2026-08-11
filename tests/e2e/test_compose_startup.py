import json
import os
import subprocess
import urllib.request

import pytest

pytestmark = pytest.mark.e2e


def test_compose_services_and_health() -> None:
    if os.getenv("RUN_E2E") != "1":
        pytest.skip("set RUN_E2E=1 after starting Docker Compose")

    result = subprocess.run(
        ["docker", "compose", "ps", "--format", "json"],
        check=True,
        capture_output=True,
        text=True,
    )
    services = [json.loads(line) for line in result.stdout.splitlines() if line]
    names = {service["Service"] for service in services}
    assert {"api", "db", "redis", "worker", "recovery"} <= names

    with urllib.request.urlopen("http://localhost:8000/health") as response:
        assert json.load(response) == {"status": "ok"}
    with urllib.request.urlopen("http://localhost:8000/ready") as response:
        assert json.load(response) == {"status": "ready"}
