from typing import cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from maintainerflow.persistence.models import ReleaseDraftRecord
from maintainerflow.release.schemas import ReleaseDraft


class ReleaseDraftRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(
        self,
        repository_id: int,
        input_hash: str,
        draft: ReleaseDraft,
    ) -> tuple[ReleaseDraftRecord, bool]:
        filters = (
            ReleaseDraftRecord.repository_id == repository_id,
            ReleaseDraftRecord.from_ref == draft.from_ref,
            ReleaseDraftRecord.to_ref == draft.to_ref,
            ReleaseDraftRecord.input_hash == input_hash,
        )
        found = await self.session.scalar(select(ReleaseDraftRecord).where(*filters))
        if found:
            return found, False
        row = ReleaseDraftRecord(
            repository_id=repository_id,
            from_ref=draft.from_ref,
            to_ref=draft.to_ref,
            input_hash=input_hash,
            schema_version=draft.schema_version,
            compare_url=draft.compare_url,
            markdown=draft.markdown,
            draft_payload=draft.model_dump(mode="json"),
            limitations=list(draft.limitations),
        )
        try:
            async with self.session.begin_nested():
                self.session.add(row)
                await self.session.flush()
        except IntegrityError:
            found = await self.session.scalar(select(ReleaseDraftRecord).where(*filters))
            if found is None:
                raise
            return found, False
        return row, True

    async def get(self, record_id: int) -> ReleaseDraftRecord | None:
        return cast(
            ReleaseDraftRecord | None,
            await self.session.get(ReleaseDraftRecord, record_id),
        )
