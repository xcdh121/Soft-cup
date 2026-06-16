"""CRUD service for courses, chapters, and knowledge points."""

from contextlib import contextmanager
from uuid import uuid4

from edu_db.models import (
    Course,
    CourseChapter,
    KnowledgePoint,
    KnowledgePointRelation,
    Project,
)
from edu_db.session import get_session_factory

from edu_core.exceptions import NotFoundError
from edu_core.schemas.courses import (
    CourseChapterDto,
    CourseDto,
    KnowledgePointDto,
    KnowledgePointRelationDto,
)
from edu_core.schemas.projects import ProjectDto


class CourseService:
    """Manage the structured course library owned by a user."""

    def create_course(
        self,
        owner_id: str,
        name: str,
        code: str | None = None,
        description: str | None = None,
        status: str = "active",
    ) -> CourseDto:
        with self._get_db_session() as db:
            course = Course(
                id=str(uuid4()),
                owner_id=owner_id,
                code=code,
                name=name,
                description=description,
                status=status,
            )
            db.add(course)
            db.commit()
            db.refresh(course)
            return CourseDto.model_validate(course)

    def list_courses(self, owner_id: str) -> list[CourseDto]:
        with self._get_db_session() as db:
            courses = (
                db.query(Course)
                .filter(Course.owner_id == owner_id)
                .order_by(Course.created_at.desc())
                .all()
            )
            return [CourseDto.model_validate(course) for course in courses]

    def get_course(self, course_id: str, owner_id: str) -> CourseDto:
        with self._get_db_session() as db:
            course = self._get_owned_course(db, course_id, owner_id)
            return CourseDto.model_validate(course)

    def update_course(
        self,
        course_id: str,
        owner_id: str,
        code: str | None = None,
        name: str | None = None,
        description: str | None = None,
        status: str | None = None,
        fields_to_update: set[str] | None = None,
    ) -> CourseDto:
        with self._get_db_session() as db:
            course = self._get_owned_course(db, course_id, owner_id)
            updates = fields_to_update or set()

            if "code" in updates:
                course.code = code
            if "name" in updates and name is not None:
                course.name = name
            if "description" in updates:
                course.description = description
            if "status" in updates and status is not None:
                course.status = status

            db.commit()
            db.refresh(course)
            return CourseDto.model_validate(course)

    def delete_course(self, course_id: str, owner_id: str) -> None:
        with self._get_db_session() as db:
            course = self._get_owned_course(db, course_id, owner_id)
            db.delete(course)
            db.commit()

    def list_course_projects(
        self, course_id: str, owner_id: str
    ) -> list[ProjectDto]:
        with self._get_db_session() as db:
            self._get_owned_course(db, course_id, owner_id)
            projects = (
                db.query(Project)
                .filter(
                    Project.course_id == course_id,
                    Project.owner_id == owner_id,
                )
                .order_by(Project.created_at.desc())
                .all()
            )
            return [ProjectDto.model_validate(project) for project in projects]

    def create_chapter(
        self,
        course_id: str,
        owner_id: str,
        title: str,
        description: str | None = None,
        parent_chapter_id: str | None = None,
        position: int = 0,
        learning_objectives: list[str] | None = None,
        estimated_minutes: int | None = None,
    ) -> CourseChapterDto:
        with self._get_db_session() as db:
            self._get_owned_course(db, course_id, owner_id)
            if parent_chapter_id is not None:
                self._get_course_chapter(db, course_id, parent_chapter_id)

            chapter = CourseChapter(
                id=str(uuid4()),
                course_id=course_id,
                parent_chapter_id=parent_chapter_id,
                title=title,
                description=description,
                position=position,
                learning_objectives=learning_objectives or [],
                estimated_minutes=estimated_minutes,
            )
            db.add(chapter)
            db.commit()
            db.refresh(chapter)
            return CourseChapterDto.model_validate(chapter)

    def list_chapters(
        self, course_id: str, owner_id: str
    ) -> list[CourseChapterDto]:
        with self._get_db_session() as db:
            self._get_owned_course(db, course_id, owner_id)
            chapters = (
                db.query(CourseChapter)
                .filter(CourseChapter.course_id == course_id)
                .order_by(CourseChapter.position, CourseChapter.created_at)
                .all()
            )
            return [
                CourseChapterDto.model_validate(chapter) for chapter in chapters
            ]

    def create_knowledge_point(
        self,
        course_id: str,
        owner_id: str,
        name: str,
        description: str | None = None,
        chapter_id: str | None = None,
        difficulty_level: str = "intermediate",
        position: int = 0,
        tags: list[str] | None = None,
    ) -> KnowledgePointDto:
        with self._get_db_session() as db:
            self._get_owned_course(db, course_id, owner_id)
            if chapter_id is not None:
                self._get_course_chapter(db, course_id, chapter_id)

            duplicate = (
                db.query(KnowledgePoint)
                .filter(
                    KnowledgePoint.course_id == course_id,
                    KnowledgePoint.name == name,
                )
                .first()
            )
            if duplicate:
                raise ValueError(
                    f"Knowledge point '{name}' already exists in this course"
                )

            knowledge_point = KnowledgePoint(
                id=str(uuid4()),
                course_id=course_id,
                chapter_id=chapter_id,
                name=name,
                description=description,
                difficulty_level=difficulty_level,
                position=position,
                tags=tags or [],
            )
            db.add(knowledge_point)
            db.commit()
            db.refresh(knowledge_point)
            return KnowledgePointDto.model_validate(knowledge_point)

    def list_knowledge_points(
        self, course_id: str, owner_id: str
    ) -> list[KnowledgePointDto]:
        with self._get_db_session() as db:
            self._get_owned_course(db, course_id, owner_id)
            knowledge_points = (
                db.query(KnowledgePoint)
                .filter(KnowledgePoint.course_id == course_id)
                .order_by(KnowledgePoint.position, KnowledgePoint.created_at)
                .all()
            )
            return [
                KnowledgePointDto.model_validate(point)
                for point in knowledge_points
            ]

    def create_knowledge_point_relation(
        self,
        course_id: str,
        owner_id: str,
        source_knowledge_point_id: str,
        target_knowledge_point_id: str,
        relation_type: str = "prerequisite",
        strength: float = 1.0,
        description: str | None = None,
    ) -> KnowledgePointRelationDto:
        with self._get_db_session() as db:
            self._get_owned_course(db, course_id, owner_id)
            if source_knowledge_point_id == target_knowledge_point_id:
                raise ValueError("source and target knowledge points cannot be the same")
            self._get_course_knowledge_point(
                db, course_id, source_knowledge_point_id
            )
            self._get_course_knowledge_point(
                db, course_id, target_knowledge_point_id
            )

            duplicate = (
                db.query(KnowledgePointRelation)
                .filter(
                    KnowledgePointRelation.source_knowledge_point_id
                    == source_knowledge_point_id,
                    KnowledgePointRelation.target_knowledge_point_id
                    == target_knowledge_point_id,
                    KnowledgePointRelation.relation_type == relation_type,
                )
                .first()
            )
            if duplicate:
                raise ValueError("Knowledge point relation already exists")

            relation = KnowledgePointRelation(
                id=str(uuid4()),
                course_id=course_id,
                source_knowledge_point_id=source_knowledge_point_id,
                target_knowledge_point_id=target_knowledge_point_id,
                relation_type=relation_type,
                strength=strength,
                description=description,
            )
            db.add(relation)
            db.commit()
            db.refresh(relation)
            return KnowledgePointRelationDto.model_validate(relation)

    def list_knowledge_point_relations(
        self, course_id: str, owner_id: str
    ) -> list[KnowledgePointRelationDto]:
        with self._get_db_session() as db:
            self._get_owned_course(db, course_id, owner_id)
            relations = (
                db.query(KnowledgePointRelation)
                .filter(KnowledgePointRelation.course_id == course_id)
                .order_by(KnowledgePointRelation.created_at)
                .all()
            )
            return [
                KnowledgePointRelationDto.model_validate(relation)
                for relation in relations
            ]

    def delete_knowledge_point_relation(
        self, course_id: str, relation_id: str, owner_id: str
    ) -> None:
        with self._get_db_session() as db:
            self._get_owned_course(db, course_id, owner_id)
            relation = (
                db.query(KnowledgePointRelation)
                .filter(
                    KnowledgePointRelation.id == relation_id,
                    KnowledgePointRelation.course_id == course_id,
                )
                .first()
            )
            if not relation:
                raise NotFoundError(
                    f"Knowledge point relation {relation_id} not found"
                )
            db.delete(relation)
            db.commit()

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
    def _get_course_chapter(
        db, course_id: str, chapter_id: str
    ) -> CourseChapter:
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
        return chapter

    @staticmethod
    def _get_course_knowledge_point(
        db, course_id: str, knowledge_point_id: str
    ) -> KnowledgePoint:
        point = (
            db.query(KnowledgePoint)
            .filter(
                KnowledgePoint.id == knowledge_point_id,
                KnowledgePoint.course_id == course_id,
            )
            .first()
        )
        if not point:
            raise NotFoundError(
                f"Knowledge point {knowledge_point_id} not found in course {course_id}"
            )
        return point

    @contextmanager
    def _get_db_session(self):
        SessionLocal = get_session_factory()
        db = SessionLocal()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
