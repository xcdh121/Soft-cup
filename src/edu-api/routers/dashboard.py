from datetime import datetime

from auth import get_current_user
from edu_core.schemas.users import UserDto
from edu_db.models import DashboardComment, StudentKnowledgeState, User
from edu_db.session import get_db
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import desc, func
from sqlalchemy.orm import Session


router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


class CommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=500)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        content = value.strip()
        if not content:
            raise ValueError("评论内容不能为空")
        return content


class CommentDto(BaseModel):
    id: str
    user_id: str
    user_name: str
    content: str
    created_at: datetime


class LeaderboardEntryDto(BaseModel):
    user_id: str
    user_name: str
    study_count: int


def to_comment_dto(comment: DashboardComment, user: User) -> CommentDto:
    return CommentDto(
        id=comment.id,
        user_id=comment.user_id,
        user_name=user.name or user.email or "学习伙伴",
        content=comment.content,
        created_at=comment.created_at,
    )


@router.get("/comments", response_model=list[CommentDto])
def list_comments(
    limit: int = Query(default=30, ge=1, le=100),
    _current_user: UserDto = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CommentDto]:
    rows = (
        db.query(DashboardComment, User)
        .join(User, User.id == DashboardComment.user_id)
        .order_by(desc(DashboardComment.created_at))
        .limit(limit)
        .all()
    )
    return [to_comment_dto(comment, user) for comment, user in rows]


@router.post(
    "/comments",
    response_model=CommentDto,
    status_code=status.HTTP_201_CREATED,
)
def create_comment(
    payload: CommentCreate,
    current_user: UserDto = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CommentDto:
    comment = DashboardComment(user_id=current_user.id, content=payload.content)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    user = db.query(User).filter(User.id == current_user.id).one()
    return to_comment_dto(comment, user)


@router.get("/leaderboard", response_model=list[LeaderboardEntryDto])
def get_learning_leaderboard(
    limit: int = Query(default=8, ge=1, le=50),
    _current_user: UserDto = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[LeaderboardEntryDto]:
    study_count = func.coalesce(func.sum(StudentKnowledgeState.attempt_count), 0)
    rows = (
        db.query(User.id, User.name, User.email, study_count.label("study_count"))
        .outerjoin(StudentKnowledgeState, StudentKnowledgeState.user_id == User.id)
        .group_by(User.id, User.name, User.email)
        .order_by(desc("study_count"), User.created_at.asc())
        .limit(limit)
        .all()
    )
    return [
        LeaderboardEntryDto(
            user_id=row.id,
            user_name=row.name or row.email or "学习伙伴",
            study_count=int(row.study_count),
        )
        for row in rows
    ]
