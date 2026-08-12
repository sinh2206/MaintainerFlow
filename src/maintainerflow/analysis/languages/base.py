from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class RepositoryFile(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str = Field(min_length=1, max_length=4_096)
    sha: str = Field(min_length=1, max_length=64)
    size: int = Field(default=0, ge=0)
    content: str | None = None
    generated: bool = False


class LanguageAnalysis(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str
    module: str
    imports: tuple[str, ...] = ()
    public_symbols: tuple[str, ...] = ()
    is_test: bool = False
    limitations: tuple[str, ...] = ()


class LanguageAnalyzer(Protocol):
    name: str
    version: str

    def supports(self, file: RepositoryFile) -> bool: ...

    def analyze(self, file: RepositoryFile) -> LanguageAnalysis: ...
