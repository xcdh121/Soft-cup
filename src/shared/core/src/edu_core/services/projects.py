"""CRUD service for managing projects."""

from contextlib import contextmanager
from datetime import datetime
from uuid import uuid4

from edu_db.models import Course, Project
from edu_db.session import get_session_factory

from edu_core.exceptions import NotFoundError
from edu_core.schemas.projects import ProjectDto


class ProjectService:
    """Service for managing projects."""

    def __init__(self) -> None:
        """Initialize the project service."""
        pass

    def create_project(
        self,
        owner_id: str,
        name: str,
        description: str | None = None,
        language_code: str | None = "zh",
        course_id: str | None = None,
    ) -> ProjectDto:
        """Create a new project.

        Args:
            owner_id: The project owner's user ID
            name: The project name
            description: Optional project description
            language_code: Language code for the project (default: "zh")
            course_id: Optional parent course ID

        Returns:
            Created ProjectDto
        """
        with self._get_db_session() as db:
            try:
                self._validate_course_ownership(db, course_id, owner_id)
                project = Project(
                    id=str(uuid4()),
                    owner_id=owner_id,
                    course_id=course_id,
                    name=name,
                    description=description,
                    language_code=language_code or "zh",
                    created_at=datetime.now(),
                )
                db.add(project)
                db.commit()
                db.refresh(project)

                return self._model_to_dto(project)
            except Exception:
                db.rollback()
                raise

    def get_project(self, project_id: str, owner_id: str) -> ProjectDto:
        """Get a project by ID.

        Args:
            project_id: The project ID
            owner_id: The project owner's user ID

        Returns:
            ProjectDto

        Raises:
            NotFoundError: If project not found
        """
        with self._get_db_session() as db:
            try:
                project = (
                    db.query(Project)
                    .filter(Project.id == project_id, Project.owner_id == owner_id)
                    .first()
                )
                if not project:
                    raise NotFoundError(f"Project {project_id} not found")

                return self._model_to_dto(project)
            except NotFoundError:
                raise
            except Exception:
                raise

    def list_projects(self, owner_id: str) -> list[ProjectDto]:
        """List all projects for a user.

        Args:
            owner_id: The project owner's user ID

        Returns:
            List of ProjectDto instances
        """
        with self._get_db_session() as db:
            try:
                projects = (
                    db.query(Project)
                    .filter(Project.owner_id == owner_id)
                    .order_by(Project.created_at.desc())
                    .all()
                )
                return [self._model_to_dto(project) for project in projects]
            except Exception:
                raise

    def update_project(
        self,
        project_id: str,
        owner_id: str,
        name: str | None = None,
        description: str | None = None,
        language_code: str | None = None,
        course_id: str | None = None,
        fields_to_update: set[str] | None = None,
    ) -> ProjectDto:
        """Update a project.

        Args:
            project_id: The project ID
            owner_id: The project owner's user ID
            name: Optional new project name
            description: Optional new project description
            language_code: Optional new language code
            course_id: Optional parent course ID
            fields_to_update: Fields explicitly included in the PATCH request

        Returns:
            Updated ProjectDto

        Raises:
            NotFoundError: If project not found
        """
        with self._get_db_session() as db:
            try:
                project = (
                    db.query(Project)
                    .filter(Project.id == project_id, Project.owner_id == owner_id)
                    .first()
                )
                if not project:
                    raise NotFoundError(f"Project {project_id} not found")

                updates = fields_to_update or set()
                if "name" in updates and name is not None:
                    project.name = name
                if "description" in updates:
                    project.description = description
                if "language_code" in updates and language_code is not None:
                    project.language_code = language_code
                if "course_id" in updates:
                    self._validate_course_ownership(db, course_id, owner_id)
                    project.course_id = course_id

                db.commit()
                db.refresh(project)

                return self._model_to_dto(project)
            except NotFoundError:
                raise
            except Exception:
                db.rollback()
                raise

    def delete_project(self, project_id: str, owner_id: str) -> None:
        """Delete a project.

        Args:
            project_id: The project ID
            owner_id: The project owner's user ID

        Raises:
            NotFoundError: If project not found
        """
        with self._get_db_session() as db:
            try:
                project = (
                    db.query(Project)
                    .filter(Project.id == project_id, Project.owner_id == owner_id)
                    .first()
                )
                if not project:
                    raise NotFoundError(f"Project {project_id} not found")

                db.delete(project)
                db.commit()
            except NotFoundError:
                raise
            except Exception:
                db.rollback()
                raise

    def _model_to_dto(self, project: Project) -> ProjectDto:
        """Convert Project model to ProjectDto."""
        return ProjectDto(
            id=project.id,
            owner_id=project.owner_id,
            course_id=project.course_id,
            name=project.name,
            description=project.description,
            language_code=project.language_code,
            created_at=project.created_at,
        )

    @staticmethod
    def _validate_course_ownership(
        db, course_id: str | None, owner_id: str
    ) -> None:
        if course_id is None:
            return

        course = (
            db.query(Course)
            .filter(Course.id == course_id, Course.owner_id == owner_id)
            .first()
        )
        if not course:
            raise NotFoundError(f"Course {course_id} not found")

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
