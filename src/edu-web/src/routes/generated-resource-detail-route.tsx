import { generatedResourceDetailRoute } from '@/routes/_config'
import { GeneratedResourceDetailPage } from '@/features/my-resources/generated-resource-detail-page'

export const GeneratedResourceDetailRoute = () => {
  const params = generatedResourceDetailRoute.useParams()

  return (
    <GeneratedResourceDetailPage
      projectId={params.projectId}
      resourceId={params.resourceId}
    />
  )
}
