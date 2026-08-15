from sqlalchemy.ext.asyncio import AsyncSession

from maintainerflow.core.schemas import CheckRunFeedbackEnvelope
from maintainerflow.persistence.repositories import (
    AnalysisRepository,
    AuditRepository,
    DeliveryRepository,
)


async def record_feedback(session: AsyncSession, feedback: CheckRunFeedbackEnvelope) -> bool:
    if feedback.actor_type.lower() == "bot":
        return False
    analyses = AnalysisRepository(session)
    repository_id = await analyses.get_repository_id(feedback.analysis_id)
    repository = await DeliveryRepository(session).get_repository_by_github_id(
        feedback.repository.github_id
    )
    if repository is None or repository_id != repository.id:
        return False
    await AuditRepository(session).record(
        "check_feedback",
        repository_id=repository.id,
        analysis_id=feedback.analysis_id,
        actor_id=feedback.actor_id,
        actor_login=feedback.actor_login,
        payload={"identifier": feedback.identifier},
    )
    return True
