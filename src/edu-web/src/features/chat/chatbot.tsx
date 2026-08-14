import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import { Link } from '@tanstack/react-router'
import {
  ArrowRightIcon,
  CalendarDaysIcon,
  CopyIcon,
  GlobeIcon,
  Loader2Icon,
} from 'lucide-react'
import { useCallback, useRef, useState } from 'react'
import { toast } from 'sonner'
import { MultiAgentCallSequence } from './components/multi-agent-call-sequence'
import { ChatImageAttachment } from './components/chat-image-attachment'
import { ChatPdfAttachment } from './components/chat-pdf-attachment'
import { PdfUploadProgress } from './components/pdf-upload-progress'
import type { PdfUploadProgressValue } from './components/pdf-upload-progress'
import {
  shouldShowSourceReadingStatus,
  SourceReadingStatus,
} from './components/source-reading-status'
import type { PromptInputMessage } from '@/components/ai-elements/prompt-input'
import type {
  ChatMessageDto,
  FilePartDto,
  SourceDocumentPartDto,
  TextPartDto,
  ToolCallPartDto,
} from '@/integrations/api/client'
import type { PdfOcrStatus } from '@/lib/xfyun-pdf-ocr'
import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from '@/components/ai-elements/conversation'
import { Message, MessageContent } from '@/components/ai-elements/message'
import {
  PromptInput,
  PromptInputActionAddAttachments,
  PromptInputActionMenu,
  PromptInputActionMenuContent,
  PromptInputActionMenuTrigger,
  PromptInputAttachment,
  PromptInputAttachments,
  PromptInputBody,
  PromptInputButton,
  PromptInputFooter,
  PromptInputHeader,
  PromptInputSelect,
  PromptInputSelectContent,
  PromptInputSelectItem,
  PromptInputSelectTrigger,
  PromptInputSelectValue,
  PromptInputSpeechButton,
  PromptInputSubmit,
  PromptInputTextarea,
  PromptInputTools,
} from '@/components/ai-elements/prompt-input'
import { Response } from '@/components/ai-elements/response'
import {
  Source,
  Sources,
  SourcesContent,
  SourcesTrigger,
} from '@/components/ai-elements/sources'
import {
  Tool,
  ToolContent,
  ToolHeader,
  ToolInput,
  ToolOutput,
} from '@/components/ai-elements/tool'
import {
  chatAtom,
  chatRuntimeEventsAtom,
  chatStreamStatusAtom,
  streamMessageAtom,
} from '@/data-acess/chat'
import {
  getPdfOcrTask,
  getPdfOcrText,
  startPdfOcrTask,
  uploadChatPdfAttachment,
} from '@/lib/xfyun-pdf-ocr'

const generateId = () =>
  `${Date.now()}-${Math.random().toString(36).slice(2, 11)}`

const VISION_CONTEXT_PREFIX = '[图片理解上下文:'
const PDF_CONTEXT_PREFIX = '[PDF识别上下文:'
const MAX_PDF_WAIT_MS = 5 * 60 * 1000
const MAX_IMAGE_BYTES = 4 * 1024 * 1024

const isHiddenAttachmentContext = (text: string) =>
  text.startsWith(VISION_CONTEXT_PREFIX) || text.startsWith(PDF_CONTEXT_PREFIX)

const delay = (milliseconds: number) =>
  new Promise<void>((resolve) => window.setTimeout(resolve, milliseconds))

const getTutorStatusLabel = (status: string | null) => {
  if (status === 'generating') return '正在生成回答和学习资源，请稍候…'
  return '正在读取你的学习画像并检索相关信息…'
}

const TutorStatus = ({ status }: { status: string | null }) => (
  <div
    aria-live="polite"
    className="flex items-center gap-2 pb-2 text-sm text-muted-foreground"
  >
    <Loader2Icon className="size-4 animate-spin" />
    <span>{getTutorStatusLabel(status)}</span>
  </div>
)

const OCR_STATUS_PROGRESS: Partial<
  Record<
    PdfOcrStatus,
    Pick<PdfUploadProgressValue, 'label' | 'detail' | 'progress'>
  >
> = {
  CREATE: {
    label: '识别任务已创建',
    detail: '文档已提交，正在准备识别',
    progress: 30,
  },
  WAITING: {
    label: '等待识别',
    detail: '文档正在 OCR 服务中排队',
    progress: 42,
  },
  DOING: {
    label: '正在识别文档',
    detail: '正在提取文字、公式与版面结构',
    progress: 65,
  },
  FINISH: {
    label: '文档识别完成',
    detail: '正在读取识别结果',
    progress: 78,
  },
  ANY_FAILED: {
    label: '部分页面识别完成',
    detail: '正在读取可用的识别结果',
    progress: 78,
  },
}

const models = [
  {
    name: 'DeepSeek V4',
    value: 'deepseek-v4-pro',
  },
]

interface ChatbotProps {
  chatId: string
  projectId: string
}

const formatToolName = (name: string) => {
  if (name === 'study_plan_get_latest') return '读取个性化学习计划'
  return name
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

const normalizeToolInput = (toolInput: unknown): Record<string, unknown> => {
  if (!toolInput) return {}
  if (Array.isArray(toolInput)) {
    return toolInput.reduce<Record<string, unknown>>((acc, item) => {
      if (
        item &&
        typeof item === 'object' &&
        'key' in item &&
        typeof item.key === 'string'
      ) {
        acc[item.key] = 'value' in item ? item.value : null
      }
      return acc
    }, {})
  }
  if (typeof toolInput === 'object') {
    return toolInput as Record<string, unknown>
  }
  return { value: toolInput }
}

const parseToolOutput = (toolCall: ToolCallPartDto) => {
  if (toolCall.tool_state === 'output-error') {
    return {
      output: undefined,
      errorText:
        typeof toolCall.tool_output === 'string'
          ? toolCall.tool_output
          : JSON.stringify(toolCall.tool_output),
    }
  }

  if (
    typeof toolCall.tool_output === 'string' &&
    toolCall.tool_output.trim().startsWith('{')
  ) {
    try {
      return { output: JSON.parse(toolCall.tool_output), errorText: undefined }
    } catch {
      return { output: toolCall.tool_output, errorText: undefined }
    }
  }

  return { output: toolCall.tool_output, errorText: undefined }
}

type ResourcePackageToolResult = Record<string, unknown> & {
  packageId: string
}

const getResourcePackageResult = (
  toolName: string,
  output: unknown,
): ResourcePackageToolResult | null => {
  if (
    ![
      'resource_package_generate',
      'note_create',
      'note_create_scoped',
    ].includes(toolName) ||
    !output ||
    typeof output !== 'object'
  ) {
    return null
  }
  const value = output as Record<string, unknown>
  const packageId = value.package_id ?? value.resource_package_id
  return typeof packageId === 'string' ? { ...value, packageId } : null
}

type StudyPlanToolResult = Record<string, unknown> & {
  status: 'available' | 'not_found'
}

const getStudyPlanResult = (
  toolName: string,
  output: unknown,
): StudyPlanToolResult | null => {
  if (
    toolName !== 'study_plan_get_latest' ||
    !output ||
    typeof output !== 'object'
  ) {
    return null
  }
  const value = output as Record<string, unknown>
  return value.status === 'available' || value.status === 'not_found'
    ? (value as StudyPlanToolResult)
    : null
}

const toToolUiState = (
  state: string,
):
  | 'input-streaming'
  | 'input-available'
  | 'output-available'
  | 'output-error' => {
  if (
    state === 'input-streaming' ||
    state === 'input-available' ||
    state === 'output-available' ||
    state === 'output-error'
  ) {
    return state
  }
  return 'input-available'
}

const ResourcePackageLink = ({
  message,
  projectId,
}: {
  message: ChatMessageDto
  projectId: string
}) => {
  const resourcePackageResult = message.parts
    ?.filter((part): part is ToolCallPartDto => part.type === 'tool_call')
    .map((toolCall) => {
      const { output } = parseToolOutput(toolCall)
      return getResourcePackageResult(toolCall.tool_name, output)
    })
    .find((result) => result !== null)

  if (!resourcePackageResult) return null

  const isGenerating = resourcePackageResult.status === 'generating'
  const resourceCount =
    typeof resourcePackageResult.resource_count === 'number'
      ? resourcePackageResult.resource_count
      : undefined

  return (
    <div className="flex w-[95%] flex-wrap items-center gap-3 rounded-lg border bg-card p-3 text-card-foreground shadow-sm">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 text-sm font-medium">
          <span
            className={`size-2 rounded-full ${isGenerating ? 'animate-pulse bg-amber-500' : 'bg-emerald-500'}`}
          />
          {isGenerating ? '资源包正在后台生成' : '资源包已生成'}
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          {isGenerating
            ? `已创建生成任务${resourceCount ? `，共 ${resourceCount} 类资源` : ''}，可进入页面查看实时进度`
            : '可以进入资源包页面查看生成结果'}
        </p>
      </div>
      <Link
        to="/dashboard/p/$projectId/resource-packages"
        params={{ projectId }}
        search={{ packageId: resourcePackageResult.packageId }}
        className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
      >
        {isGenerating ? '查看生成进度' : '查看资源包'}
        <ArrowRightIcon className="size-4" />
      </Link>
    </div>
  )
}

const StudyPlanLink = ({
  message,
  projectId,
}: {
  message: ChatMessageDto
  projectId: string
}) => {
  const result = message.parts
    ?.filter((part): part is ToolCallPartDto => part.type === 'tool_call')
    .map((toolCall) => {
      const { output } = parseToolOutput(toolCall)
      return getStudyPlanResult(toolCall.tool_name, output)
    })
    .find((value) => value !== null)

  if (!result) return null

  const hasPlan = result.status === 'available'
  const learningPath =
    result.learning_path && typeof result.learning_path === 'object'
      ? (result.learning_path as Record<string, unknown>)
      : undefined
  const title =
    typeof learningPath?.title === 'string'
      ? learningPath.title
      : '个性化学习计划'

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border bg-muted/30 p-3">
      <CalendarDaysIcon className="size-5 text-primary" />
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium">
          {hasPlan ? title : '还没有个性化学习计划'}
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          {hasPlan
            ? '已读取“个性化学习”页面中的最新计划'
            : '前往学习计划页面生成第一份计划'}
        </p>
      </div>
      <Link
        to="/dashboard/p/$projectId/study-plan"
        params={{ projectId }}
        className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
      >
        {hasPlan ? '打开学习计划' : '去生成计划'}
        <ArrowRightIcon className="size-4" />
      </Link>
    </div>
  )
}

export const Chatbot: React.FC<ChatbotProps> = ({ chatId, projectId }) => {
  const [input, setInput] = useState('')
  const [model, setModel] = useState<string>(models[0].value)
  const [webSearch, setWebSearch] = useState(false)
  const [isPreparingAttachments, setIsPreparingAttachments] = useState(false)
  const [pdfUploadProgress, setPdfUploadProgress] =
    useState<PdfUploadProgressValue | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)

  const chatKey = `${projectId}:${chatId}`
  const chatResult = useAtomValue(chatAtom(chatKey))
  const streamStatus = useAtomValue(chatStreamStatusAtom(chatId))
  const runtimeEvents = useAtomValue(chatRuntimeEventsAtom(chatId))
  const streamMessage = useAtomSet(streamMessageAtom(chatId), {
    mode: 'promise',
  })

  const messages = Result.isSuccess(chatResult)
    ? (chatResult.value.messages ?? [])
    : []
  const isStreaming = streamStatus !== null
  const isBusy = isStreaming || isPreparingAttachments
  const latestMessage = messages[messages.length - 1]
  const streamingAssistantMessageId =
    isStreaming && latestMessage?.role === 'assistant' ? latestMessage.id : null
  const blobToDataUrl = useCallback(
    async (blobUrl: string): Promise<string> => {
      const response = await fetch(blobUrl)
      const blob = await response.blob()
      if (blob.size > MAX_IMAGE_BYTES) {
        throw new Error('图片大小不能超过 4MB')
      }
      return new Promise<string>((resolve, reject) => {
        const reader = new FileReader()
        reader.onloadend = () => resolve(reader.result as string)
        reader.onerror = reject
        reader.readAsDataURL(blob)
      })
    },
    [],
  )

  const handleSubmit = async (message: PromptInputMessage) => {
    const hasText = Boolean(message.text)
    const hasAttachments = Boolean(message.files.length)
    if (!(hasText || hasAttachments)) {
      return
    }

    const parts: Array<TextPartDto | FilePartDto> = []
    const hasPdf = message.files.some(
      (file) =>
        file.mediaType === 'application/pdf' ||
        file.filename?.toLowerCase().endsWith('.pdf'),
    )

    if (hasPdf) {
      setIsPreparingAttachments(true)
      const firstPdf = message.files.find(
        (file) =>
          file.mediaType === 'application/pdf' ||
          file.filename?.toLowerCase().endsWith('.pdf'),
      )
      setPdfUploadProgress({
        fileName: firstPdf?.filename || 'document.pdf',
        label: '正在读取文档',
        detail: '正在检查 PDF 文件内容',
        progress: 5,
        state: 'active',
      })
      toast.info('正在识别 PDF，完成后将自动发送给 AI 导师')
    } else {
      setPdfUploadProgress(null)
    }

    try {
      if (hasText) {
        parts.push({
          type: 'text',
          text_content: message.text,
          order: parts.length,
        })
      }

      const attachmentParts = await Promise.all(
        message.files.map(async (file) => {
          const isPdf =
            file.mediaType === 'application/pdf' ||
            file.filename?.toLowerCase().endsWith('.pdf')
          if (isPdf) {
            const fileName = file.filename || 'document.pdf'
            setPdfUploadProgress({
              fileName,
              label: '正在读取文档',
              detail: '正在检查 PDF 文件内容',
              progress: 5,
              state: 'active',
            })
            const response = await fetch(file.url)
            if (!response.ok) throw new Error('无法读取 PDF 附件')
            const blob = await response.blob()
            setPdfUploadProgress({
              fileName,
              label: '正在上传文档',
              detail: '正在将 PDF 提交给文档识别服务',
              progress: 16,
              state: 'active',
            })
            const pdfFile = new File([blob], fileName, {
              type: 'application/pdf',
            })
            const task = await startPdfOcrTask({
              projectId,
              file: pdfFile,
              exportFormat: 'markdown',
            })
            const initialStatus = OCR_STATUS_PROGRESS[task.status]
            if (initialStatus) {
              setPdfUploadProgress({
                fileName,
                ...initialStatus,
                state: 'active',
              })
            }

            let currentTask = task
            const deadline = Date.now() + MAX_PDF_WAIT_MS
            while (
              !['FINISH', 'FAILED', 'ANY_FAILED', 'STOP'].includes(
                currentTask.status,
              )
            ) {
              if (Date.now() >= deadline) {
                throw new Error('PDF 识别等待超时，请稍后重试')
              }
              await delay(5000)
              currentTask = await getPdfOcrTask({
                projectId,
                taskNo: currentTask.task_no,
              })
              const statusProgress = OCR_STATUS_PROGRESS[currentTask.status]
              if (statusProgress) {
                setPdfUploadProgress({
                  fileName,
                  ...statusProgress,
                  state: 'active',
                })
              }
            }
            if (!['FINISH', 'ANY_FAILED'].includes(currentTask.status)) {
              throw new Error(currentTask.tip || 'PDF 文档识别失败')
            }
            const recognized = await getPdfOcrText({
              projectId,
              taskNo: currentTask.task_no,
            })
            setPdfUploadProgress({
              fileName,
              label: '正在保存文档',
              detail: '识别完成，正在保存 PDF 到聊天记录',
              progress: 88,
              state: 'active',
            })
            const uploaded = await uploadChatPdfAttachment({
              projectId,
              chatId,
              file: pdfFile,
            })
            setPdfUploadProgress({
              fileName,
              label: '正在发送给导师',
              detail: '文档与识别内容已准备完成',
              progress: 96,
              state: 'active',
            })
            return [
              {
                type: 'file' as const,
                file_name: uploaded.file_name,
                file_type: uploaded.file_type,
                file_url: uploaded.file_url,
                order: 0,
              },
              {
                type: 'text' as const,
                text_content: `${PDF_CONTEXT_PREFIX}${uploaded.file_name}]\n${recognized.content_text}`,
                order: 0,
              },
            ]
          }

          if (
            file.url &&
            !file.url.startsWith('blob:') &&
            !file.url.startsWith('data:')
          ) {
            return [
              {
                type: 'file' as const,
                file_name: file.filename || 'file',
                file_type: file.mediaType,
                file_url: file.url,
                order: 0,
              },
            ]
          }

          let dataUrl = file.url
          if (file.url.startsWith('blob:')) {
            dataUrl = await blobToDataUrl(file.url)
          }

          if (!dataUrl || !dataUrl.startsWith('data:')) {
            throw new Error('Invalid file URL')
          }

          return [
            {
              type: 'file' as const,
              file_name: file.filename || 'file',
              file_type: file.mediaType,
              file_url: dataUrl,
              order: 0,
            },
          ]
        }),
      )

      const attachmentOffset = parts.length
      parts.push(
        ...attachmentParts.flat().map((part, index) => ({
          ...part,
          order: attachmentOffset + index,
        })),
      )

      const userMessage: ChatMessageDto = {
        id: generateId(),
        chat_id: chatId,
        role: 'user',
        created_at: new Date().toISOString(),
        parts,
      }

      streamMessage({
        message: userMessage,
        projectId,
        chatId,
      })

      setInput('')
      if (hasPdf) {
        setPdfUploadProgress((current) => ({
          fileName: current?.fileName || 'document.pdf',
          label: '文档上传完成',
          detail: 'PDF 已识别并发送给 AI 导师',
          progress: 100,
          state: 'success',
        }))
        toast.success('PDF 识别完成，已发送给 AI 导师')
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : '附件处理失败'
      if (hasPdf) {
        setPdfUploadProgress((current) => ({
          fileName: current?.fileName || 'document.pdf',
          label: '文档处理失败',
          detail: errorMessage,
          progress: current?.progress || 0,
          state: 'error',
        }))
      }
      toast.error(errorMessage)
      throw error
    } finally {
      setIsPreparingAttachments(false)
    }
  }

  const handleCopy = useCallback((text: string) => {
    navigator.clipboard.writeText(text)
  }, [])

  return (
    <div className="grid size-full min-h-0 grid-cols-1 overflow-hidden xl:grid-cols-[minmax(0,1fr)_360px]">
      <div className="min-h-0 min-w-0 overflow-hidden border-r">
        <div className="mx-auto flex h-full min-h-0 max-w-4xl flex-col px-4 lg:px-6">
          <Conversation className="min-h-0">
            <ConversationContent>
              {messages.map((message: ChatMessageDto) => (
                <div key={message.id} className="flex flex-col gap-2">
                  {message.role === 'user' &&
                    message.parts &&
                    message.parts.filter((part) => part.type === 'file')
                      .length > 0 && (
                      <Message from="user">
                        <MessageContent>
                          <div className="flex flex-col gap-2">
                            {message.parts
                              .filter(
                                (part): part is FilePartDto =>
                                  part.type === 'file',
                              )
                              .map((part: FilePartDto, index: number) => (
                                <div key={`${message.id}-file-${index}`}>
                                  {part.file_type.startsWith('image/') ? (
                                    <ChatImageAttachment file={part} />
                                  ) : part.file_type === 'application/pdf' ? (
                                    <ChatPdfAttachment file={part} />
                                  ) : (
                                    <div className="flex items-center gap-2 rounded bg-muted p-2">
                                      <span className="text-sm">
                                        {part.file_name}
                                      </span>
                                      {part.file_url && (
                                        <a
                                          href={part.file_url}
                                          target="_blank"
                                          rel="noopener noreferrer"
                                          className="text-xs text-primary hover:underline"
                                        >
                                          View
                                        </a>
                                      )}
                                    </div>
                                  )}
                                </div>
                              ))}
                          </div>
                        </MessageContent>
                      </Message>
                    )}

                  {message.parts &&
                    (() => {
                      const sourceDocuments = Array.from(
                        new Map(
                          message.parts
                            .filter(
                              (part): part is SourceDocumentPartDto =>
                                part.type === 'source-document',
                            )
                            .map((source) => [
                              String(
                                source.provider_metadata?.document_id ??
                                  source.source_id,
                              ),
                              source,
                            ]),
                        ).values(),
                      ).slice(0, 5)

                      return sourceDocuments.length > 0 ? (
                        <Sources key={`${message.id}-sources`}>
                          <SourcesTrigger count={sourceDocuments.length} />
                          <SourcesContent>
                            {sourceDocuments.map((sourceDoc, index) => {
                              const documentUrl = sourceDoc.provider_metadata
                                ?.document_id
                                ? `/dashboard/p/${projectId}/d/${sourceDoc.provider_metadata.document_id}`
                                : `#${sourceDoc.source_id}`

                              return (
                                <Source
                                  key={`${message.id}-source-${index}`}
                                  href={documentUrl}
                                  title={
                                    sourceDoc.title ||
                                    sourceDoc.filename ||
                                    'Document'
                                  }
                                />
                              )
                            })}
                          </SourcesContent>
                        </Sources>
                      ) : null
                    })()}

                  {shouldShowSourceReadingStatus(
                    message,
                    streamingAssistantMessageId,
                  ) && (
                    <Message from="assistant">
                      <MessageContent>
                        <SourceReadingStatus />
                      </MessageContent>
                    </Message>
                  )}

                  {message.parts &&
                    message.parts
                      .filter(
                        (part) =>
                          part.type !== 'source-document' &&
                          !(
                            part.type === 'text' &&
                            isHiddenAttachmentContext(part.text_content)
                          ),
                      )
                      .map((part, index: number, visibleParts) => {
                        switch (part.type) {
                          case 'text':
                            return (
                              <Message
                                key={`${message.id}-${index}`}
                                from={
                                  message.role as
                                    | 'user'
                                    | 'assistant'
                                    | 'system'
                                }
                              >
                                <MessageContent>
                                  {message.id === streamingAssistantMessageId &&
                                    index ===
                                      visibleParts.findIndex(
                                        (visiblePart) =>
                                          visiblePart.type === 'text',
                                      ) && (
                                      <TutorStatus status={streamStatus} />
                                    )}
                                  <Response
                                    className={
                                      message.role === 'user'
                                        ? 'prose-invert [&_a]:text-primary-foreground [&_blockquote]:border-primary-foreground/60 [&_code]:bg-white/15 [&_pre]:bg-white/10'
                                        : undefined
                                    }
                                  >
                                    {part.text_content}
                                  </Response>
                                </MessageContent>
                                {message.role === 'assistant' &&
                                  index ===
                                    (message.parts?.length || 0) - 1 && (
                                    <div className="mt-2 flex gap-2">
                                      <button
                                        onClick={() =>
                                          handleCopy(part.text_content)
                                        }
                                        className="rounded p-1 hover:bg-muted"
                                        title="Copy"
                                      >
                                        <CopyIcon className="size-3" />
                                      </button>
                                    </div>
                                  )}
                              </Message>
                            )
                          case 'file':
                            return null
                          case 'tool_call': {
                            const toolCall = part
                            const normalizedInput = normalizeToolInput(
                              toolCall.tool_input,
                            )
                            const { output, errorText } =
                              parseToolOutput(toolCall)
                            const toolResourcePackageResult =
                              getResourcePackageResult(
                                toolCall.tool_name,
                                output,
                              )

                            return (
                              <Tool
                                key={`${message.id}-part-${index}`}
                                defaultOpen={
                                  toolCall.tool_name ===
                                  'resource_package_generate'
                                    ? false
                                    : toolCall.tool_state === 'output-error' ||
                                      toolResourcePackageResult !== null
                                }
                              >
                                <ToolHeader
                                  title={formatToolName(toolCall.tool_name)}
                                  type={`tool-${toolCall.tool_name}`}
                                  state={toToolUiState(toolCall.tool_state)}
                                />
                                <ToolContent>
                                  {Object.keys(normalizedInput).length > 0 && (
                                    <ToolInput input={normalizedInput} />
                                  )}
                                  {(output || errorText) && (
                                    <ToolOutput
                                      output={output}
                                      errorText={errorText}
                                    />
                                  )}
                                </ToolContent>
                              </Tool>
                            )
                          }
                          default:
                            return null
                        }
                      })}

                  <ResourcePackageLink
                    message={message}
                    projectId={projectId}
                  />
                  <StudyPlanLink message={message} projectId={projectId} />
                </div>
              ))}
              {isStreaming && !streamingAssistantMessageId && (
                <Message from="assistant">
                  <MessageContent>
                    <TutorStatus status={streamStatus} />
                  </MessageContent>
                </Message>
              )}
            </ConversationContent>
            <ConversationScrollButton />
          </Conversation>

          <PromptInput
            onSubmit={handleSubmit}
            className="mt-4 shrink-0"
            accept=".pdf,application/pdf,image/jpeg,image/png"
            convertAttachmentsToDataUrls={false}
            globalDrop
            maxFileSize={100 * 1024 * 1024}
            multiple
            onError={(error) => toast.error(error.message)}
          >
            <PromptInputHeader>
              {pdfUploadProgress && (
                <PdfUploadProgress value={pdfUploadProgress} />
              )}
              <PromptInputAttachments>
                {(attachment) => <PromptInputAttachment data={attachment} />}
              </PromptInputAttachments>
            </PromptInputHeader>
            <PromptInputBody>
              <PromptInputTextarea
                onChange={(event) => setInput(event.target.value)}
                ref={textareaRef}
                value={input}
              />
            </PromptInputBody>
            <PromptInputFooter>
              <PromptInputTools>
                <PromptInputActionMenu>
                  <PromptInputActionMenuTrigger />
                  <PromptInputActionMenuContent>
                    <PromptInputActionAddAttachments />
                  </PromptInputActionMenuContent>
                </PromptInputActionMenu>
                <PromptInputButton
                  variant={webSearch ? 'default' : 'ghost'}
                  onClick={() => setWebSearch(!webSearch)}
                >
                  <GlobeIcon size={16} />
                  <span>Search</span>
                </PromptInputButton>
                <PromptInputSpeechButton
                  aria-label="中文语音输入"
                  onTranscriptionChange={setInput}
                  textareaRef={textareaRef}
                  value={input}
                />
                <PromptInputSelect
                  onValueChange={(value) => {
                    setModel(value)
                  }}
                  value={model}
                >
                  <PromptInputSelectTrigger>
                    <PromptInputSelectValue />
                  </PromptInputSelectTrigger>
                  <PromptInputSelectContent>
                    {models.map((item) => (
                      <PromptInputSelectItem
                        key={item.value}
                        value={item.value}
                      >
                        {item.name}
                      </PromptInputSelectItem>
                    ))}
                  </PromptInputSelectContent>
                </PromptInputSelect>
              </PromptInputTools>
              <PromptInputSubmit
                disabled={isBusy}
                status={isBusy ? 'streaming' : 'ready'}
              />
            </PromptInputFooter>
          </PromptInput>
        </div>
      </div>

      <MultiAgentCallSequence isRunning={isStreaming} events={runtimeEvents} />
    </div>
  )
}
