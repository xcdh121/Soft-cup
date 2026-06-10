"""Router for course library operations."""

from auth import get_current_user
from dependencies import get_course_service
from edu_core.exceptions import NotFoundError
from edu_core.schemas.courses import (
    CourseChapterDto,
    CourseDto,
    KnowledgePointDto,
)
from edu_core.schemas.projects import ProjectDto
from edu_core.services import CourseService
from fastapi import APIRouter, Depends, HTTPException

from routers.schemas import (
    CourseChapterCreate,
    CourseCreate,
    CourseUpdate,
    KnowledgePointCreate,
)

router = APIRouter(prefix="/api/v1/courses", tags=["courses"])


@router.post("", response_model=CourseDto, status_code=201)
async def create_course(
    course: CourseCreate,
    current_user=Depends(get_current_user),
    service: CourseService = Depends(get_course_service),
):
    return service.create_course(
        owner_id=current_user.id,
        name=course.name,
        code=course.code,
        description=course.description,
        status=course.status,
    )


@router.get("", response_model=list[CourseDto])
async def list_courses(
    current_user=Depends(get_current_user),
    service: CourseService = Depends(get_course_service),
):
    return service.list_courses(owner_id=current_user.id)


@router.get("/{course_id}", response_model=CourseDto)
async def get_course(
    course_id: str,
    current_user=Depends(get_current_user),
    service: CourseService = Depends(get_course_service),
):
    try:
        return service.get_course(course_id, current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{course_id}", response_model=CourseDto)
async def update_course(
    course_id: str,
    course: CourseUpdate,
    current_user=Depends(get_current_user),
    service: CourseService = Depends(get_course_service),
):
    try:
        return service.update_course(
            course_id=course_id,
            owner_id=current_user.id,
            code=course.code,
            name=course.name,
            description=course.description,
            status=course.status,
            fields_to_update=course.model_fields_set,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{course_id}", status_code=204)
async def delete_course(
    course_id: str,
    current_user=Depends(get_current_user),
    service: CourseService = Depends(get_course_service),
):
    try:
        service.delete_course(course_id, current_user.id)
        return None
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{course_id}/projects", response_model=list[ProjectDto])
async def list_course_projects(
    course_id: str,
    current_user=Depends(get_current_user),
    service: CourseService = Depends(get_course_service),
):
    try:
        return service.list_course_projects(course_id, current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/{course_id}/chapters",
    response_model=CourseChapterDto,
    status_code=201,
)
async def create_chapter(
    course_id: str,
    chapter: CourseChapterCreate,
    current_user=Depends(get_current_user),
    service: CourseService = Depends(get_course_service),
):
    try:
        return service.create_chapter(
            course_id=course_id,
            owner_id=current_user.id,
            title=chapter.title,
            description=chapter.description,
            parent_chapter_id=chapter.parent_chapter_id,
            position=chapter.position,
            learning_objectives=chapter.learning_objectives,
            estimated_minutes=chapter.estimated_minutes,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/{course_id}/chapters",
    response_model=list[CourseChapterDto],
)
async def list_chapters(
    course_id: str,
    current_user=Depends(get_current_user),
    service: CourseService = Depends(get_course_service),
):
    try:
        return service.list_chapters(course_id, current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/{course_id}/knowledge-points",
    response_model=KnowledgePointDto,
    status_code=201,
)
async def create_knowledge_point(
    course_id: str,
    knowledge_point: KnowledgePointCreate,
    current_user=Depends(get_current_user),
    service: CourseService = Depends(get_course_service),
):
    try:
        return service.create_knowledge_point(
            course_id=course_id,
            owner_id=current_user.id,
            name=knowledge_point.name,
            description=knowledge_point.description,
            chapter_id=knowledge_point.chapter_id,
            difficulty_level=knowledge_point.difficulty_level,
            position=knowledge_point.position,
            tags=knowledge_point.tags,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/{course_id}/knowledge-points",
    response_model=list[KnowledgePointDto],
)
async def list_knowledge_points(
    course_id: str,
    current_user=Depends(get_current_user),
    service: CourseService = Depends(get_course_service),
):
    try:
        return service.list_knowledge_points(course_id, current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
