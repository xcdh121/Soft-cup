"""Request schemas for CRUD operations."""

from datetime import datetime
from typing import Any, Literal, Union

from pydantic import BaseModel, Field, model_validator


class ProjectCreate(BaseModel):
    name: str = Field(..., description="Name of the project")
    description: str | None = Field(None, description="Description of the project")
    language_code: str = Field(
        default="zh", description="Language code for the project"
    )
    course_id: str | None = Field(None, description="Optional parent course ID")


class ProjectUpdate(BaseModel):
    name: str | None = Field(None, description="Name of the project")
    description: str | None = Field(None, description="Description of the project")
    language_code: str | None = Field(None, description="Language code for the project")
    course_id: str | None = Field(None, description="Optional parent course ID")


class CourseCreate(BaseModel):
    name: str = Field(..., min_length=1, description="Course name")
    code: str | None = Field(None, description="Optional course code")
    description: str | None = Field(None, description="Course description")
    status: str = Field(default="active", description="Course status")


class CourseUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, description="Course name")
    code: str | None = Field(None, description="Optional course code")
    description: str | None = Field(None, description="Course description")
    status: str | None = Field(None, description="Course status")


class CourseChapterCreate(BaseModel):
    title: str = Field(..., min_length=1, description="Chapter title")
    description: str | None = Field(None, description="Chapter description")
    parent_chapter_id: str | None = Field(
        None, description="Optional parent chapter ID"
    )
    position: int = Field(default=0, ge=0, description="Chapter display order")
    learning_objectives: list[str] = Field(
        default_factory=list, description="Chapter learning objectives"
    )
    estimated_minutes: int | None = Field(
        None, ge=0, description="Estimated study duration"
    )


class KnowledgePointCreate(BaseModel):
    name: str = Field(..., min_length=1, description="Knowledge point name")
    description: str | None = Field(
        None, description="Knowledge point description"
    )
    chapter_id: str | None = Field(None, description="Optional chapter ID")
    difficulty_level: str = Field(
        default="intermediate", description="Knowledge point difficulty"
    )
    position: int = Field(default=0, ge=0, description="Display order")
    tags: list[str] = Field(
        default_factory=list, description="Knowledge point tags"
    )


class KnowledgePointUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, description="Knowledge point name")
    description: str | None = Field(
        None, description="Knowledge point Markdown body"
    )
    chapter_id: str | None = Field(None, description="Optional chapter ID")
    difficulty_level: str | None = Field(
        None, description="Knowledge point difficulty"
    )
    position: int | None = Field(None, ge=0, description="Display order")
    tags: list[str] | None = Field(None, description="Knowledge point tags")


class KnowledgePointRelationCreate(BaseModel):
    source_knowledge_point_id: str = Field(..., description="Source knowledge point ID")
    target_knowledge_point_id: str = Field(..., description="Target knowledge point ID")
    relation_type: str = Field(default="prerequisite", description="Relation type")
    strength: float = Field(default=1.0, ge=0, le=1, description="Relation strength")
    description: str | None = Field(None, description="Relation description")

    @model_validator(mode="after")
    def validate_not_self(self):
        if self.source_knowledge_point_id == self.target_knowledge_point_id:
            raise ValueError("source and target knowledge points cannot be the same")
        return self


class CourseResourceCreate(BaseModel):
    chapter_id: str | None = None
    document_id: str | None = None
    generated_resource_id: str | None = None
    resource_type: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    description: str | None = None
    source_type: str = "internal"
    source_url: str | None = None
    difficulty_level: str = "intermediate"
    estimated_minutes: int | None = Field(None, ge=0)
    license_info: str | None = None
    target_audiences: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    knowledge_point_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_source(self):
        if self.document_id and self.generated_resource_id:
            raise ValueError(
                "document_id and generated_resource_id cannot both be set"
            )
        return self


class CourseResourceUpdate(BaseModel):
    chapter_id: str | None = None
    document_id: str | None = None
    generated_resource_id: str | None = None
    resource_type: str | None = Field(None, min_length=1)
    title: str | None = Field(None, min_length=1)
    description: str | None = None
    source_type: str | None = None
    source_url: str | None = None
    difficulty_level: str | None = None
    estimated_minutes: int | None = Field(None, ge=0)
    license_info: str | None = None
    target_audiences: list[str] | None = None
    metadata: dict[str, Any] | None = None
    knowledge_point_ids: list[str] | None = None

    @model_validator(mode="after")
    def validate_source(self):
        if self.document_id and self.generated_resource_id:
            raise ValueError(
                "document_id and generated_resource_id cannot both be set"
            )
        return self


class LearnerProfileReplace(BaseModel):
    profile_data: dict[str, Any] = Field(default_factory=dict)


class LearnerProfilePatch(BaseModel):
    profile_data: dict[str, Any] = Field(default_factory=dict)


class KnowledgeStateUpsert(BaseModel):
    mastery_score: float = Field(..., ge=0, le=100)
    confidence: float = Field(default=0, ge=0, le=1)
    trend: str = "stable"
    status: str = "not_started"
    attempt_count: int = Field(default=0, ge=0)
    correct_count: int = Field(default=0, ge=0)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    last_practiced_at: datetime | None = None

    @model_validator(mode="after")
    def validate_counts(self):
        if self.correct_count > self.attempt_count:
            raise ValueError("correct_count cannot exceed attempt_count")
        return self


class DocumentCreate(BaseModel):
    file_name: str = Field(..., description="Name of the document file")
    file_type: str = Field(..., description="File extension (pdf, docx, txt, etc.)")
    file_size: int = Field(..., gt=0, description="File size in bytes")
    summary: str | None = Field(
        None, description="Auto-generated summary of the document"
    )


class DocumentUpdate(BaseModel):
    file_name: str | None = Field(None, description="Name of the document file")
    summary: str | None = Field(
        None, description="Auto-generated summary of the document"
    )


class DocumentQuestionRequest(BaseModel):
    question: str = Field(..., min_length=1, description="User question")
    selected_text: str | None = Field(
        None, description="Text selected by the user in the PDF reader"
    )
    page_number: int | None = Field(
        None, ge=1, description="Current PDF page number"
    )
    chapter_id: str | None = Field(None, description="Optional course chapter ID")
    top_k: int = Field(default=5, ge=1, le=10, description="RAG result count")


class ChatCreate(BaseModel):
    title: str | None = Field(None, description="Title of the chat")


class ChatUpdate(BaseModel):
    title: str | None = Field(None, description="Title of the chat")


class NoteCreate(BaseModel):
    title: str = Field(..., description="Title of the note")
    content: str = Field(..., description="Content of the note")
    description: str | None = Field(None, description="Description of the note")


class NoteUpdate(BaseModel):
    title: str | None = Field(None, description="Title of the note")
    content: str | None = Field(None, description="Content of the note")
    description: str | None = Field(None, description="Description of the note")


class ImportResourceRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    summary: str = Field(..., min_length=1, max_length=500)
    origin: Literal["handwriting", "pdf_ocr", "translation"]
    resource_type: Literal["lecture_note", "reading_material"]
    content_format: str = Field(..., min_length=1, max_length=50)
    content_text: str | None = Field(None, max_length=100_000)
    file_url: str | None = Field(None, max_length=2_000)

    @model_validator(mode="after")
    def validate_content(self):
        if not (self.content_text and self.content_text.strip()) and not self.file_url:
            raise ValueError("content_text or file_url is required")
        return self


class QuizCreate(BaseModel):
    name: str = Field(..., description="Name of the quiz")
    description: str | None = Field(None, description="Description of the quiz")


class QuizUpdate(BaseModel):
    name: str | None = Field(None, description="Name of the quiz")
    description: str | None = Field(None, description="Description of the quiz")


class FlashcardGroupCreate(BaseModel):
    name: str = Field(..., description="Name of the flashcard group")
    description: str | None = Field(
        None, description="Description of the flashcard group"
    )



class FlashcardGroupUpdate(BaseModel):
    name: str | None = Field(None, description="Name of the flashcard group")
    description: str | None = Field(
        None, description="Description of the flashcard group"
    )


class TextPart(BaseModel):
    type: Literal["text"]
    text: str


class FilePart(BaseModel):
    type: Literal["file"]
    media_type: str = Field(..., alias="mediaType")
    filename: str | None = None
    url: str  # This will be base64


class ChatCompletionRequest(BaseModel):
    parts: list[Union[TextPart, FilePart]]
    web_search: bool = False


class FlashcardCreate(BaseModel):
    knowledge_point_id: str | None = Field(
        None, description="Optional related knowledge point ID"
    )
    question: str = Field(..., description="Question of the flashcard")
    answer: str = Field(..., description="Answer of the flashcard")
    difficulty_level: str = Field(
        default="medium", description="Difficulty level (easy, medium, hard)"
    )
    position: int | None = Field(
        None, description="Position for ordering within the group"
    )


class FlashcardUpdate(BaseModel):
    knowledge_point_id: str | None = Field(
        None, description="Optional related knowledge point ID"
    )
    question: str | None = Field(None, description="Question of the flashcard")
    answer: str | None = Field(None, description="Answer of the flashcard")
    difficulty_level: str | None = Field(
        None, description="Difficulty level (easy, medium, hard)"
    )
    position: int | None = Field(
        None, description="Position for ordering within the group"
    )


class QuizQuestionCreate(BaseModel):
    knowledge_point_id: str | None = Field(
        None, description="Optional related knowledge point ID"
    )
    question_text: str = Field(..., description="The quiz question text")
    option_a: str = Field(..., description="Option A")
    option_b: str = Field(..., description="Option B")
    option_c: str = Field(..., description="Option C")
    option_d: str = Field(..., description="Option D")
    correct_option: str = Field(..., description="Correct option: a, b, c, or d")
    explanation: str | None = Field(
        None, description="Explanation for the correct answer"
    )
    difficulty_level: str = Field(
        default="medium", description="Difficulty level (easy, medium, hard)"
    )
    position: int | None = Field(
        None, description="Position for ordering within the quiz"
    )


class QuizQuestionUpdate(BaseModel):
    knowledge_point_id: str | None = Field(
        None, description="Optional related knowledge point ID"
    )
    question_text: str | None = Field(None, description="The quiz question text")
    option_a: str | None = Field(None, description="Option A")
    option_b: str | None = Field(None, description="Option B")
    option_c: str | None = Field(None, description="Option C")
    option_d: str | None = Field(None, description="Option D")
    correct_option: str | None = Field(
        None, description="Correct option: a, b, c, or d"
    )
    explanation: str | None = Field(
        None, description="Explanation for the correct answer"
    )
    difficulty_level: str | None = Field(
        None, description="Difficulty level (easy, medium, hard)"
    )
    position: int | None = Field(
        None, description="Position for ordering within the quiz"
    )


class QuizQuestionReorder(BaseModel):
    question_ids: list[str] = Field(
        ..., description="List of question IDs in the desired order"
    )


class PracticeRecordCreate(BaseModel):
    item_type: str = Field(
        ...,
        pattern="^(flashcard|quiz|programming|subjective|manual)$",
        description="Type of practice item",
    )
    item_id: str = Field(
        ..., description="ID of the study resource (flashcard or quiz question)"
    )
    knowledge_point_id: str | None = Field(
        None, description="Optional related knowledge point ID"
    )
    topic: str = Field(..., max_length=500, description="Topic extracted from question")
    user_answer: str | None = Field(
        None, description="User's answer (only for quizzes, null for flashcards)"
    )
    correct_answer: str = Field(
        ..., description="The correct answer - flashcard answer or quiz correct option"
    )
    was_correct: bool = Field(..., description="Whether the user got it right")
    session_id: str | None = None
    attempt_no: int = Field(1, ge=1)
    score: float | None = Field(None, ge=0, le=1)
    response_time_ms: int | None = Field(None, ge=0)
    hint_count: int = Field(0, ge=0)
    difficulty_snapshot: str | None = None
    answer_mode: Literal[
        "quiz", "flashcard", "programming", "subjective", "manual"
    ] | None = None
    mapping_method: Literal[
        "explicit", "item_binding", "rule_match", "semantic_match", "manual_review"
    ] | None = None
    mapping_confidence: float | None = Field(None, ge=0, le=1)
    recommendation_id: str | None = None
    resource_id: str | None = None
    learning_path_id: str | None = None
    learning_path_step_id: str | None = None
    is_verification: bool = False
    occurred_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PracticeRecordBatchCreate(BaseModel):
    practice_records: list[PracticeRecordCreate] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of practice records to create",
    )


class MindMapCreate(BaseModel):
    title: str = Field(..., description="Title of the mind map")
    description: str | None = Field(None, description="Description of the mind map")
    custom_instructions: str | None = Field(
        None, description="Custom instructions for AI generation"
    )

class DocumentPreviewDto(BaseModel):
    url: str = Field(..., description="URL of the document preview")

class GenerateRequest(BaseModel):
    topic: str | None = Field(None, description="Topic for generation")
    custom_instructions: str | None = Field(
        None, description="Custom instructions for generation"
    )
    count: int | None = Field(
        None, description="Number of items to generate (for flashcards/quizzes)"
    )
    difficulty: str | None = Field(
        None, description="Difficulty level (for flashcards/quizzes)"
    )


class GenerateResourcePackageRequest(BaseModel):
    profile_id: str | None = Field(None, description="Associated learner profile ID")
    learning_path_id: str | None = Field(
        None, description="Associated learning path ID"
    )
    diagnosis_id: str | None = Field(None, description="Associated diagnosis ID")
    explanation_mode: str | None = Field(
        None, description="Explanation mode for generated resources"
    )
    title: str | None = Field(None, description="Optional package title")
    description: str | None = Field(None, description="Optional package description")
    target_topic: str = Field(..., description="Target topic")
    target_goal: str | None = Field(None, description="Learning goal")
    source_document_ids: list[str] = Field(
        default_factory=list, description="Source document IDs"
    )
    chapter_ids: list[str] = Field(
        default_factory=list, description="Selected course chapter IDs"
    )
    knowledge_point_ids: list[str] = Field(
        default_factory=list, description="Knowledge point IDs"
    )
    weak_knowledge_point_ids: list[str] = Field(
        default_factory=list, description="Weak knowledge point IDs"
    )
    resource_types: list[str] = Field(
        default_factory=lambda: [
            "lecture_note",
            "mind_map",
            "practice_set",
            "ppt_outline",
            "programming_questions",
            "code_lab",
        ],
        description="Requested resource types",
    )
    difficulty_level: str = Field(
        default="intermediate", description="Target difficulty level"
    )
    generation_mode: str = Field(default="manual", description="Generation mode")
    estimated_minutes: int | None = Field(None, description="Estimated total minutes")
    custom_instructions: str | None = Field(
        None, description="Extra instructions for generation"
    )
    generation_params: dict = Field(
        default_factory=dict, description="Extra generation params"
    )


class UpdateGeneratedResourceRequest(BaseModel):
    title: str | None = Field(None, description="Resource title")
    summary: str | None = Field(None, description="Resource summary")
    generation_order: int | None = Field(None, description="Display order")
    status: str | None = Field(None, description="Resource status")
    content_text: str | None = Field(None, description="Text content")
    content_json: dict | None = Field(None, description="Structured content")
    generation_reason: str | None = Field(None, description="Generation reason")


class ProgrammingGradeRequest(BaseModel):
    question_id: str = Field(..., min_length=1, max_length=200)
    answer: str = Field(..., min_length=1, max_length=50000)
    language: Literal["python", "cpp", "java", "javascript", "go"] = Field(
        default="python",
        description="Programming language used by the submitted answer",
    )


class ProgrammingRunRequest(BaseModel):
    question_id: str = Field(..., min_length=1, max_length=200)
    code: str = Field(..., min_length=1, max_length=50000)
    stdin: str = Field(default="", max_length=20000)
    language: Literal["python", "cpp", "java", "javascript", "go"] = Field(
        default="python", description="Programming language to execute"
    )
