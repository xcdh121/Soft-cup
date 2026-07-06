import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import { Loader2Icon } from 'lucide-react'
import { useEffect } from 'react'
import type { GeneratedResource } from '@/data-acess/resource-package'
import { flashcardsAtom, refreshFlashcardsAtom } from '@/data-acess/flashcard'
import { mindMapAtom, refreshMindMapAtom } from '@/data-acess/mind-map'
import { quizQuestionsAtom, refreshQuizQuestionsAtom } from '@/data-acess/quiz'
import { NoteContent } from '@/features/note/components/note-content'

type ResourceReference = {
  target_id: string
  target_type: 'note' | 'quiz' | 'flashcards' | 'mind_map'
  topic?: string
  custom_instructions?: string
  stream_on_client?: boolean
}

const getReference = (resource: GeneratedResource): ResourceReference | null => {
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
    topic: typeof content?.topic === 'string' ? content.topic : undefined,
    custom_instructions:
      typeof content?.custom_instructions === 'string'
        ? content.custom_instructions
        : undefined,
    stream_on_client: content?.stream_on_client === true,
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

const QuizPreview = ({ projectId, quizId }: { projectId: string; quizId: string }) => {
  const result = useAtomValue(quizQuestionsAtom(`${projectId}:${quizId}`))
  const refresh = useAtomSet(refreshQuizQuestionsAtom, { mode: 'promise' })
  useEffect(() => {
    if (Result.isSuccess(result) && result.value.length > 0) return
    const id = window.setInterval(() => void refresh({ projectId, quizId }), 3000)
    return () => window.clearInterval(id)
  }, [projectId, quizId, refresh, result])
  if (result.waiting) return <Loading label="正在生成题目..." />
  if (!Result.isSuccess(result)) return <Empty label="题目暂时无法加载。" />
  if (result.value.length === 0) return <Loading label="题目正在生成，请稍候..." />

  return (
    <div className="space-y-3">
      {result.value.slice(0, 5).map((question, index) => (
        <div key={question.id} className="rounded-lg border bg-background p-3 text-sm">
          <div className="font-medium">{index + 1}. {question.question_text}</div>
          <div className="mt-2 grid gap-1 text-muted-foreground sm:grid-cols-2">
            <span>A. {question.option_a}</span><span>B. {question.option_b}</span>
            <span>C. {question.option_c}</span><span>D. {question.option_d}</span>
          </div>
          <div className="mt-2 text-xs text-emerald-700">答案：{question.correct_option.toUpperCase()}</div>
        </div>
      ))}
    </div>
  )
}

const FlashcardsPreview = ({ projectId, groupId }: { projectId: string; groupId: string }) => {
  const result = useAtomValue(flashcardsAtom(`${projectId}:${groupId}`))
  const refresh = useAtomSet(refreshFlashcardsAtom, { mode: 'promise' })
  useEffect(() => {
    if (Result.isSuccess(result) && result.value.length > 0) return
    const id = window.setInterval(
      () => void refresh({ projectId, flashcardGroupId: groupId }),
      3000,
    )
    return () => window.clearInterval(id)
  }, [groupId, projectId, refresh, result])
  if (result.waiting) return <Loading label="正在生成闪卡..." />
  if (!Result.isSuccess(result)) return <Empty label="闪卡暂时无法加载。" />
  if (result.value.length === 0) return <Loading label="闪卡正在生成，请稍候..." />

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {result.value.slice(0, 6).map((card) => (
        <div key={card.id} className="rounded-lg border bg-background p-3 text-sm">
          <div className="font-medium">{card.question}</div>
          <div className="mt-2 text-muted-foreground">{card.answer}</div>
        </div>
      ))}
    </div>
  )
}

const MindMapPreview = ({ projectId, mindMapId }: { projectId: string; mindMapId: string }) => {
  const result = useAtomValue(mindMapAtom(`${projectId}:${mindMapId}`))
  const refresh = useAtomSet(refreshMindMapAtom, { mode: 'promise' })
  const nodeCount = Result.isSuccess(result) && Array.isArray(result.value.map_data.nodes)
    ? result.value.map_data.nodes.length
    : 0
  useEffect(() => {
    if (nodeCount > 0) return
    const id = window.setInterval(() => void refresh({ projectId, mindMapId }), 3000)
    return () => window.clearInterval(id)
  }, [mindMapId, nodeCount, projectId, refresh])
  if (result.waiting) return <Loading label="正在生成思维导图..." />
  if (!Result.isSuccess(result)) return <Empty label="思维导图暂时无法加载。" />
  const nodes = Array.isArray(result.value.map_data.nodes)
    ? result.value.map_data.nodes as Array<Record<string, unknown>>
    : []
  if (nodes.length === 0) return <Loading label="思维导图正在生成，请稍候..." />

  return (
    <div className="flex flex-wrap gap-2">
      {nodes.slice(0, 12).map((node, index) => (
        <span key={String(node.id ?? index)} className="rounded-full border bg-background px-3 py-1 text-sm">
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
      return (
        <NoteContent
          projectId={projectId}
          noteId={reference.target_id}
          autoGenerate={reference.stream_on_client}
          topic={reference.topic}
          customInstructions={reference.custom_instructions}
        />
      )
    case 'quiz':
      return <QuizPreview projectId={projectId} quizId={reference.target_id} />
    case 'flashcards':
      return <FlashcardsPreview projectId={projectId} groupId={reference.target_id} />
    case 'mind_map':
      return <MindMapPreview projectId={projectId} mindMapId={reference.target_id} />
  }
}
