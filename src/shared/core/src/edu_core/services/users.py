"""CRUD service for managing users."""

from contextlib import contextmanager
from uuid import uuid4

from edu_db.models import User
from edu_db.session import get_session_factory
from sqlalchemy.exc import IntegrityError

from edu_core.exceptions import NotFoundError
from edu_core.schemas.users import UserDto


class UserService:
    """Service for managing users."""

    def __init__(self) -> None:
        """Initialize the user service."""
        pass

    def get_user(self, user_id: str) -> UserDto:
        """Get a user by ID.

        Args:
            user_id: The user ID

        Returns:
            UserDto

        Raises:
            NotFoundError: If user not found
        """
        with self._get_db_session() as db:
            try:
                user = db.query(User).filter(User.id == user_id).first()
                if not user:
                    raise NotFoundError(f"User {user_id} not found")

                return self._model_to_dto(user)
            except NotFoundError:
                raise
            except Exception:
                raise

    def list_users(self) -> list[UserDto]:
        """List all users.

        Returns:
            List of UserDto instances
        """
        with self._get_db_session() as db:
            try:
                users = db.query(User).order_by(User.created_at.desc()).all()
                return [self._model_to_dto(user) for user in users]
            except Exception:
                raise

    def get_user_auth_record(self, username: str) -> tuple[UserDto, str] | None:
        """Return the public user data and password hash for authentication."""
        normalized_username = username.strip().casefold()
        with self._get_db_session() as db:
            user = db.query(User).filter(User.username == normalized_username).first()
            if not user or not user.password_hash:
                return None
            return self._model_to_dto(user), user.password_hash

    def create_local_user(
        self,
        *,
        username: str,
        password_hash: str,
        name: str | None = None,
        is_admin: bool = False,
    ) -> UserDto:
        """Create a user whose credentials are managed by this application."""
        normalized_username = username.strip().casefold()
        with self._get_db_session() as db:
            try:
                existing = (
                    db.query(User).filter(User.username == normalized_username).first()
                )
                if existing:
                    raise ValueError("该账户名已被使用")

                user = User(
                    id=str(uuid4()),
                    username=normalized_username,
                    email=None,
                    name=(name or normalized_username).strip(),
                    password_hash=password_hash,
                    is_active=True,
                    is_admin=is_admin,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                return self._model_to_dto(user)
            except IntegrityError as exc:
                db.rollback()
                raise ValueError("该账户名已被使用") from exc
            except Exception:
                db.rollback()
                raise

    def update_profile(
        self,
        user_id: str,
        *,
        name: str | None = None,
        avatar_url: str | None = None,
    ) -> UserDto:
        """Update the editable profile fields for a user."""
        with self._get_db_session() as db:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise NotFoundError(f"User {user_id} not found")

            if name is not None:
                user.name = name
            if avatar_url is not None:
                user.avatar_url = avatar_url

            db.commit()
            db.refresh(user)
            return self._model_to_dto(user)

    def delete_user(self, user_id: str) -> None:
        """Delete a user.

        Args:
            user_id: The user ID

        Raises:
            NotFoundError: If user not found
        """
        with self._get_db_session() as db:
            try:
                user = db.query(User).filter(User.id == user_id).first()
                if not user:
                    raise NotFoundError(f"User {user_id} not found")

                db.delete(user)
                db.commit()
            except NotFoundError:
                raise
            except Exception:
                db.rollback()
                raise

    def get_or_create_user_from_token(
        self,
        user_id: str,
        username: str | None = None,
        email: str | None = None,
        name: str | None = None,
    ) -> UserDto:
        """Get or create a user from JWT token data.

        Args:
            user_id: The user ID from JWT token (sub claim)
            email: Optional email from token
            name: Optional name from token

        Returns:
            UserDto: The user DTO
        """
        with self._get_db_session() as db:
            try:
                # Try to get existing user
                user = db.query(User).filter(User.id == user_id).first()

                if user:
                    # Update user information if needed
                    updated = False
                    if username and user.username != username:
                        user.username = username
                        updated = True
                    if email and user.email != email:
                        user.email = email
                        updated = True
                    if name and user.name != name:
                        user.name = name
                        updated = True

                    if updated:
                        db.commit()
                        db.refresh(user)

                    return self._model_to_dto(user)
                else:
                    # Development-only fallback account used by auth bypass mode.
                    new_user = User(
                        id=user_id,
                        username=username or f"legacy_{user_id[:16]}",
                        email=email,
                        name=name or username or f"user_{user_id[:8]}",
                    )
                    db.add(new_user)
                    db.commit()
                    db.refresh(new_user)
                    return self._model_to_dto(new_user)
            except Exception:
                db.rollback()
                raise

    def _model_to_dto(self, user: User) -> UserDto:
        """Convert User model to UserDto."""
        return UserDto(
            id=user.id,
            username=user.username,
            name=user.name,
            email=user.email,
            avatar_url=user.avatar_url,
            is_active=user.is_active,
            is_admin=user.is_admin,
            created_at=user.created_at,
            updated_at=user.updated_at,
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
