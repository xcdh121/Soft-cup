import { ResourcePackagePage } from '@/features/resource-package/resource-package-page'
import { resourcePackageRoute } from '@/routes/_config'

export const ResourcePackageRoute = () => {
  const params = resourcePackageRoute.useParams()
  return <ResourcePackagePage projectId={params.projectId} />
}
