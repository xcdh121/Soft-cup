import { useParams } from '@tanstack/react-router'
import { DocumentTranslationPage } from '@/features/document-translation/document-translation-page'

export const DocumentTranslationRoute = () => {
  const { projectId } = useParams({ strict: false })
  return <DocumentTranslationPage projectId={projectId as string} />
}
