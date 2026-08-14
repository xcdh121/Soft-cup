import type { ChatMessageDto } from '@/integrations/api/client'

const DOT_DELAYS = ['-0.3s', '-0.15s', '0s'] as const

export const shouldShowSourceReadingStatus = (
  message: ChatMessageDto,
  streamingAssistantMessageId: string | null,
) =>
  message.role === 'assistant' &&
  message.id === streamingAssistantMessageId &&
  Boolean(message.parts?.some((part) => part.type === 'source-document')) &&
  !message.parts?.some(
    (part) => part.type === 'text' && part.text_content.trim().length > 0,
  )

export const SourceReadingStatus = () => (
  <div
    aria-label="已找到相关资料，正在阅读并组织回答…"
    aria-live="polite"
    className="flex items-end py-1 text-sm text-muted-foreground"
    role="status"
  >
    <span aria-hidden="true">已找到相关资料，正在阅读并组织回答</span>
    <span aria-hidden="true" className="ml-0.5 inline-flex h-4 items-end">
      {DOT_DELAYS.map((delay) => (
        <span
          className="inline-block animate-bounce leading-none motion-reduce:animate-none"
          data-animated-dot
          key={delay}
          style={{ animationDelay: delay, animationDuration: '1s' }}
        >
          .
        </span>
      ))}
    </span>
  </div>
)
