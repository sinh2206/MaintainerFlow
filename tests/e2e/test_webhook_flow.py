import hashlib
import hmac
import json
import os
import subprocess
import time
import urllib.request

import pytest

pytestmark = pytest.mark.e2e


def require_e2e() -> None:
    if os.getenv("RUN_E2E") != "1":
        pytest.skip("set RUN_E2E=1 after starting Docker Compose")


def test_webhook_reaches_completed_state() -> None:
    require_e2e()
    secret = os.environ["MAINTAINERFLOW_GITHUB_WEBHOOK_SECRET"]
    delivery_id = f"e2e-{time.time_ns()}"
    payload = {
        "action": "opened",
        "installation": {"id": 77},
        "repository": {"id": 123, "name": "MaintainerFlow", "owner": {"login": "test"}},
        "pull_request": {
            "number": 1,
            "base": {"sha": "a" * 40},
            "head": {"sha": "b" * 40},
        },
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    request = urllib.request.Request(
        "http://localhost:8000/webhooks/github",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": delivery_id,
            "X-Hub-Signature-256": signature,
        },
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        assert response.status == 202

    for _ in range(20):
        result = subprocess.run(
            [
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
                f"SELECT status FROM deliveries WHERE github_delivery_id='{delivery_id}'",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        if result.stdout.strip() == "completed":
            return
        time.sleep(0.25)
    pytest.fail("delivery did not reach completed state")
