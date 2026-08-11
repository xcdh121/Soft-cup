import { Result, useAtomValue } from '@effect-atom/atom-react'
import { Link } from '@tanstack/react-router'
import { ArrowLeftIcon, DownloadIcon, Loader2Icon } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { SidebarTrigger } from '@/components/ui/sidebar'
import { generatedResourceAtom } from '@/data-acess/resource-package'
import { env } from '@/env'
import { ResourceResultPreview } from '@/features/resource-package/components/resource-result-preview'

const typeLabels: Record<string, string> = {
  lecture_note: '笔记',
  flashcards: '闪卡',
  mind_map: '思维导图',
  video_recommendations: '视频推荐',
  pptx: 'PPT',
  ppt_outline: 'PPT 大纲',
}

const resolveFileUrl = (url: string) => {
  if (/^(?:https?:|data:|blob:)/i.test(url)) return url
  const baseUrl = (env.VITE_SERVER_URL ?? window.location.origin).replace(
    /\/$/,
    '',
  )
  return `${baseUrl}${url.startsWith('/') ? '' : '/'}${url}`
}

export const GeneratedResourceDetailPage = ({
  projectId,
  resourceId,
}: {
  projectId: string
  resourceId: string
}) => {
  const resourceResult = useAtomValue(
    generatedResourceAtom(`${projectId}:${resourceId}`),
  )
  const resource = Result.isSuccess(resourceResult)
    ? resourceResult.value
    : null

  return (
    <div className="min-h-full bg-background">
      <header className="sticky top-0 z-10 flex h-14 items-center border-b bg-background/95 px-5 backdrop-blur sm:px-8">
        <SidebarTrigger />
        <Button variant="ghost" size="icon" className="ml-2 size-8" asChild>
          <Link
            to="/dashboard/p/$projectId/my-resources"
            params={{ projectId }}
          >
            <ArrowLeftIcon />
            <span className="sr-only">返回我的资源</span>
          </Link>
        </Button>
        <Separator
          orientation="vertical"
          className="mx-3 data-[orientation=vertical]:h-4"
        />
        <span className="truncate text-sm font-medium">
          {resource?.title ?? '资源详情'}
        </span>
      </header>

      <main className="mx-auto w-full max-w-5xl px-5 py-8 sm:px-8 lg:py-10">
        {resourceResult.waiting ? (
          <div className="flex items-center justify-center gap-2 py-20 text-sm text-muted-foreground">
            <Loader2Icon className="size-4 animate-spin" />
            正在加载资源...
          </div>
        ) : Result.isFailure(resourceResult) || !resource ? (
          <div className="rounded-xl border border-destructive/30 px-6 py-14 text-center text-sm text-destructive">
            资源不存在或暂时无法加载。
          </div>
        ) : (
          <>
            <section className="mb-7 flex flex-col justify-between gap-4 border-b pb-6 sm:flex-row sm:items-end">
              <div>
                <Badge variant="outline" className="mb-3 text-primary">
                  {typeLabels[resource.resource_type] ?? resource.resource_type}
                </Badge>
                <h1 className="text-2xl font-semibold tracking-tight">
                  {resource.title}
                </h1>
                {resource.summary ? (
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">
                    {resource.summary}
                  </p>
                ) : null}
              </div>
              {resource.file_url ? (
                <Button variant="outline" asChild>
                  <a
                    href={resolveFileUrl(resource.file_url)}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <DownloadIcon />
                    打开文件
                  </a>
                </Button>
              ) : null}
            </section>

            <section className="rounded-xl border bg-card p-5 shadow-sm sm:p-7">
              <ResourceResultPreview
                projectId={projectId}
                resource={resource}
                truncateText={false}
              />
            </section>
          </>
        )}
      </main>
    </div>
  )
}
