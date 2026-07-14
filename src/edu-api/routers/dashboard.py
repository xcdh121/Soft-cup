from datetime import datetime

from auth import get_current_user
from edu_core.schemas.users import UserDto
from edu_db.models import (
    DashboardComment,
    DashboardCommentLike,
    StudentKnowledgeState,
    User,
)
from edu_db.session import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, status
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
    parent_id: str | None = None
    content: str
    created_at: datetime
    like_count: int = 0
    is_liked: bool = False
    replies: list["CommentDto"] = Field(default_factory=list)


class CommentLikeDto(BaseModel):
    comment_id: str
    like_count: int
    is_liked: bool


class LeaderboardEntryDto(BaseModel):
    user_id: str
    user_name: str
    study_count: int


def to_comment_dto(
    comment: DashboardComment,
    user: User,
    *,
    like_count: int = 0,
    is_liked: bool = False,
    replies: list[CommentDto] | None = None,
) -> CommentDto:
    return CommentDto(
        id=comment.id,
        user_id=comment.user_id,
        user_name=user.name or user.email or "学习伙伴",
        parent_id=comment.parent_id,
        content=comment.content,
        created_at=comment.created_at,
        like_count=like_count,
        is_liked=is_liked,
        replies=replies or [],
    )


@router.get("/comments", response_model=list[CommentDto])
def list_comments(
    limit: int = Query(default=30, ge=1, le=100),
    _current_user: UserDto = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CommentDto]:
    parent_rows = (
        db.query(DashboardComment, User)
        .join(User, User.id == DashboardComment.user_id)
        .filter(DashboardComment.parent_id.is_(None))
        .order_by(desc(DashboardComment.created_at))
        .limit(limit)
        .all()
    )
    parent_ids = [comment.id for comment, _user in parent_rows]
    reply_rows = (
        db.query(DashboardComment, User)
        .join(User, User.id == DashboardComment.user_id)
        .filter(DashboardComment.parent_id.in_(parent_ids))
        .order_by(DashboardComment.created_at.asc())
        .all()
        if parent_ids
        else []
    )
    all_comment_ids = parent_ids + [comment.id for comment, _user in reply_rows]
    like_counts = {
        comment_id: int(count)
        for comment_id, count in (
            db.query(
                DashboardCommentLike.comment_id,
                func.count(DashboardCommentLike.user_id),
            )
            .filter(DashboardCommentLike.comment_id.in_(all_comment_ids))
            .group_by(DashboardCommentLike.comment_id)
            .all()
            if all_comment_ids
            else []
        )
    }
    liked_ids = {
        comment_id
        for (comment_id,) in (
            db.query(DashboardCommentLike.comment_id)
            .filter(
                DashboardCommentLike.comment_id.in_(all_comment_ids),
                DashboardCommentLike.user_id == _current_user.id,
            )
            .all()
            if all_comment_ids
            else []
        )
    }
    replies_by_parent: dict[str, list[CommentDto]] = {}
    for reply, user in reply_rows:
        if reply.parent_id is None:
            continue
        replies_by_parent.setdefault(reply.parent_id, []).append(
            to_comment_dto(
                reply,
                user,
                like_count=like_counts.get(reply.id, 0),
                is_liked=reply.id in liked_ids,
            )
        )
    return [
        to_comment_dto(
            comment,
            user,
            like_count=like_counts.get(comment.id, 0),
            is_liked=comment.id in liked_ids,
            replies=replies_by_parent.get(comment.id, []),
        )
        for comment, user in parent_rows
    ]


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


@router.post(
    "/comments/{comment_id}/replies",
    response_model=CommentDto,
    status_code=status.HTTP_201_CREATED,
)
def create_reply(
    comment_id: str,
    payload: CommentCreate,
    current_user: UserDto = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CommentDto:
    target = (
        db.query(DashboardComment).filter(DashboardComment.id == comment_id).first()
    )
    if target is None:
        raise HTTPException(status_code=404, detail="评论不存在")
    parent_id = target.parent_id or target.id
    reply = DashboardComment(
        user_id=current_user.id,
        parent_id=parent_id,
        content=payload.content,
    )
    db.add(reply)
    db.commit()
    db.refresh(reply)
    user = db.query(User).filter(User.id == current_user.id).one()
    return to_comment_dto(reply, user)


@router.post("/comments/{comment_id}/like", response_model=CommentLikeDto)
def toggle_comment_like(
    comment_id: str,
    current_user: UserDto = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CommentLikeDto:
    if (
        not db.query(DashboardComment.id)
        .filter(DashboardComment.id == comment_id)
        .first()
    ):
        raise HTTPException(status_code=404, detail="评论不存在")
    existing = (
        db.query(DashboardCommentLike)
        .filter(
            DashboardCommentLike.comment_id == comment_id,
            DashboardCommentLike.user_id == current_user.id,
        )
        .first()
    )
    if existing:
        db.delete(existing)
        is_liked = False
    else:
        db.add(DashboardCommentLike(comment_id=comment_id, user_id=current_user.id))
        is_liked = True
    db.commit()
    like_count = (
        db.query(func.count(DashboardCommentLike.user_id))
        .filter(DashboardCommentLike.comment_id == comment_id)
        .scalar()
        or 0
    )
    return CommentLikeDto(
        comment_id=comment_id,
        like_count=int(like_count),
        is_liked=is_liked,
    )


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
