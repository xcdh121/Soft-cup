import { FileImageIcon, Loader2Icon } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { FilePartDto } from '@/integrations/api/client'
import { env } from '@/env'
import { authClient } from '@/lib/auth-client'

const isInlineImageUrl = (url: string) =>
  url.startsWith('data:') || url.startsWith('blob:')

export const resolveChatAttachmentUrl = (fileUrl: string) => {
  if (/^https?:\/\//i.test(fileUrl) || isInlineImageUrl(fileUrl)) {
    return fileUrl
  }
  const baseUrl = (env.VITE_SERVER_URL ?? window.location.origin).replace(
    /\/$/,
    '',
  )
  return `${baseUrl}${fileUrl.startsWith('/') ? '' : '/'}${fileUrl}`
}

export const ChatImageAttachment = ({ file }: { file: FilePartDto }) => {
  const inlineUrl = isInlineImageUrl(file.file_url) ? file.file_url : null
  const [imageUrl, setImageUrl] = useState<string | null>(inlineUrl)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (inlineUrl) {
      setImageUrl(inlineUrl)
      setFailed(false)
      return
    }
    if (!file.file_url) {
      setImageUrl(null)
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
        const response = await fetch(resolveChatAttachmentUrl(file.file_url), {
          headers,
          signal: controller.signal,
        })
        if (!response.ok)
          throw new Error(`Image request failed: ${response.status}`)
        objectUrl = URL.createObjectURL(await response.blob())
        if (controller.signal.aborted) {
          URL.revokeObjectURL(objectUrl)
          objectUrl = null
          return
        }
        setImageUrl(objectUrl)
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
  }, [file.file_url, inlineUrl])

  return (
    <figure className="max-w-md overflow-hidden rounded-lg border bg-card/90 text-card-foreground">
      {imageUrl ? (
        <a href={imageUrl} target="_blank" rel="noopener noreferrer">
          <img
            src={imageUrl}
            alt={file.file_name}
            className="max-h-80 w-full object-contain"
          />
        </a>
      ) : (
        <div className="flex h-36 min-w-56 items-center justify-center text-muted-foreground">
          {failed ? (
            <FileImageIcon className="size-8 opacity-60" />
          ) : (
            <Loader2Icon className="size-5 animate-spin" />
          )}
        </div>
      )}
      <figcaption className="truncate border-t px-3 py-2 text-xs text-muted-foreground">
        {failed && !file.file_url ? '历史图片未保存 · ' : ''}
        {file.file_name}
      </figcaption>
    </figure>
  )
}
