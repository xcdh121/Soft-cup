import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Response } from '@/components/ai-elements/response'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { projectCourseOutlineAtom } from '@/data-acess/course-library'
import {
  askDocumentQuestionAtom,
  bindCourseBookAtom,
  courseBooksAtom,
  documentAtom,
  documentFileBufferAtom,
  documentPreviewAtom,
  reprocessDocumentAtom,
  type CourseBook,
  type DocumentCitation,
} from '@/data-acess/document'
import { useDocumentPolling } from '@/hooks/use-document-polling'
import type { DocumentDto } from '@/integrations/api'
import { cn } from '@/lib/utils'
import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import { Link } from '@tanstack/react-router'
import {
  BookOpenIcon,
  BotIcon,
  GripVerticalIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  CircleAlertIcon,
  ClockIcon,
  CopyIcon,
  FileTextIcon,
  Loader2Icon,
  MessageSquareTextIcon,
  PanelRightCloseIcon,
  PanelRightOpenIcon,
  SendIcon,
  Trash2Icon,
  ZoomInIcon,
  ZoomOutIcon,
} from 'lucide-react'
import {
  type FormEvent,
  type KeyboardEvent,
  type MouseEvent,
  type PointerEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { Document as PdfDocument, Page as PdfPage, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'
import { toast } from 'sonner'
import { DocumentHeader } from './components/document-header'

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

const DEFAULT_SELECTION_QUESTION = '请讲解这段内容'
const MIN_SCALE = 0.75
const MAX_SCALE = 1.6
const SCALE_STEP = 0.1
const PDF_PAGE_PRELOAD_BUFFER = 3
const PDF_PRELOAD_DELAY_MS = 120
const PDF_PAGE_HEIGHT_RATIO = 1.414
const READER_WIDTH_CHANGE_THRESHOLD = 8
const PAGE_TRACKING_VIEWPORT_RATIO = 0.4
const DEFAULT_CHAPTER_SIDEBAR_WIDTH = 250
const DEFAULT_AI_SIDEBAR_WIDTH = 320
const MIN_CHAPTER_SIDEBAR_WIDTH = 180
const MAX_CHAPTER_SIDEBAR_WIDTH = 420
const MIN_AI_SIDEBAR_WIDTH = 260
const MAX_AI_SIDEBAR_WIDTH = 520
const DRAG_HANDLE_WIDTH = 6
const PDF_LOAD_OPTIONS = {
  disableAutoFetch: true,
  disableStream: false,
}

type SelectionMark = {
  id: string
  left: number
  top: number
  width: number
  height: number
}

type PendingSelection = {
  text: string
  pageNumber: number
  marks: Array<SelectionMark>
  toolbarLeft: number
  toolbarTop: number
}

type AiMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  selectedText?: string
  citations?: Array<DocumentCitation>
}

type PdfPageLoadResult = {
  getViewport: (options: { scale: number }) => {
    width: number
    height: number
  }
}

type PdfFileSource =
  | string
  | { data: Uint8Array }
  | {
      url: string
      httpHeaders?: Record<string, string>
      withCredentials?: boolean
    }

type DocumentContentProps = {
  documentId: string
  projectId: string
}

const isPdfDocument = (document: DocumentDto) =>
  document.file_type?.toLowerCase() === 'pdf'

const isReadableDocument = (document: DocumentDto) =>
  document.status === 'processed' || document.status === 'indexed'

const clamp = (value: number, min: number, max: number) =>
  Math.min(Math.max(value, min), max)

const getWheelDeltaMultiplier = (
  deltaMode: number,
  pageHeight: number,
) => {
  if (deltaMode === 1) return 40
  if (deltaMode === 2) return pageHeight
  return 1
}

const scrollPdfReaderByWheel = (
  root: HTMLDivElement,
  event: Pick<
    globalThis.WheelEvent,
    'ctrlKey' | 'metaKey' | 'deltaMode' | 'deltaX' | 'deltaY' | 'preventDefault'
  >,
) => {
  if (event.ctrlKey || event.metaKey) return

  event.preventDefault()
  const multiplier = getWheelDeltaMultiplier(event.deltaMode, root.clientHeight)
  root.scrollTo({
    top: root.scrollTop + event.deltaY * multiplier,
    left: root.scrollLeft + event.deltaX * multiplier,
    behavior: 'auto',
  })
}

const normalizeSelectedText = (text: string) => text.replace(/\s+/g, ' ').trim()

const coercePositiveInteger = (value: unknown) => {
  const numberValue = typeof value === 'string' ? Number(value) : value
  return typeof numberValue === 'number' &&
    Number.isInteger(numberValue) &&
    numberValue > 0
    ? numberValue
    : null
}

const getPresetPageCount = (document: DocumentDto) =>
  coercePositiveInteger(document.metadata.page_count) ??
  coercePositiveInteger(document.metadata.num_pages) ??
  coercePositiveInteger(document.metadata.total_pages) ??
  0

const isElementNode = (node: Node): node is Element =>
  node.nodeType === Node.ELEMENT_NODE

const isTextNode = (node: Node): node is Text =>
  node.nodeType === Node.TEXT_NODE

const getRangeElement = (range: Range) => {
  const node = range.commonAncestorContainer
  if (isElementNode(node)) return node
  if (isTextNode(node)) return node.parentElement
  return null
}

<<<<<<< Updated upstream
const serverUrl = (env.VITE_SERVER_URL ?? 'http://localhost:8000').replace(
  /\/$/,
  '',
)

const createDocumentFileUrl = (projectId: string, documentId: string) =>
  `${serverUrl}/api/v1/projects/${encodeURIComponent(
    projectId,
  )}/documents/${encodeURIComponent(documentId)}/file`

=======
>>>>>>> Stashed changes
const LoadingState = ({ label }: { label: string }) => (
  <div className="flex flex-1 items-center justify-center gap-2 text-sm text-muted-foreground">
    <Loader2Icon className="size-4 animate-spin" />
    <span>{label}</span>
  </div>
)

const CoursePdfSidebar = ({
  projectId,
  activeDocumentId,
  document,
}: {
  projectId: string
  activeDocumentId: string
  document: DocumentDto
}) => {
  const courseBooksResult = useAtomValue(courseBooksAtom(projectId))
  const courseOutlineResult = useAtomValue(projectCourseOutlineAtom(projectId))
  const bindCourseBook = useAtomSet(bindCourseBookAtom, { mode: 'promise' })
  const [selectedChapterId, setSelectedChapterId] = useState('')
  const [binding, setBinding] = useState(false)

  const groupedBooks = useMemo(() => {
    if (!Result.isSuccess(courseBooksResult)) return []
    const groups = new Map<string, Array<CourseBook>>()
    courseBooksResult.value.forEach((book) => {
      const key = book.chapter_id ?? 'uncategorized'
      groups.set(key, [...(groups.get(key) ?? []), book])
    })
    return Array.from(groups.entries())
  }, [courseBooksResult])

  const courseOutline = Result.isSuccess(courseOutlineResult)
    ? courseOutlineResult.value
    : null
  const currentBinding = Result.isSuccess(courseBooksResult)
    ? courseBooksResult.value.find((book) => book.document_id === activeDocumentId)
    : null

  useEffect(() => {
    if (currentBinding?.chapter_id) {
      setSelectedChapterId(currentBinding.chapter_id)
      return
    }
    if (!selectedChapterId && courseOutline?.chapters[0]?.id) {
      setSelectedChapterId(courseOutline.chapters[0].id)
    }
  }, [courseOutline?.chapters, currentBinding?.chapter_id, selectedChapterId])

  const selectedChapter = courseOutline?.chapters.find(
    (chapter) => chapter.id === selectedChapterId,
  )

  const handleBindCurrentPdf = async () => {
    if (!courseOutline?.courseId || !selectedChapterId) return

    setBinding(true)
    try {
      await bindCourseBook({
        projectId,
        courseId: courseOutline.courseId,
        chapterId: selectedChapterId,
        documentId: activeDocumentId,
        title: document.file_name,
        chapterTitle: selectedChapter?.title,
      })
      toast.success('已绑定到章节 PDF')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '章节 PDF 绑定失败')
    } finally {
      setBinding(false)
    }
  }

  return (
    <aside className="hidden h-full min-h-0 w-full overflow-hidden border-r bg-background/80 lg:flex lg:flex-col">
      <div className="flex h-12 items-center gap-2 border-b px-4">
        <BookOpenIcon className="size-4 text-primary" />
        <span className="text-sm font-medium">章节 PDF</span>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-3">
        <div className="mb-3 rounded-md border bg-background p-3">
          <div className="mb-2 text-xs font-medium text-muted-foreground">
            绑定当前 PDF
          </div>
          {!Result.isSuccess(courseOutlineResult) ? (
            <div className="text-xs leading-5 text-muted-foreground">
              正在加载课程章节...
            </div>
          ) : !courseOutline?.courseId ? (
            <div className="text-xs leading-5 text-muted-foreground">
              当前项目还没有绑定课程。
            </div>
          ) : courseOutline.chapters.length === 0 ? (
            <div className="text-xs leading-5 text-muted-foreground">
              当前课程还没有章节。
            </div>
          ) : (
            <div className="space-y-2">
              <Select
                value={selectedChapterId}
                disabled={Boolean(currentBinding) || binding}
                onValueChange={setSelectedChapterId}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="选择章节" />
                </SelectTrigger>
                <SelectContent>
                  {courseOutline.chapters.map((chapter) => (
                    <SelectItem key={chapter.id} value={chapter.id}>
                      {chapter.title}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                type="button"
                size="sm"
                className="w-full"
                disabled={Boolean(currentBinding) || !selectedChapterId || binding}
                onClick={handleBindCurrentPdf}
              >
                {binding ? (
                  <Loader2Icon className="size-4 animate-spin" />
                ) : (
                  <FileTextIcon className="size-4" />
                )}
                {currentBinding ? '已绑定' : '绑定当前 PDF'}
              </Button>
              {currentBinding ? (
                <div className="text-xs leading-5 text-muted-foreground">
                  当前 PDF 已在章节列表中。
                </div>
              ) : null}
            </div>
          )}
        </div>

        {courseBooksResult.waiting ? (
          <div className="flex items-center gap-2 px-2 py-3 text-sm text-muted-foreground">
            <Loader2Icon className="size-4 animate-spin" />
            <span>正在加载...</span>
          </div>
        ) : null}

        {!courseBooksResult.waiting && !Result.isSuccess(courseBooksResult) ? (
          <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
            入口加载失败
          </div>
        ) : null}

        {Result.isSuccess(courseBooksResult) && groupedBooks.length === 0 ? (
          <div className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">
            暂无章节 PDF
          </div>
        ) : null}

        <div className="space-y-4">
          {groupedBooks.map(([chapterId, books], index) => {
            const chapterTitle =
              typeof books[0]?.metadata.chapter_title === 'string'
                ? books[0].metadata.chapter_title
                : chapterId === 'uncategorized'
                  ? '未分配章节'
                  : `章节 ${index + 1}`

            return (
              <section key={chapterId} className="space-y-2">
                <div className="px-1 text-xs font-medium text-muted-foreground">
                  {chapterTitle}
                </div>
                <div className="space-y-1">
                  {books.map((book) => {
                    const active = book.document_id === activeDocumentId
                    return (
                      <Button
                        key={book.resource_id}
                        variant={active ? 'secondary' : 'ghost'}
                        className={cn(
                          'h-auto w-full justify-start px-2 py-2 text-left',
                          active && 'border border-primary/20 bg-primary/10',
                        )}
                        asChild
                      >
                        <Link
                          to="/dashboard/p/$projectId/d/$documentId"
                          params={{
                            projectId,
                            documentId: book.document_id,
                          }}
                        >
                          <FileTextIcon className="size-4" />
                          <span className="min-w-0 flex-1 truncate">
                            {book.title}
                          </span>
                        </Link>
                      </Button>
                    )
                  })}
                </div>
              </section>
            )
          })}
        </div>
      </div>
    </aside>
  )
}

const PdfToolbar = ({
  currentPage,
  numPages,
  pageInput,
  scale,
  aiOpen,
  onAiOpenChange,
  onPageInputChange,
  onPageSubmit,
  onPreviousPage,
  onNextPage,
  onZoomIn,
  onZoomOut,
}: {
  currentPage: number
  numPages: number
  pageInput: string
  scale: number
  aiOpen: boolean
  onAiOpenChange: (open: boolean) => void
  onPageInputChange: (value: string) => void
  onPageSubmit: () => void
  onPreviousPage: () => void
  onNextPage: () => void
  onZoomIn: () => void
  onZoomOut: () => void
}) => {
  const handlePageSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    onPageSubmit()
  }

  return (
    <div className="flex h-12 shrink-0 items-center justify-between gap-3 border-b bg-background px-3">
      <div className="flex min-w-0 items-center gap-2">
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          onClick={onPreviousPage}
          disabled={currentPage <= 1}
        >
          <ChevronLeftIcon className="size-4" />
          <span className="sr-only">上一页</span>
        </Button>

        <form
          onSubmit={handlePageSubmit}
          className="flex items-center gap-1 text-sm"
        >
          <input
            value={pageInput}
            onChange={(event) => onPageInputChange(event.target.value)}
            className="h-8 w-12 rounded-md border bg-background px-2 text-center"
            inputMode="numeric"
            aria-label="页码"
          />
          <span className="text-muted-foreground">/ {numPages || '-'}</span>
        </form>

        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          onClick={onNextPage}
          disabled={!numPages || currentPage >= numPages}
        >
          <ChevronRightIcon className="size-4" />
          <span className="sr-only">下一页</span>
        </Button>
      </div>

      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          onClick={onZoomOut}
          disabled={scale <= MIN_SCALE}
        >
          <ZoomOutIcon className="size-4" />
          <span className="sr-only">缩小</span>
        </Button>
        <Badge variant="outline" className="h-8 min-w-16">
          {Math.round(scale * 100)}%
        </Badge>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          onClick={onZoomIn}
          disabled={scale >= MAX_SCALE}
        >
          <ZoomInIcon className="size-4" />
          <span className="sr-only">放大</span>
        </Button>
        <Button
          type="button"
          variant={aiOpen ? 'secondary' : 'ghost'}
          size="icon-sm"
          onClick={() => onAiOpenChange(!aiOpen)}
        >
          {aiOpen ? (
            <PanelRightCloseIcon className="size-4" />
          ) : (
            <PanelRightOpenIcon className="size-4" />
          )}
          <span className="sr-only">AI 侧栏</span>
        </Button>
      </div>
    </div>
  )
}

const SelectionToolbar = ({
  selection,
  onAsk,
  onClear,
  onCopy,
}: {
  selection: PendingSelection
  onAsk: () => void
  onClear: () => void
  onCopy: () => void
}) => (
  <div
    className="absolute z-30 flex items-center gap-1 rounded-md border bg-popover p-1 text-popover-foreground shadow-lg"
    style={{
      left: selection.toolbarLeft,
      top: selection.toolbarTop,
    }}
    onMouseDown={(event) => event.preventDefault()}
  >
    <Button type="button" variant="ghost" size="sm" onClick={onCopy}>
      <CopyIcon className="size-4" />
      复制
    </Button>
    <Button type="button" size="sm" onClick={onAsk}>
      <BotIcon className="size-4" />
      AI 问答
    </Button>
    <Button type="button" variant="ghost" size="icon-sm" onClick={onClear}>
      <Trash2Icon className="size-4" />
      <span className="sr-only">清除</span>
    </Button>
  </div>
)

const PdfLoadingShell = ({
  pageWidth,
  pageHeight,
  pageCount,
}: {
  pageWidth: number
  pageHeight: number
  pageCount: number
}) => (
  <div className="flex flex-col items-center gap-5">
    <div
      className="flex items-center justify-center rounded-md border bg-background text-sm text-muted-foreground shadow-sm"
      style={{ width: pageWidth, minHeight: pageHeight }}
    >
      <Loader2Icon className="mr-2 size-4 animate-spin" />
      正在加载第 1 页{pageCount ? ` / ${pageCount}` : ''}
    </div>
  </div>
)

const ColumnResizeHandle = ({
  label,
  onPointerDown,
}: {
  label: string
  onPointerDown: (event: PointerEvent<HTMLDivElement>) => void
}) => (
  <div
    role="separator"
    aria-label={label}
    className="group flex h-full cursor-col-resize touch-none items-center justify-center border-x bg-border/40 transition-colors hover:bg-primary/20"
    onPointerDown={onPointerDown}
  >
    <GripVerticalIcon className="size-3.5 text-muted-foreground opacity-60 group-hover:text-primary group-hover:opacity-100" />
  </div>
)

const AiSidebar = ({
  activeSelection,
  currentPage,
  documentId,
  messages,
  open,
  projectId,
  question,
  sending,
  onQuestionChange,
  onOpenChange,
  onSubmitQuestion,
}: {
  activeSelection: PendingSelection | null
  currentPage: number
  documentId: string
  messages: Array<AiMessage>
  open: boolean
  projectId: string
  question: string
  sending: boolean
  onQuestionChange: (value: string) => void
  onOpenChange: (open: boolean) => void
  onSubmitQuestion: () => void
}) => {
  const messagesScrollRef = useRef<HTMLDivElement | null>(null)
  const messagesEndRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!open) return

    const frameId = window.requestAnimationFrame(() => {
      const messagesScroll = messagesScrollRef.current
      if (!messagesScroll) return

      messagesScroll.scrollTo({
        top: messagesScroll.scrollHeight,
        behavior: 'smooth',
      })
    })

    return () => window.cancelAnimationFrame(frameId)
  }, [messages, open, sending])

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    onSubmitQuestion()
  }

  const handleQuestionKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== 'Enter' || event.shiftKey) return
    event.preventDefault()
    if (sending || (!question.trim() && !activeSelection?.text.trim())) return
    onSubmitQuestion()
  }

  return (
    <aside
      className={cn(
        'flex h-full min-h-0 w-full overflow-hidden border-l bg-muted/30 transition-[padding] duration-200',
        open ? 'p-3' : 'items-start justify-center p-2',
      )}
    >
      {!open ? (
        <Button
          type="button"
          variant="secondary"
          size="icon-sm"
          className="mt-1 shadow-sm"
          onClick={() => onOpenChange(true)}
        >
          <PanelRightOpenIcon className="size-4" />
          <span className="sr-only">显示 AI 侧栏</span>
        </Button>
      ) : (
        <div className="flex h-full min-h-0 w-full flex-col rounded-md border bg-background shadow-sm">
          <div className="flex h-12 shrink-0 items-center justify-between border-b px-4">
            <div className="flex items-center gap-2">
              <div className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
                <BotIcon className="size-4" />
              </div>
              <div>
                <div className="text-sm font-semibold">AI 助手</div>
                <div className="text-xs text-muted-foreground">
                  第 {activeSelection?.pageNumber ?? currentPage} 页
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="secondary">在线</Badge>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                onClick={() => onOpenChange(false)}
              >
                <PanelRightCloseIcon className="size-4" />
                <span className="sr-only">隐藏 AI 侧栏</span>
              </Button>
            </div>
          </div>

          {activeSelection ? (
            <div className="shrink-0 border-b bg-muted/30 p-3">
              <div className="rounded-md border bg-background p-3 text-sm leading-6">
                <div className="mb-1 text-xs text-muted-foreground">
                  选中文本
                </div>
                <div className="line-clamp-4">{activeSelection.text}</div>
              </div>
            </div>
          ) : null}

          <div
            ref={messagesScrollRef}
            className="min-h-0 flex-1 space-y-3 overflow-y-auto overscroll-contain p-4"
            aria-live="polite"
          >
            {messages.length === 0 && !sending ? (
              <div className="flex h-40 items-center justify-center text-sm text-muted-foreground">
                暂无对话
              </div>
            ) : (
              messages.map((message) => (
                <div
                  key={message.id}
                  className={cn(
                    'rounded-md border p-3 text-sm leading-6',
                    message.role === 'assistant'
                      ? 'bg-background'
                      : 'bg-primary/10 border-primary/20',
                  )}
                >
                  <div className="mb-2 flex items-center gap-2 text-xs font-medium text-muted-foreground">
                    {message.role === 'assistant' ? (
                      <BotIcon className="size-3.5" />
                    ) : (
                      <MessageSquareTextIcon className="size-3.5" />
                    )}
                    {message.role === 'assistant' ? 'AI 助手' : '我的问题'}
                  </div>
                  {message.selectedText ? (
                    <blockquote className="mb-2 border-l-2 border-primary/50 pl-2 text-muted-foreground">
                      {message.selectedText}
                    </blockquote>
                  ) : null}
                  {message.role === 'assistant' ? (
                    <Response className="text-sm leading-6">
                      {message.content}
                    </Response>
                  ) : (
                    <div className="whitespace-pre-wrap">{message.content}</div>
                  )}
                  {message.citations?.length ? (
                    <div className="mt-3 flex flex-wrap gap-1">
                      {message.citations.slice(0, 5).map((citation) => (
                        <Badge
                          key={`${citation.document_id}:${citation.segment_id}:${citation.page_number}`}
                          variant="outline"
                        >
                          {citation.page_number
                            ? `第 ${citation.page_number} 页`
                            : citation.title}
                        </Badge>
                      ))}
                    </div>
                  ) : null}
                </div>
              ))
            )}

            {sending ? (
              <div className="rounded-md border bg-background p-3 text-sm leading-6">
                <div className="mb-2 flex items-center gap-2 text-xs font-medium text-muted-foreground">
                  <BotIcon className="size-3.5" />
                  AI 助手
                </div>
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Loader2Icon className="size-4 animate-spin" />
                  正在结合选中文本分析...
                </div>
              </div>
            ) : null}
            <div ref={messagesEndRef} />
          </div>

          <form onSubmit={handleSubmit} className="shrink-0 border-t p-3">
            <Textarea
              value={question}
              onChange={(event) => onQuestionChange(event.target.value)}
              onKeyDown={handleQuestionKeyDown}
              className="max-h-32 min-h-20 resize-none text-sm"
              placeholder="输入问题，Enter 发送"
            />
            <div className="mt-2 flex items-center justify-between gap-2">
              <span className="truncate text-xs text-muted-foreground">
                {documentId ? `文档 ${documentId.slice(0, 8)}` : projectId}
              </span>
              <Button
                type="submit"
                size="sm"
                disabled={
                  sending || (!question.trim() && !activeSelection?.text.trim())
                }
              >
                {sending ? (
                  <Loader2Icon className="size-4 animate-spin" />
                ) : (
                  <SendIcon className="size-4" />
                )}
                发送
              </Button>
            </div>
          </form>
        </div>
      )}
    </aside>
  )
}

const PdfReader = ({
  document,
  fileSource,
  projectId,
}: {
  document: DocumentDto
  fileSource: PdfFileSource
  projectId: string
}) => {
  const askQuestion = useAtomSet(askDocumentQuestionAtom, { mode: 'promise' })
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const pagesLayerRef = useRef<HTMLDivElement | null>(null)
  const pageRefs = useRef(new Map<number, HTMLDivElement>())
  const scrollFrameRef = useRef<number | null>(null)
  const preloadTimerRef = useRef<number | null>(null)
  const presetPageCount = useMemo(() => getPresetPageCount(document), [document])
  const [numPages, setNumPages] = useState(presetPageCount)
  const [currentPage, setCurrentPage] = useState(1)
  const [pageInput, setPageInput] = useState('1')
  const [scale, setScale] = useState(1)
  const [readerWidth, setReaderWidth] = useState(760)
  const [pendingSelection, setPendingSelection] =
    useState<PendingSelection | null>(null)
  const [aiOpen, setAiOpen] = useState(true)
  const [messages, setMessages] = useState<Array<AiMessage>>([])
  const [question, setQuestion] = useState('')
  const [sending, setSending] = useState(false)
  const [pdfLoadError, setPdfLoadError] = useState<string | null>(null)
  const [preloadReady, setPreloadReady] = useState(false)
  const [chapterSidebarWidth, setChapterSidebarWidth] = useState(
    DEFAULT_CHAPTER_SIDEBAR_WIDTH,
  )
  const [aiSidebarWidth, setAiSidebarWidth] = useState(
    DEFAULT_AI_SIDEBAR_WIDTH,
  )
  const [pageAspectRatios, setPageAspectRatios] = useState<
    Record<number, number>
  >({})

  const schedulePagePreload = useCallback(() => {
    if (preloadTimerRef.current !== null) {
      window.clearTimeout(preloadTimerRef.current)
    }

    preloadTimerRef.current = window.setTimeout(() => {
      preloadTimerRef.current = null
      setPreloadReady(true)
    }, PDF_PRELOAD_DELAY_MS)
  }, [])

  const pageWidth = useMemo(
    () => Math.round(clamp(readerWidth - 48, 360, 920) * scale),
    [readerWidth, scale],
  )
  const renderedPageNumbers = useMemo(() => {
    const pages = new Set<number>()
    if (!numPages) return pages

    const startPage = preloadReady
      ? clamp(currentPage - PDF_PAGE_PRELOAD_BUFFER, 1, numPages)
      : currentPage
    const endPage = preloadReady
      ? clamp(currentPage + PDF_PAGE_PRELOAD_BUFFER, 1, numPages)
      : currentPage
    for (let page = startPage; page <= endPage; page += 1) {
      pages.add(page)
    }
    return pages
  }, [currentPage, numPages, preloadReady])

  useEffect(() => {
    setPageInput(String(currentPage))
  }, [currentPage])

  useEffect(() => {
    setPendingSelection(null)
  }, [document.id, scale, pageWidth])

  useEffect(() => {
    setNumPages(presetPageCount)
    setCurrentPage(1)
    setPageInput('1')
    setPreloadReady(false)
    setPdfLoadError(null)
    setPageAspectRatios({})
    setPendingSelection(null)
    pageRefs.current.clear()
    scrollRef.current?.scrollTo({ top: 0, left: 0, behavior: 'auto' })
  }, [document.id, presetPageCount])

  useEffect(() => {
    setPreloadReady(false)
    schedulePagePreload()

    return () => {
      if (preloadTimerRef.current !== null) {
        window.clearTimeout(preloadTimerRef.current)
        preloadTimerRef.current = null
      }
    }
  }, [document.id, scale, schedulePagePreload])

  const updateCurrentPageFromScroll = useCallback(() => {
    const root = scrollRef.current
    if (!root || !numPages) return

    if (root.scrollTop <= 2) {
      setCurrentPage((page) => (page === 1 ? page : 1))
      return
    }

    const rootRect = root.getBoundingClientRect()
    const trackingLine =
      rootRect.top + rootRect.height * PAGE_TRACKING_VIEWPORT_RATIO
    let nextPage: number | null = null
    let closestDistance = Number.POSITIVE_INFINITY

    pageRefs.current.forEach((element, pageNumber) => {
      const pageRect = element.getBoundingClientRect()
      if (pageRect.bottom < rootRect.top || pageRect.top > rootRect.bottom) {
        return
      }

      const distance =
        pageRect.top <= trackingLine && pageRect.bottom >= trackingLine
          ? 0
          : Math.min(
              Math.abs(pageRect.top - trackingLine),
              Math.abs(pageRect.bottom - trackingLine),
            )

      if (distance < closestDistance) {
        closestDistance = distance
        nextPage = pageNumber
      }
    })

    if (nextPage === null) return

    const resolvedPage = nextPage
    setCurrentPage((page) => (page === resolvedPage ? page : resolvedPage))
  }, [numPages])

  const handleReaderScroll = useCallback(() => {
    if (scrollFrameRef.current !== null) return

    scrollFrameRef.current = window.requestAnimationFrame(() => {
      scrollFrameRef.current = null
      updateCurrentPageFromScroll()
    })
  }, [updateCurrentPageFromScroll])

  useEffect(() => {
    const root = scrollRef.current
    if (!root) return

    const handleNativeWheel = (event: globalThis.WheelEvent) => {
      scrollPdfReaderByWheel(root, event)
      handleReaderScroll()
    }

    root.addEventListener('wheel', handleNativeWheel, {
      passive: false,
    })
    return () => root.removeEventListener('wheel', handleNativeWheel)
  }, [handleReaderScroll])

  useEffect(
    () => () => {
      if (scrollFrameRef.current !== null) {
        window.cancelAnimationFrame(scrollFrameRef.current)
      }
      if (preloadTimerRef.current !== null) {
        window.clearTimeout(preloadTimerRef.current)
      }
    },
    [],
  )

  useEffect(() => {
    const node = scrollRef.current
    if (!node) return

    const observer = new ResizeObserver((entries) => {
      const entry = entries.at(0)
      if (!entry) return
      const nextWidth = Math.round(entry.contentRect.width)
      setReaderWidth((currentWidth) =>
        Math.abs(currentWidth - nextWidth) >= READER_WIDTH_CHANGE_THRESHOLD
          ? nextWidth
          : currentWidth,
      )
    })
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    const root = scrollRef.current
    if (!root || !numPages) return

    const observer = new IntersectionObserver(
      () => updateCurrentPageFromScroll(),
      {
        root,
        threshold: [0, 0.1, 0.25, 0.5, 0.75],
      },
    )

    pageRefs.current.forEach((element) => observer.observe(element))
    const frameId = window.requestAnimationFrame(updateCurrentPageFromScroll)

    return () => {
      window.cancelAnimationFrame(frameId)
      observer.disconnect()
    }
  }, [numPages, updateCurrentPageFromScroll])

  const setPageRef = useCallback(
    (pageNumber: number) => (element: HTMLDivElement | null) => {
      if (element) pageRefs.current.set(pageNumber, element)
      else pageRefs.current.delete(pageNumber)
    },
    [],
  )

  const scrollToPage = useCallback(
    (pageNumber: number) => {
      const targetPage = clamp(pageNumber, 1, Math.max(numPages, 1))
      const root = scrollRef.current
      const targetElement = pageRefs.current.get(targetPage)
      if (root && targetElement) {
        root.scrollTo({
          top: targetElement.offsetTop - root.offsetTop,
          behavior: 'smooth',
        })
      }
      setCurrentPage(targetPage)
    },
    [numPages],
  )

  const handlePageLoadSuccess = useCallback(
    (pageNumber: number) => (page: PdfPageLoadResult) => {
      const viewport = page.getViewport({ scale: 1 })
      const nextRatio = viewport.height / viewport.width
      if (!Number.isFinite(nextRatio)) return

      setPageAspectRatios((current) => {
        const currentRatio = current[pageNumber]
        if (currentRatio && Math.abs(currentRatio - nextRatio) < 0.01) {
          return current
        }
        return { ...current, [pageNumber]: nextRatio }
      })
    },
    [],
  )

  const submitQuestion = useCallback(
    async (
      submittedQuestion: string,
      selectedText?: string,
      pageNumber?: number,
    ) => {
      const finalQuestion =
        submittedQuestion.trim() || DEFAULT_SELECTION_QUESTION
      const normalizedSelection = normalizeSelectedText(selectedText ?? '')
      if (!finalQuestion && !normalizedSelection) return

      const userMessage: AiMessage = {
        id: crypto.randomUUID(),
        role: 'user',
        content: finalQuestion,
        selectedText: normalizedSelection || undefined,
      }

      setMessages((current) => [...current, userMessage])
      setQuestion('')
      setAiOpen(true)
      setSending(true)

      try {
        const response = await askQuestion({
          projectId,
          documentId: document.id,
          question: finalQuestion,
          selectedText: normalizedSelection || undefined,
          pageNumber: pageNumber ?? currentPage,
          topK: 5,
        })

        setMessages((current) => [
          ...current,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: response.answer,
            citations: response.citations,
          },
        ])
      } catch (error) {
        const message =
          error instanceof Error && error.message
            ? `AI 暂时没有返回结果：${error.message}`
            : 'AI 暂时没有返回结果，请检查模型配置或稍后重试。'
        setMessages((current) => [
          ...current,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: message,
          },
        ])
        toast.error(message)
      } finally {
        setSending(false)
      }
    },
    [askQuestion, currentPage, document.id, projectId],
  )

  const handleSelection = useCallback(
    (event: MouseEvent<HTMLDivElement>) => {
      if (!pagesLayerRef.current) return
      if (!(event.target instanceof Node)) return
      if (!pagesLayerRef.current.contains(event.target)) return

      window.setTimeout(() => {
        const selection = window.getSelection()
        const selectedText = normalizeSelectedText(selection?.toString() ?? '')
        if (!selection || !selectedText || selection.rangeCount === 0) return

        const range = selection.getRangeAt(0)
        const rangeElement = getRangeElement(range)
        const pageElement = rangeElement?.closest<HTMLElement>(
          '[data-pdf-page-number]',
        )
        if (!pageElement || !pagesLayerRef.current?.contains(pageElement))
          return

        const pageNumber =
          Number(pageElement.getAttribute('data-pdf-page-number')) ||
          currentPage
        const layerRect = pagesLayerRef.current.getBoundingClientRect()
        const rects = Array.from(range.getClientRects()).filter(
          (rect) => rect.width > 2 && rect.height > 2,
        )
        if (!rects.length) return

        const marks = rects.map((rect, index) => ({
          id: `${pageNumber}-${index}-${Math.round(rect.left)}-${Math.round(
            rect.top,
          )}`,
          left: rect.left - layerRect.left,
          top: rect.top - layerRect.top,
          width: rect.width,
          height: rect.height,
        }))

        const firstRect = rects[0]
        const toolbarWidth = 230
        setPendingSelection({
          text: selectedText,
          pageNumber,
          marks,
          toolbarLeft: clamp(
            firstRect.left - layerRect.left,
            8,
            Math.max(8, layerRect.width - toolbarWidth),
          ),
          toolbarTop: Math.max(8, firstRect.top - layerRect.top - 48),
        })
      }, 0)
    },
    [currentPage],
  )

  const handleCopySelection = async () => {
    if (!pendingSelection) return
    await navigator.clipboard.writeText(pendingSelection.text)
    toast.success('已复制')
  }

  const handleAskSelection = () => {
    if (!pendingSelection) return
    void submitQuestion(
      DEFAULT_SELECTION_QUESTION,
      pendingSelection.text,
      pendingSelection.pageNumber,
    )
    window.getSelection()?.removeAllRanges()
  }

  const handleClearSelection = () => {
    setPendingSelection(null)
    window.getSelection()?.removeAllRanges()
  }

  const handlePageSubmit = () => {
    const pageNumber = Number(pageInput)
    if (!Number.isFinite(pageNumber)) return
    scrollToPage(pageNumber)
  }

  const handleSubmitQuestion = () => {
    void submitQuestion(
      question,
      pendingSelection?.text,
      pendingSelection?.pageNumber,
    )
  }

  const startColumnResize = useCallback(
    (
      event: PointerEvent<HTMLDivElement>,
      side: 'chapter-sidebar' | 'ai-sidebar',
    ) => {
      event.preventDefault()
      event.currentTarget.setPointerCapture(event.pointerId)

      const startX = event.clientX
      const startChapterWidth = chapterSidebarWidth
      const startAiWidth = aiSidebarWidth

      const handlePointerMove = (moveEvent: globalThis.PointerEvent) => {
        const deltaX = moveEvent.clientX - startX
        if (side === 'chapter-sidebar') {
          setChapterSidebarWidth(
            clamp(
              startChapterWidth + deltaX,
              MIN_CHAPTER_SIDEBAR_WIDTH,
              MAX_CHAPTER_SIDEBAR_WIDTH,
            ),
          )
          return
        }

        setAiSidebarWidth(
          clamp(
            startAiWidth - deltaX,
            MIN_AI_SIDEBAR_WIDTH,
            MAX_AI_SIDEBAR_WIDTH,
          ),
        )
      }

      const handlePointerUp = () => {
        window.removeEventListener('pointermove', handlePointerMove)
        window.removeEventListener('pointerup', handlePointerUp)
        window.document.body.style.cursor = ''
        window.document.body.style.userSelect = ''
      }

      window.document.body.style.cursor = 'col-resize'
      window.document.body.style.userSelect = 'none'
      window.addEventListener('pointermove', handlePointerMove)
      window.addEventListener('pointerup', handlePointerUp, { once: true })
    },
    [aiSidebarWidth, chapterSidebarWidth],
  )

  return (
    <div
      className="grid h-full min-h-0 flex-1 overflow-hidden bg-muted/30"
      style={{
        gridTemplateColumns: `${chapterSidebarWidth}px ${DRAG_HANDLE_WIDTH}px minmax(0, 1fr) ${DRAG_HANDLE_WIDTH}px ${
          aiOpen ? aiSidebarWidth : 48
        }px`,
      }}
    >
      <CoursePdfSidebar
        projectId={projectId}
        activeDocumentId={document.id}
        document={document}
      />

      <ColumnResizeHandle
        label="调整章节 PDF 宽度"
        onPointerDown={(event) => startColumnResize(event, 'chapter-sidebar')}
      />

      <main className="flex h-full min-w-0 flex-1 flex-col overflow-hidden">
        <PdfToolbar
          currentPage={currentPage}
          numPages={numPages}
          pageInput={pageInput}
          scale={scale}
          aiOpen={aiOpen}
          onAiOpenChange={setAiOpen}
          onPageInputChange={setPageInput}
          onPageSubmit={handlePageSubmit}
          onPreviousPage={() => scrollToPage(currentPage - 1)}
          onNextPage={() => scrollToPage(currentPage + 1)}
          onZoomIn={() =>
            setScale((value) => clamp(value + SCALE_STEP, MIN_SCALE, MAX_SCALE))
          }
          onZoomOut={() =>
            setScale((value) => clamp(value - SCALE_STEP, MIN_SCALE, MAX_SCALE))
          }
        />

        <div
          ref={scrollRef}
          className="relative h-full min-h-0 flex-1 overflow-y-scroll overscroll-contain"
          onScroll={handleReaderScroll}
          onMouseUp={handleSelection}
          style={{ scrollbarGutter: 'stable' }}
        >
          <div
            ref={pagesLayerRef}
            className="relative mx-auto flex w-fit min-w-full flex-col items-center gap-5 px-6 py-6"
          >
            {pendingSelection?.marks.map((mark) => (
              <div
                key={mark.id}
                className="pointer-events-none absolute z-20 rounded-sm border-b-2 border-primary bg-primary/15"
                style={{
                  left: mark.left,
                  top: mark.top,
                  width: mark.width,
                  height: mark.height,
                }}
              />
            ))}

            {pendingSelection ? (
              <SelectionToolbar
                selection={pendingSelection}
                onAsk={handleAskSelection}
                onClear={handleClearSelection}
                onCopy={handleCopySelection}
              />
            ) : null}

            <PdfDocument
              file={fileSource}
              options={PDF_LOAD_OPTIONS}
              loading={
                <PdfLoadingShell
                  pageWidth={pageWidth}
                  pageHeight={Math.round(
                    pageWidth *
                      (pageAspectRatios[1] ?? PDF_PAGE_HEIGHT_RATIO),
                  )}
                  pageCount={presetPageCount}
                />
              }
              error={
                <div className="rounded-md border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
                  <div>PDF 加载失败</div>
                  {pdfLoadError ? (
                    <div className="mt-2 max-w-xl break-words text-xs opacity-80">
                      {pdfLoadError}
                    </div>
                  ) : null}
                </div>
              }
              onLoadError={(error) => {
                setPdfLoadError(error.message || String(error))
              }}
              onLoadSuccess={({ numPages: loadedPages }) => {
                setPdfLoadError(null)
                setNumPages(loadedPages)
                setCurrentPage(1)
                setPageInput('1')
                setPreloadReady(false)
                window.requestAnimationFrame(() => {
                  scrollRef.current?.scrollTo({
                    top: 0,
                    left: 0,
                    behavior: 'auto',
                  })
                  schedulePagePreload()
                })
              }}
            >
              {Array.from({ length: numPages }, (_, index) => {
                const pageNumber = index + 1
                const shouldRenderPage = renderedPageNumbers.has(pageNumber)
                const pageHeight = Math.round(
                  pageWidth *
                    (pageAspectRatios[pageNumber] ??
                      pageAspectRatios[1] ??
                      PDF_PAGE_HEIGHT_RATIO),
                )
                return (
                  <div
                    key={pageNumber}
                    ref={setPageRef(pageNumber)}
                    data-pdf-page-number={pageNumber}
                    className="overflow-hidden rounded-md border bg-background shadow-sm"
                    style={{
                      width: pageWidth,
                      minHeight: pageHeight,
                    }}
                  >
                    {shouldRenderPage ? (
                      <PdfPage
                        pageNumber={pageNumber}
                        width={pageWidth}
                        onLoadSuccess={handlePageLoadSuccess(pageNumber)}
                        loading={
                          <div
                            className="flex items-center justify-center text-sm text-muted-foreground"
                            style={{
                              width: pageWidth,
                              height: pageHeight,
                            }}
                          >
                            <Loader2Icon className="mr-2 size-4 animate-spin" />
                            正在加载页面...
                          </div>
                        }
                      />
                    ) : (
                      <div
                        className="flex items-center justify-center text-sm text-muted-foreground"
                        style={{
                          width: pageWidth,
                          height: pageHeight,
                        }}
                      >
                        第 {pageNumber} 页
                      </div>
                    )}
                  </div>
                )
              })}
            </PdfDocument>
          </div>
        </div>
      </main>

      <ColumnResizeHandle
        label="调整 AI 问答栏宽度"
        onPointerDown={(event) => startColumnResize(event, 'ai-sidebar')}
      />

      <AiSidebar
        activeSelection={pendingSelection}
        currentPage={currentPage}
        documentId={document.id}
        messages={messages}
        open={aiOpen}
        projectId={projectId}
        question={question}
        sending={sending}
        onQuestionChange={setQuestion}
        onOpenChange={setAiOpen}
        onSubmitQuestion={handleSubmitQuestion}
      />
    </div>
  )
}

const PdfBufferReader = ({
  document,
  fileBuffer,
  projectId,
}: {
  document: DocumentDto
  fileBuffer: ArrayBuffer
  projectId: string
}) => {
  const fileSource = useMemo<PdfFileSource>(
    // PDF.js transfers this TypedArray to its worker. Copy the ArrayBuffer so
    // the cached response remains usable if React remounts the reader.
    () => ({ data: new Uint8Array(fileBuffer.slice(0)) }),
    [fileBuffer],
  )

  return (
    <PdfReader
      document={document}
      fileSource={fileSource}
      projectId={projectId}
    />
  )
}

const PdfDocumentContent = ({
  document,
  documentId,
  projectId,
}: {
  document: DocumentDto
  documentId: string
  projectId: string
}) => {
  const fileResult = useAtomValue(
    documentFileBufferAtom(`${projectId}:${documentId}`),
  )

  return Result.builder(fileResult)
    .onInitialOrWaiting(() => <LoadingState label="正在下载 PDF..." />)
    .onFailure(() => (
      <div className="flex flex-1 items-center justify-center p-6">
        <div className="rounded-md border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          PDF 文件下载失败，请刷新页面重试
        </div>
      </div>
    ))
    .onSuccess((fileBuffer) => (
      <PdfBufferReader
        document={document}
        fileBuffer={fileBuffer}
        projectId={projectId}
      />
    ))
    .render()
}

const DocumentNotReadyState = ({
  document,
  projectId,
}: {
  document: DocumentDto
  projectId: string
}) => {
  const failed = document.status === 'failed'
  const Icon = failed ? CircleAlertIcon : ClockIcon
  const reprocessDocument = useAtomSet(reprocessDocumentAtom, {
    mode: 'promise',
  })
  const [retrying, setRetrying] = useState(false)

  const handleRetry = async () => {
    setRetrying(true)
    try {
      await reprocessDocument({ projectId, documentId: document.id })
      toast.success('已重新触发文档处理')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '重新处理失败')
    } finally {
      setRetrying(false)
    }
  }

  return (
    <div className="flex flex-1 items-center justify-center bg-muted/30 p-6">
      <div className="w-full max-w-md rounded-md border bg-background p-6 text-center shadow-sm">
        <div className="mx-auto mb-4 flex size-10 items-center justify-center rounded-md bg-muted text-muted-foreground">
          <Icon className={cn('size-5', !failed && 'animate-pulse')} />
        </div>
        <h2 className="text-base font-semibold">
          {failed ? '文档处理失败' : '文档正在处理'}
        </h2>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          {failed
            ? '后端没有完成 PDF 解析，请检查服务日志或重新上传。'
            : 'PDF 正在解析文本和页码。处理完成后再进入阅读器，可以避免页面反复重载。'}
        </p>
        <div className="mt-4 rounded-md bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
          当前状态：{document.status}
        </div>
        <Button
          type="button"
          className="mt-4"
          variant={failed ? 'default' : 'outline'}
          disabled={retrying}
          onClick={handleRetry}
        >
          {retrying ? (
            <Loader2Icon className="size-4 animate-spin" />
          ) : (
            <FileTextIcon className="size-4" />
          )}
          重新处理
        </Button>
      </div>
    </div>
  )
}

const IframeDocumentContent = ({
  documentId,
  projectId,
}: {
  documentId: string
  projectId: string
}) => {
  const previewResult = useAtomValue(
    documentPreviewAtom(`${projectId}:${documentId}`),
  )

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      {Result.builder(previewResult)
        .onInitialOrWaiting(() => <LoadingState label="正在加载预览..." />)
        .onFailure(() => (
          <div className="flex flex-1 items-center justify-center text-sm text-destructive">
            预览加载失败
          </div>
        ))
        .onSuccess((preview) => (
          <iframe
            src={preview.url}
            className="h-full w-full border-0"
            title="文档预览"
          />
        ))
        .render()}
    </div>
  )
}

const DocumentContent = ({ projectId, documentId }: DocumentContentProps) => {
  const documentResult = useAtomValue(
    documentAtom(`${projectId}:${documentId}`),
  )

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      {Result.builder(documentResult)
        .onInitialOrWaiting(() => <LoadingState label="正在加载文档..." />)
        .onFailure(() => (
          <div className="flex flex-1 items-center justify-center text-sm text-destructive">
            文档加载失败
          </div>
        ))
        .onSuccess((document) =>
          !isReadableDocument(document) ? (
            <DocumentNotReadyState document={document} projectId={projectId} />
          ) : isPdfDocument(document) ? (
            <PdfDocumentContent
              document={document}
              documentId={documentId}
              projectId={projectId}
            />
          ) : (
            <IframeDocumentContent
              documentId={documentId}
              projectId={projectId}
            />
          ),
        )
        .render()}
    </div>
  )
}

type DocumentDetailPageProps = {
  documentId: string
  projectId: string
}

export const DocumentDetailPage = ({
  documentId,
  projectId,
}: DocumentDetailPageProps) => {
  useDocumentPolling(projectId)

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <DocumentHeader documentId={documentId} projectId={projectId} />
      <DocumentContent projectId={projectId} documentId={documentId} />
    </div>
  )
}
