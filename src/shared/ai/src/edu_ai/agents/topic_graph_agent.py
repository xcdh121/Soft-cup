from contextlib import suppress
from typing import Any, Protocol

from edu_core.schemas.documents import DocumentStatus
from edu_db.models import Document, Project
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, Field

from edu_ai.agents.utils import generate, get_db_session


class TextStorage(Protocol):
    def read_text(self, relative_path: str) -> str: ...


class Topic(BaseModel):
    """Model for a topic in the topic graph."""

    topic: str = Field(..., description="The name of the topic.")
    subtopics: list["Topic"] = Field(default=[], description="A list of subtopics.")


class TopicGraph(BaseModel):
    """Model for the topic graph."""

    root_topics: list[Topic] = Field(
        ..., description="A list of root topics in the graph."
    )


class TopicGraphAgent:
    output_model = TopicGraph
    prompt_template = "topic_graph_prompt"

    def __init__(
        self,
        search_service: Any,
        llm: BaseChatModel,
        text_storage: TextStorage | None = None,
    ):
        self.search_service = search_service
        self.llm = llm
        self.text_storage = text_storage

    async def generate_topic_graph(
        self,
        project_id: str,
        topic: str | None = None,
        custom_instructions: str | None = None,
        **kwargs: Any,
    ) -> TopicGraph:
        """Generate a topic graph for a given project.

        Args:
            project_id: The project ID.
            topic: Optional root topic for generation.
            custom_instructions: Optional custom instructions.
            **kwargs: Additional agent-specific parameters.

        Returns:
            The generated topic graph.
        """
        with get_db_session() as db:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise ValueError(f"Project {project_id} not found")

            documents = (
                db.query(Document)
                .filter(
                    Document.project_id == project_id,
                    Document.status == DocumentStatus.INDEXED.value,
                )
                .all()
            )

            if not documents:
                return TopicGraph(root_topics=[])

            document_contents = []
            if self.text_storage:
                for doc in documents:
                    stored_path = doc.processed_text_blob_name
                    with suppress(Exception):
                        if stored_path:
                            document_contents.append(self.text_storage.read_text(stored_path))

            full_content = "\n\n".join(document_contents)

            return await generate(
                llm=self.llm,
                search_service=self.search_service,
                output_model=self.output_model,
                prompt_template=self.prompt_template,
                project_id=project_id,
                topic=topic or "",
                language_code=project.language_code,
                custom_instructions=custom_instructions,
                document_content=full_content,
                **kwargs,
            )
