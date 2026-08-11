import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import { Link } from '@tanstack/react-router'
import {
  ArchiveIcon,
  ArrowUpRightIcon,
  Code2Icon,
  DownloadIcon,
  FileTextIcon,
  Layers3Icon,
  ListChecksIcon,
  ListIcon,
  Loader2Icon,
  NetworkIcon,
  PresentationIcon,
  RefreshCwIcon,
  SearchIcon,
  VideoIcon,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { LucideIcon } from 'lucide-react'
import type {
  GeneratedResource,
  ResourcePackage,
  ResourceType,
} from '@/data-acess/resource-package'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { SidebarTrigger } from '@/components/ui/sidebar'
import {
  reconcileResourcePackagesAtom,
  resourcePackagesAtom,
} from '@/data-acess/resource-package'
import { env } from '@/env'
import { cn } from '@/lib/utils'

const RESOURCE_TYPES = [
  'lecture_note',
  'flashcards',
  'mind_map',
  'practice_set',
  'programming_questions',
  'video_recommendations',
  'pptx',
  'ppt_outline',
] as const satisfies ReadonlyArray<ResourceType>

type SupportedResourceType = (typeof RESOURCE_TYPES)[number]
type ResourceFilter = 'all' | SupportedResourceType
type ResourceItem = {
  resource: GeneratedResource
  resourcePackage: ResourcePackage
}

type ResourceMeta = {
  label: string
  icon: LucideIcon
}

const RESOURCE_META: Record<SupportedResourceType, ResourceMeta> = {
  lecture_note: { label: '笔记', icon: FileTextIcon },
  flashcards: { label: '闪卡', icon: Layers3Icon },
  mind_map: { label: '思维导图', icon: NetworkIcon },
  practice_set: { label: '题库', icon: ListChecksIcon },
  programming_questions: { label: '编程练习', icon: Code2Icon },
  video_recommendations: { label: '视频推荐', icon: VideoIcon },
  pptx: { label: 'PPT', icon: PresentationIcon },
  ppt_outline: { label: 'PPT 大纲', icon: ListIcon },
}

const STATUS_META: Record<
  GeneratedResource['status'],
  { label: string; className: string }
> = {
  completed: {
    label: '已完成',
    className:
      'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/50 dark:text-emerald-300',
  },
  generating: {
    label: '生成中',
    className:
      'border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-900 dark:bg-blue-950/50 dark:text-blue-300',
  },
  pending: {
    label: '等待中',
    className:
      'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950/50 dark:text-amber-300',
  },
  failed: {
    label: '生成失败',
    className:
      'border-red-200 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950/50 dark:text-red-300',
  },
}

const isSupportedResourceType = (
  resourceType: ResourceType,
): resourceType is SupportedResourceType =>
  RESOURCE_TYPES.includes(resourceType as SupportedResourceType)

const formatDate = (value: string) =>
  new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date(value))

const resolveFileUrl = (url: string) => {
  if (/^(?:https?:|data:|blob:)/i.test(url)) return url
  const baseUrl = (env.VITE_SERVER_URL ?? window.location.origin).replace(
    /\/$/,
    '',
  )
  return `${baseUrl}${url.startsWith('/') ? '' : '/'}${url}`
}

const ResourceAction = ({ item }: { item: ResourceItem }) => {
  const { resource } = item

  if (resource.resource_type === 'programming_questions') {
    return (
      <Button variant="ghost" size="sm" asChild>
        <Link
          to="/dashboard/p/$projectId/programming/$resourceId"
          params={{
            projectId: resource.project_id,
            resourceId: resource.id,
          }}
        >
          开始编程
          <ArrowUpRightIcon />
        </Link>
      </Button>
    )
  }

  if (resource.resource_type === 'practice_set') {
    const targetId = resource.content_json?.target_id
    if (typeof targetId === 'string' && targetId) {
      return (
        <Button variant="ghost" size="sm" asChild>
          <Link
            to="/dashboard/p/$projectId/q/$quizId"
            params={{
              projectId: resource.project_id,
              quizId: targetId,
            }}
          >
            开始练习
            <ArrowUpRightIcon />
          </Link>
        </Button>
      )
    }
  }

  if (resource.resource_type === 'mind_map') {
    return (
      <Button variant="ghost" size="sm" asChild>
        <Link
          to="/dashboard/p/$projectId/r/$resourceId"
          params={{
            projectId: resource.project_id,
            resourceId: resource.id,
          }}
        >
          查看
          <ArrowUpRightIcon />
        </Link>
      </Button>
    )
  }

  if (resource.resource_type === 'pptx' && resource.file_url) {
    return (
      <Button variant="ghost" size="sm" asChild>
        <a
          href={resolveFileUrl(resource.file_url)}
          target="_blank"
          rel="noreferrer"
        >
          <DownloadIcon />
          打开
        </a>
      </Button>
    )
  }

  if (
    resource.resource_type === 'ppt_outline' ||
    resource.resource_type === 'video_recommendations'
  ) {
    return (
      <Button variant="ghost" size="sm" asChild>
        <Link
          to="/dashboard/p/$projectId/r/$resourceId"
          params={{
            projectId: resource.project_id,
            resourceId: resource.id,
          }}
        >
          查看
          <ArrowUpRightIcon />
        </Link>
      </Button>
    )
  }

  if (resource.preview_url) {
    return (
      <Button variant="ghost" size="sm" asChild>
        <a href={resource.preview_url}>
          查看
          <ArrowUpRightIcon />
        </a>
      </Button>
    )
  }

  return (
    <Button variant="ghost" size="sm" asChild>
      <Link
        to="/dashboard/p/$projectId/r/$resourceId"
        params={{
          projectId: resource.project_id,
          resourceId: resource.id,
        }}
      >
        查看
        <ArrowUpRightIcon />
      </Link>
    </Button>
  )
}

const ResourceRow = ({ item }: { item: ResourceItem }) => {
  const { resource, resourcePackage } = item
  const meta = RESOURCE_META[resource.resource_type as SupportedResourceType]
  const status = STATUS_META[resource.status]
  const Icon = meta.icon

  return (
    <article className="grid gap-3 border-b border-border/70 px-4 py-4 transition-colors last:border-b-0 hover:bg-muted/30 lg:grid-cols-[minmax(0,2fr)_8rem_minmax(10rem,1fr)_7.5rem_6.5rem_5rem] lg:items-center lg:gap-4">
      <div className="flex min-w-0 items-center gap-3">
        <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/[0.07] text-primary">
          <Icon className="size-4" />
        </div>
        <div className="min-w-0">
          <h2 className="truncate text-sm font-medium text-foreground">
            {resource.title}
          </h2>
          <p className="mt-0.5 truncate text-xs text-muted-foreground lg:max-w-xl">
            {resource.summary || '暂无资源摘要'}
          </p>
        </div>
      </div>

      <div className="flex items-center justify-between lg:block">
        <span className="text-xs text-muted-foreground lg:hidden">类型</span>
        <span className="text-sm">{meta.label}</span>
      </div>
      <div className="flex min-w-0 items-center justify-between lg:block">
        <span className="text-xs text-muted-foreground lg:hidden">
          所属资源包
        </span>
        <span className="max-w-56 truncate text-sm text-muted-foreground lg:block">
          {resourcePackage.title}
        </span>
      </div>
      <div className="flex items-center justify-between lg:block">
        <span className="text-xs text-muted-foreground lg:hidden">
          更新时间
        </span>
        <span className="text-sm text-muted-foreground">
          {formatDate(resource.updated_at)}
        </span>
      </div>
      <div className="flex items-center justify-between lg:block">
        <span className="text-xs text-muted-foreground lg:hidden">状态</span>
        <Badge variant="outline" className={status.className}>
          {status.label}
        </Badge>
      </div>
      <div className="flex justify-end">
        <ResourceAction item={item} />
      </div>
    </article>
  )
}

export const MyResourcesPage = ({ projectId }: { projectId: string }) => {
  const packagesResult = useAtomValue(resourcePackagesAtom(projectId))
  const reconcileResources = useAtomSet(reconcileResourcePackagesAtom, {
    mode: 'promise',
  })
  const reconciledProjectRef = useRef<string | null>(null)
  const [activeFilter, setActiveFilter] = useState<ResourceFilter>('all')
  const [query, setQuery] = useState('')
  const [isRefreshing, setIsRefreshing] = useState(false)

  useEffect(() => {
    if (!projectId || reconciledProjectRef.current === projectId) return
    reconciledProjectRef.current = projectId
    void reconcileResources(projectId).catch(() => undefined)
  }, [projectId, reconcileResources])

  const packages = Result.isSuccess(packagesResult) ? packagesResult.value : []
  const resources = useMemo<Array<ResourceItem>>(
    () =>
      packages
        .flatMap((resourcePackage) =>
          resourcePackage.resources
            .filter((resource) =>
              isSupportedResourceType(resource.resource_type),
            )
            .map((resource) => ({ resource, resourcePackage })),
        )
        .sort(
          (left, right) =>
            new Date(right.resource.updated_at).getTime() -
            new Date(left.resource.updated_at).getTime(),
        ),
    [packages],
  )
  const typeCounts = useMemo(
    () =>
      Object.fromEntries(
        RESOURCE_TYPES.map((type) => [
          type,
          resources.filter((item) => item.resource.resource_type === type)
            .length,
        ]),
      ) as Record<SupportedResourceType, number>,
    [resources],
  )
  const normalizedQuery = query.trim().toLocaleLowerCase('zh-CN')
  const filteredResources = resources.filter(
    ({ resource, resourcePackage }) => {
      if (activeFilter !== 'all' && resource.resource_type !== activeFilter) {
        return false
      }
      if (!normalizedQuery) return true
      return [resource.title, resource.summary, resourcePackage.title]
        .filter(Boolean)
        .some((value) =>
          String(value).toLocaleLowerCase('zh-CN').includes(normalizedQuery),
        )
    },
  )

  const handleRefresh = async () => {
    setIsRefreshing(true)
    try {
      await reconcileResources(projectId)
    } finally {
      setIsRefreshing(false)
    }
  }

  return (
    <div className="min-h-full bg-background">
      <header className="sticky top-0 z-10 flex h-14 items-center border-b bg-background/95 px-5 backdrop-blur sm:px-8">
        <SidebarTrigger />
        <Separator
          orientation="vertical"
          className="mx-3 data-[orientation=vertical]:h-4"
        />
        <span className="text-sm font-medium">我的资源</span>
      </header>

      <main className="mx-auto w-full max-w-7xl px-5 py-7 sm:px-8 lg:px-10">
        <section className="flex flex-col justify-between gap-4 border-b pb-6 sm:flex-row sm:items-end">
          <div>
            <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
              <ArchiveIcon className="size-4 text-primary" />
              Resource workspace
            </div>
            <h1 className="text-2xl font-semibold tracking-tight">我的资源</h1>
            <p className="mt-1.5 text-sm text-muted-foreground">
              集中查看当前项目生成的学习内容。
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-muted-foreground">
              共{' '}
              <strong className="font-semibold text-primary">
                {resources.length}
              </strong>{' '}
              项
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={isRefreshing}
              onClick={() => void handleRefresh()}
            >
              <RefreshCwIcon className={cn(isRefreshing && 'animate-spin')} />
              刷新
            </Button>
          </div>
        </section>

        <section className="mt-6">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
            <Select
              value={activeFilter}
              onValueChange={(value) =>
                setActiveFilter(value as ResourceFilter)
              }
            >
              <SelectTrigger className="w-full bg-card sm:w-52">
                <SelectValue placeholder="选择资源类型" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">
                  全部资源（{resources.length}）
                </SelectItem>
                {RESOURCE_TYPES.map((type) => (
                  <SelectItem key={type} value={type}>
                    {RESOURCE_META[type].label}（{typeCounts[type]}）
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <div className="relative w-full sm:max-w-sm">
              <SearchIcon className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="搜索资源或资源包"
                className="bg-card pl-9"
              />
            </div>
          </div>

          {packagesResult.waiting ? (
            <div className="flex items-center justify-center gap-2 rounded-xl border py-16 text-sm text-muted-foreground">
              <Loader2Icon className="size-4 animate-spin" />
              正在加载资源...
            </div>
          ) : Result.isFailure(packagesResult) ? (
            <div className="rounded-xl border border-destructive/30 py-14 text-center text-sm text-destructive">
              资源加载失败，请确认服务已启动后重试。
            </div>
          ) : filteredResources.length > 0 ? (
            <div className="overflow-hidden rounded-xl border bg-card shadow-[0_1px_2px_rgba(23,70,120,0.04)]">
              <div className="hidden grid-cols-[minmax(0,2fr)_8rem_minmax(10rem,1fr)_7.5rem_6.5rem_5rem] gap-4 border-b bg-muted/35 px-4 py-2.5 text-xs font-medium text-muted-foreground lg:grid">
                <span>资源名称</span>
                <span>类型</span>
                <span>所属资源包</span>
                <span>更新时间</span>
                <span>状态</span>
                <span className="text-right">操作</span>
              </div>
              {filteredResources.map((item) => (
                <ResourceRow key={item.resource.id} item={item} />
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-dashed py-16 text-center">
              <ArchiveIcon className="mx-auto size-7 text-primary/70" />
              <h2 className="mt-3 text-sm font-medium">
                {activeFilter !== 'all' || query
                  ? '没有匹配的资源'
                  : '暂无学习资源'}
              </h2>
              <p className="mt-1.5 text-xs text-muted-foreground">
                {activeFilter !== 'all' || query
                  ? '请调整筛选条件后再试。'
                  : '资源生成完成后会自动显示在这里。'}
              </p>
            </div>
          )}
        </section>
      </main>
    </div>
  )
}
