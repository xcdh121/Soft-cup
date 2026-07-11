"""Note tools for agent."""

import asyncio
import json
from contextlib import suppress

from edu_ai.chatbot.context import ChatbotContext
from edu_core.schemas.notes import NoteDto
from edu_core.services.notes import NoteService
from langchain.tools import tool
from langgraph.prebuilt import ToolRuntime


def build_enhanced_prompt(
    custom_instructions: str | None,
    query: str | None = None,
    document_ids: list[str] | None = None,
) -> str:
    """Build enhanced prompt with optional query and document filtering."""
    prompt = custom_instructions or ""
    if query:
        prompt += f" Focus on: {query}"
    if document_ids:
        prompt += f" Based on specific documents: {', '.join(document_ids)}"
    return prompt


def increment_usage(usage, user_id: str, feature: str) -> None:
    """Increment usage tracking, log errors but don't fail."""
    if not usage:
        return
    with suppress(Exception):
        usage.check_and_increment(user_id, feature)


@tool(
    "note_create",
    description="Create a study note (markdown) from project documents. Provide a short topic plus optional custom instructions (length, structure, focus, etc.).",
)
async def create_note(
    topic: str,
    runtime: ToolRuntime[ChatbotContext],
    custom_instructions: str | None = None,
) -> str:
    """Create a study note from project documents."""
    ctx = runtime.context
    increment_usage(ctx.usage, ctx.user_id, "note_generation")

    svc = NoteService(queue_service=ctx.queue)
    # Create a new note first
    note = svc.create_note(
        project_id=ctx.project_id,
        title="Generated Note",
        description="AI-generated study note",
        content="",
    )

    generated_resource = None
    if ctx.resource_packages is not None:
        generated_resource = await asyncio.to_thread(
            ctx.resource_packages.register_chat_note,
            user_id=ctx.user_id,
            project_id=ctx.project_id,
            note_id=note.id,
            topic=topic,
            custom_instructions=custom_instructions,
        )

    # Send message to queue
    try:
        svc.queue_generation(
            note_id=note.id,
            project_id=ctx.project_id,
            topic=topic,
            custom_instructions=custom_instructions,
            user_id=ctx.user_id,
            generated_resource_id=(
                generated_resource.id if generated_resource is not None else None
            ),
        )
    except Exception as exc:
        if generated_resource is not None:
            await asyncio.to_thread(
                ctx.resource_packages.finish_chat_note,
                project_id=ctx.project_id,
                generated_resource_id=generated_resource.id,
                error_message=str(exc),
            )
        raise

    return json.dumps(
        {
            "status": "queued",
            "message": "Your request to generate a note has been queued.",
            "note_id": note.id,
            "resource_package_id": (
                generated_resource.resource_package_id
                if generated_resource is not None
                else None
            ),
            "preview_url": (
                generated_resource.preview_url
                if generated_resource is not None
                else None
            ),
        },
        ensure_ascii=False,
    )


@tool(
    "note_create_scoped",
    description="Create a study note from specific documents. Use when user references specific docs or IDs.",
)
async def create_note_scoped(
    custom_instructions: str,
    document_ids: list[str],
    query: str,
    runtime: ToolRuntime[ChatbotContext],
) -> str:
    """Create a study note from specific documents."""
    ctx = runtime.context
    increment_usage(ctx.usage, ctx.user_id, "note_generation")

    enhanced_prompt = build_enhanced_prompt(custom_instructions, query, document_ids)

    svc = NoteService(queue_service=ctx.queue)
    # Create a new note first
    note = svc.create_note(
        project_id=ctx.project_id,
        user_id=ctx.user_id,
        title="Generated Note",
        description="AI-generated study note",
    )

    # Send message to queue
    svc.queue_generation(
        note_id=note.id,
        project_id=ctx.project_id,
        topic=query,
        custom_instructions=enhanced_prompt,
        user_id=ctx.user_id,
    )

    return json.dumps(
        {
            "status": "queued",
            "message": "Your request to generate a note from specific documents has been queued.",
            "note_id": note.id,
        },
        ensure_ascii=False,
    )


@tool(
    "note_list",
    description="List notes only when the user explicitly asks to browse or find notes. Never use it to verify a note created in the current turn.",
)
async def list_notes(runtime: ToolRuntime[ChatbotContext]) -> str:
    """List notes for a project."""
    ctx = runtime.context
    svc = NoteService(queue_service=ctx.queue)
    notes = await asyncio.to_thread(svc.list_notes, ctx.project_id)

    notes_dto = [NoteDto.model_validate(n) for n in notes]
    result = {
        "data": [n.model_dump() for n in notes_dto],
        "count": len(notes_dto),
    }
    return json.dumps(result, ensure_ascii=False, default=str)


@tool(
    "note_get",
    description="Get an existing note by ID only when the user explicitly asks to open or read it. Never use it to verify a note created in the current turn.",
)
async def get_note(
    note_id: str,
    runtime: ToolRuntime[ChatbotContext],
) -> str:
    """Get a specific note by ID."""
    ctx = runtime.context
    svc = NoteService(queue_service=ctx.queue)
    note = await asyncio.to_thread(svc.get_note, note_id, ctx.project_id)

    if not note:
        return json.dumps({"error": "Note not found"}, ensure_ascii=False)

    note_dto = NoteDto.model_validate(note)
    result = note_dto.model_dump()
    return json.dumps(result, ensure_ascii=False, default=str)


@tool("note_delete", description="Delete a note")
async def delete_note(
    note_id: str,
    runtime: ToolRuntime[ChatbotContext],
) -> str:
    """Delete a note."""
    ctx = runtime.context
    svc = NoteService(queue_service=ctx.queue)
    await asyncio.to_thread(svc.delete_note, note_id, ctx.project_id)

    result = {
        "success": True,
        "note_id": note_id,
        "message": "Note successfully deleted.",
    }
    return json.dumps(result, ensure_ascii=False)


tools = [
    create_note,
    # create_note_scoped,
    list_notes,
    get_note,
    delete_note,
]
