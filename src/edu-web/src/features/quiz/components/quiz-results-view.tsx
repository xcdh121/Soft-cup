import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import { useNavigate } from '@tanstack/react-router'
import { Option } from 'effect'
import {
  BrainCircuit,
  CheckCircle,
  ChevronDown,
  Loader2,
  RotateCcw,
  TriangleAlert,
  Trophy,
  Upload,
  X,
  XCircle,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import type { QuizQuestionDto } from '@/integrations/api/client'
import { Response } from '@/components/ai-elements/response'
import { Button } from '@/components/ui/button'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { Separator } from '@/components/ui/separator'
import { quizQuestionsAtom } from '@/data-acess/quiz'
import {
  getQuizCorrectOption,
  quizDetailStateAtom,
  quizStatsAtom,
  resetQuizAtom,
  submitPendingPracticeRecordsAtom,
} from '@/data-acess/quiz-detail-state'
import { authClient } from '@/lib/auth-client'

type QuizAnalysisMeta = {
  total: number
  correct: number
  accuracy: number
}

type QuizAnalysisStreamEvent =
  | { type: 'model'; model: string }
  | { type: 'meta'; total: number; correct: number; accuracy: number }
  | { type: 'status'; message: string }
  | { type: 'delta'; content: string }
  | { type: 'error'; message: string }
  | { type: 'done' }

const serverUrl = import.meta.env.VITE_SERVER_URL ?? window.location.origin

const getOptionText = (
  question: QuizQuestionDto,
  option: 'A' | 'B' | 'C' | 'D',
) => {
  if (option === 'A') return question.option_a
  if (option === 'B') return question.option_b
  if (option === 'C') return question.option_c
  return question.option_d
}

type CompletionHeaderProps = {
  total: number
}

const CompletionHeader = ({ total }: CompletionHeaderProps) => (
  <div className="text-center space-y-2">
    <div className="flex items-center justify-center gap-2 mb-2">
      <Trophy className="h-8 w-8 text-[#5483B3]" />
      <h2 className="text-3xl font-bold">测验已完成！</h2>
    </div>
    <p className="text-muted-foreground">
      你已完成全部 {total} 道题，完成状态无需等待 AI 分析
    </p>
  </div>
)

type StatCardProps = {
  icon?: React.ReactNode
  value: string | number
  label: string
  valueColor?: string
}

const StatCard = ({ icon, value, label, valueColor }: StatCardProps) => (
  <div className="flex flex-col items-center space-y-3 p-6 rounded-lg border bg-card">
    <div className={`flex items-center ${icon ? 'gap-2' : ''}`}>
      {icon}
      <div className={`text-4xl font-bold ${valueColor || ''}`}>{value}</div>
    </div>
    <div className="text-sm font-medium text-muted-foreground">{label}</div>
  </div>
)

const StatsGrid = ({
  quizId,
  projectId,
}: {
  quizId: string
  projectId: string
}) => {
  const statsResult = useAtomValue(quizStatsAtom(`${projectId}:${quizId}`))

  return Result.builder(statsResult)
    .onSuccess((stats) => {
      return (
        <div className="grid grid-cols-3 gap-6">
          <StatCard
            icon={<CheckCircle className="h-6 w-6 text-green-600" />}
            value={stats.correct}
            label="正确"
            valueColor="text-green-600"
          />
          <StatCard
            icon={<XCircle className="h-6 w-6 text-red-600" />}
            value={stats.incorrect}
            label="错误"
            valueColor="text-red-600"
          />
          <StatCard
            icon={null}
            value={`${stats.percentage}%`}
            label="正确率"
            valueColor="text-blue-600"
          />
        </div>
      )
    })
    .render()
}

type QuizQuestionListItemProps = {
  question: QuizQuestionDto
  index: number
  userAnswer?: 'A' | 'B' | 'C' | 'D'
  isCorrect: boolean
}

const QuizQuestionListItem = ({
  question,
  index,
  userAnswer,
  isCorrect,
}: QuizQuestionListItemProps) => {
  const correctOption = getQuizCorrectOption(question)

  return (
    <div className="border-b last:border-0 pb-3 last:pb-0 space-y-2">
      <div className="flex items-start gap-2">
        <span className="text-xs font-medium text-muted-foreground w-6 shrink-0">
          {index + 1}
        </span>
        <div className="flex-1 space-y-1.5 min-w-0">
          <p className="text-sm font-medium leading-relaxed">
            {question.question_text}
          </p>
          <div className="flex flex-wrap items-center gap-3 text-xs">
            <div className="flex items-center gap-1.5">
              <span className="text-muted-foreground">你的答案：</span>
              <span
                className={`font-medium ${
                  isCorrect ? 'text-green-600' : 'text-red-600'
                }`}
              >
                {userAnswer?.toUpperCase() || '未作答'}
                {userAnswer && ` - ${getOptionText(question, userAnswer)}`}
              </span>
            </div>
            {!isCorrect && (
              <>
                <span className="text-muted-foreground">•</span>
                <div className="flex items-center gap-1.5">
                  <span className="text-muted-foreground">正确答案：</span>
                  <span className="font-medium text-green-700">
                    {(correctOption ?? question.correct_option).toUpperCase()}
                    {correctOption
                      ? ` - ${getOptionText(question, correctOption)}`
                      : null}
                  </span>
                </div>
              </>
            )}
          </div>
          {question.explanation && (
            <div className="text-xs text-muted-foreground leading-relaxed">
              <Response className="text-xs">{question.explanation}</Response>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

type QuizReviewSectionProps = {
  title: string
  questions: Array<{
    question: QuizQuestionDto
    index: number
    userAnswer?: 'A' | 'B' | 'C' | 'D'
  }>
  icon: React.ReactNode
  isOpen: boolean
  onOpenChange: (open: boolean) => void
}

const QuizReviewSection = ({
  title,
  questions,
  icon,
  isOpen,
  onOpenChange,
}: QuizReviewSectionProps) => {
  if (questions.length === 0) return null

  return (
    <Collapsible open={isOpen} onOpenChange={onOpenChange}>
      <CollapsibleTrigger className="flex w-full items-center justify-between rounded-lg border bg-card p-4 hover:bg-accent transition-colors">
        <div className="flex items-center gap-2">
          {icon}
          <span className="font-semibold">
            {title} ({questions.length})
          </span>
        </div>
        <ChevronDown
          className={`h-4 w-4 transition-transform ${
            isOpen ? 'rotate-180' : ''
          }`}
        />
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-2 space-y-2">
        <div className="rounded-lg border bg-muted/50 p-4 space-y-3">
          {questions.map(({ question, index, userAnswer }) => {
            const isCorrect = userAnswer === getQuizCorrectOption(question)
            return (
              <QuizQuestionListItem
                key={question.id}
                question={question}
                index={index}
                userAnswer={userAnswer}
                isCorrect={isCorrect}
              />
            )
          })}
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}

type CompletionActionsProps = {
  quizId: string
  projectId: string
}

const CompletionActions = ({ quizId, projectId }: CompletionActionsProps) => {
  const navigate = useNavigate()

  const stateResult = useAtomValue(quizDetailStateAtom(quizId))
  const resetQuiz = useAtomSet(resetQuizAtom)
  const submitPendingPracticeRecords = useAtomSet(
    submitPendingPracticeRecordsAtom,
    {
      mode: 'promise',
    },
  )

  const hasPendingPracticeRecords =
    Option.isSome(stateResult) &&
    Object.keys(stateResult.value.pendingPracticeRecords).length > 0

  const handleSubmit = async () => {
    await submitPendingPracticeRecords({ quizId, projectId })
    navigate({
      to: '/dashboard/p/$projectId/learning-evaluation/practice',
      params: { projectId },
    })
  }

  const handleRetry = () => {
    resetQuiz({ quizId })
  }

  const handleClose = () => {
    navigate({
      to: '/dashboard/p/$projectId/learning-evaluation/practice',
      params: { projectId },
    })
  }

  return (
    <div className="flex flex-col gap-3">
      {hasPendingPracticeRecords && (
        <Button
          onClick={handleSubmit}
          variant="default"
          className="w-full flex items-center justify-center gap-2"
          size="lg"
        >
          <Upload className="h-4 w-4" />
          提交练习记录（
          {Object.keys(stateResult.value.pendingPracticeRecords).length}）
        </Button>
      )}

      <div className="flex gap-3">
        <Button
          onClick={handleRetry}
          variant="outline"
          className="flex-1 flex items-center justify-center gap-2"
          size="lg"
        >
          <RotateCcw className="h-4 w-4" />
          再试一次
        </Button>
        <Button
          onClick={handleClose}
          variant="outline"
          className="flex-1 flex items-center justify-center gap-2"
          size="lg"
        >
          <X className="h-4 w-4" />
          关闭
        </Button>
      </div>
    </div>
  )
}

const AiQuizAnalysis = ({
  projectId,
  quizId,
  answers,
}: {
  projectId: string
  quizId: string
  answers: Array<{ question_id: string; selected_option: string }>
}) => {
  const navigate = useNavigate()
  const [analysisText, setAnalysisText] = useState('')
  const [meta, setMeta] = useState<QuizAnalysisMeta | null>(null)
  const [modelName, setModelName] = useState('')
  const [streamStatus, setStreamStatus] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const loadAnalysis = useCallback(
    async (signal?: AbortSignal) => {
      setIsLoading(true)
      setError(null)
      setAnalysisText('')
      setMeta(null)
      setModelName('')
      setStreamStatus('正在连接 AI 分析服务…')
      try {
        const {
          data: { session },
        } = await authClient.auth.getSession()
        const response = await fetch(
          `${serverUrl}/api/v1/projects/${encodeURIComponent(projectId)}/quizzes/${encodeURIComponent(quizId)}/analysis/stream`,
          {
            method: 'POST',
            signal,
            headers: {
              'Content-Type': 'application/json',
              ...(session?.access_token
                ? { Authorization: `Bearer ${session.access_token}` }
                : {}),
            },
            body: JSON.stringify({ answers }),
          },
        )
        if (!response.ok) {
          const payload: unknown = await response.json().catch(() => null)
          const detail =
            payload &&
            typeof payload === 'object' &&
            'detail' in payload &&
            typeof payload.detail === 'string'
              ? payload.detail
              : 'AI 分析生成失败'
          throw new Error(detail)
        }
        if (!response.body) throw new Error('AI 分析服务未返回可读取的数据流')

        const decoder = new TextDecoder()
        const reader = response.body.getReader()
        let buffer = ''
        const streamState: { error?: string } = {}

        const processEvent = (block: string) => {
          const data = block
            .split(/\r?\n/)
            .filter((line) => line.startsWith('data:'))
            .map((line) => line.slice(5).trimStart())
            .join('\n')
          if (!data) return

          const event = JSON.parse(data) as QuizAnalysisStreamEvent
          if (event.type === 'model') setModelName(event.model)
          if (event.type === 'status') setStreamStatus(event.message)
          if (event.type === 'meta') {
            setMeta({
              total: event.total,
              correct: event.correct,
              accuracy: event.accuracy,
            })
          }
          if (event.type === 'delta') {
            setStreamStatus('')
            setAnalysisText((current) => current + event.content)
          }
          if (event.type === 'error') streamState.error = event.message
        }

        let streamEnded = false
        while (!streamEnded) {
          const { done, value } = await reader.read()
          if (done) {
            streamEnded = true
            continue
          }
          buffer += decoder.decode(value, { stream: true })
          const blocks = buffer.split(/\r?\n\r?\n/)
          buffer = blocks.pop() ?? ''
          blocks.forEach(processEvent)
        }
        buffer += decoder.decode()
        if (buffer.trim()) processEvent(buffer)
        if (streamState.error) throw new Error(streamState.error)
      } catch (requestError) {
        if (
          requestError instanceof DOMException &&
          requestError.name === 'AbortError'
        ) {
          return
        }
        setError(
          requestError instanceof Error
            ? requestError.message
            : 'AI 分析生成失败，请稍后重试。',
        )
      } finally {
        if (!signal?.aborted) {
          setIsLoading(false)
          setStreamStatus('')
        }
      }
    },
    [answers, projectId, quizId],
  )

  useEffect(() => {
    const controller = new AbortController()
    void loadAnalysis(controller.signal)
    return () => controller.abort()
  }, [loadAnalysis])

  if (isLoading && !analysisText) {
    return (
      <div className="flex items-center gap-3 rounded-2xl border border-primary/20 bg-primary/5 p-5">
        <Loader2 className="size-5 animate-spin text-primary" />
        <div>
          <div className="font-semibold">AI 正在分析本次作答</div>
          <div className="mt-1 text-sm text-muted-foreground">
            {streamStatus || '正在归纳掌握情况、薄弱点和下一步建议…'}
          </div>
        </div>
      </div>
    )
  }

  if (error && !analysisText) {
    return (
      <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-5">
        <div className="flex gap-2 text-sm text-destructive">
          <TriangleAlert className="mt-0.5 size-4 shrink-0" />
          <span>{error}</span>
        </div>
        <Button
          className="mt-4"
          variant="outline"
          onClick={() => void loadAnalysis()}
        >
          重新分析
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-5 rounded-2xl border border-primary/20 bg-primary/5 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 font-semibold">
            {isLoading ? (
              <Loader2 className="size-5 animate-spin text-primary" />
            ) : (
              <BrainCircuit className="size-5 text-primary" />
            )}
            {isLoading ? 'AI 正在流式分析本次作答' : 'AI 作答分析已完成'}
          </div>
          {modelName ? (
            <div className="mt-1 text-xs text-muted-foreground">
              模型：{modelName}
            </div>
          ) : null}
        </div>
        {meta ? (
          <span className="rounded-full bg-background px-3 py-1 text-sm font-medium">
            正确率 {meta.accuracy}%（{meta.correct}/{meta.total}）
          </span>
        ) : null}
      </div>
      <div className="min-h-28 rounded-xl bg-card p-4 text-card-foreground">
        <Response className="text-sm leading-7">{analysisText}</Response>
        {isLoading ? (
          <span
            className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-primary align-middle"
            aria-label="AI 正在输出"
          />
        ) : null}
      </div>
      {error ? (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
          <span className="flex gap-2">
            <TriangleAlert className="mt-0.5 size-4 shrink-0" />
            流式输出中断：{error}
          </span>
          <Button variant="outline" onClick={() => void loadAnalysis()}>
            重新分析
          </Button>
        </div>
      ) : null}
      <Button
        className="w-full"
        size="lg"
        onClick={() =>
          navigate({
            to: '/dashboard/p/$projectId/learning-evaluation/history',
            params: { projectId },
          })
        }
      >
        查看历史错题分析
      </Button>
    </div>
  )
}

type QuizResultsViewProps = {
  quizId: string
  projectId: string
}

export const QuizResultsView = ({
  quizId,
  projectId,
}: QuizResultsViewProps) => {
  const [showCorrect, setShowCorrect] = useState(false)
  const [showIncorrect, setShowIncorrect] = useState(false)

  const stateResult = useAtomValue(quizDetailStateAtom(quizId))
  const statsResult = useAtomValue(quizStatsAtom(`${projectId}:${quizId}`))
  const questionsResult = useAtomValue(
    quizQuestionsAtom(`${projectId}:${quizId}`),
  )

  const state = Option.isSome(stateResult) ? stateResult.value : null
  if (!state) return null

  const questions = Result.isSuccess(questionsResult)
    ? questionsResult.value
    : []

  const { correct, incorrect } = useMemo(() => {
    const correctQuestions: Array<{
      question: QuizQuestionDto
      index: number
      userAnswer?: 'A' | 'B' | 'C' | 'D'
    }> = []
    const incorrectQuestions: Array<{
      question: QuizQuestionDto
      index: number
      userAnswer?: 'A' | 'B' | 'C' | 'D'
    }> = []

    questions.forEach((q, idx) => {
      const userAnswer = state.selectedByQuestionId[q.id]
      const isCorrect = userAnswer === getQuizCorrectOption(q)

      const item = {
        question: q,
        index: idx,
        userAnswer,
      }

      if (isCorrect) {
        correctQuestions.push(item)
      } else {
        incorrectQuestions.push(item)
      }
    })

    return { correct: correctQuestions, incorrect: incorrectQuestions }
  }, [questions, state.selectedByQuestionId])

  const total = questions.length
  const analysisAnswers = useMemo(
    () =>
      questions.flatMap((question) => {
        const selected = state.selectedByQuestionId[question.id]
        return selected
          ? [{ question_id: question.id, selected_option: selected }]
          : []
      }),
    [questions, state.selectedByQuestionId],
  )

  return Result.builder(statsResult)
    .onSuccess(() => (
      <div className="flex flex-col flex-1 min-h-0 overflow-auto p-4">
        <div className="max-w-3xl mx-auto w-full space-y-8 py-8">
          <CompletionHeader total={total} />

          <StatsGrid quizId={quizId} projectId={projectId} />

          <Separator />

          <div className="space-y-4">
            <QuizReviewSection
              title="正确答案"
              questions={correct}
              icon={<CheckCircle className="h-5 w-5 text-green-600" />}
              isOpen={showCorrect}
              onOpenChange={setShowCorrect}
            />

            <QuizReviewSection
              title="错误答案"
              questions={incorrect}
              icon={<XCircle className="h-5 w-5 text-red-600" />}
              isOpen={showIncorrect}
              onOpenChange={setShowIncorrect}
            />
          </div>

          <Separator />

          <CompletionActions quizId={quizId} projectId={projectId} />

          <Separator />

          <AiQuizAnalysis
            projectId={projectId}
            quizId={quizId}
            answers={analysisAnswers}
          />
        </div>
      </div>
    ))
    .render()
}
