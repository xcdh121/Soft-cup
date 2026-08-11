from .admin import router as admin_router
from .agent_runs import router as agent_runs_router
from .auth import router as auth_router
from .billing import router as billing_router
from .chats import router as chats_router
from .course_covers import router as course_covers_router
from .courses import knowledge_points_router
from .courses import router as courses_router
from .dashboard import router as dashboard_router
from .diagnosis import router as diagnosis_router
from .documents import course_books_router
from .documents import router as documents_router
from .flashcard_groups import router as flashcard_groups_router
from .handwriting import router as handwriting_router
from .intervention_outcomes import router as intervention_outcomes_router
from .knowledge_states import knowledge_graph_router
from .knowledge_states import router as knowledge_states_router
from .learner_profiles import router as learner_profiles_router
from .learning_paths import router as learning_paths_router
from .kt_parameters import router as kt_parameters_router
from .mind_maps import router as mind_maps_router
from .notes import router as notes_router
from .pdf_ocr import router as pdf_ocr_router
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
from .translation import router as translation_router
from .usage import router as usage_router
from .users import router as users_router

__all__ = [
    "admin_router",
    "agent_runs_router",
    "auth_router",
    "billing_router",
    "chats_router",
    "course_books_router",
    "course_covers_router",
    "courses_router",
    "dashboard_router",
    "diagnosis_router",
    "documents_router",
    "flashcard_groups_router",
    "generated_resources_router",
    "handwriting_router",
    "intervention_outcomes_router",
    "knowledge_graph_router",
    "knowledge_points_router",
    "knowledge_states_router",
    "kt_parameters_router",
    "learner_profiles_router",
    "learning_paths_router",
    "mind_maps_router",
    "notes_router",
    "pdf_ocr_router",
    "practice_records_router",
    "projects_router",
    "quizzes_router",
    "recommendations_router",
    "resource_packages_router",
    "speech_router",
    "study_plans_router",
    "translation_router",
    "usage_router",
    "users_router",
]
