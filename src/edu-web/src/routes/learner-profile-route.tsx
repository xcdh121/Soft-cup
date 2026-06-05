import { LearnerProfilePage } from '@/features/learner-profile/learner-profile-page'
import { learnerProfileRoute } from '@/routes/_config'

export const LearnerProfileRoute = () => {
  const params = learnerProfileRoute.useParams()
  return <LearnerProfilePage projectId={params.projectId} />
}
