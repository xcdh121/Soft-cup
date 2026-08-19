import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import { Option } from 'effect'
import {
  CheckCircle,
  ChevronDown,
  LoaderCircle,
  Send,
  Sparkles,
  XCircle,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { AiExplanationMessage } from '@/data-acess/quiz-ai-explanation'
import { Response } from '@/components/ai-elements/response'
import { Button } from '@/components/ui/button'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Textarea } from '@/components/ui/textarea'
import { streamQuizAiExplanationAtom } from '@/data-acess/quiz-ai-explanation'
import {
  currentQuestionAtom,
  getQuizCorrectOption,
  quizDetailStateAtom,
  setSelectedAnswerAtom,
} from '@/data-acess/quiz-detail-state'
import { cn } from '@/lib/utils'

type QuizQuestionCardProps = {
  quizId: string
  projectId: string
}

export const QuizQuestionCard = ({
  quizId,
  projectId,
}: QuizQuestionCardProps) => {
  const [aiOpen, setAiOpen] = useState(false)
  const [messages, setMessages] = useState<Array<AiExplanationMessage>>([])
  const [question, setQuestion] = useState('')
  const [modelName, setModelName] = useState('DeepSeek V4 Flash')
  const [aiError, setAiError] = useState<string | null>(null)
  const [streamStatus, setStreamStatus] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  const [explanationOpen, setExplanationOpen] = useState(false)
  const requestInFlight = useRef(false)
  const stateResult = useAtomValue(quizDetailStateAtom(quizId))
  const currentQuestionResult = useAtomValue(
    currentQuestionAtom(`${projectId}:${quizId}`),
  )
  const setSelectedAnswer = useAtomSet(setSelectedAnswerAtom, {
    mode: 'promise',
  })
  const streamExplanation = useAtomSet(streamQuizAiExplanationAtom, {
    mode: 'promise',
  })

  const state = Option.isSome(stateResult) ? stateResult.value : null
  const currentQuestion = Result.isSuccess(currentQuestionResult)
    ? currentQuestionResult.value
    : null

  useEffect(() => {
    setMessages([])
    setQuestion('')
    setAiError(null)
    setStreamStatus('')
    setAiOpen(false)
    setExplanationOpen(false)
  }, [currentQuestion?.id])

  if (!state || !currentQuestion) return null

  const selected = state.selectedByQuestionId[currentQuestion.id]
  const showResults =
    state.showResults || state.submittedByQuestionId[currentQuestion.id]
  const correctOption = getQuizCorrectOption(currentQuestion)
  const options = [
    { key: 'A' as const, label: currentQuestion.option_a },
    { key: 'B' as const, label: currentQuestion.option_b },
    { key: 'C' as const, label: currentQuestion.option_c },
    { key: 'D' as const, label: currentQuestion.option_d },
  ]

  const handleSelect = async (option: 'A' | 'B' | 'C' | 'D') => {
    if (showResults) return
    await setSelectedAnswer({ quizId, questionId: currentQuestion.id, option })
  }

  const answerClasses = (option: 'A' | 'B' | 'C' | 'D') => {
    if (!showResults) {
      return selected === option
        ? 'border-primary/20 bg-primary/[0.06]'
        : 'border-transparent bg-transparent hover:border-primary/15 hover:bg-primary/[0.035]'
    }
    if (correctOption === option) {
      return 'border-primary/15 bg-primary/[0.045]'
    }
    if (selected === option) {
      return 'border-destructive/20 bg-destructive/[0.05]'
    }
    return 'border-transparent bg-transparent text-muted-foreground'
  }

  const optionBadgeClasses = (option: 'A' | 'B' | 'C' | 'D') => {
    if (!showResults) {
      return selected === option
        ? 'border-primary bg-primary text-primary-foreground'
        : 'border-input bg-card text-muted-foreground'
    }
    if (correctOption === option) {
      return 'border-primary bg-primary text-primary-foreground'
    }
    if (selected === option) {
      return 'border-destructive bg-destructive text-destructive-foreground'
    }
    return 'border-input bg-card text-muted-foreground'
  }

  const runAi = async (userQuestion?: string) => {
    if (requestInFlight.current) return
    requestInFlight.current = true
    const history = messages.filter((message) => message.content.trim())
    const nextMessages: Array<AiExplanationMessage> = userQuestion
      ? [
          ...history,
          { role: 'user', content: userQuestion },
          { role: 'assistant', content: '' },
        ]
      : [...history, { role: 'assistant', content: '' }]

    setMessages(nextMessages)
    setQuestion('')
    setAiError(null)
    setStreamStatus('正在连接 DeepSeek…')
    setIsGenerating(true)
    try {
      await streamExplanation({
        projectId,
        quizId,
        questionId: currentQuestion.id,
        question: userQuestion,
        history,
        onModel: setModelName,
        onStatus: setStreamStatus,
        onDelta: (delta) => {
          setStreamStatus('')
          setMessages((current) => {
            const updated = [...current]
            const last = updated.at(-1)
            if (last?.role === 'assistant') {
              updated[updated.length - 1] = {
                ...last,
                content: last.content + delta,
              }
            }
            return updated
          })
        },
      })
    } catch (error) {
      setAiError(error instanceof Error ? error.message : 'AI 解析生成失败')
    } finally {
      requestInFlight.current = false
      setStreamStatus('')
      setIsGenerating(false)
    }
  }

  const openAi = () => {
    setAiOpen(true)
    if (messages.length === 0) void runAi()
  }

  const submitQuestion = () => {
    const value = question.trim()
    if (value) void runAi(value)
  }

  return (
    <div className="mx-auto w-full max-w-4xl px-5 py-7 sm:px-8 md:px-12 md:py-10">
      <div className="flex items-center gap-3 border-l-4 border-primary pl-4">
        <h2 className="text-xl font-semibold tracking-tight">
          {state.currentQuestionIndex + 1}. 单选题
        </h2>
      </div>

      <h3 className="mt-9 text-lg font-medium leading-8 md:text-xl">
        {currentQuestion.question_text}
      </h3>

      <div className="mt-7 grid gap-2">
        {options.map((option) => {
          const isCorrectOption = showResults && correctOption === option.key
          const isWrongSelection =
            showResults &&
            selected === option.key &&
            correctOption !== option.key

          return (
            <button
              key={option.key}
              type="button"
              onClick={() => handleSelect(option.key)}
              disabled={showResults}
              className={cn(
                'group flex w-full items-center gap-4 rounded-xl border px-3 py-3 text-left transition-colors sm:px-4',
                showResults ? 'cursor-default' : 'cursor-pointer',
                answerClasses(option.key),
              )}
            >
              <span className="relative shrink-0">
                <span
                  className={cn(
                    'flex size-10 items-center justify-center rounded-full border-2 text-lg font-medium transition-colors',
                    optionBadgeClasses(option.key),
                  )}
                >
                  {option.key}
                </span>
                {isCorrectOption ? (
                  <CheckCircle className="absolute -top-1.5 -right-1.5 size-5 fill-[#18a66a] text-white" />
                ) : isWrongSelection ? (
                  <XCircle className="absolute -top-1.5 -right-1.5 size-5 fill-destructive text-white" />
                ) : null}
              </span>
              <span className="min-w-0 text-base leading-7 md:text-lg">
                {option.label}
              </span>
            </button>
          )
        })}
      </div>

      {showResults ? (
        <section className="mt-8 rounded-xl border border-border/70 bg-muted/55 p-5 md:p-6">
          <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-start">
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-sm font-medium">
                {selected === correctOption ? (
                  <>
                    <CheckCircle className="size-5 text-[#15945f]" />
                    <span className="text-[#137e53]">回答正确</span>
                  </>
                ) : (
                  <>
                    <XCircle className="size-5 text-destructive" />
                    <span className="text-destructive">回答错误</span>
                  </>
                )}
              </div>
              <p className="text-sm md:text-base">
                <span className="text-muted-foreground">正确答案：</span>
                <span className="font-semibold text-primary">
                  {correctOption ?? currentQuestion.correct_option}
                </span>
              </p>
            </div>

            <Button
              type="button"
              variant="ghost"
              className="h-9 shrink-0 self-start rounded-full border border-primary/15 bg-primary/10 px-4 text-primary hover:bg-primary/15 hover:text-primary"
              onClick={openAi}
              disabled={isGenerating}
            >
              {isGenerating ? (
                <LoaderCircle className="size-4 animate-spin" />
              ) : (
                <Sparkles className="size-4" />
              )}
              AI 解析
            </Button>
          </div>

          {currentQuestion.explanation ? (
            <div className="mt-4 border-t border-border/70 pt-3">
              <button
                type="button"
                className="flex items-center gap-1.5 text-sm font-medium text-primary hover:text-primary/80"
                aria-expanded={explanationOpen}
                onClick={() => setExplanationOpen((open) => !open)}
              >
                查看解析
                <ChevronDown
                  className={cn(
                    'size-4 transition-transform',
                    explanationOpen && 'rotate-180',
                  )}
                />
              </button>
              {explanationOpen ? (
                <Response className="mt-3 text-sm leading-7 text-muted-foreground">
                  {currentQuestion.explanation}
                </Response>
              ) : null}
            </div>
          ) : null}
        </section>
      ) : null}

      <Sheet open={aiOpen} onOpenChange={setAiOpen}>
        <SheetContent className="flex w-full flex-col p-0 sm:max-w-xl">
          <SheetHeader className="border-b p-5">
            <SheetTitle className="flex items-center gap-2">
              <Sparkles className="size-5 text-[#5483B3]" />
              AI 本题解析
            </SheetTitle>
            <SheetDescription>
              由 {modelName} 流式生成，可继续针对本题提问。
            </SheetDescription>
          </SheetHeader>

          <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-5">
            <div className="rounded-xl border bg-muted/30 p-4 text-sm font-medium leading-6">
              {currentQuestion.question_text}
            </div>
            {messages.map((message, index) => (
              <div
                key={`${message.role}-${index}`}
                className={cn(
                  'rounded-2xl px-4 py-3 text-sm leading-7',
                  message.role === 'user'
                    ? 'ml-10 whitespace-pre-wrap bg-primary text-primary-foreground'
                    : 'mr-4 border bg-card',
                )}
              >
                {message.content ? (
                  message.role === 'assistant' ? (
                    <Response className="text-sm leading-7">
                      {message.content}
                    </Response>
                  ) : (
                    message.content
                  )
                ) : (
                  <span className="flex items-center gap-2 text-muted-foreground">
                    <LoaderCircle className="size-4 animate-spin" />
                    {streamStatus || '正在生成本题解析…'}
                  </span>
                )}
              </div>
            ))}
            {aiError && (
              <div className="rounded-xl border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">
                {aiError}
              </div>
            )}
          </div>

          <div className="border-t bg-background p-4">
            <div className="flex items-end gap-2">
              <Textarea
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault()
                    submitQuestion()
                  }
                }}
                placeholder="继续问这道题，例如：为什么 B 选项不对？"
                className="max-h-32 min-h-11 resize-none"
                disabled={isGenerating}
              />
              <Button
                size="icon"
                onClick={submitQuestion}
                disabled={isGenerating || !question.trim()}
              >
                {isGenerating ? (
                  <LoaderCircle className="size-4 animate-spin" />
                ) : (
                  <Send className="size-4" />
                )}
              </Button>
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              Enter 发送，Shift + Enter 换行
            </p>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  )
}
