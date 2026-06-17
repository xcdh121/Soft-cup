"""CRUD service for course resources and their knowledge-point links."""

from contextlib import contextmanager
from uuid import uuid4

from edu_db.models import (
    Course,
    CourseChapter,
    CourseResource,
    CourseResourceKnowledgePoint,
    Document,
    GeneratedResource,
    KnowledgePoint,
    Project,
)
from edu_db.session import get_session_factory

from edu_core.exceptions import NotFoundError
from edu_core.schemas.course_resources import CourseResourceDto


class CourseResourceService:
    """Manage reusable learning resources in an owned course."""

    def create_resource(
        self,
        course_id: str,
        owner_id: str,
        *,
        chapter_id: str | None,
        document_id: str | None,
        generated_resource_id: str | None,
        resource_type: str,
        title: str,
        description: str | None,
        source_type: str,
        source_url: str | None,
        difficulty_level: str,
        estimated_minutes: int | None,
        license_info: str | None,
        target_audiences: list[str],
        metadata: dict,
        knowledge_point_ids: list[str],
    ) -> CourseResourceDto:
        with self._get_db_session() as db:
            self._get_owned_course(db, course_id, owner_id)
            self._validate_references(
                db,
                course_id,
                owner_id,
                chapter_id,
                document_id,
                generated_resource_id,
                knowledge_point_ids,
            )

            resource = CourseResource(
                id=str(uuid4()),
                course_id=course_id,
                chapter_id=chapter_id,
                document_id=document_id,
                generated_resource_id=generated_resource_id,
                resource_type=resource_type,
                title=title,
                description=description,
                source_type=source_type,
                source_url=source_url,
                difficulty_level=difficulty_level,
                estimated_minutes=estimated_minutes,
                license_info=license_info,
                target_audiences=target_audiences,
                extra_metadata=metadata,
            )
            db.add(resource)
            self._replace_knowledge_point_links(
                db, resource, knowledge_point_ids
            )
            db.commit()
            db.refresh(resource)
            return self._to_dto(resource)

    def list_resources(
        self, course_id: str, owner_id: str
    ) -> list[CourseResourceDto]:
        with self._get_db_session() as db:
            self._get_owned_course(db, course_id, owner_id)
            resources = (
                db.query(CourseResource)
                .filter(CourseResource.course_id == course_id)
                .order_by(CourseResource.created_at.desc())
                .all()
            )
            return [self._to_dto(resource) for resource in resources]

    def get_resource(
        self, course_id: str, resource_id: str, owner_id: str
    ) -> CourseResourceDto:
        with self._get_db_session() as db:
            self._get_owned_course(db, course_id, owner_id)
            return self._to_dto(
                self._get_course_resource(db, course_id, resource_id)
            )

    def list_resources_by_knowledge_point(
        self, knowledge_point_id: str, owner_id: str
    ) -> list[CourseResourceDto]:
        with self._get_db_session() as db:
            point = self._get_owned_knowledge_point(
                db, knowledge_point_id, owner_id
            )
            resources = (
                db.query(CourseResource)
                .join(
                    CourseResourceKnowledgePoint,
                    CourseResource.id
                    == CourseResourceKnowledgePoint.course_resource_id,
                )
                .filter(
                    CourseResource.course_id == point.course_id,
                    CourseResourceKnowledgePoint.knowledge_point_id
                    == knowledge_point_id,
                )
                .order_by(CourseResource.created_at.desc())
                .all()
            )
            return [self._to_dto(resource) for resource in resources]

    def create_resource_for_knowledge_point(
        self,
        knowledge_point_id: str,
        owner_id: str,
        *,
        chapter_id: str | None,
        document_id: str | None,
        generated_resource_id: str | None,
        resource_type: str,
        title: str,
        description: str | None,
        source_type: str,
        source_url: str | None,
        difficulty_level: str,
        estimated_minutes: int | None,
        license_info: str | None,
        target_audiences: list[str],
        metadata: dict,
        knowledge_point_ids: list[str],
    ) -> CourseResourceDto:
        with self._get_db_session() as db:
            point = self._get_owned_knowledge_point(
                db, knowledge_point_id, owner_id
            )
            linked_point_ids = list(
                dict.fromkeys([knowledge_point_id, *knowledge_point_ids])
            )
            resource_chapter_id = (
                chapter_id if chapter_id is not None else point.chapter_id
            )
            self._validate_references(
                db,
                point.course_id,
                owner_id,
                resource_chapter_id,
                document_id,
                generated_resource_id,
                linked_point_ids,
            )

            resource = CourseResource(
                id=str(uuid4()),
                course_id=point.course_id,
                chapter_id=resource_chapter_id,
                document_id=document_id,
                generated_resource_id=generated_resource_id,
                resource_type=resource_type,
                title=title,
                description=description,
                source_type=source_type,
                source_url=source_url,
                difficulty_level=difficulty_level,
                estimated_minutes=estimated_minutes,
                license_info=license_info,
                target_audiences=target_audiences,
                extra_metadata=metadata,
            )
            db.add(resource)
            self._replace_knowledge_point_links(db, resource, linked_point_ids)
            db.commit()
            db.refresh(resource)
            return self._to_dto(resource)

    def update_resource(
        self,
        course_id: str,
        resource_id: str,
        owner_id: str,
        updates: dict,
    ) -> CourseResourceDto:
        with self._get_db_session() as db:
            self._get_owned_course(db, course_id, owner_id)
            resource = self._get_course_resource(db, course_id, resource_id)

            chapter_id = updates.get("chapter_id", resource.chapter_id)
            document_id = updates.get("document_id", resource.document_id)
            generated_resource_id = updates.get(
                "generated_resource_id", resource.generated_resource_id
            )
            if document_id and generated_resource_id:
                raise ValueError(
                    "document_id and generated_resource_id cannot both be set"
                )

            knowledge_point_ids = updates.get(
                "knowledge_point_ids",
                [
                    link.knowledge_point_id
                    for link in resource.knowledge_point_links
                ],
            )
            self._validate_references(
                db,
                course_id,
                owner_id,
                chapter_id,
                document_id,
                generated_resource_id,
                knowledge_point_ids,
            )

            column_map = {"metadata": "extra_metadata"}
            for field, value in updates.items():
                if field == "knowledge_point_ids":
                    continue
                setattr(resource, column_map.get(field, field), value)

            if "knowledge_point_ids" in updates:
                self._replace_knowledge_point_links(
                    db, resource, knowledge_point_ids
                )

            db.commit()
            db.refresh(resource)
            return self._to_dto(resource)

    def delete_resource(
        self, course_id: str, resource_id: str, owner_id: str
    ) -> None:
        with self._get_db_session() as db:
            self._get_owned_course(db, course_id, owner_id)
            resource = self._get_course_resource(db, course_id, resource_id)
            db.delete(resource)
            db.commit()

    def _validate_references(
        self,
        db,
        course_id: str,
        owner_id: str,
        chapter_id: str | None,
        document_id: str | None,
        generated_resource_id: str | None,
        knowledge_point_ids: list[str],
    ) -> None:
        if chapter_id:
            chapter = (
                db.query(CourseChapter)
                .filter(
                    CourseChapter.id == chapter_id,
                    CourseChapter.course_id == course_id,
                )
                .first()
            )
            if not chapter:
                raise NotFoundError(
                    f"Chapter {chapter_id} not found in course {course_id}"
                )

        if document_id:
            document = (
                db.query(Document)
                .join(Project, Document.project_id == Project.id)
                .filter(
                    Document.id == document_id,
                    Document.owner_id == owner_id,
                    Project.course_id == course_id,
                )
                .first()
            )
            if not document:
                raise NotFoundError(
                    f"Document {document_id} is not available in course {course_id}"
                )

        if generated_resource_id:
            generated = (
                db.query(GeneratedResource)
                .join(Project, GeneratedResource.project_id == Project.id)
                .filter(
                    GeneratedResource.id == generated_resource_id,
                    GeneratedResource.user_id == owner_id,
                    Project.course_id == course_id,
                )
                .first()
            )
            if not generated:
                raise NotFoundError(
                    "Generated resource "
                    f"{generated_resource_id} is not available in course {course_id}"
                )

        unique_ids = set(knowledge_point_ids)
        if unique_ids:
            found_ids = {
                row.id
                for row in db.query(KnowledgePoint)
                .filter(
                    KnowledgePoint.course_id == course_id,
                    KnowledgePoint.id.in_(unique_ids),
                )
                .all()
            }
            missing_ids = unique_ids - found_ids
            if missing_ids:
                raise NotFoundError(
                    "Knowledge points not found in course: "
                    + ", ".join(sorted(missing_ids))
                )

    @staticmethod
    def _replace_knowledge_point_links(
        db, resource: CourseResource, knowledge_point_ids: list[str]
    ) -> None:
        resource.knowledge_point_links.clear()
        for knowledge_point_id in dict.fromkeys(knowledge_point_ids):
            resource.knowledge_point_links.append(
                CourseResourceKnowledgePoint(
                    id=str(uuid4()),
                    knowledge_point_id=knowledge_point_id,
                    relevance_score=1.0,
                )
            )

    @staticmethod
    def _get_owned_course(db, course_id: str, owner_id: str) -> Course:
        course = (
            db.query(Course)
            .filter(Course.id == course_id, Course.owner_id == owner_id)
            .first()
        )
        if not course:
            raise NotFoundError(f"Course {course_id} not found")
        return course

    @staticmethod
    def _get_course_resource(
        db, course_id: str, resource_id: str
    ) -> CourseResource:
        resource = (
            db.query(CourseResource)
            .filter(
                CourseResource.id == resource_id,
                CourseResource.course_id == course_id,
            )
            .first()
        )
        if not resource:
            raise NotFoundError(
                f"Resource {resource_id} not found in course {course_id}"
            )
        return resource

    @staticmethod
    def _get_owned_knowledge_point(
        db, knowledge_point_id: str, owner_id: str
    ) -> KnowledgePoint:
        point = (
            db.query(KnowledgePoint)
            .join(Course, KnowledgePoint.course_id == Course.id)
            .filter(
                KnowledgePoint.id == knowledge_point_id,
                Course.owner_id == owner_id,
            )
            .first()
        )
        if not point:
            raise NotFoundError(f"Knowledge point {knowledge_point_id} not found")
        return point

    @staticmethod
    def _to_dto(resource: CourseResource) -> CourseResourceDto:
        return CourseResourceDto(
            id=resource.id,
            course_id=resource.course_id,
            chapter_id=resource.chapter_id,
            document_id=resource.document_id,
            generated_resource_id=resource.generated_resource_id,
            resource_type=resource.resource_type,
            title=resource.title,
            description=resource.description,
            source_type=resource.source_type,
            source_url=resource.source_url,
            difficulty_level=resource.difficulty_level,
            estimated_minutes=resource.estimated_minutes,
            license_info=resource.license_info,
            target_audiences=resource.target_audiences or [],
            metadata=resource.extra_metadata or {},
            knowledge_point_ids=[
                link.knowledge_point_id
                for link in resource.knowledge_point_links
            ],
            created_at=resource.created_at,
            updated_at=resource.updated_at,
        )

    @contextmanager
    def _get_db_session(self):
        session_local = get_session_factory()
        db = session_local()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
