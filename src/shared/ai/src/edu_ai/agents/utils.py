import logging
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, TypeVar

from edu_db.session import get_session_factory
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel

from edu_core.model_providers import LlmProviderConfig, create_chat_model
from edu_ai.prompts.prompts_utils import render_prompt

if TYPE_CHECKING:
    from edu_core.services import SearchService

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class ContentAgentConfig(BaseModel):
    llm_model: str
    llm_api_key: str = ""
    llm_base_url: str | None = None


@contextmanager
def get_db_session():
    """Context manager for database sessions with transaction handling.

    Yields:
        Database session

    Raises:
        Exception: If transaction fails, automatically rolls back
    """
    SessionLocal = get_session_factory()
    db = SessionLocal(expire_on_commit=False)
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_llm(config: ContentAgentConfig) -> BaseChatModel:
    """Create a chat model instance from provider config.

    Args:
        config: The ContentAgentConfig

    Returns:
        A chat model instance
    """
    return create_chat_model(
        LlmProviderConfig(
            model=config.llm_model,
            api_key=config.llm_api_key,
            base_url=config.llm_base_url,
            temperature=0.7,
        )
    )


async def get_context(
    project_id: str, topic: str, search_service: "SearchService"
) -> str:
    """Fetch relevant document segments directly from DocumentService."""
    if not topic:
        logger.warning(f"No topic provided for project: {project_id}")
        return ""

    # Use existing search logic in DocumentService
    # We request top 10 chunks to give the AI enough context
    results = await search_service.search_documents(
        query=topic, project_id=project_id, top_k=10
    )

    if not results:
        logger.warning(f"No documents found for topic: {topic}")
        return "No relevant documents found in the project."

    # Join content blocks
    return "\n\n---\n\n".join([r.content for r in results])


async def generate[T](
    llm: BaseChatModel,
    search_service: "SearchService",
    output_model: type[T],
    prompt_template: str,
    project_id: str,
    topic: str,
    language_code: str,
    custom_instructions: str | None = None,
    document_content: str | None = None,
    **kwargs: Any,
) -> T:
    """
    Main generation flow:
    1. Search documents using 'topic'
    2. Build Prompt (Context + Instructions)
    3. Call LLM
    4. Parse Result
    """
    logger.info(f"Generating for topic: {topic}")

    # 1. RAG Search or use provided content
    if document_content:
        context_text = document_content
    else:
        context_text = await get_context(project_id, topic, search_service)

    # 2. Prepare Parser
    parser = JsonOutputParser(pydantic_object=output_model)

    # 3. Render Prompt
    prompt_input = render_prompt(
        prompt_template,
        document_content=context_text,
        topic=topic,
        custom_instructions=custom_instructions or "No specific instructions.",
        format_instructions=parser.get_format_instructions(),
        language_code=language_code or "en",
        **kwargs,  # Pass extra args like 'count', 'difficulty'
    )

    # 4. Invoke LLM
    try:
        response = await llm.ainvoke(prompt_input)
        parsed_data = parser.parse(response.content)
        return output_model(**parsed_data)
    except Exception as e:
        logger.error(f"AI Generation failed: {e}")
        raise
