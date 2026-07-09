from .auth import router as auth_router
from .chats import router as chats_router
from .courses import knowledge_points_router
from .courses import router as courses_router
from .dashboard import router as dashboard_router
from .diagnosis import router as diagnosis_router
from .documents import router as documents_router
from .flashcard_groups import router as flashcard_groups_router
from .knowledge_states import knowledge_graph_router
from .knowledge_states import router as knowledge_states_router
from .learner_profiles import router as learner_profiles_router
from .learning_paths import router as learning_paths_router
from .mind_maps import router as mind_maps_router
from .notes import router as notes_router
from .practice_records import router as practice_records_router
from .projects import router as projects_router
from .quizzes import router as quizzes_router
from .recommendations import router as recommendations_router
from .resource_packages import (
    generated_resources_router,
    resource_packages_router,
)
from .speech import router as speech_router
from .study_plans import study_plans_router
from .usage import router as usage_router
from .users import router as users_router

__all__ = [
    "auth_router",
    "chats_router",
    "courses_router",
    "dashboard_router",
    "diagnosis_router",
    "documents_router",
    "flashcard_groups_router",
    "generated_resources_router",
    "knowledge_graph_router",
    "knowledge_points_router",
    "knowledge_states_router",
    "learner_profiles_router",
    "learning_paths_router",
    "mind_maps_router",
    "notes_router",
    "practice_records_router",
    "projects_router",
    "quizzes_router",
    "recommendations_router",
    "resource_packages_router",
    "speech_router",
    "study_plans_router",
    "usage_router",
    "users_router",
]
