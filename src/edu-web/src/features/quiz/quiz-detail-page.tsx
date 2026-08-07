import { QuizDetail } from './components/quiz-detail'
import { QuizHeader } from './components/quiz-header'

type QuizDetailPageProps = {
  projectId: string
  quizId: string
}

export const QuizDetailPage = ({ projectId, quizId }: QuizDetailPageProps) => {
  return (
    <div className="flex h-full flex-col">
      <QuizHeader quizId={quizId} projectId={projectId} />

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <div className="mx-auto flex min-h-0 w-full flex-1 flex-col">
          <QuizDetail
            quizId={quizId}
            projectId={projectId}
            className="flex-1"
          />
        </div>
      </div>
    </div>
  )
}
