import { LearningEvaluationPage } from '@/features/learning-evaluation/learning-evaluation-page'
import { learningEvaluationRoute } from '@/routes/_config'

export const LearningEvaluationRoute = () => {
  const params = learningEvaluationRoute.useParams()
  return <LearningEvaluationPage projectId={params.projectId} />
}
