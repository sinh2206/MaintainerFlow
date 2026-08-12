from maintainerflow.analysis.languages.base import RepositoryFile
from maintainerflow.analysis.languages.python import PythonAnalyzer


def test_python_ast_extracts_imports_symbols_and_test_role() -> None:
    result = PythonAnalyzer().analyze(
        RepositoryFile(
            path="tests/test_service.py",
            sha="abc",
            content="from maintainerflow import config\n\ndef test_flow():\n    pass\n",
        )
    )

    assert result.module == "tests.test_service"
    assert "maintainerflow" in result.imports
    assert "maintainerflow.config" in result.imports
    assert result.public_symbols == ("test_flow",)
    assert result.is_test


def test_python_ast_fails_safe_on_invalid_missing_and_generated_source() -> None:
    analyzer = PythonAnalyzer()
    invalid = analyzer.analyze(RepositoryFile(path="bad.py", sha="a", content="def ("))
    missing = analyzer.analyze(RepositoryFile(path="empty.py", sha="b"))
    generated = analyzer.analyze(
        RepositoryFile(path="generated.py", sha="c", content="x = 1", generated=True)
    )

    assert invalid.limitations == ("python_syntax_error",)
    assert missing.limitations == ("source_content_unavailable",)
    assert generated.limitations == ("generated_file_skipped",)


def test_python_ast_resolves_relative_import() -> None:
    result = PythonAnalyzer().analyze(
        RepositoryFile(
            path="src/pkg/service.py",
            sha="relative",
            content="from . import utils\n",
        )
    )

    assert result.imports == ("pkg.utils",)
