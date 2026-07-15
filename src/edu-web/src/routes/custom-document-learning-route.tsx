import { CustomDocumentLearningPage } from '@/features/document/custom-document-learning-page'
import { customDocumentLearningRoute } from '@/routes/_config'

export const CustomDocumentLearningRoute = () => {
  const params = customDocumentLearningRoute.useParams()
  return <CustomDocumentLearningPage projectId={params.projectId} />
}
