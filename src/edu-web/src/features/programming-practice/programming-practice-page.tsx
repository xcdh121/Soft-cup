import { Result, useAtomValue } from '@effect-atom/atom-react'
import {
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Code2,
  Lightbulb,
} from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { parseProgrammingQuestions } from '@/data-acess/learning-evaluation'
import { resourcePackagesAtom } from '@/data-acess/resource-package'
import { ProjectHeader } from '@/features/project/components/project-header'
import { cn } from '@/lib/utils'

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

const readStoredList = (key: string): Array<string> => {
  if (typeof window === 'undefined') return []
  try {
    const parsed = JSON.parse(window.localStorage.getItem(key) ?? '[]')
    return Array.isArray(parsed) ? parsed.map(String) : []
  } catch {
    return []
  }
}

export const ProgrammingPracticePage = ({
  projectId,
  resourceId,
}: {
  projectId: string
  resourceId: string
}) => {
  const packagesResult = useAtomValue(resourcePackagesAtom(projectId))
  const draftKey = `programming-drafts:${projectId}:${resourceId}`
  const submittedKey = `programming-submitted:${projectId}:${resourceId}`
  const [activeIndex, setActiveIndex] = useState(0)
  const [drafts, setDrafts] = useState<Record<string, string>>(() =>
    readStoredObject(draftKey),
  )
  const [submittedIds, setSubmittedIds] = useState<Array<string>>(() =>
    readStoredList(submittedKey),
  )
  const [revealedSolutions, setRevealedSolutions] = useState<Array<string>>([])

  const content = Result.builder(packagesResult)
    .onInitialOrWaiting(() => (
      <div className="grid gap-4 lg:grid-cols-[240px_1fr]">
        <Skeleton className="h-96 rounded-2xl" />
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
      const answer = Object.hasOwn(drafts, question.id)
        ? drafts[question.id]
        : (question.starterCode ?? '')
      const isSubmitted = submittedIds.includes(question.id)
      const isSolutionRevealed = revealedSolutions.includes(question.id)
      const completion = Math.round(
        (submittedIds.filter((id) => questions.some((item) => item.id === id))
          .length /
          questions.length) *
          100,
      )

      const updateAnswer = (value: string) => {
        const next = { ...drafts, [question.id]: value }
        setDrafts(next)
        window.localStorage.setItem(draftKey, JSON.stringify(next))
      }

      const submitAnswer = () => {
        const nextDrafts = { ...drafts, [question.id]: answer }
        const nextSubmitted = submittedIds.includes(question.id)
          ? submittedIds
          : [...submittedIds, question.id]
        setDrafts(nextDrafts)
        setSubmittedIds(nextSubmitted)
        window.localStorage.setItem(draftKey, JSON.stringify(nextDrafts))
        window.localStorage.setItem(submittedKey, JSON.stringify(nextSubmitted))
      }

      return (
        <>
          <Card className="rounded-2xl">
            <CardContent className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="flex items-center gap-2 text-lg font-semibold">
                  <Code2 className="size-5 text-primary" />
                  {resource.title}
                </div>
                <p className="mt-1 text-sm text-muted-foreground">
                  本组共 {questions.length} 道题，答案会保存在当前浏览器中。
                </p>
              </div>
              <div className="w-full max-w-64">
                <div className="mb-2 flex justify-between text-xs text-muted-foreground">
                  <span>完成进度</span>
                  <span>{completion}%</span>
                </div>
                <Progress value={completion} />
              </div>
            </CardContent>
          </Card>

          <div className="grid gap-4 lg:grid-cols-[240px_minmax(0,1fr)]">
            <Card className="h-fit rounded-2xl">
              <CardHeader className="pb-3">
                <CardTitle className="text-base">题目列表</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {questions.map((item, index) => {
                  const submitted = submittedIds.includes(item.id)
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => setActiveIndex(index)}
                      className={cn(
                        'flex w-full items-center gap-3 rounded-xl border px-3 py-3 text-left text-sm transition-colors hover:bg-muted/60',
                        activeIndex === index && 'border-primary bg-primary/5',
                      )}
                    >
                      <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-semibold">
                        {submitted ? (
                          <CheckCircle2 className="size-4 text-emerald-600" />
                        ) : (
                          index + 1
                        )}
                      </span>
                      <span className="line-clamp-2">{item.title}</span>
                    </button>
                  )
                })}
              </CardContent>
            </Card>

            <div className="space-y-4">
              <Card className="rounded-2xl">
                <CardHeader>
                  <div className="text-xs text-muted-foreground">
                    第 {activeIndex + 1} 题 / 共 {questions.length} 题
                  </div>
                  <CardTitle className="text-xl">{question.title}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-5">
                  <p className="whitespace-pre-wrap text-sm leading-7">
                    {question.description}
                  </p>

                  {question.inputFormat || question.outputFormat ? (
                    <div className="grid gap-4 sm:grid-cols-2">
                      {question.inputFormat ? (
                        <div>
                          <h3 className="mb-2 text-sm font-semibold">
                            输入格式
                          </h3>
                          <p className="whitespace-pre-wrap text-sm text-muted-foreground">
                            {question.inputFormat}
                          </p>
                        </div>
                      ) : null}
                      {question.outputFormat ? (
                        <div>
                          <h3 className="mb-2 text-sm font-semibold">
                            输出格式
                          </h3>
                          <p className="whitespace-pre-wrap text-sm text-muted-foreground">
                            {question.outputFormat}
                          </p>
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
                              <p className="mt-3 text-muted-foreground">
                                {example.explanation}
                              </p>
                            ) : null}
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}

                  {question.hints.length ? (
                    <div className="flex gap-2 rounded-xl border border-amber-200 bg-amber-50/60 p-3 text-sm dark:border-amber-900 dark:bg-amber-950/20">
                      <Lightbulb className="mt-0.5 size-4 shrink-0 text-amber-600" />
                      <span>{question.hints[0]}</span>
                    </div>
                  ) : null}
                </CardContent>
              </Card>

              <Card className="rounded-2xl">
                <CardHeader>
                  <CardTitle className="text-base">编写答案</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <Textarea
                    value={answer}
                    onChange={(event) => updateAnswer(event.target.value)}
                    spellCheck={false}
                    className="min-h-80 resize-y font-mono text-sm leading-6"
                    placeholder="请在这里编写代码答案..."
                  />
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="text-sm text-muted-foreground">
                      {isSubmitted
                        ? '本题已提交，等待后续评阅。'
                        : '完成后提交本题。'}
                    </div>
                    <div className="flex gap-2">
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
                        onClick={submitAnswer}
                        disabled={!answer.trim()}
                      >
                        {isSubmitted ? '更新答案' : '提交本题'}
                      </Button>
                    </div>
                  </div>

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
                  onClick={() =>
                    setActiveIndex((index) => Math.max(0, index - 1))
                  }
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
          </div>
        </>
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
