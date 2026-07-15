import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import { ExternalLinkIcon, Loader2Icon, PlayCircleIcon } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { GeneratedResource } from '@/data-acess/resource-package'
import { env } from '@/env'
import { flashcardsAtom } from '@/data-acess/flashcard'
import { mindMapAtom, refreshMindMapAtom } from '@/data-acess/mind-map'
import { quizQuestionsAtom } from '@/data-acess/quiz'
import { NoteContent } from '@/features/note/components/note-content'
import { authClient } from '@/lib/auth-client'

type ResourceReference = {
  target_id: string
  target_type: 'note' | 'quiz' | 'flashcards' | 'mind_map'
}

type VideoRecommendation = {
  title: string
  url: string
  thumbnail_url?: string | null
  summary?: string | null
  source?: string | null
  published_at?: string | null
  duration?: string | null
}

type ProgrammingQuestion = {
  id: string
  title: string
  description: string
  examples: Array<{
    input: string
    output: string
    explanation?: string
  }>
  hints: Array<string>
  difficulty?: string
}

const resolveGeneratedFileUrl = (fileUrl: string) => {
  if (/^https?:\/\//i.test(fileUrl) || fileUrl.startsWith('blob:')) {
    return fileUrl
  }
  const baseUrl = (env.VITE_SERVER_URL ?? 'http://localhost:8000').replace(
    /\/$/,
    '',
  )
  return `${baseUrl}${fileUrl.startsWith('/') ? '' : '/'}${fileUrl}`
}

const GeneratedImagePreview = ({ resource }: { resource: GeneratedResource }) => {
  const fileUrl = resource.preview_url ?? resource.file_url
  const [imageUrl, setImageUrl] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (!fileUrl) {
      setFailed(true)
      return
    }
    const controller = new AbortController()
    let objectUrl: string | null = null
    setImageUrl(null)
    setFailed(false)

    void (async () => {
      try {
        const {
          data: { session },
        } = await authClient.auth.getSession()
        const headers: Record<string, string> = {}
        if (session?.access_token) {
          headers.Authorization = `Bearer ${session.access_token}`
        }
        const response = await fetch(resolveGeneratedFileUrl(fileUrl), {
          headers,
          signal: controller.signal,
        })
        if (!response.ok) throw new Error(`Image request failed: ${response.status}`)
        objectUrl = URL.createObjectURL(await response.blob())
        if (!controller.signal.aborted) setImageUrl(objectUrl)
      } catch (error) {
        if (!(error instanceof DOMException && error.name === 'AbortError')) {
          setFailed(true)
        }
      }
    })()

    return () => {
      controller.abort()
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [fileUrl])

  if (failed || !fileUrl) return <Empty label="图片预览暂时不可用。" />
  if (!imageUrl) return <Loading label="正在加载生成的图片..." />
  return (
    <a href={imageUrl} target="_blank" rel="noreferrer">
      <img
        src={imageUrl}
        alt={resource.title}
        className="max-h-[36rem] w-full rounded-xl border bg-muted object-contain"
      />
    </a>
  )
}

const getProgrammingQuestions = (
  resource: GeneratedResource,
): Array<ProgrammingQuestion> => {
  if (resource.resource_type !== 'programming_questions') return []
  const questions = resource.content_json?.questions
  if (!Array.isArray(questions)) return []

  return questions.flatMap((item, index) => {
    if (!item || typeof item !== 'object') return []
    const candidate = item as Record<string, unknown>
    const title = candidate.title
    const description = candidate.description
    if (typeof title !== 'string' || typeof description !== 'string') return []
    const examples = Array.isArray(candidate.examples)
      ? candidate.examples.flatMap((example) => {
          if (!example || typeof example !== 'object') return []
          const row = example as Record<string, unknown>
          return [
            {
              input: String(row.input ?? ''),
              output: String(row.output ?? ''),
              explanation:
                typeof row.explanation === 'string'
                  ? row.explanation
                  : undefined,
            },
          ]
        })
      : []
    const hints = Array.isArray(candidate.hints)
      ? candidate.hints.map(String)
      : []

    return [
      {
        id: String(candidate.id ?? `q${index + 1}`),
        title,
        description,
        examples,
        hints,
        difficulty:
          typeof candidate.difficulty === 'string'
            ? candidate.difficulty
            : undefined,
      },
    ]
  })
}

const ProgrammingQuestionsPreview = ({
  questions,
}: {
  questions: Array<ProgrammingQuestion>
}) => {
  if (questions.length === 0)
    return <Empty label="No coding problems generated yet." />

  return (
    <div className="space-y-3">
      {questions.slice(0, 5).map((question, index) => (
        <div
          key={question.id}
          className="rounded-lg border bg-background p-3 text-sm"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="font-medium">
              {index + 1}. {question.title}
            </div>
            {question.difficulty ? (
              <span className="rounded-full border px-2 py-0.5 text-xs text-muted-foreground">
                {question.difficulty}
              </span>
            ) : null}
          </div>
          <div className="mt-2 line-clamp-3 text-muted-foreground">
            {question.description}
          </div>
          {question.examples[0] ? (
            <div className="mt-3 grid gap-2 rounded-md bg-muted/50 p-2 text-xs sm:grid-cols-2">
              <div>
                <div className="font-medium">Input</div>
                <pre className="mt-1 whitespace-pre-wrap">
                  {question.examples[0].input}
                </pre>
              </div>
              <div>
                <div className="font-medium">Output</div>
                <pre className="mt-1 whitespace-pre-wrap">
                  {question.examples[0].output}
                </pre>
              </div>
            </div>
          ) : null}
        </div>
      ))}
    </div>
  )
}

const getVideoRecommendations = (
  resource: GeneratedResource,
): Array<VideoRecommendation> => {
  if (resource.resource_type !== 'video_recommendations') return []
  const videos = resource.content_json?.videos
  if (!Array.isArray(videos)) return []

  return videos.flatMap((item) => {
    if (!item || typeof item !== 'object') return []
    const candidate = item as Record<string, unknown>
    if (
      typeof candidate.url !== 'string' ||
      typeof candidate.title !== 'string'
    ) {
      return []
    }
    return [
      {
        title: candidate.title,
        url: candidate.url,
        thumbnail_url:
          typeof candidate.thumbnail_url === 'string'
            ? candidate.thumbnail_url
            : null,
        summary:
          typeof candidate.summary === 'string' ? candidate.summary : null,
        source: typeof candidate.source === 'string' ? candidate.source : null,
        published_at:
          typeof candidate.published_at === 'string'
            ? candidate.published_at
            : null,
        duration:
          typeof candidate.duration === 'string' ? candidate.duration : null,
      },
    ]
  })
}

const VideoRecommendationsPreview = ({
  videos,
}: {
  videos: Array<VideoRecommendation>
}) => {
  if (videos.length === 0) return <Empty label="暂未找到相关视频。" />

  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {videos.map((video, index) => (
        <a
          key={`${video.url}-${index}`}
          href={video.url}
          target="_blank"
          rel="noreferrer"
          className="group overflow-hidden rounded-xl border bg-background transition hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-sm"
        >
          <div className="relative aspect-video overflow-hidden bg-muted">
            {video.thumbnail_url ? (
              <img
                src={video.thumbnail_url}
                alt=""
                referrerPolicy="no-referrer"
                className="size-full object-cover transition group-hover:scale-[1.02]"
              />
            ) : (
              <div className="flex size-full items-center justify-center">
                <PlayCircleIcon className="size-10 text-muted-foreground" />
              </div>
            )}
            <div className="absolute inset-0 flex items-center justify-center bg-black/0 transition group-hover:bg-black/15">
              <PlayCircleIcon className="size-11 text-white opacity-0 drop-shadow transition group-hover:opacity-100" />
            </div>
            {video.duration ? (
              <span className="absolute bottom-2 right-2 rounded bg-black/70 px-1.5 py-0.5 text-xs text-white">
                {video.duration}
              </span>
            ) : null}
          </div>
          <div className="space-y-2 p-3">
            <div className="line-clamp-2 text-sm font-medium">
              {video.title}
            </div>
            {video.summary ? (
              <div className="line-clamp-2 text-xs text-muted-foreground">
                {video.summary}
              </div>
            ) : null}
            <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
              <span className="truncate">{video.source ?? '视频来源'}</span>
              <ExternalLinkIcon className="size-3.5 shrink-0" />
            </div>
          </div>
        </a>
      ))}
    </div>
  )
}

const getReference = (
  resource: GeneratedResource,
): ResourceReference | null => {
  const content = resource.content_json
  const targetId = content?.target_id
  const targetType = content?.target_type

  if (
    typeof targetId !== 'string' ||
    !['note', 'quiz', 'flashcards', 'mind_map'].includes(String(targetType))
  ) {
    return null
  }

  return {
    target_id: targetId,
    target_type: targetType as ResourceReference['target_type'],
  }
}

const Loading = ({ label }: { label: string }) => (
  <div className="flex items-center gap-2 text-sm text-muted-foreground">
    <Loader2Icon className="size-4 animate-spin" />
    <span>{label}</span>
  </div>
)

const Empty = ({ label }: { label: string }) => (
  <div className="text-sm text-muted-foreground">{label}</div>
)

const IncrementalQuizPreview = ({
  resource,
}: {
  resource: GeneratedResource
}) => {
  const questions = resource.content_json?.questions
  if (!Array.isArray(questions) || questions.length === 0) return null

  return (
    <div className="space-y-3">
      {resource.status === 'generating' ? (
        <Loading label={`已生成 ${questions.length} 道题，后续题目正在生成…`} />
      ) : null}
      {questions.slice(0, 5).flatMap((item, index) => {
        if (!item || typeof item !== 'object') return []
        const question = item as Record<string, unknown>
        if (typeof question.question_text !== 'string') return []
        return [
          <div
            key={`${String(question.question_text)}-${index}`}
            className="rounded-lg border bg-background p-3 text-sm"
          >
            <div className="font-medium">
              {index + 1}. {question.question_text}
            </div>
            <div className="mt-2 grid gap-1 text-muted-foreground sm:grid-cols-2">
              <span>A. {String(question.option_a ?? '')}</span>
              <span>B. {String(question.option_b ?? '')}</span>
              <span>C. {String(question.option_c ?? '')}</span>
              <span>D. {String(question.option_d ?? '')}</span>
            </div>
          </div>,
        ]
      })}
    </div>
  )
}

const IncrementalFlashcardsPreview = ({
  resource,
}: {
  resource: GeneratedResource
}) => {
  const flashcards = resource.content_json?.flashcards
  if (!Array.isArray(flashcards) || flashcards.length === 0) return null

  return (
    <div className="space-y-3">
      {resource.status === 'generating' ? (
        <Loading label={`已生成 ${flashcards.length} 张，后续闪卡正在生成…`} />
      ) : null}
      <div className="grid gap-3 sm:grid-cols-2">
        {flashcards.slice(0, 6).flatMap((item, index) => {
          if (!item || typeof item !== 'object') return []
          const card = item as Record<string, unknown>
          if (typeof card.question !== 'string') return []
          return [
            <div
              key={`${String(card.question)}-${index}`}
              className="rounded-lg border bg-background p-3 text-sm"
            >
              <div className="font-medium">{card.question}</div>
              <div className="mt-2 text-muted-foreground">
                {String(card.answer ?? '')}
              </div>
            </div>,
          ]
        })}
      </div>
    </div>
  )
}

const QuizPreview = ({
  projectId,
  quizId,
}: {
  projectId: string
  quizId: string
}) => {
  const result = useAtomValue(quizQuestionsAtom(`${projectId}:${quizId}`))
  if (result.waiting) return <Loading label="正在生成题目..." />
  if (!Result.isSuccess(result)) return <Empty label="题目暂时无法加载。" />
  if (result.value.length === 0)
    return <Loading label="题目正在生成，请稍候..." />

  return (
    <div className="space-y-3">
      {result.value.slice(0, 5).map((question, index) => (
        <div
          key={question.id}
          className="rounded-lg border bg-background p-3 text-sm"
        >
          <div className="font-medium">
            {index + 1}. {question.question_text}
          </div>
          <div className="mt-2 grid gap-1 text-muted-foreground sm:grid-cols-2">
            <span>A. {question.option_a}</span>
            <span>B. {question.option_b}</span>
            <span>C. {question.option_c}</span>
            <span>D. {question.option_d}</span>
          </div>
          <div className="mt-2 text-xs text-emerald-700">
            答案：{question.correct_option.toUpperCase()}
          </div>
        </div>
      ))}
    </div>
  )
}

const FlashcardsPreview = ({
  projectId,
  groupId,
}: {
  projectId: string
  groupId: string
}) => {
  const result = useAtomValue(flashcardsAtom(`${projectId}:${groupId}`))
  if (result.waiting) return <Loading label="正在生成闪卡..." />
  if (!Result.isSuccess(result)) return <Empty label="闪卡暂时无法加载。" />
  if (result.value.length === 0)
    return <Loading label="闪卡正在生成，请稍候..." />

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {result.value.slice(0, 6).map((card) => (
        <div
          key={card.id}
          className="rounded-lg border bg-background p-3 text-sm"
        >
          <div className="font-medium">{card.question}</div>
          <div className="mt-2 text-muted-foreground">{card.answer}</div>
        </div>
      ))}
    </div>
  )
}

const MindMapPreview = ({
  projectId,
  mindMapId,
}: {
  projectId: string
  mindMapId: string
}) => {
  const result = useAtomValue(mindMapAtom(`${projectId}:${mindMapId}`))
  const refresh = useAtomSet(refreshMindMapAtom, { mode: 'promise' })
  const nodeCount =
    Result.isSuccess(result) && Array.isArray(result.value.map_data.nodes)
      ? result.value.map_data.nodes.length
      : 0
  useEffect(() => {
    if (nodeCount > 0) return
    const id = window.setInterval(
      () => void refresh({ projectId, mindMapId }),
      3000,
    )
    return () => window.clearInterval(id)
  }, [mindMapId, nodeCount, projectId, refresh])
  if (result.waiting) return <Loading label="正在生成思维导图..." />
  if (!Result.isSuccess(result)) return <Empty label="思维导图暂时无法加载。" />
  const nodes = Array.isArray(result.value.map_data.nodes)
    ? (result.value.map_data.nodes as Array<Record<string, unknown>>)
    : []
  if (nodes.length === 0) return <Loading label="思维导图正在生成，请稍候..." />

  return (
    <div className="flex flex-wrap gap-2">
      {nodes.slice(0, 12).map((node, index) => (
        <span
          key={String(node.id ?? index)}
          className="rounded-full border bg-background px-3 py-1 text-sm"
        >
          {String(node.label ?? node.title ?? node.text ?? `节点 ${index + 1}`)}
        </span>
      ))}
    </div>
  )
}

export const ResourceResultPreview = ({
  projectId,
  resource,
}: {
  projectId: string
  resource: GeneratedResource
}) => {
  if (
    resource.resource_type === 'practice_set' &&
    Array.isArray(resource.content_json?.questions) &&
    resource.content_json.questions.length > 0
  ) {
    return <IncrementalQuizPreview resource={resource} />
  }

  if (
    resource.resource_type === 'flashcards' &&
    Array.isArray(resource.content_json?.flashcards) &&
    resource.content_json.flashcards.length > 0
  ) {
    return <IncrementalFlashcardsPreview resource={resource} />
  }

  if (resource.resource_type === 'programming_questions') {
    return (
      <ProgrammingQuestionsPreview
        questions={getProgrammingQuestions(resource)}
      />
    )
  }

  if (resource.resource_type === 'video_recommendations') {
    return (
      <VideoRecommendationsPreview videos={getVideoRecommendations(resource)} />
    )
  }

  if (resource.resource_type === 'image') {
    return <GeneratedImagePreview resource={resource} />
  }

  if (resource.content_text) {
    return (
      <div className="whitespace-pre-wrap text-sm">
        {resource.content_text.slice(0, 1200)}
        {resource.content_text.length > 1200 ? '...' : ''}
      </div>
    )
  }

  const reference = getReference(resource)
  if (!reference) {
    return resource.content_json ? (
      <Empty label="结构化结果已生成，请通过上方链接查看完整内容。" />
    ) : null
  }

  switch (reference.target_type) {
    case 'note':
      return <NoteContent projectId={projectId} noteId={reference.target_id} />
    case 'quiz':
      return <QuizPreview projectId={projectId} quizId={reference.target_id} />
    case 'flashcards':
      return (
        <FlashcardsPreview
          projectId={projectId}
          groupId={reference.target_id}
        />
      )
    case 'mind_map':
      return (
        <MindMapPreview projectId={projectId} mindMapId={reference.target_id} />
      )
  }
}
