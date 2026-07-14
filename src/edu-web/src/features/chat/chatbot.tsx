import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import { Link } from '@tanstack/react-router'
import { CopyIcon, ExternalLinkIcon, GlobeIcon } from 'lucide-react'
import { useCallback, useRef, useState } from 'react'
import { DigitalAvatarPanel } from './components/digital-avatar-panel'
import type { PromptInputMessage } from '@/components/ai-elements/prompt-input'
import type {
  ChatMessageDto,
  FilePartDto,
  SourceDocumentPartDto,
  TextPartDto,
  ToolCallPartDto,
} from '@/integrations/api/client'
import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from '@/components/ai-elements/conversation'
import { Loader } from '@/components/ai-elements/loader'
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
  chatStreamStatusAtom,
  streamMessageAtom,
} from '@/data-acess/chat'

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

interface ChatbotProps {
  chatId: string
  projectId: string
}

const formatToolName = (name: string) =>
  name
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')

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

export const Chatbot: React.FC<ChatbotProps> = ({ chatId, projectId }) => {
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

    const parts: Array<TextPartDto | FilePartDto> = []

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
          }
        }

        let dataUrl = file.url
        if (file.url.startsWith('blob:')) {
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
        }
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
                    message.parts
                      .filter((part) => part.type !== 'source-document')
                      .map((part, index: number) => {
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
                            const resourcePackageResult =
                              getResourcePackageResult(
                                toolCall.tool_name,
                                output,
                              )

                            return (
                              <Tool
                                key={`${message.id}-part-${index}`}
                                defaultOpen={
                                  toolCall.tool_state === 'output-error' ||
                                  resourcePackageResult !== null
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
                                  {resourcePackageResult && (
                                    <div className="border-t p-4">
                                      <Link
                                        to="/dashboard/p/$projectId/resource-packages"
                                        params={{ projectId }}
                                        className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
                                      >
                                        查看生成的资源包
                                        <ExternalLinkIcon className="size-4" />
                                      </Link>
                                    </div>
                                  )}
                                </ToolContent>
                              </Tool>
                            )
                          }
                          default:
                            return null
                        }
                      })}
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
                disabled={!input && !isStreaming}
                status={isStreaming ? 'streaming' : 'ready'}
              />
            </PromptInputFooter>
          </PromptInput>
        </div>
      </div>

      <DigitalAvatarPanel />
    </div>
  )
}
