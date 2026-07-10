import { ProgrammingPracticePage } from '@/features/programming-practice/programming-practice-page'
import { programmingPracticeRoute } from '@/routes/_config'

export const ProgrammingPracticeRoute = () => {
  const params = programmingPracticeRoute.useParams()
  return (
    <ProgrammingPracticePage
      projectId={params.projectId}
      resourceId={params.resourceId}
    />
  )
}
