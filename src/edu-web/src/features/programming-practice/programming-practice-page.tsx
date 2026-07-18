import { Result, useAtomValue } from '@effect-atom/atom-react'
import { Link } from '@tanstack/react-router'
import {
  ChevronLeft,
  ChevronRight,
  Lightbulb,
  Loader2,
  Play,
  Sparkles,
  Terminal,
  TriangleAlert,
} from 'lucide-react'
import { useState } from 'react'
import { Response } from '@/components/ai-elements/response'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { parseProgrammingQuestions } from '@/data-acess/learning-evaluation'
import { resourcePackagesAtom } from '@/data-acess/resource-package'
import { ProjectHeader } from '@/features/project/components/project-header'
import { cn } from '@/lib/utils'
import { authClient } from '@/lib/auth-client'

type ProgrammingGrade = {
  score: number
  passed: boolean
  verdict: 'accepted' | 'needs_improvement' | 'incorrect'
  summary: string
  strengths: Array<string>
  issues: Array<string>
  suggestions: Array<string>
  complexity_analysis: string | null
  grading_mode: 'ai'
  language?: ProgrammingLanguage
}

type ProgrammingRunResult = {
  language: string
  version: string
  stdout: string
  stderr: string
  output: string
  exit_code: number | null
  signal: string | null
}

const getProgrammingRunOutput = (result: ProgrammingRunResult): string => {
  if (result.output) return result.output
  if (result.signal) {
    return `程序被信号 ${result.signal} 终止，且没有产生输出。`
  }
  if (result.exit_code === 0) {
    return '程序运行完成（退出码 0），但没有产生任何标准输出。请确认已调用入口函数，并使用 print 或 cout 输出结果。'
  }
  if (result.exit_code !== null) {
    return `程序已结束（退出码 ${result.exit_code}），但没有产生输出。`
  }
  return '代码沙箱已返回运行结果，但程序没有产生输出。'
}

const serverUrl = import.meta.env.VITE_SERVER_URL ?? window.location.origin

const programmingLanguages = [
  { value: 'python', label: 'Python' },
  { value: 'cpp', label: 'C++' },
] as const

type ProgrammingLanguage = (typeof programmingLanguages)[number]['value']

const isProgrammingLanguage = (value: string): value is ProgrammingLanguage =>
  programmingLanguages.some((language) => language.value === value)

const getApiErrorMessage = (payload: unknown): string | null => {
  if (!payload || typeof payload !== 'object') return null
  if ('detail' in payload && typeof payload.detail === 'string') {
    return payload.detail
  }
  if ('message' in payload && typeof payload.message === 'string') {
    return payload.message
  }
  if (
    'error' in payload &&
    payload.error &&
    typeof payload.error === 'object'
  ) {
    const error = payload.error
    if ('message' in error && typeof error.message === 'string') {
      return error.message
    }
  }
  return null
}

const readStoredObject = (key: string): Record<string, string> => {
  if (typeof window === 'undefined') return {}
  try {
    const parsed = JSON.parse(window.localStorage.getItem(key) ?? '{}')
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? (parsed as Record<string, string>)
      : {}
  } catch {
    return {}
  }
}

const readStoredGrades = (key: string): Record<string, ProgrammingGrade> => {
  if (typeof window === 'undefined') return {}
  try {
    const parsed = JSON.parse(window.localStorage.getItem(key) ?? '{}')
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? (parsed as Record<string, ProgrammingGrade>)
      : {}
  } catch {
    return {}
  }
}

const GradeList = ({
  title,
  items,
  tone,
}: {
  title: string
  items: Array<string>
  tone: 'success' | 'danger' | 'primary'
}) => (
  <div className="rounded-xl bg-background/80 p-4">
    <div
      className={cn(
        'mb-2 text-sm font-semibold',
        tone === 'success' && 'text-emerald-700',
        tone === 'danger' && 'text-destructive',
        tone === 'primary' && 'text-primary',
      )}
    >
      {title}
    </div>
    {items.length ? (
      <ul className="space-y-2 text-sm text-muted-foreground">
        {items.map((item, index) => (
          <li key={`${item}-${index}`} className="flex gap-2 leading-6">
            <span aria-hidden>•</span>
            <Response className="min-w-0 flex-1 text-sm">{item}</Response>
          </li>
        ))}
      </ul>
    ) : (
      <p className="text-sm text-muted-foreground">暂无</p>
    )}
  </div>
)

export const ProgrammingPracticePage = ({
  projectId,
  resourceId,
}: {
  projectId: string
  resourceId: string
}) => {
  const packagesResult = useAtomValue(resourcePackagesAtom(projectId))
  const draftKey = `programming-drafts:${projectId}:${resourceId}`
  const gradeKey = `programming-grades:${projectId}:${resourceId}`
  const languageKey = `programming-languages:${projectId}:${resourceId}`
  const inputKey = `programming-inputs:${projectId}:${resourceId}`
  const [activeIndex, setActiveIndex] = useState(0)
  const [drafts, setDrafts] = useState<Record<string, string>>(() =>
    readStoredObject(draftKey),
  )
  const [grades, setGrades] = useState<Record<string, ProgrammingGrade>>(() =>
    readStoredGrades(gradeKey),
  )
  const [languages, setLanguages] = useState<Record<string, string>>(() =>
    readStoredObject(languageKey),
  )
  const [inputs, setInputs] = useState<Record<string, string>>(() =>
    readStoredObject(inputKey),
  )
  const [runResults, setRunResults] = useState<
    Partial<Record<string, ProgrammingRunResult>>
  >({})
  const [runErrors, setRunErrors] = useState<Partial<Record<string, string>>>(
    {},
  )
  const [runningDraftId, setRunningDraftId] = useState<string | null>(null)
  const [revealedSolutions, setRevealedSolutions] = useState<Array<string>>([])
  const [isGrading, setIsGrading] = useState(false)
  const [gradingError, setGradingError] = useState<string | null>(null)

  const content = Result.builder(packagesResult)
    .onInitialOrWaiting(() => (
      <div className="mx-auto max-w-5xl space-y-4">
        <Skeleton className="h-72 rounded-2xl" />
        <Skeleton className="h-[560px] rounded-2xl" />
      </div>
    ))
    .onFailure(() => (
      <Card className="border-destructive/40">
        <CardContent className="py-12 text-center text-sm text-muted-foreground">
          编程题加载失败，请稍后重试。
        </CardContent>
      </Card>
    ))
    .onSuccess((packages) => {
      const resource = packages
        .flatMap((resourcePackage) => resourcePackage.resources)
        .find(
          (candidate) =>
            candidate.id === resourceId &&
            candidate.resource_type === 'programming_questions',
        )

      if (!resource) {
        return (
          <Card>
            <CardContent className="py-12 text-center text-sm text-muted-foreground">
              未找到这组编程题。
            </CardContent>
          </Card>
        )
      }

      const questions = parseProgrammingQuestions(resource.content_json)
      if (questions.length === 0) {
        return (
          <Card>
            <CardContent className="py-12 text-center text-sm text-muted-foreground">
              这组编程题暂时没有可作答内容。
            </CardContent>
          </Card>
        )
      }

      const question = questions[Math.min(activeIndex, questions.length - 1)]
      const storedLanguage = languages[question.id] ?? 'python'
      const language = isProgrammingLanguage(storedLanguage)
        ? storedLanguage
        : 'python'
      const draftId = `${question.id}:${language}`
      const answer = Object.hasOwn(drafts, draftId)
        ? drafts[draftId]
        : language === 'python' && Object.hasOwn(drafts, question.id)
          ? drafts[question.id]
          : language === 'python'
            ? (question.starterCode ?? '')
            : ''
      const stdin = inputs[draftId] ?? ''
      const runResult = runResults[draftId]
      const runError = runErrors[draftId]
      const isRunning = runningDraftId === draftId
      const storedGrade = Object.hasOwn(grades, question.id)
        ? grades[question.id]
        : undefined
      const grade =
        storedGrade && (storedGrade.language ?? 'python') === language
          ? storedGrade
          : undefined
      const isSubmitted = Boolean(grade)
      const isSolutionRevealed = revealedSolutions.includes(question.id)
      const completion = Math.round(
        (Object.keys(grades).filter((id) =>
          questions.some((item) => item.id === id),
        ).length /
          questions.length) *
          100,
      )

      const updateAnswer = (value: string) => {
        const next = { ...drafts, [draftId]: value }
        setDrafts(next)
        window.localStorage.setItem(draftKey, JSON.stringify(next))
      }

      const updateLanguage = (value: string) => {
        if (!isProgrammingLanguage(value)) return
        const next = { ...languages, [question.id]: value }
        setLanguages(next)
        window.localStorage.setItem(languageKey, JSON.stringify(next))
      }

      const updateInput = (value: string) => {
        const next = { ...inputs, [draftId]: value }
        setInputs(next)
        window.localStorage.setItem(inputKey, JSON.stringify(next))
      }

      const runAnswer = async () => {
        const nextDrafts = { ...drafts, [draftId]: answer }
        setDrafts(nextDrafts)
        window.localStorage.setItem(draftKey, JSON.stringify(nextDrafts))
        setRunningDraftId(draftId)
        setRunErrors((current) => ({ ...current, [draftId]: '' }))

        try {
          const {
            data: { session },
          } = await authClient.auth.getSession()
          const response = await fetch(
            `${serverUrl}/api/v1/projects/${projectId}/generated-resources/${resourceId}/programming-run`,
            {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                ...(session?.access_token
                  ? { Authorization: `Bearer ${session.access_token}` }
                  : {}),
              },
              body: JSON.stringify({
                question_id: question.id,
                code: answer,
                stdin,
                language,
              }),
            },
          )
          const payload: unknown = await response.json().catch(() => null)
          if (!response.ok) {
            throw new Error(
              getApiErrorMessage(payload) ??
                `代码运行服务返回错误（HTTP ${response.status}）`,
            )
          }
          if (
            !payload ||
            typeof payload !== 'object' ||
            !('output' in payload)
          ) {
            throw new Error('代码运行服务返回了无法识别的数据。')
          }
          setRunResults((current) => ({
            ...current,
            [draftId]: payload as ProgrammingRunResult,
          }))
        } catch (error) {
          setRunErrors((current) => ({
            ...current,
            [draftId]:
              error instanceof TypeError
                ? `无法连接代码运行服务（${serverUrl}）。请确认后端已启动。`
                : error instanceof Error
                  ? error.message
                  : '代码运行失败，请稍后重试。',
          }))
        } finally {
          setRunningDraftId(null)
        }
      }

      const submitAnswer = async () => {
        const nextDrafts = { ...drafts, [draftId]: answer }
        setDrafts(nextDrafts)
        window.localStorage.setItem(draftKey, JSON.stringify(nextDrafts))
        setIsGrading(true)
        setGradingError(null)

        try {
          const {
            data: { session },
          } = await authClient.auth.getSession()
          const response = await fetch(
            `${serverUrl}/api/v1/projects/${projectId}/generated-resources/${resourceId}/programming-grade`,
            {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                ...(session?.access_token
                  ? { Authorization: `Bearer ${session.access_token}` }
                  : {}),
              },
              body: JSON.stringify({
                question_id: question.id,
                answer,
                language,
              }),
            },
          )
          const payload: unknown = await response.json().catch(() => null)
          if (!response.ok) {
            throw new Error(
              getApiErrorMessage(payload) ??
                `判题服务返回错误（HTTP ${response.status}）`,
            )
          }
          if (
            !payload ||
            typeof payload !== 'object' ||
            !('score' in payload)
          ) {
            throw new Error('判题服务返回了无法识别的数据，请稍后重试。')
          }

          const programmingGrade = {
            ...(payload as ProgrammingGrade),
            language,
          }
          const nextGrades = { ...grades, [question.id]: programmingGrade }
          setGrades(nextGrades)
          window.localStorage.setItem(gradeKey, JSON.stringify(nextGrades))
        } catch (error) {
          setGradingError(
            error instanceof TypeError
              ? `无法连接判题服务（${serverUrl}）。请确认后端已启动，并检查 VITE_SERVER_URL 与跨域配置。`
              : error instanceof Error
                ? error.message
                : 'AI 评分失败，请稍后重试。',
          )
        } finally {
          setIsGrading(false)
        }
      }

      return (
        <div className="mx-auto max-w-5xl space-y-4">
          <Card className="rounded-2xl">
            <CardHeader>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="text-xs text-muted-foreground">
                  第 {activeIndex + 1} 题 / 共 {questions.length} 题
                </div>
                <div className="flex min-w-48 items-center gap-3 text-xs text-muted-foreground">
                  <span className="shrink-0">完成 {completion}%</span>
                  <Progress value={completion} className="h-2" />
                </div>
              </div>
              <CardTitle className="text-xl">{question.title}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              <Response className="text-sm leading-7">
                {question.description}
              </Response>

              {question.inputFormat || question.outputFormat ? (
                <div className="grid gap-4 sm:grid-cols-2">
                  {question.inputFormat ? (
                    <div>
                      <h3 className="mb-2 text-sm font-semibold">输入格式</h3>
                      <Response className="text-sm text-muted-foreground">
                        {question.inputFormat}
                      </Response>
                    </div>
                  ) : null}
                  {question.outputFormat ? (
                    <div>
                      <h3 className="mb-2 text-sm font-semibold">输出格式</h3>
                      <Response className="text-sm text-muted-foreground">
                        {question.outputFormat}
                      </Response>
                    </div>
                  ) : null}
                </div>
              ) : null}

              {question.examples.length ? (
                <div>
                  <h3 className="mb-2 text-sm font-semibold">示例</h3>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {question.examples.map((example, index) => (
                      <div
                        key={index}
                        className="rounded-xl border bg-muted/30 p-3 text-xs"
                      >
                        <div className="font-medium">输入</div>
                        <pre className="mt-1 whitespace-pre-wrap">
                          {example.input}
                        </pre>
                        <div className="mt-3 font-medium">输出</div>
                        <pre className="mt-1 whitespace-pre-wrap">
                          {example.output}
                        </pre>
                        {example.explanation ? (
                          <Response className="mt-3 text-muted-foreground">
                            {example.explanation}
                          </Response>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              {question.hints.length ? (
                <div className="flex gap-2 rounded-xl border border-[#7DA0CA] bg-[#C1E8FF]/40 p-3 text-sm dark:border-[#5483B3] dark:bg-[#052659]/50">
                  <Lightbulb className="mt-0.5 size-4 shrink-0 text-[#5483B3]" />
                  <Response className="text-sm">{question.hints[0]}</Response>
                </div>
              ) : null}
            </CardContent>
          </Card>

          <Card className="rounded-2xl">
            <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3">
              <CardTitle className="text-base">编写答案</CardTitle>
              <div className="flex items-center gap-2">
                <label
                  htmlFor="programming-language"
                  className="text-sm text-muted-foreground"
                >
                  编程语言
                </label>
                <Select value={language} onValueChange={updateLanguage}>
                  <SelectTrigger
                    id="programming-language"
                    className="w-36 bg-background"
                    aria-label="选择编程语言"
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {programmingLanguages.map((item) => (
                      <SelectItem key={item.value} value={item.value}>
                        {item.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <Textarea
                value={answer}
                onChange={(event) => updateAnswer(event.target.value)}
                spellCheck={false}
                className="min-h-80 resize-y font-mono text-sm leading-6"
                placeholder="请在这里编写代码答案..."
              />
              <div className="grid gap-4 lg:grid-cols-2">
                <div className="space-y-2">
                  <label
                    htmlFor="programming-stdin"
                    className="text-sm font-semibold"
                  >
                    标准输入
                  </label>
                  <Textarea
                    id="programming-stdin"
                    value={stdin}
                    onChange={(event) => updateInput(event.target.value)}
                    spellCheck={false}
                    className="min-h-32 resize-y rounded-none font-mono text-sm"
                    placeholder="输入程序运行时需要读取的数据，例如：&#10;3 5"
                  />
                </div>
                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2 text-sm font-semibold">
                      <Terminal className="size-4" />
                      运行输出
                    </div>
                    {runResult ? (
                      <span className="text-xs text-muted-foreground">
                        退出码：{runResult.exit_code ?? '—'}
                      </span>
                    ) : null}
                  </div>
                  <pre
                    className={cn(
                      'min-h-32 overflow-auto border bg-slate-950 p-3 font-mono text-sm leading-6 text-slate-100',
                      runError && 'border-destructive/70 text-red-300',
                    )}
                    aria-live="polite"
                  >
                    {isRunning
                      ? '正在运行...'
                      : runError ||
                        (runResult
                          ? getProgrammingRunOutput(runResult)
                          : null) ||
                        '点击“运行代码”后在这里查看输出。'}
                  </pre>
                </div>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="text-sm text-muted-foreground">
                  {grade
                    ? `AI 已评分：${grade.score} 分`
                    : '提交后将由 AI 从正确性、复杂度和代码质量等方面评分。'}
                </div>
                <div className="flex gap-2">
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => void runAnswer()}
                    disabled={!answer.trim() || isRunning}
                  >
                    {isRunning ? (
                      <Loader2 className="mr-2 size-4 animate-spin" />
                    ) : (
                      <Play className="mr-2 size-4" />
                    )}
                    {isRunning ? '运行中' : '运行代码'}
                  </Button>
                  {question.referenceSolution ? (
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() =>
                        setRevealedSolutions((current) =>
                          current.includes(question.id)
                            ? current.filter((id) => id !== question.id)
                            : [...current, question.id],
                        )
                      }
                    >
                      {isSolutionRevealed ? '收起参考答案' : '查看参考答案'}
                    </Button>
                  ) : null}
                  <Button
                    type="button"
                    onClick={() => void submitAnswer()}
                    disabled={!answer.trim() || isGrading}
                  >
                    {isGrading ? (
                      <>
                        <Loader2 className="mr-2 size-4 animate-spin" />
                        AI 评分中
                      </>
                    ) : isSubmitted ? (
                      '重新提交并评分'
                    ) : (
                      '提交并由 AI 评分'
                    )}
                  </Button>
                </div>
              </div>

              {gradingError ? (
                <div className="flex gap-2 rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
                  <TriangleAlert className="mt-0.5 size-4 shrink-0" />
                  <span>{gradingError}</span>
                </div>
              ) : null}

              {grade ? (
                <div className="space-y-5 rounded-2xl border border-primary/20 bg-primary/5 p-5">
                  <div className="flex flex-wrap items-center justify-between gap-4">
                    <div className="flex items-center gap-3">
                      <div
                        className={cn(
                          'flex size-16 items-center justify-center rounded-full border-4 text-xl font-bold',
                          grade.passed
                            ? 'border-emerald-500/30 text-emerald-700'
                            : 'border-destructive/30 text-destructive',
                        )}
                      >
                        {grade.score}
                      </div>
                      <div>
                        <div className="flex items-center gap-2 font-semibold">
                          <Sparkles className="size-4 text-primary" />
                          AI 评分结果
                        </div>
                        <div className="mt-1 text-sm text-muted-foreground">
                          {grade.passed ? '已通过' : '暂未通过'} · 满分 100
                        </div>
                      </div>
                    </div>
                    <div className="w-full max-w-56">
                      <Progress value={grade.score} className="h-2" />
                    </div>
                  </div>

                  <Response className="text-sm leading-7">
                    {grade.summary}
                  </Response>

                  <div className="grid gap-4 lg:grid-cols-3">
                    <GradeList
                      title="做得好的地方"
                      items={grade.strengths}
                      tone="success"
                    />
                    <GradeList
                      title="存在的问题"
                      items={grade.issues}
                      tone="danger"
                    />
                    <GradeList
                      title="改进建议"
                      items={grade.suggestions}
                      tone="primary"
                    />
                  </div>

                  {grade.complexity_analysis ? (
                    <div className="rounded-xl bg-background/80 p-4 text-sm">
                      <div className="mb-1 font-semibold">复杂度分析</div>
                      <Response className="leading-6 text-muted-foreground">
                        {grade.complexity_analysis}
                      </Response>
                    </div>
                  ) : null}

                  <div className="flex justify-end border-t pt-4">
                    {activeIndex < questions.length - 1 ? (
                      <Button
                        type="button"
                        onClick={() =>
                          setActiveIndex((index) =>
                            Math.min(questions.length - 1, index + 1),
                          )
                        }
                      >
                        分析完成，继续下一题
                        <ChevronRight className="ml-2 size-4" />
                      </Button>
                    ) : (
                      <Button asChild>
                        <Link
                          to="/dashboard/p/$projectId/learning-evaluation/history"
                          params={{ projectId }}
                        >
                          查看历史错题分析
                        </Link>
                      </Button>
                    )}
                  </div>
                </div>
              ) : null}

              {isSolutionRevealed && question.referenceSolution ? (
                <div>
                  <h3 className="mb-2 text-sm font-semibold">参考答案</h3>
                  <pre className="overflow-x-auto rounded-xl bg-slate-950 p-4 text-xs leading-6 text-slate-100">
                    {question.referenceSolution}
                  </pre>
                </div>
              ) : null}
            </CardContent>
          </Card>

          <div className="flex justify-between">
            <Button
              variant="outline"
              disabled={activeIndex === 0}
              onClick={() => setActiveIndex((index) => Math.max(0, index - 1))}
            >
              <ChevronLeft className="size-4" />
              上一题
            </Button>
            <Button
              variant="outline"
              disabled={activeIndex >= questions.length - 1}
              onClick={() =>
                setActiveIndex((index) =>
                  Math.min(questions.length - 1, index + 1),
                )
              }
            >
              下一题
              <ChevronRight className="size-4" />
            </Button>
          </div>
        </div>
      )
    })
    .render()

  return (
    <div className="flex h-full max-h-screen flex-col">
      <ProjectHeader projectId={projectId} />
      <div className="min-h-0 flex-1 overflow-y-auto">
        <main className="container mx-auto max-w-7xl space-y-4 px-4 py-6">
          {content}
        </main>
      </div>
    </div>
  )
}
