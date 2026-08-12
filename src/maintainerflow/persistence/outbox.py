import re
from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from maintainerflow.core.enums import OutboxStatus
from maintainerflow.core.sanitize import sanitize_text
from maintainerflow.persistence.models import OutboxEvent


def safe_error_code(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", sanitize_text(value, 128))[:128]


class OutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_key(self, key: str) -> OutboxEvent | None:
        return cast(
            OutboxEvent | None,
            await self.session.scalar(
                select(OutboxEvent).where(OutboxEvent.idempotency_key == key)
            ),
        )

    async def enqueue(
        self,
        *,
        event_type: str,
        aggregate_id: str,
        idempotency_key: str,
        payload: dict[str, object],
    ) -> tuple[OutboxEvent, bool]:
        existing = await self.get_by_key(idempotency_key)
        if existing:
            return existing, False
        event = OutboxEvent(
            event_type=event_type,
            aggregate_id=aggregate_id,
            idempotency_key=idempotency_key,
            payload=payload,
            status=OutboxStatus.PENDING.value,
            attempts=0,
        )
        try:
            async with self.session.begin_nested():
                self.session.add(event)
                await self.session.flush()
            return event, True
        except IntegrityError:
            existing = await self.get_by_key(idempotency_key)
            if existing is None:
                raise
            return existing, False

    async def claim(self, limit: int, lease_seconds: int) -> list[OutboxEvent]:
        now = datetime.now(UTC)
        rows = list(
            await self.session.scalars(
                select(OutboxEvent)
                .where(
                    or_(
                        (OutboxEvent.status == OutboxStatus.PENDING.value)
                        & (OutboxEvent.available_at <= now),
                        (OutboxEvent.status == OutboxStatus.PROCESSING.value)
                        & (OutboxEvent.lease_expires_at < now),
                    )
                )
                .order_by(OutboxEvent.id)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        )
        for row in rows:
            row.status = OutboxStatus.PROCESSING.value
            row.attempts += 1
            row.lease_expires_at = now + timedelta(seconds=lease_seconds)
            row.last_error = None
        await self.session.flush()
        return rows

    async def mark_sent(self, event_id: int, check_id: int) -> None:
        event = await self.session.get(OutboxEvent, event_id)
        if event:
            event.status = OutboxStatus.SENT.value
            event.github_check_id = check_id
            event.lease_expires_at = None
            event.sent_at = datetime.now(UTC)

    async def retry(self, event_id: int, error_code: str, delay_seconds: int) -> None:
        event = await self.session.get(OutboxEvent, event_id)
        if event:
            event.status = OutboxStatus.PENDING.value
            event.available_at = datetime.now(UTC) + timedelta(seconds=max(1, delay_seconds))
            event.lease_expires_at = None
            event.last_error = safe_error_code(error_code)

    async def dead_letter(self, event_id: int, error_code: str) -> None:
        event = await self.session.get(OutboxEvent, event_id)
        if event:
            event.status = OutboxStatus.DEAD_LETTER.value
            event.lease_expires_at = None
            event.last_error = safe_error_code(error_code)
