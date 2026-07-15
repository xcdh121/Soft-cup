import { HandwritingRecognitionPage } from '@/features/handwriting-recognition/handwriting-recognition-page'
import { handwritingRecognitionRoute } from '@/routes/_config'

export const HandwritingRecognitionRoute = () => {
  const params = handwritingRecognitionRoute.useParams()
  return <HandwritingRecognitionPage projectId={params.projectId} />
}
