import re
from typing import Protocol

from maintainerflow.issue.schemas import IssueSource, SimilarIssue

STOP_WORDS = frozenset(
    {"a", "an", "and", "for", "in", "is", "of", "on", "the", "to", "with", "please"}
)


class CandidateRetriever(Protocol):
    async def retrieve(self, query: IssueSource, limit: int) -> tuple[IssueSource, ...]: ...


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if len(token) > 1 and token not in STOP_WORDS
    }


def _jaccard(left: set[str], right: set[str]) -> float:
    return len(left & right) / len(left | right) if left or right else 0


class LexicalDuplicateEngine:
    def score(self, query: IssueSource, candidate: IssueSource) -> float:
        query_title = _tokens(query.title)
        candidate_title = _tokens(candidate.title)
        if query_title and query_title == candidate_title:
            return 1.0
        title_score = _jaccard(query_title, candidate_title)
        body_score = _jaccard(_tokens(query.body), _tokens(candidate.body))
        score = title_score * 0.8 + body_score * 0.2
        if title_score < 0.34:
            score *= 0.5
        return round(score, 4)

    def rank(
        self,
        query: IssueSource,
        candidates: tuple[IssueSource, ...],
        *,
        top_k: int = 3,
        min_score: float = 0.2,
    ) -> tuple[SimilarIssue, ...]:
        ranked = sorted(
            (
                (self.score(query, candidate), candidate)
                for candidate in candidates
                if candidate.github_id != query.github_id
            ),
            key=lambda item: (-item[0], item[1].number),
        )
        return tuple(
            SimilarIssue(
                github_id=candidate.github_id,
                number=candidate.number,
                url=candidate.url,
                score=score,
                reason="exact_title" if score == 1 else "lexical_overlap",
            )
            for score, candidate in ranked[:top_k]
            if score >= min_score
        )
