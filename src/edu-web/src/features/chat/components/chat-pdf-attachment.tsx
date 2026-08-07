import { DownloadIcon, FileTextIcon, Loader2Icon } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { resolveChatAttachmentUrl } from './chat-image-attachment'
import type { FilePartDto } from '@/integrations/api/client'
import { authClient } from '@/lib/auth-client'

export const ChatPdfAttachment = ({ file }: { file: FilePartDto }) => {
  const [isDownloading, setIsDownloading] = useState(false)

  const download = async () => {
    if (isDownloading) return
    setIsDownloading(true)
    try {
      const {
        data: { session },
      } = await authClient.auth.getSession()
      const response = await fetch(resolveChatAttachmentUrl(file.file_url), {
        headers: session?.access_token
          ? { Authorization: `Bearer ${session.access_token}` }
          : {},
      })
      if (!response.ok)
        throw new Error(`PDF request failed: ${response.status}`)
      const objectUrl = URL.createObjectURL(await response.blob())
      const link = document.createElement('a')
      link.href = objectUrl
      link.download = file.file_name || 'document.pdf'
      link.click()
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
    } catch {
      toast.error('PDF 下载失败，请稍后重试')
    } finally {
      setIsDownloading(false)
    }
  }

  return (
    <div className="flex min-w-64 items-center gap-3 rounded-lg border bg-card/90 px-3 py-2 text-card-foreground">
      <div className="flex size-9 shrink-0 items-center justify-center rounded-md bg-red-50 text-red-600 dark:bg-red-950/40 dark:text-red-300">
        <FileTextIcon className="size-5" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium">{file.file_name}</div>
        <div className="text-xs text-muted-foreground">PDF 文档</div>
      </div>
      <button
        type="button"
        onClick={download}
        disabled={isDownloading}
        className="rounded-md p-2 text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-50"
        aria-label={`下载 ${file.file_name}`}
      >
        {isDownloading ? (
          <Loader2Icon className="size-4 animate-spin" />
        ) : (
          <DownloadIcon className="size-4" />
        )}
      </button>
    </div>
  )
}
