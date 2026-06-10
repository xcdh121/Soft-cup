"""Request schemas for CRUD operations."""

from typing import List, Union, Literal
from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., description="Name of the project")
    description: str | None = Field(None, description="Description of the project")
    language_code: str = Field(
        default="en", description="Language code for the project"
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


from typing import List, Union, Literal


class TextPart(BaseModel):
    type: Literal["text"]
    text: str


class FilePart(BaseModel):
    type: Literal["file"]
    media_type: str = Field(..., alias="mediaType")
    filename: str | None = None
    url: str  # This will be base64


class ChatCompletionRequest(BaseModel):
    parts: List[Union[TextPart, FilePart]]


class FlashcardCreate(BaseModel):
    question: str = Field(..., description="Question of the flashcard")
    answer: str = Field(..., description="Answer of the flashcard")
    difficulty_level: str = Field(
        default="medium", description="Difficulty level (easy, medium, hard)"
    )
    position: int | None = Field(
        None, description="Position for ordering within the group"
    )


class FlashcardUpdate(BaseModel):
    question: str | None = Field(None, description="Question of the flashcard")
    answer: str | None = Field(None, description="Answer of the flashcard")
    difficulty_level: str | None = Field(
        None, description="Difficulty level (easy, medium, hard)"
    )
    position: int | None = Field(
        None, description="Position for ordering within the group"
    )


class QuizQuestionCreate(BaseModel):
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
        pattern="^(flashcard|quiz)$",
        description="Type of study resource: flashcard or quiz",
    )
    item_id: str = Field(
        ..., description="ID of the study resource (flashcard or quiz question)"
    )
    topic: str = Field(..., max_length=500, description="Topic extracted from question")
    user_answer: str | None = Field(
        None, description="User's answer (only for quizzes, null for flashcards)"
    )
    correct_answer: str = Field(
        ..., description="The correct answer - flashcard answer or quiz correct option"
    )
    was_correct: bool = Field(..., description="Whether the user got it right")


class PracticeRecordBatchCreate(BaseModel):
    practice_records: list[PracticeRecordCreate] = Field(
        ...,
        min_items=1,
        max_items=100,
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
    title: str | None = Field(None, description="Optional package title")
    description: str | None = Field(None, description="Optional package description")
    target_topic: str = Field(..., description="Target topic")
    target_goal: str | None = Field(None, description="Learning goal")
    source_document_ids: list[str] = Field(
        default_factory=list, description="Source document IDs"
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
