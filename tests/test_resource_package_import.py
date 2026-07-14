import unittest
from unittest.mock import patch

from edu_core.services.resource_packages import ResourcePackageService
from edu_db.models import Base, GeneratedResource, Project, ResourcePackage, User
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


class ResourcePackageImportTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.session_patch = patch(
            "edu_core.services.resource_packages.get_session_factory",
            return_value=self.session_factory,
        )
        self.session_patch.start()
        with self.session_factory() as db:
            db.add(User(id="user-1", name="Test", email="test@example.com"))
            db.add(Project(id="project-1", owner_id="user-1", name="AI Study"))
            db.commit()

    def tearDown(self):
        self.session_patch.stop()
        self.engine.dispose()

    def test_imports_completed_text_resource(self):
        service = ResourcePackageService()

        result = service.import_resource(
            user_id="user-1",
            project_id="project-1",
            title="课堂手写笔记",
            summary="讯飞手写识别结果",
            origin="handwriting",
            resource_type="lecture_note",
            content_format="text",
            content_text="二叉树的遍历方式",
        )

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.resource_count, 1)
        self.assertEqual(result.resources[0].content_text, "二叉树的遍历方式")
        with self.session_factory() as db:
            self.assertEqual(db.query(ResourcePackage).count(), 1)
            self.assertEqual(db.query(GeneratedResource).count(), 1)

    def test_imports_pdf_file_resource(self):
        service = ResourcePackageService()

        result = service.import_resource(
            user_id="user-1",
            project_id="project-1",
            title="PDF 识别文档",
            summary="讯飞 PDF OCR 结果",
            origin="pdf_ocr",
            resource_type="reading_material",
            content_format="word",
            file_url="https://example.test/result.docx",
        )

        self.assertEqual(
            result.resources[0].file_url, "https://example.test/result.docx"
        )


if __name__ == "__main__":
    unittest.main()
