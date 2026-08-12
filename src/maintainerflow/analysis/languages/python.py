import ast
from pathlib import PurePosixPath

from maintainerflow.analysis.languages.base import LanguageAnalysis, RepositoryFile


def _module(path: str) -> str:
    parts = list(PurePosixPath(path).with_suffix("").parts)
    if parts and parts[0] in {"src", "lib"}:
        parts.pop(0)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _relative(current: str, module: str | None, level: int) -> str:
    package = current.split(".")[:-1]
    base = package[: max(0, len(package) - max(0, level - 1))]
    if module:
        base.extend(module.split("."))
    return ".".join(base)


class PythonAnalyzer:
    name = "python"
    version = "python-ast-v1"

    def supports(self, file: RepositoryFile) -> bool:
        return file.path.endswith(".py")

    def analyze(self, file: RepositoryFile) -> LanguageAnalysis:
        module = _module(file.path)
        lowered = file.path.lower()
        is_test = lowered.startswith("tests/") or "/test" in lowered or lowered.endswith("_test.py")
        if file.generated or file.content is None:
            reason = "generated_file_skipped" if file.generated else "source_content_unavailable"
            return LanguageAnalysis(
                path=file.path, module=module, is_test=is_test, limitations=(reason,)
            )
        try:
            tree = ast.parse(file.content, filename=file.path)
        except SyntaxError:
            return LanguageAnalysis(
                path=file.path, module=module, is_test=is_test, limitations=("python_syntax_error",)
            )
        imports: list[str] = []
        symbols: list[str] = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                base = (
                    _relative(module, node.module, node.level)
                    if node.level
                    else (node.module or "")
                )
                if node.module:
                    imports.append(base)
                    imports.extend(f"{base}.{alias.name}" for alias in node.names)
                else:
                    imports.extend(f"{base}.{alias.name}".strip(".") for alias in node.names)
            elif isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ) and not node.name.startswith("_"):
                symbols.append(node.name)
        return LanguageAnalysis(
            path=file.path,
            module=module,
            imports=tuple(dict.fromkeys(item for item in imports if item)),
            public_symbols=tuple(symbols),
            is_test=is_test,
        )
