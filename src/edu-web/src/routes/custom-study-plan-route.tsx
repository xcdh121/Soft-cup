import { CustomStudyPlanPage } from '@/features/study-plan/custom-study-plan-page'
import { customStudyPlanRoute } from '@/routes/_config'

export const CustomStudyPlanRoute = () => {
  const params = customStudyPlanRoute.useParams()
  return <CustomStudyPlanPage projectId={params.projectId} />
}
