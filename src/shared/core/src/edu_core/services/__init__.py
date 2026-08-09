"""Services for managing entities."""

from edu_core.exceptions import NotFoundError
from edu_core.services.admin import AdminService
from edu_core.services.agent_orchestration import AgentOrchestrationService
from edu_core.services.billing import BillingError, BillingService
from edu_core.services.chats import ChatService
from edu_core.services.course_resources import CourseResourceService
from edu_core.services.courses import CourseService
from edu_core.services.document_upload import DocumentUploadService
from edu_core.services.documents import DocumentService
from edu_core.services.flashcard_groups import FlashcardGroupService
from edu_core.services.knowledge_states import KnowledgeStateService
from edu_core.services.learning_closed_loop import (
    KTConfigurationService,
    LearningClosedLoopService,
)
from edu_core.services.learner_profiles import LearnerProfileService
from edu_core.services.mind_maps import MindMapService
from edu_core.services.notes import NoteService
from edu_core.services.practice import PracticeService
from edu_core.services.projects import ProjectService
from edu_core.services.quizzes import QuizService
from edu_core.services.quota import QuotaService
from edu_core.services.resource_packages import ResourcePackageService
from edu_core.services.search import SearchService
from edu_core.services.study_plans import StudyPlanService
from edu_core.services.usage import UsageService
from edu_core.services.users import UserService

__all__ = [
    "AdminService",
    "AgentOrchestrationService",
    "BillingError",
    "BillingService",
    "ChatService",
    "CourseResourceService",
    "CourseService",
    "DocumentService",
    "DocumentUploadService",
    "FlashcardGroupService",
    "KnowledgeStateService",
    "KTConfigurationService",
    "LearningClosedLoopService",
    "LearnerProfileService",
    "MindMapService",
    "NotFoundError",
    "NoteService",
    "PracticeService",
    "ProjectService",
    "QuizService",
    "QuotaService",
    "ResourcePackageService",
    "SearchService",
    "SearchService",
    "StudyPlanService",
    "UsageService",
    "UserService",
]
