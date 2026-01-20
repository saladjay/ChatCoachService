from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.dependencies import UserProfileServiceDep
from app.models.schemas import Message


router = APIRouter(prefix="/user_profile", tags=["user_profile"])


class LearnTraitsRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    messages: list[Message] | None = None
    selected_sentences: list[str] | None = None
    provider: str | None = None
    model: str | None = None
    store: bool = True
    map_to_standard: bool = True


@router.post("/traits/learn")
async def learn_traits(
    request: LearnTraitsRequest,
    user_profile_service: UserProfileServiceDep,
) -> dict[str, Any]:
    if request.messages is None and request.selected_sentences is None:
        raise HTTPException(
            status_code=400,
            detail="Either messages or selected_sentences must be provided",
        )

    try:
        result = await user_profile_service.learn_new_traits(
            user_id=request.user_id,
            messages=request.messages,
            selected_sentences=request.selected_sentences,
            provider=request.provider,
            model=request.model,
            store=request.store,
            map_to_standard=request.map_to_standard,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return {
        "user_id": request.user_id,
        **result,
    }


class GetTraitVectorRequest(BaseModel):
    user_id: str = Field(..., min_length=1)


@router.post("/trait_vector/get")
async def get_trait_vector(
    request: GetTraitVectorRequest,
    user_profile_service: UserProfileServiceDep,
) -> dict[str, Any]:
    result = await user_profile_service.get_trait_vector(request.user_id)
    if result is None:
        raise HTTPException(status_code=404, detail="profile not found")
    return result


class UpdateTraitVectorRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    mappings: list[dict[str, Any]] = Field(default_factory=list)
    source: str = "trait_mapping"


@router.post("/trait_vector/update")
async def update_trait_vector(
    request: UpdateTraitVectorRequest,
    user_profile_service: UserProfileServiceDep,
) -> dict[str, Any]:
    try:
        return await user_profile_service.update_trait_vector_from_mappings(
            request.user_id,
            request.mappings,
            source=request.source,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


class SetTraitFrozenRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    trait_name: str = Field(..., min_length=1)
    frozen: bool = True


@router.post("/trait_vector/freeze")
async def set_trait_frozen(
    request: SetTraitFrozenRequest,
    user_profile_service: UserProfileServiceDep,
) -> dict[str, Any]:
    return await user_profile_service.set_trait_frozen(
        request.user_id,
        request.trait_name,
        request.frozen,
    )


class RollbackProfileRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    steps: int = Field(default=1, ge=1)


@router.post("/profile/rollback")
async def rollback_profile(
    request: RollbackProfileRequest,
    user_profile_service: UserProfileServiceDep,
) -> dict[str, Any]:
    result = await user_profile_service.rollback_profile(request.user_id, request.steps)
    if result is None:
        raise HTTPException(status_code=404, detail="rollback target not found")
    return result


class RollbackToVersionRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    target_version: int = Field(..., ge=1)


@router.post("/profile/rollback_to_version")
async def rollback_to_version(
    request: RollbackToVersionRequest,
    user_profile_service: UserProfileServiceDep,
) -> dict[str, Any]:
    result = await user_profile_service.rollback_profile_to_version(
        request.user_id,
        request.target_version,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="target version not found")
    return result


class VersionHistoryRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    limit: int = Field(default=10, ge=1, le=100)


@router.post("/profile/version_history")
async def get_version_history(
    request: VersionHistoryRequest,
    user_profile_service: UserProfileServiceDep,
) -> dict[str, Any]:
    history = await user_profile_service.get_version_history(request.user_id, request.limit)
    return {"user_id": request.user_id, "history": history}


class ListNewTraitPoolRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    status: str | None = None


@router.post("/new_trait_pool/list")
async def list_new_trait_pool(
    request: ListNewTraitPoolRequest,
    user_profile_service: UserProfileServiceDep,
) -> dict[str, Any]:
    items = await user_profile_service.list_new_trait_pool(request.user_id, status=request.status)
    return {"user_id": request.user_id, "items": items}


class ReviewNewTraitCandidateRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    trait_name: str = Field(..., min_length=1)
    action: str = Field(..., min_length=1)
    merged_into: str | None = None
    note: str | None = None


@router.post("/new_trait_pool/review")
async def review_new_trait_candidate(
    request: ReviewNewTraitCandidateRequest,
    user_profile_service: UserProfileServiceDep,
) -> dict[str, Any]:
    try:
        result = await user_profile_service.review_new_trait_candidate(
            request.user_id,
            request.trait_name,
            request.action,
            merged_into=request.merged_into,
            note=request.note,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if result is None:
        raise HTTPException(status_code=404, detail="trait candidate not found")
    return result
