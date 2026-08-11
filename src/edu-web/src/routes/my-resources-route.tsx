import { useParams } from '@tanstack/react-router'
import { MyResourcesPage } from '@/features/my-resources/my-resources-page'

export const MyResourcesRoute = () => {
  const { projectId } = useParams({ strict: false })

  return <MyResourcesPage projectId={projectId ?? ''} />
}
