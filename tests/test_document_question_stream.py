import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from config import Settings
from routers.documents import stream_document_question
from routers.schemas import DocumentQuestionRequest


class _DocumentService:
    def get_document(self, *, document_id: str, owner_id: str, project_id: str):
        del owner_id
        return SimpleNamespace(
            id=document_id,
            project_id=project_id,
            file_name="线性代数.pdf",
            metadata={"display_title": "线性代数"},
        )

    def get_page_context(
        self,
        *,
        document_id: str,
        owner_id: str,
        project_id: str,
        page_number: int,
    ):
        del owner_id, project_id
        return SimpleNamespace(
            document_id=document_id,
            page_number=page_number,
            content="矩阵是按行和列排列的元素集合。",
            segments=[SimpleNamespace(id="segment-1", page_number=page_number)],
        )


class _SearchService:
    async def search_documents(self, *, query: str, project_id: str, top_k: int):
        del query, project_id, top_k
        return []


class _StreamingModel:
    async def astream(self, prompt: str):
        self.prompt = prompt
        for content in ("矩阵是", [{"text": "一种二维结构。"}]):
            yield SimpleNamespace(content=content)


class DocumentQuestionStreamTest(unittest.IsolatedAsyncioTestCase):
    async def test_stream_emits_deltas_citations_and_done(self):
        model = _StreamingModel()
        with patch(
            "routers.documents.create_chat_model", return_value=model
        ) as create_model:
            response = await stream_document_question(
                project_id="project-1",
                document_id="document-1",
                request=DocumentQuestionRequest(
                    question="什么是矩阵?",
                    selected_text="矩阵",
                    page_number=3,
                ),
                current_user=SimpleNamespace(id="student-1"),
                service=_DocumentService(),
                search_service=_SearchService(),
                settings=Settings(
                    llm_api_key="test-key",
                    llm_model="test-model",
                ),
            )

        body = b"".join([chunk async for chunk in response.body_iterator]).decode()
        events = [
            json.loads(block.removeprefix("data: "))
            for block in body.strip().split("\n\n")
        ]

        self.assertEqual(
            "".join(event["content"] for event in events if event["type"] == "delta"),
            "矩阵是一种二维结构。",
        )
        self.assertEqual(events[-2]["type"], "citations")
        self.assertEqual(events[-2]["citations"][0]["page_number"], 3)
        self.assertEqual(events[-1], {"type": "done"})
        self.assertTrue(create_model.call_args.kwargs["streaming"])
        self.assertIn("Student question:\n什么是矩阵?", model.prompt)


if __name__ == "__main__":
    unittest.main()
