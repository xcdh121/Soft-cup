import { useParams } from '@tanstack/react-router'
import type { LearningEvaluationSection } from '@/features/learning-evaluation/learning-evaluation-page'
import { LearningEvaluationPage } from '@/features/learning-evaluation/learning-evaluation-page'

export const LearningEvaluationRoute = ({
  section = 'history',
}: {
  section?: LearningEvaluationSection
}) => {
  const params = useParams({ strict: false })
  return (
    <LearningEvaluationPage
      projectId={String(params.projectId)}
      section={section}
    />
  )
}
