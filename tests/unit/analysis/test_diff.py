from maintainerflow.analysis.diff import parse_unified_diff


def test_parses_rename_and_binary() -> None:
    parsed = parse_unified_diff(
        """diff --git a/old.py b/new.py
similarity index 100%
rename from old.py
rename to new.py
diff --git a/image.png b/image.png
Binary files a/image.png and b/image.png differ"""
    )
    assert parsed.files[0].change_type == "renamed"
    assert parsed.files[0].previous_path == "old.py"
    assert parsed.files[1].change_type == "binary"


def test_empty_truncated_and_malformed_fail_safe() -> None:
    assert "empty" in parse_unified_diff("").limitations[0].lower()
    truncated = parse_unified_diff(
        "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n" + "+x\n" * 20,
        max_bytes=50,
    )
    assert truncated.truncated
    malformed = parse_unified_diff("not a diff")
    assert malformed.files == ()
    assert "Malformed" in malformed.limitations[0]
