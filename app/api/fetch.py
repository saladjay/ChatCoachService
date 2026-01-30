import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.dependencies import SessionCategorizedCacheServiceDep


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fetch", tags=["fetch"])


class GenerateProgressResponse(BaseModel):
    found: bool = Field(...)
    session_id: str = Field(...)
    scene: int = Field(...)
    resource: str | None = Field(default=None)
    categories: dict[str, dict[str, Any]] = Field(default_factory=dict)
    timelines: dict[str, list[dict[str, Any]]] | None = Field(default=None)


@router.get("/generate/progress", response_model=GenerateProgressResponse)
async def get_generate_progress(
    cache_service: SessionCategorizedCacheServiceDep,
    session_id: str | None = Query(default=None),
    request_id: str | None = Query(default=None),
    resource: str | None = Query(default=None),
    scene: int = Query(default=1, ge=1, le=3),
    include_timeline: bool = Query(default=False),
    categories: list[str] | None = Query(default=None),
) -> GenerateProgressResponse:
    sid = session_id or request_id
    if not sid:
        raise HTTPException(status_code=400, detail="Missing session_id or request_id")

    # If caller didn't provide resource, try to infer it (Orchestrator cache uses resource=request.resource/url)
    if not resource:
        try:
            resources = await cache_service.list_resources(session_id=sid, limit=1, scene=scene)
            if resources:
                resource = resources[0]
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Cache service error: {e}")

    if not resource:
        return GenerateProgressResponse(
            found=False,
            session_id=sid,
            scene=scene,
            resource=None,
            categories={},
            timelines={} if include_timeline else None,
        )

    try:
        cats = await cache_service.get_resource_categories(
            session_id=sid,
            resource=resource,
            scene=scene,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Cache service error: {e}")

    if categories:
        wanted = set(categories)
        cats = {k: v for (k, v) in cats.items() if k in wanted}

    timelines: dict[str, list[dict[str, Any]]] | None
    if include_timeline:
        timelines = {}
        for category in sorted(cats.keys()):
            try:
                timelines[category] = await cache_service.get_timeline(
                    session_id=sid,
                    category=category,
                    scene=scene,
                )
            except Exception as e:
                raise HTTPException(status_code=502, detail=f"Cache service error: {e}")
    else:
        timelines = None

    return GenerateProgressResponse(
        found=bool(cats),
        session_id=sid,
        scene=scene,
        resource=resource,
        categories=cats,
        timelines=timelines,
    )
