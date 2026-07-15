from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any
from uuid import uuid4

from edu_core.exceptions import NotFoundError
from edu_core.services.knowledge_point_matching import resolve_knowledge_point_id
from edu_db.models import Flashcard, FlashcardGroup, Project
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, Field

from edu_ai.agents.topic_graph_agent import TopicGraphAgent
from edu_ai.agents.utils import generate, generate_stream, get_db_session


class FlashcardGenerationResult(BaseModel):
    """Model for flashcard generation result."""

    question: str = Field(..., description="The flashcard question")
    answer: str = Field(..., description="The flashcard answer")
    difficulty_level: str = Field(
        ..., description="The difficulty level of the flashcard"
    )


class FlashcardGroupGenerationResult(BaseModel):
    """Model for flashcard generation result."""

    name: str = Field(..., description="The name of the flashcard group")
    description: str = Field(..., description="The description of the flashcard group")
    flashcards: list[FlashcardGenerationResult] = Field(
        ..., description="The flashcards of the flashcard group"
    )


class FlashcardAgent:
    output_model = FlashcardGroupGenerationResult
    prompt_template = "flashcard_prompt"

    def __init__(
        self,
        search_service: Any,
        llm: BaseChatModel,
        topic_graph_agent: TopicGraphAgent | None = None,
    ):
        self.search_service = search_service
        self.llm = llm
        self.topic_graph_agent = topic_graph_agent

    async def generate_and_save_stream(
        self, project_id: str, topic: str | None = None,
        custom_instructions: str | None = None, group_id: str | None = None,
        count: int | None = None, difficulty: str | None = None,
    ) -> AsyncGenerator[dict[str, Any]]:
        """Generate flashcards and emit each complete card as it becomes available."""
        if not group_id:
            raise ValueError("group_id is required for flashcard generation")
        with get_db_session() as db:
            project = db.query(Project).filter(Project.id == project_id).first()
            group = db.query(FlashcardGroup).filter(
                FlashcardGroup.id == group_id, FlashcardGroup.project_id == project_id
            ).first()
            if not project or not group:
                raise NotFoundError("Project or flashcard group not found")
            requested_knowledge_point_id = resolve_knowledge_point_id(
                db,
                project.course_id,
                texts=[topic],
                allow_contains=False,
            )

            generation_topic = topic
            if self.topic_graph_agent:
                graph = await self.topic_graph_agent.generate_topic_graph(
                    project_id=project_id, topic=topic,
                    custom_instructions=custom_instructions,
                )
                topics = [item for root in graph.root_topics for item in
                          [root.topic, *(sub.topic for sub in root.subtopics)]]
                if topics:
                    generation_topic = ", ".join(topics)
            options: dict[str, Any] = {}
            if count is not None:
                options["count"] = count
            if difficulty is not None:
                options["difficulty"] = difficulty

            sent_count = 0
            final_result: FlashcardGroupGenerationResult | None = None
            async for partial in generate_stream(
                llm=self.llm, search_service=self.search_service,
                output_model=self.output_model, prompt_template=self.prompt_template,
                project_id=project_id, topic=generation_topic or "",
                language_code=project.language_code,
                custom_instructions=custom_instructions, **options,
            ):
                cards = []
                for raw in partial.get("flashcards") or []:
                    try:
                        cards.append(FlashcardGenerationResult.model_validate(raw))
                    except Exception:
                        continue
                try:
                    final_result = self.output_model.model_validate(partial)
                except Exception:
                    final_result = None
                # The parser can temporarily repair the object currently being
                # written. Hold that tail item until the next card (or final JSON)
                # proves that it is complete.
                stable_cards = cards if final_result is not None else cards[:-1]
                for position, card in enumerate(
                    stable_cards[sent_count:], start=sent_count
                ):
                    yield {"event": "flashcard_created", "group_id": group_id,
                           "position": position, "flashcard": card.model_dump()}
                sent_count = len(stable_cards)

            if final_result is None:
                raise ValueError("The model did not return a complete flashcard group")
            group.name, group.description = final_result.name, final_result.description
            group.updated_at = datetime.now()
            db.query(Flashcard).filter(Flashcard.group_id == group_id).delete()
            for position, item in enumerate(final_result.flashcards):
                knowledge_point_id = requested_knowledge_point_id or resolve_knowledge_point_id(
                    db,
                    project.course_id,
                    texts=[item.question, item.answer],
                )
                db.add(Flashcard(
                    id=str(uuid4()), group_id=group_id, project_id=project_id,
                    knowledge_point_id=knowledge_point_id,
                    question=item.question, answer=item.answer,
                    difficulty_level=item.difficulty_level, position=position,
                    created_at=datetime.now(),
                ))
            db.commit()
            yield {"event": "flashcards_completed", "group_id": group_id,
                   "name": group.name, "description": group.description,
                   "count": len(final_result.flashcards)}

    async def generate_and_save(
        self,
        project_id: str,
        topic: str | None = None,
        custom_instructions: str | None = None,
        group_id: str | None = None,
        count: int | None = None,
        difficulty: str | None = None,
        **kwargs: Any,
    ) -> FlashcardGroup:
        """Generate flashcards and save to the database.

        Args:
            project_id: The project ID
            topic: Optional topic for generation
            custom_instructions: Optional custom instructions
            group_id: The flashcard group ID to populate (required)
            count: Optional count of flashcards to generate
            difficulty: Optional difficulty level

        Returns:
            Updated FlashcardGroup model

        Raises:
            NotFoundError: If flashcard group or project not found
            ValueError: If group_id is not provided
        """
        if not group_id:
            raise ValueError("group_id is required for flashcard generation")

        with get_db_session() as db:
            # Find existing flashcard group
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise NotFoundError(f"Project {project_id} not found")

            language_code = project.language_code
            requested_knowledge_point_id = resolve_knowledge_point_id(
                db,
                project.course_id,
                texts=[topic],
                allow_contains=False,
            )

            group = (
                db.query(FlashcardGroup)
                .filter(
                    FlashcardGroup.id == group_id,
                    FlashcardGroup.project_id == project_id,
                )
                .first()
            )
            if not group:
                raise NotFoundError(f"Flashcard group {group_id} not found")

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

            # Generate flashcards using AI
            kwargs = {}
            if count is not None:
                kwargs["count"] = count
            if difficulty is not None:
                kwargs["difficulty"] = difficulty

            result = await generate(
                llm=self.llm,
                search_service=self.search_service,
                output_model=self.output_model,
                prompt_template=self.prompt_template,
                project_id=project_id,
                topic=generation_topic or "",
                language_code=language_code,
                custom_instructions=custom_instructions,
                **kwargs,
            )

            # Update group with generated name and description
            group.name = result.name
            group.description = result.description
            group.updated_at = datetime.now()
            db.flush()

            # Delete existing flashcards and create new ones
            db.query(Flashcard).filter(Flashcard.group_id == group_id).delete()

            # Save flashcards to database
            for position, flashcard_item in enumerate(result.flashcards):
                knowledge_point_id = requested_knowledge_point_id or resolve_knowledge_point_id(
                    db,
                    project.course_id,
                    texts=[flashcard_item.question, flashcard_item.answer],
                )
                flashcard = Flashcard(
                    id=str(uuid4()),
                    group_id=group_id,
                    project_id=project_id,
                    knowledge_point_id=knowledge_point_id,
                    question=flashcard_item.question,
                    answer=flashcard_item.answer,
                    difficulty_level=flashcard_item.difficulty_level,
                    position=position,
                    created_at=datetime.now(),
                )
                db.add(flashcard)

            db.flush()
            return group
