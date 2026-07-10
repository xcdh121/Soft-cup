import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from '@/components/ai-elements/conversation'
import { Loader } from '@/components/ai-elements/loader'
import { Message, MessageContent } from '@/components/ai-elements/message'
import type { PromptInputMessage } from '@/components/ai-elements/prompt-input'
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
import { Badge } from '@/components/ui/badge'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import {
  chatAtom,
  chatStreamStatusAtom,
  streamMessageAtom,
} from '@/data-acess/chat'
import type {
  ChatMessageDto,
  FilePartDto,
  SourceDocumentPartDto,
  TextPartDto,
  ToolCallPartDto,
} from '@/integrations/api/client'
import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import { Link } from '@tanstack/react-router'
import {
  ActivityIcon,
  CheckCircle2Icon,
  Clock3Icon,
  CopyIcon,
  ExternalLinkIcon,
  GlobeIcon,
  WrenchIcon,
  XCircleIcon,
} from 'lucide-react'
import { useCallback, useMemo, useRef, useState } from 'react'

const generateId = () =>
  `${Date.now()}-${Math.random().toString(36).slice(2, 11)}`

const models = [
  {
    name: 'GPT 4o',
    value: 'openai/gpt-4o',
  },
  {
    name: 'Deepseek R1',
    value: 'deepseek/deepseek-r1',
  },
]

type ToolTimelineItem = {
  id: string
  messageId: string
  toolName: string
  toolState: string
  toolInput: unknown
  toolOutput: unknown
}

interface ChatbotProps {
  chatId: string
  projectId: string
  developerMode: boolean
  toolActivityOpen: boolean
  onToolActivityOpenChange: (open: boolean) => void
}

const TOOL_LABELS: Record<string, string> = {
  search_project_documents: '检索课程资料',
  note_create: '创建学习笔记',
  note_create_scoped: '基于指定资料创建笔记',
  note_list: '查找笔记',
  note_get: '读取笔记',
  note_delete: '删除笔记',
  quiz_create: '生成测验',
  flashcard_create: '生成闪卡',
  mind_map_create: '生成思维导图',
  resource_package_generate: '生成资源包',
}

const formatToolName = (name: string) =>
  TOOL_LABELS[name] ??
  name
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')

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

const getResourcePackageResult = (toolName: string, output: unknown) => {
  if (
    toolName !== 'resource_package_generate' ||
    !output ||
    typeof output !== 'object'
  ) {
    return null
  }
  const value = output as Record<string, unknown>
  return typeof value.package_id === 'string' ? value : null
}

const getToolStatusLabel = (state: string) => {
  if (state === 'output-available') return '已完成'
  if (state === 'output-error') return '失败'
  if (state === 'input-streaming') return '准备中'
  return '进行中'
}

const getToolStatusIcon = (state: string) => {
  if (state === 'output-available') {
    return <CheckCircle2Icon className="size-3.5 text-green-600" />
  }
  if (state === 'output-error') {
    return <XCircleIcon className="size-3.5 text-destructive" />
  }
  if (state === 'input-streaming') {
    return <Clock3Icon className="size-3.5 text-muted-foreground" />
  }
  return <ActivityIcon className="size-3.5 animate-pulse text-primary" />
}

const getToolStatusVariant = (state: string): 'secondary' | 'destructive' => {
  return state === 'output-error' ? 'destructive' : 'secondary'
}

const summarizeToolValue = (value: unknown) => {
  if (value === null || value === undefined || value === '') return 'None'
  if (typeof value === 'string') {
    return value.length > 120 ? `${value.slice(0, 120)}...` : value
  }
  try {
    const text = JSON.stringify(value)
    return text.length > 120 ? `${text.slice(0, 120)}...` : text
  } catch {
    return String(value)
  }
}

const collectToolTimeline = (
  messages: ReadonlyArray<ChatMessageDto>,
): ToolTimelineItem[] =>
  messages.flatMap((message) =>
    Array.from(message.parts ?? [])
      .filter((part): part is ToolCallPartDto => part.type === 'tool_call')
      .map((part, index) => ({
        id: part.id ?? `${message.id}-${part.tool_call_id ?? index}`,
        messageId: message.id,
        toolName: part.tool_name,
        toolState: part.tool_state,
        toolInput: part.tool_input,
        toolOutput: part.tool_output,
      })),
  )

const getTaskTitle = (toolCalls: ReadonlyArray<ToolCallPartDto>) => {
  const names = toolCalls.map((tool) => tool.tool_name)
  if (names.some((name) => name.startsWith('note_'))) return '处理学习笔记'
  if (names.some((name) => name.startsWith('quiz_'))) return '生成学习测验'
  if (names.some((name) => name.startsWith('flashcard_'))) return '生成学习闪卡'
  if (names.some((name) => name.startsWith('mind_map_'))) return '生成思维导图'
  if (names.includes('resource_package_generate')) return '生成学习资源包'
  return '处理学习任务'
}

const getTaskState = (toolCalls: ReadonlyArray<ToolCallPartDto>) => {
  if (toolCalls.some((tool) => tool.tool_state === 'output-error')) {
    return 'output-error'
  }
  if (
    toolCalls.length > 0 &&
    toolCalls.every((tool) => tool.tool_state === 'output-available')
  ) {
    return 'output-available'
  }
  return 'input-available'
}

const ToolTaskCard = ({
  toolCalls,
  projectId,
}: {
  toolCalls: ReadonlyArray<ToolCallPartDto>
  projectId: string
}) => {
  const taskState = getTaskState(toolCalls)
  const resourcePackageResult = toolCalls
    .map((toolCall) => ({
      toolName: toolCall.tool_name,
      output: parseToolOutput(toolCall).output,
    }))
    .map(({ toolName, output }) => getResourcePackageResult(toolName, output))
    .find((result) => result !== null)

  return (
    <div className="not-prose mb-4 w-full rounded-md border bg-card text-card-foreground">
      <div className="flex items-center justify-between gap-3 px-4 py-3">
        <div className="flex min-w-0 items-center gap-2">
          <WrenchIcon className="size-4 shrink-0 text-primary" />
          <span className="truncate text-sm font-medium">
            {getTaskTitle(toolCalls)}
          </span>
        </div>
        <Badge
          variant={getToolStatusVariant(taskState)}
          className="shrink-0 gap-1"
        >
          {getToolStatusIcon(taskState)}
          {getToolStatusLabel(taskState)}
        </Badge>
      </div>

      <div className="border-t px-4 py-2">
        {toolCalls.map((toolCall) => (
          <div
            key={toolCall.tool_call_id}
            className="flex min-h-9 items-center justify-between gap-3 border-b py-2 last:border-b-0"
          >
            <div className="flex min-w-0 items-center gap-2 text-sm">
              {getToolStatusIcon(toolCall.tool_state)}
              <span className="truncate">
                {formatToolName(toolCall.tool_name)}
              </span>
            </div>
            <span className="shrink-0 text-xs text-muted-foreground">
              {getToolStatusLabel(toolCall.tool_state)}
            </span>
          </div>
        ))}
      </div>

      {resourcePackageResult && (
        <div className="border-t px-4 py-3">
          <Link
            to="/dashboard/p/$projectId/resource-packages"
            params={{ projectId }}
            className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"
          >
            查看生成的资源包
            <ExternalLinkIcon className="size-4" />
          </Link>
        </div>
      )}
    </div>
  )
}

const ToolActivityContent = ({
  tools,
  isStreaming,
}: {
  tools: ReadonlyArray<ToolTimelineItem>
  isStreaming: boolean
}) => (
  <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-4">
    {tools.length === 0 ? (
      <div className="flex min-h-40 flex-col items-center justify-center rounded-md border border-dashed bg-muted/30 px-4 text-center">
        {isStreaming ? (
          <>
            <ActivityIcon className="mb-3 size-5 animate-pulse text-primary" />
            <div className="text-sm font-medium">正在处理</div>
            <p className="mt-1 text-xs leading-5 text-muted-foreground">
              工具调用出现后会显示在这里。
            </p>
          </>
        ) : (
          <>
            <WrenchIcon className="mb-3 size-5 text-muted-foreground" />
            <div className="text-sm font-medium">暂无工具调用</div>
          </>
        )}
      </div>
    ) : (
      <div className="flex flex-col gap-3">
        {tools.map((tool, index) => (
          <div
            key={tool.id}
            className="rounded-md border bg-card p-3 text-card-foreground"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium">
                    {index + 1}
                  </span>
                  <div className="truncate text-sm font-medium">
                    {formatToolName(tool.toolName)}
                  </div>
                </div>
                <div className="mt-1 truncate pl-8 text-xs text-muted-foreground">
                  message: {tool.messageId}
                </div>
              </div>
              <Badge
                variant={getToolStatusVariant(tool.toolState)}
                className="shrink-0 gap-1"
              >
                {getToolStatusIcon(tool.toolState)}
                {getToolStatusLabel(tool.toolState)}
              </Badge>
            </div>

            <div className="mt-3 flex flex-col gap-2 rounded-md bg-muted/40 p-2 text-xs">
              <div>
                <div className="font-medium text-muted-foreground">Input</div>
                <div className="mt-1 break-words font-mono text-[11px] leading-4">
                  {summarizeToolValue(tool.toolInput)}
                </div>
              </div>
              <div>
                <div className="font-medium text-muted-foreground">Output</div>
                <div className="mt-1 break-words font-mono text-[11px] leading-4">
                  {summarizeToolValue(tool.toolOutput)}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    )}
  </div>
)

export const Chatbot: React.FC<ChatbotProps> = ({
  chatId,
  projectId,
  developerMode,
  toolActivityOpen,
  onToolActivityOpenChange,
}) => {
  const [input, setInput] = useState('')
  const [model, setModel] = useState<string>(models[0].value)
  const [webSearch, setWebSearch] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)

  const chatKey = `${projectId}:${chatId}`
  const chatResult = useAtomValue(chatAtom(chatKey))
  const streamStatus = useAtomValue(chatStreamStatusAtom(chatId))
  const streamMessage = useAtomSet(streamMessageAtom, {
    mode: 'promise',
  })

  const messages = Result.isSuccess(chatResult)
    ? (chatResult.value.messages ?? [])
    : []
  const isStreaming = streamStatus !== null
  const toolTimeline = useMemo(() => collectToolTimeline(messages), [messages])

  const blobToDataUrl = useCallback(
    async (blobUrl: string): Promise<string> => {
      const response = await fetch(blobUrl)
      const blob = await response.blob()
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

    const parts: (TextPartDto | FilePartDto)[] = []

    if (hasText) {
      parts.push({
        type: 'text',
        text_content: message.text,
        order: parts.length,
      })
    }

    const fileParts = await Promise.all(
      message.files.map(async (file, index) => {
        if (
          file.url &&
          !file.url.startsWith('blob:') &&
          !file.url.startsWith('data:')
        ) {
          return {
            type: 'file' as const,
            file_name: file.filename || 'file',
            file_type: file.mediaType,
            file_url: file.url,
            order: parts.length + index,
          } as FilePartDto
        }

        let dataUrl = file.url
        if (file.url?.startsWith('blob:')) {
          dataUrl = await blobToDataUrl(file.url)
        }

        if (!dataUrl || !dataUrl.startsWith('data:')) {
          throw new Error('Invalid file URL')
        }

        return {
          type: 'file' as const,
          file_name: file.filename || 'file',
          file_type: file.mediaType,
          file_url: dataUrl,
          order: parts.length + index,
        } as FilePartDto
      }),
    )

    parts.push(...fileParts)

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
  }

  const handleCopy = useCallback((text: string) => {
    navigator.clipboard.writeText(text)
  }, [])

  return (
    <div className="size-full min-h-0 overflow-hidden">
      <div className="min-h-0 min-w-0 size-full overflow-hidden">
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
                                <div
                                  key={`${message.id}-file-${index}`}
                                  className="flex items-center gap-2 rounded bg-muted p-2"
                                >
                                  <span className="text-sm">
                                    {part.file_name}
                                  </span>
                                  <a
                                    href={part.file_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-xs text-primary hover:underline"
                                  >
                                    View
                                  </a>
                                </div>
                              ))}
                          </div>
                        </MessageContent>
                      </Message>
                    )}

                  {message.parts &&
                    (() => {
                      const sourceDocuments = message.parts.filter(
                        (part): part is SourceDocumentPartDto =>
                          part.type === 'source-document',
                      )

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

                  {message.parts &&
                    (() => {
                      const visibleParts = message.parts.filter(
                        (part) => part.type !== 'source-document',
                      )
                      const toolCallsById = new Map<string, ToolCallPartDto>()
                      visibleParts.forEach((part) => {
                        if (part.type === 'tool_call') {
                          toolCallsById.set(part.tool_call_id, part)
                        }
                      })
                      const toolCalls = Array.from(toolCallsById.values())
                      const firstToolIndex = visibleParts.findIndex(
                        (part) => part.type === 'tool_call',
                      )
                      let lastTextIndex = -1
                      visibleParts.forEach((part, index) => {
                        if (part.type === 'text') lastTextIndex = index
                      })

                      return visibleParts.map((part, index: number) => {
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
                                  <Response>{part.text_content}</Response>
                                </MessageContent>
                                {message.role === 'assistant' &&
                                  index === lastTextIndex && (
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
                          case 'tool_call':
                            return index === firstToolIndex ? (
                              <ToolTaskCard
                                key={`${message.id}-tool-task`}
                                toolCalls={toolCalls}
                                projectId={projectId}
                              />
                            ) : null
                          default:
                            return null
                        }
                      })
                    })()}
                </div>
              ))}
              {isStreaming && <Loader />}
            </ConversationContent>
            <ConversationScrollButton />
          </Conversation>

          <PromptInput
            onSubmit={handleSubmit}
            className="mt-4 shrink-0"
            globalDrop
            multiple
          >
            <PromptInputHeader>
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
                    setModel(value as string)
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
                disabled={!input && !isStreaming}
                status={isStreaming ? 'streaming' : 'ready'}
              />
            </PromptInputFooter>
          </PromptInput>
        </div>
      </div>

      {developerMode && (
        <Sheet open={toolActivityOpen} onOpenChange={onToolActivityOpenChange}>
          <SheetContent side="right" className="w-full gap-0 p-0 sm:max-w-md">
            <SheetHeader className="border-b pr-12">
              <SheetTitle className="flex items-center gap-2">
                <WrenchIcon className="size-4 text-primary" />
                工具调试
              </SheetTitle>
              <SheetDescription>
                仅开发模式显示工具输入、输出和执行状态。
              </SheetDescription>
            </SheetHeader>
            <ToolActivityContent
              tools={toolTimeline}
              isStreaming={isStreaming}
            />
          </SheetContent>
        </Sheet>
      )}
    </div>
  )
}
