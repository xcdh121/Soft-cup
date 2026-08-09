from datetime import datetime
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from edu_db.base import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    username: Mapped[str] = mapped_column(
        String, unique=True, index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=True)
    # Nullable so existing/dev users can be migrated without inventing credentials.
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    projects = relationship(
        "Project", back_populates="owner", cascade="all, delete-orphan"
    )
    documents = relationship(
        "Document", back_populates="owner", cascade="all, delete-orphan"
    )
    chats = relationship("Chat", back_populates="user", cascade="all, delete-orphan")
    usage = relationship(
        "UserUsage", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    resource_packages = relationship(
        "ResourcePackage", back_populates="user", cascade="all, delete-orphan"
    )
    generated_resources = relationship(
        "GeneratedResource", back_populates="user", cascade="all, delete-orphan"
    )
    courses = relationship(
        "Course", back_populates="owner", cascade="all, delete-orphan"
    )
    learner_profiles = relationship(
        "LearnerProfile", back_populates="user", cascade="all, delete-orphan"
    )
    knowledge_states = relationship(
        "StudentKnowledgeState", back_populates="user", cascade="all, delete-orphan"
    )
    dashboard_comments = relationship(
        "DashboardComment", back_populates="user", cascade="all, delete-orphan"
    )


class DashboardComment(Base):
    __tablename__ = "dashboard_comments"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    parent_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("dashboard_comments.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    user = relationship("User", back_populates="dashboard_comments")


class DashboardCommentLike(Base):
    __tablename__ = "dashboard_comment_likes"

    comment_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("dashboard_comments.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    owner_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE")
    )
    course_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("courses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    language_code: Mapped[str] = mapped_column(String, default="zh")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    owner = relationship("User", back_populates="projects")
    documents = relationship(
        "Document", back_populates="project", cascade="all, delete-orphan"
    )
    chats = relationship("Chat", back_populates="project", cascade="all, delete-orphan")
    resource_packages = relationship(
        "ResourcePackage", back_populates="project", cascade="all, delete-orphan"
    )
    course = relationship("Course", back_populates="projects")
    learner_profiles = relationship(
        "LearnerProfile", back_populates="project", cascade="all, delete-orphan"
    )


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    owner_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE")
    )
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True
    )

    # File information
    file_name: Mapped[str] = mapped_column(String)  # Original file name
    file_type: Mapped[str] = mapped_column(String)  # pdf, docx, txt, etc.
    file_size: Mapped[int] = mapped_column(Integer)  # Size in bytes

    # Azure Blob Storage references
    original_blob_name: Mapped[str] = mapped_column(
        String, unique=True, nullable=True, index=True
    )
    processed_text_blob_name: Mapped[str] = mapped_column(
        String, unique=True, nullable=True, index=True
    )

    # Document metadata
    summary: Mapped[str] = mapped_column(
        Text, nullable=True
    )  # Auto-generated summary of the document
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    # Document processing metadata
    status: Mapped[str] = mapped_column(String, default="uploaded")

    # Timestamps
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    owner = relationship("User", back_populates="documents")
    project = relationship("Project", back_populates="documents")
    segments = relationship(
        "DocumentSegment", back_populates="document", cascade="all, delete-orphan"
    )


class DocumentSegment(Base):
    __tablename__ = "document_segments"
    __table_args__ = (
        Index(
            "ix_document_segments_document_page",
            "document_id",
            "page_number",
        ),
    )

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    document_id: Mapped[str] = mapped_column(
        String, ForeignKey("documents.id", ondelete="CASCADE")
    )

    # Content
    content: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String, default="text")
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)

    # Metadata for RAG
    embedding_vector: Mapped[list] = mapped_column(Vector(3072), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    document = relationship("Document", back_populates="segments")


class Chat(Base):
    __tablename__ = "chats"
    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE")
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    project = relationship("Project", back_populates="chats")
    user = relationship("User", back_populates="chats")
    messages = relationship(
        "ChatMessage", back_populates="chat", cascade="all, delete-orphan"
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    chat_id: Mapped[str] = mapped_column(
        String, ForeignKey("chats.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(String)  # user, assistant
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    chat = relationship("Chat", back_populates="messages")
    parts = relationship(
        "ChatMessagePart",
        back_populates="message",
        cascade="all, delete-orphan",
        order_by="ChatMessagePart.order",
    )


class ChatMessagePart(Base):
    __tablename__ = "chat_message_parts"
    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    message_id: Mapped[str] = mapped_column(
        String, ForeignKey("chat_messages.id", ondelete="CASCADE")
    )
    part_type: Mapped[str] = mapped_column(
        String
    )  # text, file, tool_call, source-document
    order: Mapped[int] = mapped_column(Integer, default=0)

    # Text part
    text_content: Mapped[str] = mapped_column(Text, nullable=True)

    # File part
    file_name: Mapped[str] = mapped_column(String, nullable=True)
    file_type: Mapped[str] = mapped_column(String, nullable=True)
    file_url: Mapped[str] = mapped_column(String, nullable=True)

    # Tool Call part
    tool_call_id: Mapped[str] = mapped_column(String, nullable=True)
    tool_name: Mapped[str] = mapped_column(String, nullable=True)
    tool_input: Mapped[dict] = mapped_column(JSON, nullable=True)
    tool_output: Mapped[dict] = mapped_column(JSON, nullable=True)
    tool_state: Mapped[str] = mapped_column(String, nullable=True)

    # Source Document part
    source_id: Mapped[str] = mapped_column(String, nullable=True)
    media_type: Mapped[str] = mapped_column(String, nullable=True)
    source_title: Mapped[str] = mapped_column(String, nullable=True)
    source_filename: Mapped[str] = mapped_column(String, nullable=True)
    provider_metadata: Mapped[dict] = mapped_column(JSON, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    message = relationship("ChatMessage", back_populates="parts")


class FlashcardGroup(Base):
    __tablename__ = "flashcard_groups"
    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)


    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    project = relationship("Project")
    flashcards = relationship(
        "Flashcard", back_populates="group", cascade="all, delete-orphan"
    )


class Flashcard(Base):
    __tablename__ = "flashcards"
    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    group_id: Mapped[str] = mapped_column(
        String, ForeignKey("flashcard_groups.id", ondelete="CASCADE")
    )
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE")
    )
    knowledge_point_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("knowledge_points.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    difficulty_level: Mapped[str] = mapped_column(
        String, default="medium"
    )  # easy, medium, hard
    position: Mapped[int] = mapped_column(
        Integer, default=0, index=True
    )  # Position for ordering within group

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    group = relationship("FlashcardGroup", back_populates="flashcards")
    project = relationship("Project")


class Quiz(Base):
    __tablename__ = "quizzes"
    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE")
    )

    name: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    project = relationship("Project")
    questions = relationship(
        "QuizQuestion", back_populates="quiz", cascade="all, delete-orphan"
    )


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"
    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    quiz_id: Mapped[str] = mapped_column(
        String, ForeignKey("quizzes.id", ondelete="CASCADE")
    )
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE")
    )
    knowledge_point_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("knowledge_points.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    question_text: Mapped[str] = mapped_column(Text)
    option_a: Mapped[str] = mapped_column(Text)
    option_b: Mapped[str] = mapped_column(Text)
    option_c: Mapped[str] = mapped_column(Text)
    option_d: Mapped[str] = mapped_column(Text)
    correct_option: Mapped[str] = mapped_column(String)  # a, b, c, d
    explanation: Mapped[str] = mapped_column(Text, nullable=True)
    difficulty_level: Mapped[str] = mapped_column(
        String, default="medium"
    )  # easy, medium, hard
    position: Mapped[int] = mapped_column(
        Integer, default=0, index=True
    )  # Position for ordering within quiz

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    quiz = relationship("Quiz", back_populates="questions")
    project = relationship("Project")


class Note(Base):
    __tablename__ = "notes"
    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text)  # Markdown content

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    project = relationship("Project")


class PracticeRecord(Base):
    __tablename__ = "practice_records"
    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )

    knowledge_point_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("knowledge_points.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    item_type: Mapped[str] = mapped_column(
        String, index=True
    )  # "flashcard" or "quiz" - type of study resource
    item_id: Mapped[str] = mapped_column(
        String, index=True
    )  # flashcard_id or quiz_question_id - ID of the study resource
    topic: Mapped[str] = mapped_column(Text)  # Extracted from question/flashcard text
    user_answer: Mapped[str] = mapped_column(
        String, nullable=True
    )  # Only for quizzes, what user selected; null for flashcards
    correct_answer: Mapped[str] = mapped_column(
        Text
    )  # The correct answer - for flashcards this is the answer field, for quizzes the correct option
    was_correct: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # Whether the user got it right

    # P0 learning-event context. Existing callers can omit every field.
    session_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    attempt_no: Mapped[int] = mapped_column(Integer, default=1)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hint_count: Mapped[int] = mapped_column(Integer, default=0)
    difficulty_snapshot: Mapped[str | None] = mapped_column(String, nullable=True)
    answer_mode: Mapped[str] = mapped_column(String, default="manual", index=True)
    mapping_method: Mapped[str | None] = mapped_column(String, nullable=True)
    mapping_status: Mapped[str] = mapped_column(String, default="pending", index=True)
    mapping_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    recommendation_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("recommendations.id", ondelete="SET NULL"), nullable=True
    )
    resource_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("generated_resources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    learning_path_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("learning_paths.id", ondelete="SET NULL"), nullable=True
    )
    learning_path_step_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("learning_path_steps.id", ondelete="SET NULL"), nullable=True
    )
    is_verification: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user = relationship("User")
    project = relationship("Project")
    knowledge_point = relationship("KnowledgePoint")


class MindMap(Base):
    __tablename__ = "mind_maps"
    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )

    # Map content
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    map_data: Mapped[dict] = mapped_column(
        JSON
    )  # Structured mind map data (nodes, edges)

    # Timestamps
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user = relationship("User")
    project = relationship("Project")


class FlashcardProgress(Base):
    __tablename__ = "flashcard_progress"
    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    flashcard_id: Mapped[str] = mapped_column(
        String, ForeignKey("flashcards.id", ondelete="CASCADE"), index=True
    )
    group_id: Mapped[str] = mapped_column(
        String, ForeignKey("flashcard_groups.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )

    # Simple mastery tracking
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    incorrect_count: Mapped[int] = mapped_column(Integer, default=0)
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    mastery_level: Mapped[int] = mapped_column(
        Integer, default=0
    )  # 0=unseen, 1=learning, 2=mastered
    is_mastered: Mapped[bool] = mapped_column(Boolean, default=False)
    last_result: Mapped[bool] = mapped_column(Boolean, nullable=True)
    last_practiced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user = relationship("User")
    flashcard = relationship("Flashcard")
    group = relationship("FlashcardGroup")
    project = relationship("Project")





class UserUsage(Base):
    __tablename__ = "user_usage"
    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), index=True, unique=True
    )

    # Daily usage counters (reset daily)
    chat_messages_today: Mapped[int] = mapped_column(Integer, default=0)
    flashcard_generations_today: Mapped[int] = mapped_column(Integer, default=0)
    quiz_generations_today: Mapped[int] = mapped_column(Integer, default=0)
    mindmap_generations_today: Mapped[int] = mapped_column(Integer, default=0)
    document_uploads_today: Mapped[int] = mapped_column(Integer, default=0)

    # Last reset date
    last_reset_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user = relationship("User")


class StudyPlan(Base):
    __tablename__ = "study_plans"
    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )

    content: Mapped[dict] = mapped_column(JSON)  # Structured JSON study plan
    weak_topics: Mapped[list[str]] = mapped_column(
        JSON, default=list
    )  # List of weak topics identified

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user = relationship("User")
    project = relationship("Project")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    goal: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, index=True)
    trigger: Mapped[dict] = mapped_column(JSON, default=dict)
    context_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    final_result: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    user = relationship("User")
    project = relationship("Project")
    events = relationship(
        "AgentEvent", back_populates="run", cascade="all, delete-orphan"
    )
    artifacts = relationship(
        "AgentArtifact", back_populates="run", cascade="all, delete-orphan"
    )
    skill_executions = relationship(
        "SkillExecution", back_populates="run", cascade="all, delete-orphan"
    )
    tool_calls = relationship(
        "AgentToolCall", back_populates="run", cascade="all, delete-orphan"
    )


class SkillExecution(Base):
    __tablename__ = "skill_executions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String, ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )
    agent_name: Mapped[str] = mapped_column(String, index=True)
    skill_id: Mapped[str] = mapped_column(String, index=True)
    skill_version: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, index=True)
    input_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    output_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    output_artifact_key: Mapped[str | None] = mapped_column(String, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)
    fallback_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    run = relationship("AgentRun", back_populates="skill_executions")
    tool_calls = relationship("AgentToolCall", back_populates="skill_execution")


class AgentToolCall(Base):
    __tablename__ = "agent_tool_calls"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_agent_tool_calls_idempotency_key"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String, ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )
    skill_execution_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("skill_executions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    agent_name: Mapped[str] = mapped_column(String, index=True)
    skill_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    tool_name: Mapped[str] = mapped_column(String, index=True)
    tool_version: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, index=True)
    risk_level: Mapped[str] = mapped_column(String)
    approval_status: Mapped[str] = mapped_column(String)
    arguments: Mapped[dict] = mapped_column(JSON, default=dict)
    result_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence_refs: Mapped[list[dict]] = mapped_column(JSON, default=list)
    idempotency_key: Mapped[str | None] = mapped_column(String, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    run = relationship("AgentRun", back_populates="tool_calls")
    skill_execution = relationship("SkillExecution", back_populates="tool_calls")


class AgentEvent(Base):
    __tablename__ = "agent_events"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    run_id: Mapped[str] = mapped_column(
        String, ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )

    event_type: Mapped[str] = mapped_column(String, index=True)
    agent_name: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String, index=True)
    summary: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    run = relationship("AgentRun", back_populates="events")


class AgentArtifact(Base):
    __tablename__ = "agent_artifacts"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    run_id: Mapped[str] = mapped_column(
        String, ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )

    agent_name: Mapped[str] = mapped_column(String, index=True)
    artifact_key: Mapped[str] = mapped_column(String, index=True)
    artifact: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    run = relationship("AgentRun", back_populates="artifacts")


class Diagnosis(Base):
    __tablename__ = "diagnoses"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String, ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    status: Mapped[str] = mapped_column(String, index=True)
    diagnosis: Mapped[dict] = mapped_column(JSON, default=dict)
    next_actions: Mapped[list[str]] = mapped_column(JSON, default=list)
    trigger_type: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    trigger_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    primary_knowledge_point_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("knowledge_points.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    state_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    explanation_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("explanations.id", ondelete="SET NULL"), nullable=True
    )
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    diagnosis_version: Mapped[str] = mapped_column(String, default="diagnosis-rule-v1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    run = relationship("AgentRun")
    project = relationship("Project")
    user = relationship("User")
    recommendations = relationship(
        "Recommendation", back_populates="diagnosis_record", cascade="all, delete-orphan"
    )
    learning_paths = relationship(
        "LearningPath", back_populates="diagnosis_record", cascade="all, delete-orphan"
    )


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String, ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )
    diagnosis_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("diagnoses.id", ondelete="CASCADE"), nullable=True, index=True
    )
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    recommendation_type: Mapped[str] = mapped_column(String, index=True)
    target_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    title: Mapped[str] = mapped_column(String, index=True)
    reason_codes: Mapped[list[str]] = mapped_column(JSON, default=list)
    reason_text: Mapped[list[str]] = mapped_column(JSON, default=list)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    recommended_by: Mapped[str | None] = mapped_column(String, nullable=True)
    feedback: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    explanation_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("explanations.id", ondelete="SET NULL"), nullable=True
    )
    source_state_event_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("knowledge_state_events.id", ondelete="SET NULL"),
        nullable=True,
    )
    expected_outcome: Mapped[dict] = mapped_column(JSON, default=dict)
    verification_plan: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String, default="active", index=True)
    valid_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    run = relationship("AgentRun")
    diagnosis_record = relationship("Diagnosis", back_populates="recommendations")
    project = relationship("Project")
    user = relationship("User")


class LearningPath(Base):
    __tablename__ = "learning_paths"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String, ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )
    diagnosis_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("diagnoses.id", ondelete="CASCADE"), nullable=True, index=True
    )
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    content: Mapped[dict] = mapped_column(JSON, default=dict)
    based_on_recommendation_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1)
    previous_path_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("learning_paths.id", ondelete="SET NULL"), nullable=True
    )
    adjust_trigger_type: Mapped[str | None] = mapped_column(String, nullable=True)
    adjust_trigger_id: Mapped[str | None] = mapped_column(String, nullable=True)
    adjust_trigger_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    explanation_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("explanations.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String, default="active", index=True)
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    replaced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    run = relationship("AgentRun")
    diagnosis_record = relationship("Diagnosis", back_populates="learning_paths")
    project = relationship("Project")
    user = relationship("User")


class ResourcePackage(Base):
    __tablename__ = "resource_packages"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[str | None] = mapped_column(String, nullable=True)
    learning_path_id: Mapped[str | None] = mapped_column(String, nullable=True)

    title: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    generation_mode: Mapped[str] = mapped_column(String, default="manual")
    status: Mapped[str] = mapped_column(String, default="draft", index=True)
    target_topic: Mapped[str] = mapped_column(String, index=True)
    target_goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty_level: Mapped[str] = mapped_column(String, default="intermediate")
    estimated_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    source_document_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    knowledge_point_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    weak_knowledge_point_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    preferred_resource_types: Mapped[list[str]] = mapped_column(JSON, default=list)
    generation_params: Mapped[dict] = mapped_column(JSON, default=dict)
    agent_trace: Mapped[list[dict]] = mapped_column(JSON, default=list)

    resource_count: Mapped[int] = mapped_column(Integer, default=0)
    completed_resource_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_resource_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    project = relationship("Project", back_populates="resource_packages")
    user = relationship("User", back_populates="resource_packages")
    resources = relationship(
        "GeneratedResource",
        back_populates="resource_package",
        cascade="all, delete-orphan",
        order_by="GeneratedResource.generation_order",
    )


class GeneratedResource(Base):
    __tablename__ = "generated_resources"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    resource_package_id: Mapped[str] = mapped_column(
        String, ForeignKey("resource_packages.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    resource_type: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str] = mapped_column(String, index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending", index=True)
    format: Mapped[str] = mapped_column(String, default="markdown")
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    file_url: Mapped[str | None] = mapped_column(String, nullable=True)
    preview_url: Mapped[str | None] = mapped_column(String, nullable=True)
    cover_image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    source_document_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    knowledge_point_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    difficulty_level: Mapped[str] = mapped_column(String, default="intermediate")
    estimated_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    generation_order: Mapped[int] = mapped_column(Integer, default=0, index=True)
    generator_agent: Mapped[str | None] = mapped_column(String, nullable=True)
    generation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    resource_package = relationship("ResourcePackage", back_populates="resources")
    project = relationship("Project")
    user = relationship("User", back_populates="generated_resources")


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    owner_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    owner = relationship("User", back_populates="courses")
    projects = relationship("Project", back_populates="course")
    chapters = relationship(
        "CourseChapter",
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="CourseChapter.position",
    )
    knowledge_points = relationship(
        "KnowledgePoint", back_populates="course", cascade="all, delete-orphan"
    )
    resources = relationship(
        "CourseResource", back_populates="course", cascade="all, delete-orphan"
    )


class CourseChapter(Base):
    __tablename__ = "course_chapters"
    __table_args__ = (
        CheckConstraint("position >= 0", name="ck_course_chapters_position"),
        CheckConstraint(
            "estimated_minutes IS NULL OR estimated_minutes >= 0",
            name="ck_course_chapters_estimated_minutes",
        ),
    )

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    course_id: Mapped[str] = mapped_column(
        String, ForeignKey("courses.id", ondelete="CASCADE"), index=True
    )
    parent_chapter_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("course_chapters.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0, index=True)
    learning_objectives: Mapped[list[str]] = mapped_column(JSON, default=list)
    estimated_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    course = relationship("Course", back_populates="chapters")
    parent = relationship(
        "CourseChapter", remote_side=[id], back_populates="children"
    )
    children = relationship("CourseChapter", back_populates="parent")
    knowledge_points = relationship(
        "KnowledgePoint", back_populates="chapter", passive_deletes=True
    )
    resources = relationship(
        "CourseResource", back_populates="chapter", passive_deletes=True
    )


class KnowledgePoint(Base):
    __tablename__ = "knowledge_points"
    __table_args__ = (
        UniqueConstraint(
            "course_id", "name", name="uq_knowledge_points_course_name"
        ),
        CheckConstraint("position >= 0", name="ck_knowledge_points_position"),
    )

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    course_id: Mapped[str] = mapped_column(
        String, ForeignKey("courses.id", ondelete="CASCADE"), index=True
    )
    chapter_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("course_chapters.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty_level: Mapped[str] = mapped_column(
        String, default="intermediate", index=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0, index=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    course = relationship("Course", back_populates="knowledge_points")
    chapter = relationship("CourseChapter", back_populates="knowledge_points")
    outgoing_relations = relationship(
        "KnowledgePointRelation",
        foreign_keys="KnowledgePointRelation.source_knowledge_point_id",
        back_populates="source",
        cascade="all, delete-orphan",
    )
    incoming_relations = relationship(
        "KnowledgePointRelation",
        foreign_keys="KnowledgePointRelation.target_knowledge_point_id",
        back_populates="target",
        cascade="all, delete-orphan",
    )
    resource_links = relationship(
        "CourseResourceKnowledgePoint",
        back_populates="knowledge_point",
        cascade="all, delete-orphan",
    )
    student_states = relationship(
        "StudentKnowledgeState",
        back_populates="knowledge_point",
        cascade="all, delete-orphan",
    )


class KnowledgePointRelation(Base):
    __tablename__ = "knowledge_point_relations"
    __table_args__ = (
        UniqueConstraint(
            "source_knowledge_point_id",
            "target_knowledge_point_id",
            "relation_type",
            name="uq_knowledge_point_relations_edge",
        ),
        CheckConstraint(
            "source_knowledge_point_id <> target_knowledge_point_id",
            name="ck_knowledge_point_relations_not_self",
        ),
        CheckConstraint(
            "strength >= 0 AND strength <= 1",
            name="ck_knowledge_point_relations_strength",
        ),
    )

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    course_id: Mapped[str] = mapped_column(
        String, ForeignKey("courses.id", ondelete="CASCADE"), index=True
    )
    source_knowledge_point_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("knowledge_points.id", ondelete="CASCADE"),
        index=True,
    )
    target_knowledge_point_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("knowledge_points.id", ondelete="CASCADE"),
        index=True,
    )
    relation_type: Mapped[str] = mapped_column(
        String, default="prerequisite", index=True
    )
    strength: Mapped[float] = mapped_column(Float, default=1.0)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    course = relationship("Course")
    source = relationship(
        "KnowledgePoint",
        foreign_keys=[source_knowledge_point_id],
        back_populates="outgoing_relations",
    )
    target = relationship(
        "KnowledgePoint",
        foreign_keys=[target_knowledge_point_id],
        back_populates="incoming_relations",
    )


class CourseResource(Base):
    __tablename__ = "course_resources"
    __table_args__ = (
        CheckConstraint(
            "estimated_minutes IS NULL OR estimated_minutes >= 0",
            name="ck_course_resources_estimated_minutes",
        ),
    )

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    course_id: Mapped[str] = mapped_column(
        String, ForeignKey("courses.id", ondelete="CASCADE"), index=True
    )
    chapter_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("course_chapters.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    document_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    generated_resource_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("generated_resources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    resource_type: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String, default="internal", index=True)
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    difficulty_level: Mapped[str] = mapped_column(
        String, default="intermediate", index=True
    )
    estimated_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    license_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_audiences: Mapped[list[str]] = mapped_column(JSON, default=list)
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    course = relationship("Course", back_populates="resources")
    chapter = relationship("CourseChapter", back_populates="resources")
    document = relationship("Document")
    generated_resource = relationship("GeneratedResource")
    knowledge_point_links = relationship(
        "CourseResourceKnowledgePoint",
        back_populates="resource",
        cascade="all, delete-orphan",
    )


class CourseResourceKnowledgePoint(Base):
    __tablename__ = "course_resource_knowledge_points"
    __table_args__ = (
        UniqueConstraint(
            "course_resource_id",
            "knowledge_point_id",
            name="uq_course_resource_knowledge_points_pair",
        ),
        CheckConstraint(
            "relevance_score >= 0 AND relevance_score <= 1",
            name="ck_course_resource_knowledge_points_relevance",
        ),
    )

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    course_resource_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("course_resources.id", ondelete="CASCADE"),
        index=True,
    )
    knowledge_point_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("knowledge_points.id", ondelete="CASCADE"),
        index=True,
    )
    relevance_score: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    resource = relationship(
        "CourseResource", back_populates="knowledge_point_links"
    )
    knowledge_point = relationship(
        "KnowledgePoint", back_populates="resource_links"
    )


class LearnerProfile(Base):
    __tablename__ = "learner_profiles"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "project_id", name="uq_learner_profiles_user_project"
        ),
        CheckConstraint(
            "completeness_score >= 0 AND completeness_score <= 1",
            name="ck_learner_profiles_completeness",
        ),
    )

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String, default="incomplete", index=True)
    profile_data: Mapped[dict] = mapped_column(JSON, default=dict)
    completeness_score: Mapped[float] = mapped_column(Float, default=0.0)
    last_refreshed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user = relationship("User", back_populates="learner_profiles")
    project = relationship("Project", back_populates="learner_profiles")
    revisions = relationship(
        "LearnerProfileRevision",
        back_populates="profile",
        cascade="all, delete-orphan",
        order_by="LearnerProfileRevision.created_at",
    )


class LearnerProfileRevision(Base):
    __tablename__ = "learner_profile_revisions"
    __table_args__ = (
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_learner_profile_revisions_confidence",
        ),
    )

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    profile_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("learner_profiles.id", ondelete="CASCADE"),
        index=True,
    )
    field_key: Mapped[str] = mapped_column(String, index=True)
    old_value: Mapped[object | None] = mapped_column(JSON, nullable=True)
    new_value: Mapped[object | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_type: Mapped[str] = mapped_column(String, default="manual", index=True)
    source_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    profile = relationship("LearnerProfile", back_populates="revisions")


class StudentKnowledgeState(Base):
    __tablename__ = "student_knowledge_states"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "knowledge_point_id",
            name="uq_student_knowledge_states_user_point",
        ),
        CheckConstraint(
            "mastery_score >= 0 AND mastery_score <= 100",
            name="ck_student_knowledge_states_mastery",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_student_knowledge_states_confidence",
        ),
        CheckConstraint(
            "attempt_count >= 0 AND correct_count >= 0 "
            "AND correct_count <= attempt_count",
            name="ck_student_knowledge_states_counts",
        ),
    )

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    knowledge_point_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("knowledge_points.id", ondelete="CASCADE"),
        index=True,
    )
    mastery_score: Mapped[float] = mapped_column(Float, default=0.0)
    mastery_probability: Mapped[float] = mapped_column(Float, default=0.0)
    p_correct_next: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    trend: Mapped[str] = mapped_column(String, default="stable", index=True)
    status: Mapped[str] = mapped_column(String, default="not_started", index=True)
    algorithm: Mapped[str] = mapped_column(String, default="legacy_ewma", index=True)
    model_version: Mapped[str] = mapped_column(String, default="legacy-rule-v1")
    parameter_set_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("kt_parameter_sets.id", ondelete="SET NULL"), nullable=True
    )
    threshold_version: Mapped[str] = mapped_column(String, default="threshold-v1")
    effective_event_count: Mapped[float] = mapped_column(Float, default=0.0)
    last_event_id: Mapped[str | None] = mapped_column(String, nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    state_version: Mapped[int] = mapped_column(Integer, default=0)
    lock_version: Mapped[int] = mapped_column(Integer, default=0)
    status_reason_codes: Mapped[list[str]] = mapped_column(JSON, default=list)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    evidence: Mapped[list[dict]] = mapped_column(JSON, default=list)
    last_practiced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user = relationship("User", back_populates="knowledge_states")
    knowledge_point = relationship(
        "KnowledgePoint", back_populates="student_states"
    )
    events = relationship(
        "KnowledgeStateEvent",
        back_populates="knowledge_state",
        cascade="all, delete-orphan",
        order_by="KnowledgeStateEvent.created_at",
    )


class KnowledgeStateEvent(Base):
    __tablename__ = "knowledge_state_events"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "knowledge_point_id",
            "source_type",
            "source_id",
            name="uq_knowledge_state_events_source",
        ),
        CheckConstraint(
            "score_before >= 0 AND score_before <= 100",
            name="ck_knowledge_state_events_score_before",
        ),
        CheckConstraint(
            "score_after >= 0 AND score_after <= 100",
            name="ck_knowledge_state_events_score_after",
        ),
    )

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    knowledge_state_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("student_knowledge_states.id", ondelete="CASCADE"),
        index=True,
    )
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    knowledge_point_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("knowledge_points.id", ondelete="CASCADE"),
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String, index=True)
    source_type: Mapped[str] = mapped_column(String, index=True)
    source_id: Mapped[str] = mapped_column(String, index=True)
    score_before: Mapped[float] = mapped_column(Float)
    score_after: Mapped[float] = mapped_column(Float)
    impact: Mapped[float] = mapped_column(Float)
    was_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    algorithm: Mapped[str] = mapped_column(String, default="legacy_ewma", index=True)
    model_version: Mapped[str] = mapped_column(String, default="legacy-rule-v1")
    parameter_set_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("kt_parameter_sets.id", ondelete="SET NULL"), nullable=True
    )
    prior_mastery: Mapped[float | None] = mapped_column(Float, nullable=True)
    prior_after_forgetting: Mapped[float | None] = mapped_column(Float, nullable=True)
    posterior_after_observation: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    posterior_after_learning: Mapped[float | None] = mapped_column(Float, nullable=True)
    p_correct_before: Mapped[float | None] = mapped_column(Float, nullable=True)
    p_correct_next: Mapped[float | None] = mapped_column(Float, nullable=True)
    observed_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    event_weight: Mapped[float] = mapped_column(Float, default=1.0)
    effective_parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    reason_codes: Mapped[list[str]] = mapped_column(JSON, default=list)
    explanation_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_payload_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    supersedes_event_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("knowledge_state_events.id", ondelete="SET NULL"),
        nullable=True,
    )
    state_version: Mapped[int] = mapped_column(Integer, default=1)
    shadow_results: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    knowledge_state = relationship(
        "StudentKnowledgeState", back_populates="events"
    )


class KTParameterSet(Base):
    __tablename__ = "kt_parameter_sets"
    __table_args__ = (
        UniqueConstraint("version", "scope_type", "scope_id", name="uq_kt_parameter_scope"),
    )

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(String)
    version: Mapped[str] = mapped_column(String, index=True)
    scope_type: Mapped[str] = mapped_column(String, default="global", index=True)
    scope_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    initial_mastery: Mapped[float] = mapped_column(Float, default=0.20)
    learn_probability: Mapped[float] = mapped_column(Float, default=0.12)
    slip_probability: Mapped[float] = mapped_column(Float, default=0.10)
    guess_probability: Mapped[float] = mapped_column(Float, default=0.20)
    forget_probability_daily: Mapped[float] = mapped_column(Float, default=0.005)
    difficulty_adjustments: Mapped[dict] = mapped_column(JSON, default=dict)
    answer_mode_adjustments: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String, default="draft", index=True)
    expert_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    effective_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class KnowledgePointKTParameter(Base):
    __tablename__ = "knowledge_point_kt_parameters"
    __table_args__ = (
        UniqueConstraint(
            "knowledge_point_id", "parameter_set_id", name="uq_kp_kt_parameter"
        ),
    )

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    knowledge_point_id: Mapped[str] = mapped_column(
        String, ForeignKey("knowledge_points.id", ondelete="CASCADE"), index=True
    )
    parameter_set_id: Mapped[str] = mapped_column(
        String, ForeignKey("kt_parameter_sets.id", ondelete="CASCADE"), index=True
    )
    initial_mastery_override: Mapped[float | None] = mapped_column(Float, nullable=True)
    learn_override: Mapped[float | None] = mapped_column(Float, nullable=True)
    slip_override: Mapped[float | None] = mapped_column(Float, nullable=True)
    guess_override: Mapped[float | None] = mapped_column(Float, nullable=True)
    forget_override: Mapped[float | None] = mapped_column(Float, nullable=True)
    expert_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ItemKnowledgePointMapping(Base):
    __tablename__ = "item_knowledge_point_mappings"
    __table_args__ = (
        UniqueConstraint(
            "item_type", "item_id", "knowledge_point_id", name="uq_item_kp_mapping"
        ),
    )

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    item_type: Mapped[str] = mapped_column(String, index=True)
    item_id: Mapped[str] = mapped_column(String, index=True)
    knowledge_point_id: Mapped[str] = mapped_column(
        String, ForeignKey("knowledge_points.id", ondelete="CASCADE"), index=True
    )
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    mapping_method: Mapped[str] = mapped_column(String, default="manual_review")
    mapping_confidence: Mapped[float] = mapped_column(Float, default=1.0)
    review_status: Mapped[str] = mapped_column(String, default="approved", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Explanation(Base):
    __tablename__ = "explanations"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    object_type: Mapped[str] = mapped_column(String, index=True)
    object_id: Mapped[str] = mapped_column(String, index=True)
    summary: Mapped[str] = mapped_column(Text)
    reason_codes: Mapped[list[str]] = mapped_column(JSON, default=list)
    model_version: Mapped[str] = mapped_column(String)
    threshold_version: Mapped[str] = mapped_column(String, default="threshold-v1")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ExplanationEvidence(Base):
    __tablename__ = "explanation_evidences"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    explanation_id: Mapped[str] = mapped_column(
        String, ForeignKey("explanations.id", ondelete="CASCADE"), index=True
    )
    source_type: Mapped[str] = mapped_column(String)
    source_id: Mapped[str] = mapped_column(String)
    knowledge_point_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("knowledge_points.id", ondelete="SET NULL"),
        nullable=True,
    )
    contribution_direction: Mapped[str] = mapped_column(String, default="supporting")
    contribution_score: Mapped[float] = mapped_column(Float, default=0.0)
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    display_order: Mapped[int] = mapped_column(Integer, default=0)


class DiagnosisCause(Base):
    __tablename__ = "diagnosis_causes"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    diagnosis_id: Mapped[str] = mapped_column(
        String, ForeignKey("diagnoses.id", ondelete="CASCADE"), index=True
    )
    parent_cause_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("diagnosis_causes.id", ondelete="CASCADE"), nullable=True
    )
    cause_type: Mapped[str] = mapped_column(String, index=True)
    knowledge_point_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("knowledge_points.id", ondelete="SET NULL"),
        nullable=True,
    )
    relation_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("knowledge_point_relations.id", ondelete="SET NULL"),
        nullable=True,
    )
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    rank: Mapped[int] = mapped_column(Integer, default=1)
    reason_text: Mapped[str] = mapped_column(Text)


class RecommendationInteraction(Base):
    __tablename__ = "recommendation_interactions"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    recommendation_id: Mapped[str] = mapped_column(
        String, ForeignKey("recommendations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String, index=True)
    resource_id: Mapped[str | None] = mapped_column(String, nullable=True)
    learning_session_id: Mapped[str | None] = mapped_column(String, nullable=True)
    progress: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason_code: Mapped[str | None] = mapped_column(String, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)


class InterventionOutcome(Base):
    __tablename__ = "intervention_outcomes"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    recommendation_id: Mapped[str] = mapped_column(
        String, ForeignKey("recommendations.id", ondelete="CASCADE"), index=True
    )
    knowledge_point_id: Mapped[str] = mapped_column(
        String, ForeignKey("knowledge_points.id", ondelete="CASCADE"), index=True
    )
    baseline_state_event_id: Mapped[str] = mapped_column(
        String, ForeignKey("knowledge_state_events.id", ondelete="CASCADE")
    )
    verification_event_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("knowledge_state_events.id", ondelete="CASCADE"),
        unique=True,
    )
    mastery_before: Mapped[float] = mapped_column(Float)
    mastery_after: Mapped[float] = mapped_column(Float)
    mastery_gain: Mapped[float] = mapped_column(Float)
    verification_score: Mapped[float] = mapped_column(Float)
    target_mastery: Mapped[float] = mapped_column(Float, default=0.8)
    target_achieved: Mapped[bool] = mapped_column(Boolean, default=False)
    attribution_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    evaluation_window_hours: Mapped[int] = mapped_column(Integer, default=72)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    explanation_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("explanations.id", ondelete="SET NULL"), nullable=True
    )


class LearningPathStep(Base):
    __tablename__ = "learning_path_steps"
    __table_args__ = (
        UniqueConstraint("learning_path_id", "step_no", name="uq_learning_path_step_no"),
    )

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    learning_path_id: Mapped[str] = mapped_column(
        String, ForeignKey("learning_paths.id", ondelete="CASCADE"), index=True
    )
    step_no: Mapped[int] = mapped_column(Integer)
    step_type: Mapped[str] = mapped_column(String)
    target_id: Mapped[str | None] = mapped_column(String, nullable=True)
    knowledge_point_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("knowledge_points.id", ondelete="SET NULL"),
        nullable=True,
    )
    recommendation_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("recommendations.id", ondelete="SET NULL"), nullable=True
    )
    objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    acceptance_condition: Mapped[dict] = mapped_column(JSON, default=dict)
    baseline_mastery: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_mastery: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending", index=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completion_event_id: Mapped[str | None] = mapped_column(String, nullable=True)
