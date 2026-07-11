import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import { Option } from 'effect'
import {
  CheckCircle,
  LoaderCircle,
  Send,
  Sparkles,
  XCircle,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { AiExplanationMessage } from '@/data-acess/quiz-ai-explanation'
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
  const [modelName, setModelName] = useState('DeepSeek')
  const [aiError, setAiError] = useState<string | null>(null)
  const [streamStatus, setStreamStatus] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
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
  }, [currentQuestion?.id])

  if (!state || !currentQuestion) return null

  const selected = state.selectedByQuestionId[currentQuestion.id]
  const showResults = state.showResults
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
        ? 'bg-primary/10 border-primary'
        : 'bg-card border-border'
    }
    if (currentQuestion.correct_option === option) {
      return 'bg-green-50 border-green-500 text-green-900'
    }
    if (selected === option) return 'bg-red-50 border-red-500 text-red-900'
    return 'bg-muted/50 border-border'
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
    <div className="flex flex-1 items-center justify-center">
      <div className="flex w-full max-w-4xl items-start gap-3">
        <div className="min-w-0 flex-1 rounded-xl border bg-card p-12 shadow-lg">
          <div className="space-y-10">
            <div>
              <h3 className="mb-6 text-lg font-medium leading-relaxed">
                {currentQuestion.question_text}
              </h3>
              {showResults && (
                <div className="mb-4 flex items-center gap-2">
                  {selected === currentQuestion.correct_option ? (
                    <>
                      <CheckCircle className="size-5 shrink-0 text-green-600" />
                      <span className="text-sm font-medium text-green-600">
                        正确
                      </span>
                    </>
                  ) : (
                    <>
                      <XCircle className="size-5 shrink-0 text-red-600" />
                      <span className="text-sm font-medium text-red-600">
                        错误
                      </span>
                    </>
                  )}
                </div>
              )}
            </div>

            <div className="grid gap-3">
              {options.map((option) => (
                <button
                  key={option.key}
                  type="button"
                  onClick={() => handleSelect(option.key)}
                  disabled={showResults}
                  className={cn(
                    'rounded-lg border p-4 text-left transition-all',
                    showResults ? 'cursor-default' : 'hover:shadow-md',
                    answerClasses(option.key),
                  )}
                >
                  <div className="flex gap-3">
                    <span className="shrink-0 font-semibold">
                      {option.key}.
                    </span>
                    <span className="leading-relaxed">{option.label}</span>
                  </div>
                </button>
              ))}
            </div>

            {showResults && (
              <div className="space-y-2 border-t pt-4 text-sm">
                <span className="text-muted-foreground">正确答案：</span>
                <span className="font-semibold text-green-700">
                  {currentQuestion.correct_option}.{' '}
                  {
                    options.find(
                      (item) => item.key === currentQuestion.correct_option,
                    )?.label
                  }
                </span>
                {currentQuestion.explanation && (
                  <div className="leading-relaxed text-muted-foreground">
                    <span className="font-medium">解析：</span>
                    {currentQuestion.explanation}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        <Button
          type="button"
          variant="outline"
          className="h-auto shrink-0 flex-col gap-1.5 px-3 py-3 text-xs"
          onClick={openAi}
          disabled={isGenerating}
        >
          <Sparkles className="size-5 text-[#5483B3]" />
          AI 解析
        </Button>
      </div>

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
                  'whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-7',
                  message.role === 'user'
                    ? 'ml-10 bg-primary text-primary-foreground'
                    : 'mr-4 border bg-card',
                )}
              >
                {message.content || (
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
