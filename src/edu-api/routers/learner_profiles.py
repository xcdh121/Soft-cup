"""Router for project-scoped learner profiles."""

from auth import get_current_user
from dependencies import get_learner_profile_service
from edu_core.exceptions import NotFoundError
from edu_core.schemas.learner_profiles import (
    LearnerProfileDto,
    LearnerProfileFieldConfirmation,
    LearnerProfileRevisionDto,
)
from edu_core.services import LearnerProfileService
from fastapi import APIRouter, Depends, HTTPException

from routers.schemas import LearnerProfilePatch, LearnerProfileReplace


router = APIRouter(
    prefix="/api/v1/projects/{project_id}/learner-profile",
    tags=["learner-profiles"],
)


@router.post("/confirm", response_model=LearnerProfileDto)
async def confirm_learner_profile_field(
    project_id: str,
    payload: LearnerProfileFieldConfirmation,
    current_user=Depends(get_current_user),
    service: LearnerProfileService = Depends(get_learner_profile_service),
):
    return service.confirm_field(
        project_id, current_user.id, payload.field_key, payload.value
    )


@router.post("/revisions/{revision_id}/revert", response_model=LearnerProfileDto)
async def revert_learner_profile_revision(
    project_id: str,
    revision_id: str,
    current_user=Depends(get_current_user),
    service: LearnerProfileService = Depends(get_learner_profile_service),
):
    try:
        return service.revert_revision(project_id, current_user.id, revision_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/revisions",
    response_model=list[LearnerProfileRevisionDto],
)
async def list_learner_profile_revisions(
    project_id: str,
    current_user=Depends(get_current_user),
    service: LearnerProfileService = Depends(get_learner_profile_service),
):
    try:
        return service.list_revisions(project_id, current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/refresh", response_model=LearnerProfileDto)
async def refresh_learner_profile(
    project_id: str,
    current_user=Depends(get_current_user),
    service: LearnerProfileService = Depends(get_learner_profile_service),
):
    try:
        return service.refresh_profile(project_id, current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("", response_model=LearnerProfileDto)
async def get_learner_profile(
    project_id: str,
    current_user=Depends(get_current_user),
    service: LearnerProfileService = Depends(get_learner_profile_service),
):
    try:
        return service.get_profile(project_id, current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("", response_model=LearnerProfileDto)
async def replace_learner_profile(
    project_id: str,
    profile: LearnerProfileReplace,
    current_user=Depends(get_current_user),
    service: LearnerProfileService = Depends(get_learner_profile_service),
):
    try:
        return service.replace_profile(
            project_id, current_user.id, profile.profile_data
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("", response_model=LearnerProfileDto)
async def patch_learner_profile(
    project_id: str,
    profile: LearnerProfilePatch,
    current_user=Depends(get_current_user),
    service: LearnerProfileService = Depends(get_learner_profile_service),
):
    try:
        return service.patch_profile(
            project_id, current_user.id, profile.profile_data
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
