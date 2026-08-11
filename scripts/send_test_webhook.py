import argparse
import hashlib
import hmac
import json
import time
import urllib.request


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a signed MaintainerFlow test webhook")
    parser.add_argument("--secret", required=True)
    parser.add_argument("--url", default="http://localhost:8000/webhooks/github")
    parser.add_argument("--delivery", default=f"local-{time.time_ns()}")
    parser.add_argument("--invalid-signature", action="store_true")
    args = parser.parse_args()

    payload = {
        "action": "opened",
        "installation": {"id": 77},
        "repository": {"id": 123, "name": "MaintainerFlow", "owner": {"login": "local"}},
        "pull_request": {
            "number": 1,
            "base": {"sha": "a" * 40},
            "head": {"sha": "b" * 40},
        },
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    signature = "sha256=" + hmac.new(args.secret.encode(), body, hashlib.sha256).hexdigest()
    if args.invalid_signature:
        signature = "sha256=invalid"
    request = urllib.request.Request(
        args.url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": args.delivery,
            "X-Hub-Signature-256": signature,
        },
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        print(response.read().decode())


if __name__ == "__main__":
    main()
