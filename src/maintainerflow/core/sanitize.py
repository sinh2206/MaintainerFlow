import html
import re

SECRET = re.compile(r"(?:github_pat_|ghs_|ghp_|AIza|sk-)[A-Za-z0-9_-]{8,}")
MARKDOWN = re.compile(r"([\\`*_[\]{}()#+.!|])")


def sanitize_text(value: str, limit: int, *, escape_markdown: bool = False) -> str:
    value = "".join(char for char in value if char in "\n\t" or ord(char) >= 32)
    value = SECRET.sub("[REDACTED]", value)
    if escape_markdown:
        value = MARKDOWN.sub(r"\\\1", html.escape(value, quote=False))
    return value[:limit]
