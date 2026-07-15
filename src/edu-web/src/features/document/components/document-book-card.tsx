import { useAtomSet } from '@effect-atom/atom-react'
import { Link } from '@tanstack/react-router'
import { format } from 'date-fns'
import {
  BookOpenIcon,
  CheckCircle2Icon,
  FileTextIcon,
  Loader2Icon,
  MoreVerticalIcon,
  TrashIcon,
  XCircleIcon,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Document as PdfDocument, Page as PdfPage, pdfjs } from 'react-pdf'
import type { LucideIcon } from 'lucide-react'
import type { DocumentDto, DocumentStatus } from '@/integrations/api/client'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useConfirmationDialog } from '@/components/confirmation-dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { deleteDocumentAtom } from '@/data-acess/document'
import { env } from '@/env'
import { cn } from '@/lib/utils'

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

type Props = {
  accessToken: string | null | undefined
  document: DocumentDto
}

type PdfFileSource =
  | string
  | {
      url: string
      httpHeaders: Record<string, string>
      withCredentials: false
    }

const serverUrl = (env.VITE_SERVER_URL ?? 'http://localhost:8000').replace(
  /\/$/,
  '',
)

const getStatusInfo = (
  status: typeof DocumentStatus.Type,
): {
  label: string
  variant: 'default' | 'secondary' | 'destructive'
  icon: LucideIcon
} => {
  switch (status) {
    case 'processed':
    case 'indexed':
      return {
        label: '就绪',
        variant: 'default',
        icon: CheckCircle2Icon,
      }
    case 'failed':
      return {
        label: '失败',
        variant: 'destructive',
        icon: XCircleIcon,
      }
    default:
      return {
        label: '处理中',
        variant: 'secondary',
        icon: Loader2Icon,
      }
  }
}

const getDisplayTitle = (document: DocumentDto) => {
  const metadataTitle = document.metadata.display_title
  if (typeof metadataTitle === 'string' && metadataTitle.trim()) {
    return metadataTitle.trim()
  }

  return document.file_name.replace(/\.[^.]+$/, '')
}

const formatFileSize = (size: number) => {
  if (size < 1024 * 1024) return `${Math.max(1, Math.round(size / 1024))} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

const DefaultCover = ({
  extension,
  loading = false,
}: {
  extension: string
  loading?: boolean
}) => (
  <div className="absolute inset-0 flex flex-col items-center justify-center bg-gradient-to-br from-slate-100 via-slate-50 to-slate-200 text-slate-500 dark:from-slate-800 dark:via-slate-900 dark:to-slate-950 dark:text-slate-400">
    <div className="flex size-14 items-center justify-center rounded-2xl border border-white/60 bg-white/70 shadow-sm dark:border-white/10 dark:bg-white/5">
      {loading ? (
        <Loader2Icon className="size-7 animate-spin" />
      ) : (
        <FileTextIcon className="size-7" />
      )}
    </div>
    <span className="mt-4 rounded-full border bg-background/75 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.2em] shadow-sm">
      {extension || 'DOC'}
    </span>
  </div>
)

const PdfFirstPageCover = ({
  accessToken,
  document,
}: {
  accessToken: string | null | undefined
  document: DocumentDto
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const [coverWidth, setCoverWidth] = useState(0)
  const [shouldLoad, setShouldLoad] = useState(false)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const resizeObserver = new ResizeObserver(([entry]) => {
      setCoverWidth(Math.floor(entry.contentRect.width))
    })
    resizeObserver.observe(container)

    const visibilityObserver = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return
        setShouldLoad(true)
        visibilityObserver.disconnect()
      },
      { rootMargin: '320px' },
    )
    visibilityObserver.observe(container)

    return () => {
      resizeObserver.disconnect()
      visibilityObserver.disconnect()
    }
  }, [])

  const fileSource = useMemo<PdfFileSource>(() => {
    const fileUrl = `${serverUrl}/api/v1/projects/${encodeURIComponent(
      document.project_id ?? '',
    )}/documents/${encodeURIComponent(document.id)}/file`

    if (!accessToken) return fileUrl
    return {
      url: fileUrl,
      httpHeaders: { Authorization: `Bearer ${accessToken}` },
      withCredentials: false,
    }
  }, [accessToken, document.id, document.project_id])

  const waitingForSession = accessToken === undefined
  const renderPdf =
    shouldLoad && coverWidth > 0 && !waitingForSession && !failed

  return (
    <div
      ref={containerRef}
      className="absolute inset-0 overflow-hidden bg-white"
    >
      {!renderPdf && (
        <DefaultCover extension="PDF" loading={!failed && shouldLoad} />
      )}
      {renderPdf && (
        <PdfDocument
          file={fileSource}
          loading={<DefaultCover extension="PDF" loading />}
          error={<DefaultCover extension="PDF" />}
          onLoadError={() => setFailed(true)}
          className="flex min-h-full items-start justify-center"
        >
          <PdfPage
            pageNumber={1}
            width={coverWidth}
            renderAnnotationLayer={false}
            renderTextLayer={false}
            loading={<DefaultCover extension="PDF" loading />}
            onRenderError={() => setFailed(true)}
          />
        </PdfDocument>
      )}
    </div>
  )
}

export const DocumentBookCard = ({ accessToken, document }: Props) => {
  const deleteDocument = useAtomSet(deleteDocumentAtom, { mode: 'promise' })
  const confirmationDialog = useConfirmationDialog()
  const statusInfo = getStatusInfo(document.status)
  const StatusIcon = statusInfo.icon
  const isPdf = document.file_type.toLowerCase() === 'pdf'
  const title = getDisplayTitle(document)

  const handleDelete = async (event: React.MouseEvent) => {
    event.preventDefault()
    event.stopPropagation()

    const confirmed = await confirmationDialog.open({
      title: '删除文档',
      description: `确定要删除“${document.file_name}”吗？此操作无法撤销。`,
      confirmLabel: '删除',
      cancelLabel: '取消',
      variant: 'destructive',
    })

    if (confirmed) {
      await deleteDocument({
        documentId: document.id,
        projectId: document.project_id ?? '',
      })
    }
  }

  return (
    <li className="group relative min-w-0">
      <Link
        to="/dashboard/p/$projectId/d/$documentId"
        params={{
          projectId: document.project_id ?? '',
          documentId: document.id,
        }}
        aria-label={`打开《${title}》`}
        className="block rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-4"
      >
        <div className="relative mx-auto aspect-[3/4] w-full max-w-56 transition-transform duration-200 ease-out group-hover:-translate-y-1">
          <div className="absolute inset-y-1 -right-2 w-4 rounded-r-md border bg-muted shadow-sm" />
          <div className="absolute inset-0 overflow-hidden rounded-sm border bg-muted shadow-[0_12px_28px_-12px_rgba(15,23,42,0.55)] transition-shadow duration-200 group-hover:shadow-[0_18px_34px_-12px_rgba(15,23,42,0.65)]">
            {isPdf ? (
              <PdfFirstPageCover
                accessToken={accessToken}
                document={document}
              />
            ) : (
              <DefaultCover extension={document.file_type} />
            )}
            <div className="pointer-events-none absolute inset-y-0 left-0 w-3 bg-gradient-to-r from-black/20 via-black/5 to-transparent" />
            <div className="pointer-events-none absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-black/20 to-transparent" />
          </div>
          <Badge
            variant={statusInfo.variant}
            className="absolute bottom-2 left-2 z-10 gap-1 border-background/50 shadow-sm"
          >
            <StatusIcon
              className={cn(
                'size-3',
                statusInfo.variant === 'secondary' && 'animate-spin',
              )}
            />
            {statusInfo.label}
          </Badge>
        </div>

        <div className="mx-auto mt-4 max-w-56 px-0.5">
          <h2 className="line-clamp-2 min-h-10 text-sm font-semibold leading-5 text-foreground">
            {title}
          </h2>
          <div className="mt-1.5 flex items-center gap-1.5 text-xs text-muted-foreground">
            <BookOpenIcon className="size-3.5 shrink-0" />
            <span>{formatFileSize(document.file_size)}</span>
            <span aria-hidden="true">·</span>
            <time dateTime={document.uploaded_at}>
              {format(new Date(document.uploaded_at), 'yyyy/MM/dd')}
            </time>
          </div>
        </div>
      </Link>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            type="button"
            variant="secondary"
            size="icon"
            aria-label={`管理《${title}》`}
            className="absolute right-2 top-2 z-20 size-8 border bg-background/85 opacity-0 shadow-sm backdrop-blur-sm transition-opacity group-focus-within:opacity-100 group-hover:opacity-100"
            onClick={(event) => event.stopPropagation()}
          >
            <MoreVerticalIcon className="size-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={handleDelete} variant="destructive">
            <TrashIcon className="size-4" />
            <span>删除</span>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </li>
  )
}
