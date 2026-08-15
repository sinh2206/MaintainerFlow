import hashlib
import json
from typing import Any

from maintainerflow.core.schemas import AnalysisSnapshot, PullRequestSource


def _hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def create_snapshot(
    source: PullRequestSource,
    *,
    config: dict[str, Any],
    rules_version: str,
    prompt_version: str,
    model_version: str,
) -> AnalysisSnapshot:
    diff_hash = _hash(source.diff.encode())
    metadata_hash = _hash(
        json.dumps(
            {
                "title": source.title,
                "body": source.body,
                "changed_files": [file.model_dump(mode="json") for file in source.changed_files],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    )
    config_hash = _hash(json.dumps(config, sort_keys=True, separators=(",", ":")).encode())
    identity = {
        "repository": source.repository.model_dump(mode="json"),
        "pull_request_number": source.number,
        "base_sha": source.base_sha,
        "head_sha": source.head_sha,
        "diff_hash": diff_hash,
        "metadata_hash": metadata_hash,
        "config_hash": config_hash,
        "rules_version": rules_version,
        "prompt_version": prompt_version,
        "model_version": model_version,
    }
    snapshot_id = _hash(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode())
    return AnalysisSnapshot(id=snapshot_id, **identity)
