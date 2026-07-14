import { ResourcePackagePage } from '@/features/resource-package/resource-package-page'
import { resourcePackageRoute } from '@/routes/_config'

export const ResourcePackageRoute = () => {
  const params = resourcePackageRoute.useParams()
  const search = resourcePackageRoute.useSearch()
  return (
    <ResourcePackagePage
      projectId={params.projectId}
      initialPackageId={search?.packageId}
    />
  )
}
