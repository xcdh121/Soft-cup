from collections.abc import AsyncGenerator
from datetime import datetime
from time import monotonic
from typing import Any

from edu_core.exceptions import NotFoundError
from edu_db.models import Note, Project
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, Field

from edu_ai.agents.topic_graph_agent import TopicGraphAgent
from edu_ai.agents.utils import generate, generate_stream, get_db_session


class NoteGenerationResult(BaseModel):
    """Model for note generation result."""

    title: str = Field(..., description="The title of the note")
    description: str = Field(..., description="The description of the note")
    content: str = Field(..., description="The content of the note")


class NoteAgent:
    output_model = NoteGenerationResult
    prompt_template = "note_prompt"

    def __init__(
        self,
        search_service: Any,
        llm: BaseChatModel,
        topic_graph_agent: TopicGraphAgent | None = None,
    ):
        self.search_service = search_service
        self.llm = llm
        self.topic_graph_agent = topic_graph_agent

    async def generate_and_save(
        self,
        project_id: str,
        topic: str | None = None,
        custom_instructions: str | None = None,
        note_id: str | None = None,
        **kwargs: Any,
    ) -> Note:
        """Generate note content and save to the database.

        Args:
            project_id: The project ID
            topic: Optional topic for generation
            custom_instructions: Optional custom instructions
            note_id: The note ID to populate (required)

        Returns:
            Updated Note model

        Raises:
            NotFoundError: If note or project not found
            ValueError: If note_id is not provided
        """
        if not note_id:
            raise ValueError("note_id is required for note generation")

        with get_db_session() as db:
            # Find existing note
            note = (
                db.query(Note)
                .filter(
                    Note.id == note_id,
                    Note.project_id == project_id,
                )
                .first()
            )
            if not note:
                raise NotFoundError(f"Note {note_id} not found")

            # Get project language code
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise NotFoundError(f"Project {project_id} not found")
            language_code = project.language_code

            generation_topic = topic
            if self.topic_graph_agent:
                topic_graph = await self.topic_graph_agent.generate_topic_graph(
                    project_id=project_id,
                    topic=topic,
                    custom_instructions=custom_instructions,
                )
                if topic_graph.root_topics:
                    topics = []
                    for root_topic in topic_graph.root_topics:
                        topics.append(root_topic.topic)
                        for subtopic in root_topic.subtopics:
                            topics.append(subtopic.topic)
                    generation_topic = ", ".join(topics)

            # Generate note using AI
            result = await generate(
                llm=self.llm,
                search_service=self.search_service,
                output_model=self.output_model,
                prompt_template=self.prompt_template,
                project_id=project_id,
                topic=generation_topic or "",
                language_code=language_code,
                custom_instructions=custom_instructions,
            )

            # Update note with generated content
            note.title = result.title
            note.description = result.description
            note.content = result.content
            note.updated_at = datetime.now()

            db.flush()
            return note

    async def generate_and_save_stream(
        self,
        project_id: str,
        topic: str | None = None,
        custom_instructions: str | None = None,
        note_id: str | None = None,
    ) -> AsyncGenerator[dict[str, Any]]:
        if not note_id:
            raise ValueError("note_id is required for note generation")

        with get_db_session() as db:
            note = db.query(Note).filter(
                Note.id == note_id, Note.project_id == project_id
            ).first()
            if not note:
                raise NotFoundError(f"Note {note_id} not found")
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise NotFoundError(f"Project {project_id} not found")

            generation_topic = topic
            if self.topic_graph_agent:
                topic_graph = await self.topic_graph_agent.generate_topic_graph(
                    project_id=project_id,
                    topic=topic,
                    custom_instructions=custom_instructions,
                )
                topics = [
                    item
                    for root in topic_graph.root_topics
                    for item in [root.topic, *(sub.topic for sub in root.subtopics)]
                ]
                if topics:
                    generation_topic = ", ".join(topics)

            previous_content = ""
            emitted_content = ""
            last_persisted_at = 0.0
            final_result: NoteGenerationResult | None = None
            async for partial in generate_stream(
                llm=self.llm,
                search_service=self.search_service,
                output_model=self.output_model,
                prompt_template=self.prompt_template,
                project_id=project_id,
                topic=generation_topic or "",
                language_code=project.language_code,
                custom_instructions=custom_instructions,
            ):
                content = partial.get("content")
                if isinstance(content, str) and content != previous_content:
                    previous_content = content
                    now = monotonic()
                    should_publish = (
                        not emitted_content
                        or now - last_persisted_at >= 0.25
                        or len(content) - len(emitted_content) >= 96
                    )
                    if should_publish:
                        delta = (
                            content[len(emitted_content) :]
                            if content.startswith(emitted_content)
                            else content
                        )
                        # Persist the latest stable snapshot before publishing the
                        # event. Resource-package pages and note detail pages may
                        # be opened by a different request, so an in-memory SSE
                        # delta alone is not enough for them to render progress.
                        note.content = content
                        note.updated_at = datetime.now()
                        db.commit()
                        emitted_content = content
                        last_persisted_at = now
                        yield {
                            "event": "note_delta",
                            "note_id": note_id,
                            "delta": delta,
                            "content": content,
                        }
                try:
                    final_result = self.output_model.model_validate(partial)
                except Exception:
                    continue

            if final_result is None:
                raise ValueError("The model did not return a complete note")
            if final_result.content != emitted_content:
                delta = (
                    final_result.content[len(emitted_content) :]
                    if final_result.content.startswith(emitted_content)
                    else final_result.content
                )
                note.content = final_result.content
                note.updated_at = datetime.now()
                db.commit()
                yield {
                    "event": "note_delta",
                    "note_id": note_id,
                    "delta": delta,
                    "content": final_result.content,
                }
            note.title = final_result.title
            note.description = final_result.description
            note.content = final_result.content
            note.updated_at = datetime.now()
            db.commit()
            yield {
                "event": "note_completed",
                "note_id": note_id,
                "title": note.title,
                "description": note.description,
                "content": note.content,
            }
