from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any
from uuid import uuid4

from edu_core.exceptions import NotFoundError
from edu_db.models import MindMap, Project
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, Field

from edu_ai.agents.topic_graph_agent import TopicGraphAgent
from edu_ai.agents.utils import generate, generate_stream, get_db_session


class MindMapNodeData(BaseModel):
    """Model for a mind map node."""

    id: str = Field(..., description="Unique identifier for the node")
    label: str = Field(..., description="Text label for the node")
    position: dict[str, float] = Field(
        ..., description="Position coordinates {x, y} for the node"
    )
    data: dict = Field(default_factory=dict, description="Additional data for the node")


class MindMapEdgeData(BaseModel):
    """Model for a mind map edge."""

    id: str = Field(..., description="Unique identifier for the edge")
    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    label: str | None = Field(default=None, description="Optional label for the edge")


class MindMapGenerationResult(BaseModel):
    """Model for mind map generation result."""

    title: str = Field(..., description="The title of the mind map")
    description: str = Field(..., description="The description of the mind map")
    nodes: list[MindMapNodeData] = Field(
        ..., description="List of nodes in the mind map"
    )
    edges: list[MindMapEdgeData] = Field(
        ..., description="List of edges in the mind map"
    )


class MindMapAgent:
    output_model = MindMapGenerationResult
    prompt_template = "mind_map_prompt"

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
        mind_map_id: str | None = None,
        user_id: str | None = None,
        **kwargs: Any,
    ) -> MindMap:
        """Generate mind map content and save to the database.

        If mind_map_id is provided, updates existing mind map.
        Otherwise, creates a new mind map (requires user_id).

        Args:
            project_id: The project ID
            topic: Optional topic for generation
            custom_instructions: Optional custom instructions
            mind_map_id: Optional mind map ID to populate (if None, creates new)
            user_id: Required if creating new mind map

        Returns:
            Updated or created MindMap model

        Raises:
            NotFoundError: If mind_map_id is provided but mind map not found
            ValueError: If creating new mind map but user_id not provided
        """
        with get_db_session() as db:
            if mind_map_id:
                # Update existing mind map
                if not user_id:
                    raise ValueError(
                        "user_id is required when updating existing mind map"
                    )

                mind_map = (
                    db.query(MindMap)
                    .filter(
                        MindMap.id == mind_map_id,
                        MindMap.project_id == project_id,
                        MindMap.user_id == user_id,
                    )
                    .first()
                )
                if not mind_map:
                    raise NotFoundError(f"Mind map {mind_map_id} not found")
            else:
                # Create new mind map
                if not user_id:
                    raise ValueError("user_id is required when creating new mind map")

                mind_map = MindMap(
                    id=str(uuid4()),
                    user_id=user_id,
                    project_id=project_id,
                    title="Generating...",
                    description="Mind map is being generated",
                    map_data={"nodes": [], "edges": []},
                    generated_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                db.add(mind_map)
                db.flush()

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

            # Generate mind map using AI
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

            # Convert agent result to map_data format
            map_data = {
                "nodes": [
                    {
                        "id": node.id,
                        "data": {"label": node.label, **node.data},
                        "position": node.position,
                    }
                    for node in result.nodes
                ],
                "edges": [
                    {
                        "id": edge.id,
                        "source": edge.source,
                        "target": edge.target,
                        "label": edge.label,
                    }
                    for edge in result.edges
                ],
            }

            # Update mind map with generated content
            mind_map.title = result.title
            mind_map.description = result.description
            mind_map.map_data = map_data
            mind_map.updated_at = datetime.now()

            db.flush()
            return mind_map

    async def generate_and_save_stream(
        self,
        project_id: str,
        topic: str | None = None,
        custom_instructions: str | None = None,
        mind_map_id: str | None = None,
        user_id: str | None = None,
    ) -> AsyncGenerator[dict[str, Any]]:
        if not mind_map_id or not user_id:
            raise ValueError("mind_map_id and user_id are required")

        with get_db_session() as db:
            mind_map = db.query(MindMap).filter(
                MindMap.id == mind_map_id,
                MindMap.project_id == project_id,
                MindMap.user_id == user_id,
            ).first()
            if not mind_map:
                raise NotFoundError(f"Mind map {mind_map_id} not found")
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

            sent_node_ids: set[str] = set()
            sent_edge_ids: set[str] = set()
            final_result: MindMapGenerationResult | None = None
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
                try:
                    final_result = self.output_model.model_validate(partial)
                except Exception:
                    final_result = None
                nodes = []
                for raw in partial.get("nodes") or []:
                    try:
                        node = MindMapNodeData.model_validate(raw)
                    except Exception:
                        continue
                    if node.id not in sent_node_ids:
                        nodes.append(node.model_dump())
                stable_nodes = (
                    nodes
                    if final_result is not None or "edges" in partial
                    else nodes[:-1]
                )
                for node in stable_nodes:
                    sent_node_ids.add(str(node["id"]))
                edges = []
                for raw in partial.get("edges") or []:
                    try:
                        edge = MindMapEdgeData.model_validate(raw)
                    except Exception:
                        continue
                    if edge.id not in sent_edge_ids:
                        edges.append(edge.model_dump())
                stable_edges = edges if final_result is not None else edges[:-1]
                for edge in stable_edges:
                    sent_edge_ids.add(str(edge["id"]))
                if stable_nodes or stable_edges:
                    yield {
                        "event": "mind_map_batch",
                        "mind_map_id": mind_map_id,
                        "nodes": stable_nodes,
                        "edges": stable_edges,
                    }

            if final_result is None:
                raise ValueError("The model did not return a complete mind map")
            map_data = {
                "nodes": [
                    {
                        "id": node.id,
                        "data": {"label": node.label, **node.data},
                        "position": node.position,
                    }
                    for node in final_result.nodes
                ],
                "edges": [edge.model_dump() for edge in final_result.edges],
            }
            mind_map.title = final_result.title
            mind_map.description = final_result.description
            mind_map.map_data = map_data
            mind_map.updated_at = datetime.now()
            db.commit()
            yield {
                "event": "mind_map_completed",
                "mind_map_id": mind_map_id,
                "title": mind_map.title,
                "description": mind_map.description,
                "map_data": map_data,
            }
