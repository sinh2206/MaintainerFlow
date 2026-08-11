import json
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import ValidationError

from maintainerflow.api.dependencies import EnqueueDep, SessionDep, SettingsDep
from maintainerflow.core.errors import (
    InvalidEventPayloadError,
    InvalidSignatureError,
    UnsupportedEventError,
)
from maintainerflow.core.schemas import JsonObject, WebhookResponse
from maintainerflow.github.auth import verify_webhook_signature
from maintainerflow.github.events import parse_event
from maintainerflow.services.process_delivery import record_and_enqueue_delivery

router = APIRouter(prefix="/webhooks", tags=["github"])


@router.post("/github", response_model=WebhookResponse, status_code=status.HTTP_202_ACCEPTED)
async def github_webhook(
    request: Request,
    settings: SettingsDep,
    session: SessionDep,
    enqueue: EnqueueDep,
    github_event: Annotated[str, Header(alias="X-GitHub-Event")],
    github_delivery: Annotated[str, Header(alias="X-GitHub-Delivery", min_length=1)],
    github_signature: Annotated[str | None, Header(alias="X-Hub-Signature-256")] = None,
) -> WebhookResponse:
    body = await request.body()
    try:
        verify_webhook_signature(
            body,
            github_signature,
            settings.github_webhook_secret.get_secret_value(),
        )
    except InvalidSignatureError as exc:
        raise HTTPException(status_code=401, detail="invalid webhook signature") from exc

    try:
        payload: JsonObject = json.loads(body)
        if not isinstance(payload, dict):
            raise InvalidEventPayloadError("payload must be a JSON object")
        envelope = parse_event(github_event, payload)
    except (json.JSONDecodeError, InvalidEventPayloadError, ValidationError) as exc:
        raise HTTPException(status_code=400, detail="invalid webhook payload") from exc
    except UnsupportedEventError:
        return WebhookResponse(status="ignored")

    result = await record_and_enqueue_delivery(
        session=session,
        envelope=envelope,
        github_delivery_id=github_delivery,
        request_id=request.state.request_id,
        enqueue=enqueue,
    )
    return WebhookResponse(
        status="accepted" if result.created else "duplicate",
        delivery_id=result.delivery_id,
    )
