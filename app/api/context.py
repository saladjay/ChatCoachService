from typing import Any

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.dependencies import PersistenceServiceDep


router = APIRouter(prefix="/context", tags=["context"])


class DispatchSummaryRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    target_id: str = Field(..., min_length=1)
    conversation_id: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    url: str = Field(..., min_length=1, description="Webhook target URL")


@router.get("/summaries")
async def list_summaries(
    user_id: str,
    target_id: str,
    persistence_service: PersistenceServiceDep,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    logs = await persistence_service.list_conversation_summaries(
        user_id=user_id,
        target_id=target_id,
        limit=limit,
        offset=offset,
    )
    return {
        "user_id": user_id,
        "target_id": target_id,
        "summaries": [
            {
                "id": log.id,
                "conversation_id": log.conversation_id,
                "summary": log.summary,
                "created_at": log.created_at,
            }
            for log in logs
        ],
    }


@router.post("/summary/dispatch")
async def dispatch_summary(
    request: DispatchSummaryRequest,
) -> dict[str, Any]:
    payload = {
        "user_id": request.user_id,
        "target_id": request.target_id,
        "conversation_id": request.conversation_id,
        "summary": request.summary,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(request.url, json=payload)

    return {
        "dispatched": resp.is_success,
        "status_code": resp.status_code,
        "response_text": resp.text,
    }
