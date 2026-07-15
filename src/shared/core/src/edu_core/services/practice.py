"""CRUD service for managing practice records."""

from contextlib import contextmanager
from uuid import uuid4

from edu_db.models import (
    Flashcard,
    PracticeRecord,
    Project,
    QuizQuestion,
)
from edu_db.session import get_session_factory

from edu_core.schemas.practice import PracticeRecordDto
from edu_core.services.knowledge_point_matching import resolve_knowledge_point_id


class PracticeService:
    """Service for managing practice records."""

    def __init__(self) -> None:
        """Initialize the practice service."""
        pass

    def create_practice_record(
        self,
        user_id: str,
        project_id: str,
        item_type: str,
        item_id: str,
        knowledge_point_id: str | None,
        topic: str,
        user_answer: str | None,
        correct_answer: str,
        was_correct: bool,
    ) -> PracticeRecordDto:
        """Create a single practice record.

        Args:
            user_id: The user's unique identifier
            project_id: The project ID
            item_type: Type of study resource ('flashcard' or 'quiz')
            item_id: ID of the flashcard or quiz question
            topic: Topic of the study resource
            user_answer: User's answer (can be None for flashcards)
            correct_answer: The correct answer
            was_correct: Whether the user's answer was correct

        Returns:
            Created PracticeRecordDto

        Raises:
            ValueError: If the referenced study resource doesn't exist
        """
        with self._get_db_session() as db:
            try:
                # Validate that the referenced study resource exists
                if not self._validate_item(db, item_type, item_id):
                    raise ValueError(
                        f"Study resource {item_id} of type {item_type} not found"
                    )
                project = self._get_owned_project(db, project_id, user_id)
                resolved_knowledge_point_id = self._resolve_knowledge_point(
                    db,
                    project.course_id,
                    knowledge_point_id,
                    topic,
                    item_type,
                    item_id,
                )

                practice_record = PracticeRecord(
                    id=str(uuid4()),
                    user_id=user_id,
                    project_id=project_id,
                    knowledge_point_id=resolved_knowledge_point_id,
                    item_type=item_type,
                    item_id=item_id,
                    topic=topic,
                    user_answer=user_answer,
                    correct_answer=correct_answer,
                    was_correct=was_correct,
                )

                db.add(practice_record)
                db.commit()
                db.refresh(practice_record)

                return self._model_to_dto(practice_record)
            except ValueError:
                raise
            except Exception:
                db.rollback()
                raise

    def create_practice_records_batch(
        self,
        user_id: str,
        project_id: str,
        practice_records_data: list[dict],
    ) -> list[PracticeRecordDto]:
        """Create multiple practice records in a batch.

        Args:
            user_id: The user's unique identifier
            project_id: The project ID
            practice_records_data: List of dictionaries containing practice record data

        Returns:
            List of created PracticeRecordDto instances
        """
        with self._get_db_session() as db:
            try:
                created_records = []
                project = self._get_owned_project(db, project_id, user_id)

                for record_data in practice_records_data:
                    item_type = record_data.get("item_type")
                    item_id = record_data.get("item_id")

                    # Validate that the referenced study resource exists
                    if not self._validate_item(db, item_type, item_id):
                        continue
                    resolved_knowledge_point_id = self._resolve_knowledge_point(
                        db,
                        project.course_id,
                        record_data.get("knowledge_point_id"),
                        record_data.get("topic"),
                        item_type,
                        item_id,
                    )

                    practice_record = PracticeRecord(
                        id=str(uuid4()),
                        user_id=user_id,
                        project_id=project_id,
                        knowledge_point_id=resolved_knowledge_point_id,
                        item_type=item_type,
                        item_id=item_id,
                        topic=record_data.get("topic"),
                        user_answer=record_data.get("user_answer"),
                        correct_answer=record_data.get("correct_answer"),
                        was_correct=record_data.get("was_correct"),
                    )

                    db.add(practice_record)
                    created_records.append(practice_record)

                db.commit()

                # Refresh all records
                for record in created_records:
                    db.refresh(record)

                return [self._model_to_dto(record) for record in created_records]
            except Exception:
                db.rollback()
                raise

    def list_practice_records(
        self, user_id: str, project_id: str | None = None
    ) -> list[PracticeRecordDto]:
        """Retrieve practice records for a user, optionally filtered by project.

        Args:
            user_id: The user's unique identifier
            project_id: Optional project ID to filter by

        Returns:
            List of PracticeRecordDto instances
        """
        with self._get_db_session() as db:
            try:
                query = db.query(PracticeRecord).filter(
                    PracticeRecord.user_id == user_id
                )

                if project_id:
                    query = query.filter(PracticeRecord.project_id == project_id)

                records = query.order_by(PracticeRecord.created_at.desc()).all()

                return [self._model_to_dto(record) for record in records]
            except Exception:
                raise

    def _validate_item(self, db, item_type: str, item_id: str) -> bool:
        """Validate that the referenced study resource exists.

        Args:
            db: Database session
            item_type: Type of study resource ('flashcard' or 'quiz')
            item_id: ID of the study resource to validate

        Returns:
            True if study resource exists, False otherwise
        """
        try:
            if item_type == "flashcard":
                flashcard = db.query(Flashcard).filter(Flashcard.id == item_id).first()
                return flashcard is not None
            elif item_type == "quiz":
                question = (
                    db.query(QuizQuestion).filter(QuizQuestion.id == item_id).first()
                )
                return question is not None
            else:
                return False
        except Exception:
            return False

    @staticmethod
    def _get_owned_project(db, project_id: str, user_id: str) -> Project:
        project = (
            db.query(Project)
            .filter(Project.id == project_id, Project.owner_id == user_id)
            .first()
        )
        if not project:
            raise ValueError(f"Project {project_id} not found")
        return project

    @staticmethod
    def _resolve_knowledge_point(
        db,
        course_id: str | None,
        knowledge_point_id: str | None,
        topic: str | None,
        item_type: str | None,
        item_id: str | None,
    ) -> str | None:
        stored_knowledge_point_id = None
        content_texts: list[str | None] = [topic]
        if item_type == "quiz" and item_id:
            item = db.query(QuizQuestion).filter(QuizQuestion.id == item_id).first()
            if item:
                stored_knowledge_point_id = item.knowledge_point_id
                content_texts.extend([item.question_text, item.explanation])
        elif item_type == "flashcard" and item_id:
            item = db.query(Flashcard).filter(Flashcard.id == item_id).first()
            if item:
                stored_knowledge_point_id = item.knowledge_point_id
                content_texts.extend([item.question, item.answer])

        return resolve_knowledge_point_id(
            db,
            course_id,
            explicit_id=knowledge_point_id or stored_knowledge_point_id,
            texts=content_texts,
        )

    def _model_to_dto(self, record: PracticeRecord) -> PracticeRecordDto:
        """Convert PracticeRecord model to PracticeRecordDto."""
        return PracticeRecordDto(
            id=record.id,
            user_id=record.user_id,
            project_id=record.project_id,
            knowledge_point_id=record.knowledge_point_id,
            item_type=record.item_type,
            item_id=record.item_id,
            topic=record.topic,
            user_answer=record.user_answer,
            correct_answer=record.correct_answer,
            was_correct=record.was_correct,
            created_at=record.created_at,
        )

    @contextmanager
    def _get_db_session(self):
        """Context manager for database sessions."""
        SessionLocal = get_session_factory()
        db = SessionLocal()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
