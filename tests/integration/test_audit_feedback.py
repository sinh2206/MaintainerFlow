from pathlib import Path

from sqlalchemy import func, select

from maintainerflow.core.schemas import CheckRunFeedbackEnvelope, PullRequestSource
from maintainerflow.persistence.database import Database
from maintainerflow.persistence.models import AuditEvent
from maintainerflow.persistence.repositories import AnalysisRepository, DeliveryRepository
from maintainerflow.services.analyze_pull_request import analyze_pull_request
from maintainerflow.services.record_feedback import record_feedback
from tests.helpers import make_envelope

FIXTURE = Path(__file__).parents[2] / "benchmarks/datasets/pr-risk/fixtures/01-readme-only.json"


async def test_feedback_is_append_only_and_scoped_to_analysis_repository(
    database: Database,
) -> None:
    envelope = make_envelope()
    source = PullRequestSource.model_validate_json(FIXTURE.read_text(encoding="utf-8")).model_copy(
        update={"repository": envelope.repository}
    )
    async with database.session() as session:
        async with session.begin():
            delivery, _ = await DeliveryRepository(session).create("feedback", envelope, "request")
            run = await analyze_pull_request(
                source,
                repository=AnalysisRepository(session),
                repository_id=delivery.repository_id,
            )
        assert run.analysis_id is not None
        feedback = CheckRunFeedbackEnvelope(
            repository=envelope.repository,
            installation=envelope.installation,
            analysis_id=run.analysis_id,
            identifier="useful",
            actor_id=10,
            actor_login="maintainer",
            actor_type="User",
        )
        async with session.begin():
            assert await record_feedback(session, feedback)
        async with session.begin():
            assert not await record_feedback(
                session, feedback.model_copy(update={"actor_type": "Bot"})
            )
            assert not await record_feedback(
                session,
                feedback.model_copy(
                    update={"repository": envelope.repository.model_copy(update={"github_id": 999})}
                ),
            )

        assert await session.scalar(select(func.count()).select_from(AuditEvent)) == 1
        stored = await AnalysisRepository(session).get_result(run.snapshot.id)
        assert stored == run.result
