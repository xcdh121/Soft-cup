import { createRootRoute, createRoute, redirect } from '@tanstack/react-router'
import { Suspense, lazy } from 'react'
import { z } from 'zod'
import { authClient } from '@/lib/auth-client'
import { AppShell } from '@/routes/_app-shell'

const LoadingPage = () => {
  return (
    <div className="flex h-screen items-center justify-center">正在加载...</div>
  )
}

// Dynamic imports for code-splitting
const ProjectDetailRoute = lazy(() =>
  import('./project-detail-route').then((m) => ({
    default: m.ProjectDetailRoute,
  })),
)
const SignInPage = lazy(() =>
  import('@/features/auth/sign-in-page').then((m) => ({
    default: m.SignInPage,
  })),
)
const SignUpPage = lazy(() =>
  import('@/features/auth/sign-up-page').then((m) => ({
    default: m.SignUpPage,
  })),
)
const ChatDetailRoute = lazy(() =>
  import('./chat-detail-route').then((m) => ({ default: m.ChatDetailRoute })),
)
const DocumentDetailRoute = lazy(() =>
  import('./document-detail-route').then((m) => ({
    default: m.DocumentDetailRoute,
  })),
)
const CustomDocumentLearningRoute = lazy(() =>
  import('./custom-document-learning-route').then((m) => ({
    default: m.CustomDocumentLearningRoute,
  })),
)
const QuizDetailRoute = lazy(() =>
  import('./quiz-detail-route').then((m) => ({ default: m.QuizDetailRoute })),
)
const QuizEditRoute = lazy(() =>
  import('./quiz-edit-route').then((m) => ({ default: m.QuizEditRoute })),
)
const FlashcardDetailRoute = lazy(() =>
  import('./flashcard-detail-route').then((m) => ({
    default: m.FlashcardDetailRoute,
  })),
)
const FlashcardEditRoute = lazy(() =>
  import('./flashcard-edit-route').then((m) => ({
    default: m.FlashcardEditRoute,
  })),
)
const NoteDetailRoute = lazy(() =>
  import('./note-detail-route').then((m) => ({
    default: m.NoteDetailRoute,
  })),
)
const MindMapDetailRoute = lazy(() =>
  import('./mind-map-detail-route').then((m) => ({
    default: m.MindMapDetailRoute,
  })),
)

const StudyPlanRoute = lazy(() =>
  import('./study-plan-route').then((m) => ({
    default: m.StudyPlanRoute,
  })),
)
const CustomStudyPlanRoute = lazy(() =>
  import('./custom-study-plan-route').then((m) => ({
    default: m.CustomStudyPlanRoute,
  })),
)
const ResourcePackageRoute = lazy(() =>
  import('./resource-package-route').then((m) => ({
    default: m.ResourcePackageRoute,
  })),
)
const HandwritingRecognitionRoute = lazy(() =>
  import('./handwriting-recognition-route').then((m) => ({
    default: m.HandwritingRecognitionRoute,
  })),
)
const PdfOcrRoute = lazy(() =>
  import('./pdf-ocr-route').then((m) => ({
    default: m.PdfOcrRoute,
  })),
)
const DocumentTranslationRoute = lazy(() =>
  import('./document-translation-route').then((m) => ({
    default: m.DocumentTranslationRoute,
  })),
)
const ProgrammingPracticeRoute = lazy(() =>
  import('./programming-practice-route').then((m) => ({
    default: m.ProgrammingPracticeRoute,
  })),
)
const LearnerProfileRoute = lazy(() =>
  import('./learner-profile-route').then((m) => ({
    default: m.LearnerProfileRoute,
  })),
)
const CourseLibraryRoute = lazy(() =>
  import('./course-library-route').then((m) => ({
    default: m.CourseLibraryRoute,
  })),
)
const MyCoursesRoute = lazy(() =>
  import('./my-courses-route').then((m) => ({
    default: m.MyCoursesRoute,
  })),
)
const KnowledgeGraphRoute = lazy(() =>
  import('./knowledge-graph-route').then((m) => ({
    default: m.KnowledgeGraphRoute,
  })),
)
const LearningEvaluationRoute = lazy(() =>
  import('./learning-evaluation-route').then((m) => ({
    default: m.LearningEvaluationRoute,
  })),
)
const SettingsPage = lazy(() =>
  import('@/features/settings/settings-page').then((m) => ({
    default: m.SettingsPage,
  })),
)
const DashboardRoute = lazy(() =>
  import('./dashboard-route').then((m) => ({ default: m.DashboardRoute })),
)
const DashboardPage = lazy(() =>
  import('@/features/dashboard/dashboard-page').then((m) => ({
    default: m.DashboardPage,
  })),
)
const AgentRuntimeRoute = lazy(() =>
  import('./agent-runtime-route').then((m) => ({
    default: m.AgentRuntimeRoute,
  })),
)
const requireAuth = async () => {
  const {
    data: { session },
  } = await authClient.auth.getSession()
  const isAuthenticated = !!session

  if (!isAuthenticated) {
    const isSignInPage = window.location.pathname === '/sign-in'

    throw redirect({
      to: '/sign-in',
      search: {
        redirect: isSignInPage ? undefined : window.location.pathname,
      },
    })
  }
}

export const rootRoute = createRootRoute({
  component: AppShell,
})

// Dashboard layout route - parent for all authenticated routes
export const dashboardRoute = createRoute({
  path: '/dashboard',
  getParentRoute: () => rootRoute,
  beforeLoad: requireAuth,
  component: () => (
    <Suspense fallback={<LoadingPage />}>
      <DashboardRoute />
    </Suspense>
  ),
})

export const indexRoute = createRoute({
  path: '/',
  getParentRoute: () => rootRoute,
  validateSearch: z.object({ redirect: z.string().optional() }).optional(),
  beforeLoad: () => {
    throw redirect({ to: '/sign-in' })
  },
})

export const signInRoute = createRoute({
  path: '/sign-in',
  getParentRoute: () => rootRoute,
  validateSearch: z.object({ redirect: z.string().optional() }).optional(),
  component: () => (
    <Suspense fallback={<LoadingPage />}>
      <SignInPage />
    </Suspense>
  ),
})

export const signUpRoute = createRoute({
  path: '/sign-up',
  getParentRoute: () => rootRoute,
  validateSearch: z.object({ redirect: z.string().optional() }).optional(),
  component: () => (
    <Suspense fallback={<LoadingPage />}>
      <SignUpPage />
    </Suspense>
  ),
})

export const dashboardIndexRoute = createRoute({
  path: '/',
  getParentRoute: () => dashboardRoute,
  component: () => (
    <Suspense fallback={<LoadingPage />}>
      <DashboardPage />
    </Suspense>
  ),
})

export const projectDetailRoute = createRoute({
  path: '/p/$projectId',
  getParentRoute: () => dashboardRoute,
  component: () => (
    <Suspense fallback={<LoadingPage />}>
      <ProjectDetailRoute />
    </Suspense>
  ),
})

export const chatDetailRoute = createRoute({
  path: '/p/$projectId/c/$chatId',
  getParentRoute: () => dashboardRoute,
  component: () => (
    <Suspense fallback={<LoadingPage />}>
      <ChatDetailRoute />
    </Suspense>
  ),
})

export const documentDetailRoute = createRoute({
  path: '/p/$projectId/d/$documentId',
  getParentRoute: () => dashboardRoute,
  component: () => (
    <Suspense fallback={<LoadingPage />}>
      <DocumentDetailRoute />
    </Suspense>
  ),
})

export const customDocumentLearningRoute = createRoute({
  path: '/p/$projectId/custom-documents',
  getParentRoute: () => dashboardRoute,
  component: () => (
    <Suspense fallback={<LoadingPage />}>
      <CustomDocumentLearningRoute />
    </Suspense>
  ),
})

export const flashcardDetailRoute = createRoute({
  path: '/p/$projectId/f/$flashcardGroupId',
  getParentRoute: () => dashboardRoute,
  component: () => (
    <Suspense fallback={<LoadingPage />}>
      <FlashcardDetailRoute />
    </Suspense>
  ),
})

export const flashcardEditRoute = createRoute({
  path: '/p/$projectId/f/$flashcardGroupId/edit',
  getParentRoute: () => dashboardRoute,
  component: () => (
    <Suspense fallback={<LoadingPage />}>
      <FlashcardEditRoute />
    </Suspense>
  ),
})

export const quizDetailRoute = createRoute({
  path: '/p/$projectId/q/$quizId',
  getParentRoute: () => dashboardRoute,
  component: () => (
    <Suspense fallback={<LoadingPage />}>
      <QuizDetailRoute />
    </Suspense>
  ),
})

export const quizEditRoute = createRoute({
  path: '/p/$projectId/q/$quizId/edit',
  getParentRoute: () => dashboardRoute,
  component: () => (
    <Suspense fallback={<LoadingPage />}>
      <QuizEditRoute />
    </Suspense>
  ),
})

export const noteDetailRoute = createRoute({
  path: '/p/$projectId/n/$noteId',
  getParentRoute: () => dashboardRoute,
  component: () => (
    <Suspense fallback={<LoadingPage />}>
      <NoteDetailRoute />
    </Suspense>
  ),
})

export const mindMapDetailRoute = createRoute({
  path: '/p/$projectId/m/$mindMapId',
  getParentRoute: () => dashboardRoute,
  component: () => (
    <Suspense fallback={<LoadingPage />}>
      <MindMapDetailRoute />
    </Suspense>
  ),
})

export const studyPlanRoute = createRoute({
  path: '/p/$projectId/study-plan',
  getParentRoute: () => dashboardRoute,
  component: () => (
    <Suspense fallback={<LoadingPage />}>
      <StudyPlanRoute />
    </Suspense>
  ),
})

export const customStudyPlanRoute = createRoute({
  path: '/p/$projectId/study-plan/customize',
  getParentRoute: () => dashboardRoute,
  component: () => (
    <Suspense fallback={<LoadingPage />}>
      <CustomStudyPlanRoute />
    </Suspense>
  ),
})

export const resourcePackageRoute = createRoute({
  path: '/p/$projectId/resource-packages',
  getParentRoute: () => dashboardRoute,
  validateSearch: z.object({ packageId: z.string().optional() }).optional(),
  component: () => (
    <Suspense fallback={<LoadingPage />}>
      <ResourcePackageRoute />
    </Suspense>
  ),
})

export const handwritingRecognitionRoute = createRoute({
  path: '/p/$projectId/handwriting-recognition',
  getParentRoute: () => dashboardRoute,
  component: () => (
    <Suspense fallback={<LoadingPage />}>
      <HandwritingRecognitionRoute />
    </Suspense>
  ),
})

export const pdfOcrRoute = createRoute({
  path: '/p/$projectId/pdf-ocr',
  getParentRoute: () => dashboardRoute,
  component: () => (
    <Suspense fallback={<LoadingPage />}>
      <PdfOcrRoute />
    </Suspense>
  ),
})

export const documentTranslationRoute = createRoute({
  path: '/p/$projectId/document-translation',
  getParentRoute: () => dashboardRoute,
  component: () => (
    <Suspense fallback={<LoadingPage />}>
      <DocumentTranslationRoute />
    </Suspense>
  ),
})

export const programmingPracticeRoute = createRoute({
  path: '/p/$projectId/programming/$resourceId',
  getParentRoute: () => dashboardRoute,
  component: () => (
    <Suspense fallback={<LoadingPage />}>
      <ProgrammingPracticeRoute />
    </Suspense>
  ),
})

export const learnerProfileRoute = createRoute({
  path: '/p/$projectId/learner-profile',
  getParentRoute: () => dashboardRoute,
  component: () => (
    <Suspense fallback={<LoadingPage />}>
      <LearnerProfileRoute />
    </Suspense>
  ),
})

export const courseLibraryRoute = createRoute({
  path: '/course-library',
  getParentRoute: () => dashboardRoute,
  validateSearch: z.object({ courseId: z.string().optional() }).optional(),
  component: () => (
    <Suspense fallback={<LoadingPage />}>
      <CourseLibraryRoute />
    </Suspense>
  ),
})

export const myCoursesRoute = createRoute({
  path: '/my-courses',
  getParentRoute: () => dashboardRoute,
  component: () => (
    <Suspense fallback={<LoadingPage />}>
      <MyCoursesRoute />
    </Suspense>
  ),
})

export const knowledgeGraphRoute = createRoute({
  path: '/p/$projectId/knowledge-graph',
  getParentRoute: () => dashboardRoute,
  component: () => (
    <Suspense fallback={<LoadingPage />}>
      <KnowledgeGraphRoute />
    </Suspense>
  ),
})

export const learningEvaluationRoute = createRoute({
  path: '/p/$projectId/learning-evaluation',
  getParentRoute: () => dashboardRoute,
  component: () => (
    <Suspense fallback={<LoadingPage />}>
      <LearningEvaluationRoute section="history" />
    </Suspense>
  ),
})

export const learningEvaluationHistoryRoute = createRoute({
  path: '/p/$projectId/learning-evaluation/history',
  getParentRoute: () => dashboardRoute,
  component: () => (
    <Suspense fallback={<LoadingPage />}>
      <LearningEvaluationRoute section="history" />
    </Suspense>
  ),
})

export const learningEvaluationProgrammingRoute = createRoute({
  path: '/p/$projectId/learning-evaluation/programming',
  getParentRoute: () => dashboardRoute,
  component: () => (
    <Suspense fallback={<LoadingPage />}>
      <LearningEvaluationRoute section="practice" />
    </Suspense>
  ),
})

export const learningEvaluationChoiceRoute = createRoute({
  path: '/p/$projectId/learning-evaluation/choice',
  getParentRoute: () => dashboardRoute,
  component: () => (
    <Suspense fallback={<LoadingPage />}>
      <LearningEvaluationRoute section="practice" />
    </Suspense>
  ),
})

export const learningEvaluationPracticeRoute = createRoute({
  path: '/p/$projectId/learning-evaluation/practice',
  getParentRoute: () => dashboardRoute,
  component: () => (
    <Suspense fallback={<LoadingPage />}>
      <LearningEvaluationRoute section="practice" />
    </Suspense>
  ),
})

export const settingsRoute = createRoute({
  path: '/settings',
  getParentRoute: () => dashboardRoute,
  component: () => (
    <Suspense fallback={<LoadingPage />}>
      <SettingsPage />
    </Suspense>
  ),
})

export const agentRuntimeRoute = createRoute({
  path: '/agent-runtime',
  getParentRoute: () => dashboardRoute,
  component: () => (
    <Suspense fallback={<LoadingPage />}>
      <AgentRuntimeRoute />
    </Suspense>
  ),
})

export const routeTree = rootRoute.addChildren([
  dashboardRoute.addChildren([
    dashboardIndexRoute,
    projectDetailRoute,
    chatDetailRoute,
    customDocumentLearningRoute,
    documentDetailRoute,
    flashcardDetailRoute,
    flashcardEditRoute,
    quizDetailRoute,
    quizEditRoute,
    noteDetailRoute,
    mindMapDetailRoute,

    studyPlanRoute,
    customStudyPlanRoute,
    resourcePackageRoute,
    handwritingRecognitionRoute,
    pdfOcrRoute,
    documentTranslationRoute,
    programmingPracticeRoute,
    learnerProfileRoute,
    myCoursesRoute,
    courseLibraryRoute,
    knowledgeGraphRoute,
    learningEvaluationRoute,
    learningEvaluationHistoryRoute,
    learningEvaluationProgrammingRoute,
    learningEvaluationChoiceRoute,
    learningEvaluationPracticeRoute,
    agentRuntimeRoute,
    settingsRoute,
  ]),
  indexRoute,
  signInRoute,
  signUpRoute,
])
