import re
import shlex
from dataclasses import dataclass
from typing import cast

from maintainerflow.core.schemas import ChangedFile

HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


@dataclass(frozen=True)
class ParsedDiff:
    files: tuple[ChangedFile, ...]
    additions: int
    deletions: int
    truncated: bool = False
    limitations: tuple[str, ...] = ()


def _clean_path(value: str) -> str:
    value = value.strip().strip('"')
    return value[2:] if value.startswith(("a/", "b/")) else value


def parse_unified_diff(raw: str, max_bytes: int = 1_000_000) -> ParsedDiff:
    encoded = raw.encode()
    truncated = len(encoded) > max_bytes
    text = encoded[:max_bytes].decode(errors="ignore") if truncated else raw
    limitations: list[str] = []
    if truncated:
        limitations.append(f"Diff truncated at {max_bytes} bytes.")
    if not text.strip():
        return ParsedDiff((), 0, 0, limitations=("Diff is empty.",))

    files: list[ChangedFile] = []
    current: dict[str, object] | None = None
    patch: list[str] = []

    def flush() -> None:
        nonlocal current, patch
        if current is None:
            return
        path = str(current.get("path") or "")
        malformed = not bool(path)
        if malformed:
            path = "unknown"
        files.append(
            ChangedFile(
                path=path,
                previous_path=current.get("previous_path"),
                change_type=current.get("change_type", "modified"),
                additions=current.get("additions", 0),
                deletions=current.get("deletions", 0),
                patch="\n".join(patch),
                malformed=malformed,
            )
        )
        current, patch = None, []

    for line in text.splitlines():
        if line.startswith("diff --git "):
            flush()
            try:
                parts = shlex.split(line)
                old_path, path = _clean_path(parts[-2]), _clean_path(parts[-1])
                current = {
                    "path": path,
                    "previous_path": old_path if old_path != path else None,
                    "change_type": "modified",
                    "additions": 0,
                    "deletions": 0,
                }
            except (ValueError, IndexError):
                current = {"path": "", "change_type": "unknown", "malformed": True}
            patch.append(line)
            continue
        if current is None:
            continue
        patch.append(line)
        if line.startswith("new file mode"):
            current["change_type"] = "added"
        elif line.startswith("deleted file mode"):
            current["change_type"] = "deleted"
        elif line.startswith("rename from "):
            current["previous_path"] = _clean_path(line[12:])
            current["change_type"] = "renamed"
        elif line.startswith("rename to "):
            current["path"] = _clean_path(line[10:])
            current["change_type"] = "renamed"
        elif line.startswith("Binary files ") or line == "GIT binary patch":
            current["change_type"] = "binary"
        elif line.startswith("+") and not line.startswith("+++"):
            current["additions"] = cast(int, current.get("additions", 0)) + 1
        elif line.startswith("-") and not line.startswith("---"):
            current["deletions"] = cast(int, current.get("deletions", 0)) + 1
        elif line.startswith("@@") and HUNK.match(line) is None:
            current["malformed"] = True
    flush()

    if not files:
        limitations.append("Malformed diff: no file header found.")
    elif any(file.malformed for file in files):
        limitations.append("One or more diff entries are malformed.")
    return ParsedDiff(
        tuple(files),
        sum(file.additions for file in files),
        sum(file.deletions for file in files),
        truncated,
        tuple(limitations),
    )
