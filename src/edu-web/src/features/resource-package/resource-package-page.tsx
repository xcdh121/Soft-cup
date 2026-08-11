import { useEffect, useMemo, useState } from 'react'
import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import { Link, useNavigate } from '@tanstack/react-router'
import {
  BookPlusIcon,
  CheckCircle2Icon,
  ExternalLinkIcon,
  Loader2Icon,
  TagsIcon,
} from 'lucide-react'
import type {
  DifficultyLevel,
  GeneratedResource,
  GeneratedResourceStatus,
  ResourcePackage,
  ResourceType,
} from '@/data-acess/resource-package'
import type { ProjectCourseOutline } from '@/data-acess/course-library'
import { Badge } from '@/components/ui/badge'
import { Response } from '@/components/ai-elements/response'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  addGeneratedResourceToCourseAtom,
  projectCourseOutlineAtom,
} from '@/data-acess/course-library'
import {
  generateResourcePackageAtom,
  generatedResourcesAtom,
  refreshResourcePackagesAtom,
  resourcePackageProgressAtom,
  resourcePackagesAtom,
} from '@/data-acess/resource-package'
import { ProjectHeader } from '@/features/project/components/project-header'
import { ResourceResultPreview } from '@/features/resource-package/components/resource-result-preview'
import { cn } from '@/lib/utils'
import { useResourcePackageStream } from '@/hooks/use-resource-package-stream'

const RESOURCE_TYPE_OPTIONS: Array<{
  value: ResourceType
  label: string
  description: string
}> = [
  {
    value: 'lecture_note',
    label: '笔记',
    description: '结构化笔记',
  },
  {
    value: 'mind_map',
    label: '思维导图',
    description: '知识结构图',
  },
  {
    value: 'practice_set',
    label: '题库',
    description: '分层练习题',
  },
  {
    value: 'flashcards',
    label: '闪卡',
    description: '记忆卡片',
  },
  {
    value: 'ppt_outline',
    label: 'PPT 大纲',
    description: '演示大纲',
  },
  {
    value: 'image',
    label: 'AI 图片',
    description: '讯飞文生图',
  },
  {
    value: 'pptx',
    label: 'PPTX',
    description: '演示文件',
  },
  {
    value: 'programming_questions',
    label: '编程练习',
    description: '编程练习题',
  },
  {
    value: 'video_recommendations',
    label: '视频推荐',
    description: '学习视频',
  },
]

const DIFFICULTY_STAGES: Array<{
  value: DifficultyLevel
  label: string
  color: string
  animationDuration: string
}> = [
  {
    value: 'beginner',
    label: '基础',
    color: '#93c5fd',
    animationDuration: '2.4s',
  },
  {
    value: 'beginner',
    label: '入门',
    color: '#60a5fa',
    animationDuration: '2s',
  },
  {
    value: 'intermediate',
    label: '进阶',
    color: '#3b82f6',
    animationDuration: '1.5s',
  },
  {
    value: 'advanced',
    label: '熟练',
    color: '#2563eb',
    animationDuration: '1s',
  },
  {
    value: 'advanced',
    label: '挑战',
    color: '#1d4ed8',
    animationDuration: '0.45s',
  },
]

const resourceTypeLabelMap = new Map(
  RESOURCE_TYPE_OPTIONS.map((option) => [option.value, option.label]),
)

const statusToneMap: Record<
  ResourcePackage['status'] | GeneratedResource['status'],
  'default' | 'secondary' | 'destructive' | 'outline'
> = {
  draft: 'outline',
  generating: 'secondary',
  completed: 'default',
  failed: 'destructive',
  pending: 'outline',
}

const CourseResourceLinker = ({
  resource,
  courseOutline,
}: {
  resource: GeneratedResource
  courseOutline: ProjectCourseOutline | null
}) => {
  const addToCourse = useAtomSet(addGeneratedResourceToCourseAtom, {
    mode: 'promise',
  })
  const inferredPointId =
    courseOutline?.knowledgePoints.find((point) =>
      resource.knowledge_point_ids.includes(point.id),
    )?.id ?? ''
  const [knowledgePointId, setKnowledgePointId] = useState(inferredPointId)
  const [isAdding, setIsAdding] = useState(false)
  const [added, setAdded] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setKnowledgePointId(inferredPointId)
    setAdded(false)
    setError(null)
  }, [inferredPointId, resource.id])

  if (
    !courseOutline?.courseId ||
    resource.resource_type === 'image' ||
    resource.status !== 'completed'
  ) {
    return null
  }

  const courseId = courseOutline.courseId
  const selectedPoint = courseOutline.knowledgePoints.find(
    (point) => point.id === knowledgePointId,
  )

  const handleAdd = async () => {
    if (!selectedPoint) return
    setIsAdding(true)
    setError(null)
    try {
      await addToCourse({
        courseId,
        chapterId: selectedPoint.chapter_id,
        knowledgePointIds: [selectedPoint.id],
        resource,
      })
      setAdded(true)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '加入课程失败')
    } finally {
      setIsAdding(false)
    }
  }

  return (
    <div className="mt-3 rounded-lg border bg-background p-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <Select
          value={knowledgePointId || undefined}
          onValueChange={(value) => {
            setKnowledgePointId(value)
            setAdded(false)
          }}
        >
          <SelectTrigger className="min-w-0 flex-1" aria-label="关联知识点">
            <SelectValue placeholder="选择要加入的课程知识点" />
          </SelectTrigger>
          <SelectContent>
            {courseOutline.knowledgePoints.map((point) => {
              const chapter = courseOutline.chapters.find(
                (item) => item.id === point.chapter_id,
              )
              return (
                <SelectItem key={point.id} value={point.id}>
                  {chapter ? `${chapter.title} · ` : ''}
                  {point.name}
                </SelectItem>
              )
            })}
          </SelectContent>
        </Select>
        <Button
          type="button"
          variant={added ? 'secondary' : 'outline'}
          size="sm"
          disabled={!selectedPoint || isAdding || added}
          onClick={() => void handleAdd()}
        >
          {isAdding ? (
            <Loader2Icon className="size-4 animate-spin" />
          ) : added ? (
            <CheckCircle2Icon className="size-4" />
          ) : (
            <BookPlusIcon className="size-4" />
          )}
          {added ? '已加入课程' : '加入课程'}
        </Button>
      </div>
      {error ? <p className="mt-2 text-xs text-destructive">{error}</p> : null}
      <p className="mt-2 text-xs text-muted-foreground">
        只新增课程资源关联，不会修改课程、章节或知识点的原有描述。
      </p>
    </div>
  )
}

const ResourcePackageSelector = ({
  projectId,
  selectedPackageId,
  livePackage,
  onSelect,
}: {
  projectId: string
  selectedPackageId: string | null
  livePackage?: ResourcePackage
  onSelect: (resourcePackage: ResourcePackage | null) => void
}) => {
  const packagesResult = useAtomValue(resourcePackagesAtom(projectId))
  const persistedPackages = Result.isSuccess(packagesResult)
    ? packagesResult.value
    : []
  const packages = livePackage
    ? [
        livePackage,
        ...persistedPackages.filter((item) => item.id !== livePackage.id),
      ]
    : persistedPackages
  const [category, setCategory] = useState<'all' | ResourceType>('all')
  const filteredPackages = packages.filter(
    (resourcePackage) =>
      category === 'all' ||
      resourcePackage.preferred_resource_types.includes(category) ||
      resourcePackage.resources.some(
        (resource) => resource.resource_type === category,
      ),
  )

  if (packagesResult.waiting && !livePackage) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2Icon className="size-4 animate-spin" />
        <span>正在加载资源包...</span>
      </div>
    )
  }

  if (!Result.isSuccess(packagesResult) && !livePackage) {
    return (
      <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-3 text-sm text-destructive">
        资源包加载失败。
      </div>
    )
  }

  if (packages.length === 0) {
    return (
      <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
        还没有资源包，请先在左侧生成一个。
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2 md:flex-row">
      <Select
        value={category}
        onValueChange={(value) => {
          const nextCategory = value as 'all' | ResourceType
          setCategory(nextCategory)
          const selectedPackage = packages.find(
            (item) => item.id === selectedPackageId,
          )
          if (
            selectedPackage &&
            nextCategory !== 'all' &&
            !selectedPackage.preferred_resource_types.includes(nextCategory) &&
            !selectedPackage.resources.some(
              (resource) => resource.resource_type === nextCategory,
            )
          ) {
            onSelect(null)
          }
        }}
      >
        <SelectTrigger className="w-full md:w-40" aria-label="资源包分类">
          <TagsIcon className="size-4" />
          <SelectValue placeholder="资源分类" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">全部类型</SelectItem>
          {RESOURCE_TYPE_OPTIONS.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {filteredPackages.length > 0 ? (
        <Select
          value={selectedPackageId ?? undefined}
          onValueChange={(packageId) => {
            const resourcePackage = packages.find(
              (item) => item.id === packageId,
            )
            if (resourcePackage) onSelect(resourcePackage)
          }}
        >
          <SelectTrigger className="w-full min-w-0 md:flex-1">
            <SelectValue placeholder="选择一个资源包" />
          </SelectTrigger>
          <SelectContent>
            {filteredPackages.map((resourcePackage) => (
              <SelectItem key={resourcePackage.id} value={resourcePackage.id}>
                {resourcePackage.title} ·{' '}
                {resourcePackage.completed_resource_count}/
                {resourcePackage.resource_count}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      ) : (
        <div className="flex h-9 flex-1 items-center rounded-md border border-dashed px-3 text-sm text-muted-foreground">
          当前分类暂无资源包
        </div>
      )}
    </div>
  )
}

const ResourcePreview = ({
  projectId,
  resourcePackage,
  courseOutline,
}: {
  projectId: string
  resourcePackage: ResourcePackage
  courseOutline: ProjectCourseOutline | null
}) => {
  const resourcesResult = useAtomValue(
    generatedResourcesAtom(`${projectId}:${resourcePackage.id}`),
  )
  const [liveResources, setLiveResources] =
    useState<Array<GeneratedResource> | null>(null)

  useEffect(() => {
    setLiveResources(null)
  }, [resourcePackage.id])

  useEffect(() => {
    if (Result.isSuccess(resourcesResult)) {
      setLiveResources(resourcesResult.value)
    }
  }, [resourcesResult])

  useEffect(() => {
    if (resourcePackage.status !== 'generating') return
    let cancelled = false
    let timerId: number | undefined
    const poll = async () => {
      try {
        const response = await fetch(
          `/api/v1/projects/${projectId}/resource-packages/${resourcePackage.id}/resources`,
        )
        if (response.ok && !cancelled) {
          setLiveResources((await response.json()) as Array<GeneratedResource>)
        }
      } finally {
        if (!cancelled) timerId = window.setTimeout(poll, 1500)
      }
    }
    void poll()
    return () => {
      cancelled = true
      if (timerId !== undefined) window.clearTimeout(timerId)
    }
  }, [projectId, resourcePackage.id, resourcePackage.status])

  const resources =
    liveResources ??
    (Result.isSuccess(resourcesResult) ? resourcesResult.value : [])

  if (resourcesResult.waiting && liveResources === null) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2Icon className="size-4 animate-spin" />
        <span>正在加载生成结果...</span>
      </div>
    )
  }

  if (!Result.isSuccess(resourcesResult) && liveResources === null) {
    return (
      <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-3 text-sm text-destructive">
        生成结果加载失败。
      </div>
    )
  }

  if (resources.length === 0) {
    return (
      <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
        这个资源包暂时还没有可预览的生成结果。
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {resources.map((resource) => (
        <div key={resource.id} className="rounded-xl border p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="font-medium">{resource.title}</div>
              <div className="mt-1 text-sm text-muted-foreground">
                {resource.summary ? (
                  <Response className="text-sm">{resource.summary}</Response>
                ) : (
                  '暂无摘要'
                )}
              </div>
            </div>
            <Badge variant={statusToneMap[resource.status]}>
              {resource.status}
            </Badge>
          </div>

          <div className="mt-3 flex flex-wrap gap-2">
            <Badge variant="outline">
              {resourceTypeLabelMap.get(resource.resource_type) ??
                resource.resource_type}
            </Badge>
            <Badge variant="outline">{resource.format}</Badge>
            <Badge variant="outline">{resource.difficulty_level}</Badge>
          </div>

          {resource.preview_url && resource.resource_type !== 'image' ? (
            <div className="mt-3">
              <a
                href={resource.preview_url}
                className="text-sm text-primary underline underline-offset-4"
              >
                打开生成资源
              </a>
            </div>
          ) : null}

          {resource.file_url && resource.resource_type !== 'image' ? (
            <div className="mt-3">
              <a
                href={resource.file_url}
                target="_blank"
                rel="noreferrer"
                className="text-sm text-primary underline underline-offset-4"
              >
                打开导出文件
              </a>
            </div>
          ) : null}

          <div className="mt-3 rounded-lg bg-muted/40 p-3">
            <ResourceResultPreview projectId={projectId} resource={resource} />
          </div>
          <CourseResourceLinker
            resource={resource}
            courseOutline={courseOutline}
          />
        </div>
      ))}
    </div>
  )
}

const ResourcePreviewPanel = ({
  projectId,
  resourcePackage,
  streamingResources,
  streamingStatuses,
  courseOutline,
}: {
  projectId: string
  resourcePackage: ResourcePackage | null
  streamingResources: Array<GeneratedResource>
  streamingStatuses: Partial<Record<ResourceType, GeneratedResourceStatus>>
  courseOutline: ProjectCourseOutline | null
}) => {
  const hasStreamingResources = Object.values(streamingStatuses).some(
    (status) => status === 'pending' || status === 'generating',
  )
  if (
    hasStreamingResources ||
    (!resourcePackage && Object.keys(streamingStatuses).length > 0)
  ) {
    return (
      <div className="space-y-3">
        {Object.entries(streamingStatuses)
          .filter(
            ([type]) =>
              !streamingResources.some((item) => item.resource_type === type),
          )
          .map(([type, status]) => (
            <div
              key={type}
              className="flex items-center justify-between rounded-xl border p-4"
            >
              <div className="font-medium">
                {resourceTypeLabelMap.get(type as ResourceType) ?? type}
              </div>
              <Badge variant={statusToneMap[status]}>{status}</Badge>
            </div>
          ))}
        {streamingResources.map((resource) => (
          <div key={resource.id} className="rounded-xl border p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="font-medium">{resource.title}</div>
              <Badge variant={statusToneMap[resource.status]}>
                {resource.status}
              </Badge>
            </div>
            {resource.preview_url && resource.resource_type !== 'image' ? (
              <div className="mt-3">
                <a
                  href={resource.preview_url}
                  className="inline-flex items-center gap-1 text-sm text-primary underline underline-offset-4"
                >
                  打开生成资源
                  <ExternalLinkIcon className="size-3.5" />
                </a>
              </div>
            ) : null}
            <div className="mt-3 rounded-lg bg-muted/40 p-3">
              <ResourceResultPreview
                projectId={projectId}
                resource={resource}
              />
            </div>
            <CourseResourceLinker
              resource={resource}
              courseOutline={courseOutline}
            />
          </div>
        ))}
      </div>
    )
  }
  if (!resourcePackage) {
    return (
      <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
        选择一个资源包以查看生成结果。
      </div>
    )
  }

  return (
    <ResourcePreview
      projectId={projectId}
      resourcePackage={resourcePackage}
      courseOutline={courseOutline}
    />
  )
}

export const ResourcePackagePage = ({
  projectId,
  initialPackageId,
}: {
  projectId: string
  initialPackageId?: string
}) => {
  const generateResourcePackage = useAtomSet(generateResourcePackageAtom, {
    mode: 'promise',
  })
  const navigate = useNavigate()
  const courseOutlineResult = useAtomValue(projectCourseOutlineAtom(projectId))
  const globalPackageProgress = useAtomValue(resourcePackageProgressAtom)
  const packageProgress =
    globalPackageProgress?.projectId === projectId &&
    (!initialPackageId ||
      !globalPackageProgress.packageId ||
      globalPackageProgress.packageId === initialPackageId)
      ? globalPackageProgress
      : null
  useResourcePackageStream({ projectId, packageId: initialPackageId })
  const packagesResult = useAtomValue(resourcePackagesAtom(projectId))
  const refreshResourcePackages = useAtomSet(refreshResourcePackagesAtom, {
    mode: 'promise',
  })

  useEffect(() => {
    void refreshResourcePackages(projectId)
  }, [projectId, refreshResourcePackages])

  useEffect(() => {
    const progressPackageId = packageProgress?.packageId
    if (!progressPackageId || progressPackageId === initialPackageId) {
      return
    }
    void navigate({
      to: '/dashboard/p/$projectId/resource-packages',
      params: { projectId },
      search: { packageId: progressPackageId },
      replace: true,
    })
  }, [initialPackageId, navigate, packageProgress?.packageId, projectId])

  const [title, setTitle] = useState('')
  const [topic, setTopic] = useState('')
  const [instructions, setInstructions] = useState('')
  const [difficultyStage, setDifficultyStage] = useState(2)
  const [selectedChapterIds, setSelectedChapterIds] = useState<Set<string>>(
    new Set(),
  )
  const [selectedTypes, setSelectedTypes] = useState<Array<ResourceType>>([
    'lecture_note',
    'mind_map',
    'practice_set',
    'flashcards',
    'ppt_outline',
    'image',
    'pptx',
    'programming_questions',
    'video_recommendations',
  ])
  const [selectedPackage, setSelectedPackage] =
    useState<ResourcePackage | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    if (!initialPackageId || !Result.isSuccess(packagesResult)) return
    const requestedPackage = packagesResult.value.find(
      (resourcePackage) => resourcePackage.id === initialPackageId,
    )
    if (requestedPackage) setSelectedPackage(requestedPackage)
  }, [initialPackageId, packagesResult])

  const courseOutline =
    courseOutlineResult._tag === 'Success' ? courseOutlineResult.value : null
  const selectedDifficultyStage =
    DIFFICULTY_STAGES[difficultyStage] ?? DIFFICULTY_STAGES[2]
  const difficulty = selectedDifficultyStage.value
  const difficultyProgress =
    (difficultyStage / (DIFFICULTY_STAGES.length - 1)) * 100

  const isGenerateDisabled =
    !topic.trim() || selectedTypes.length === 0 || isSubmitting

  const helperText = useMemo(
    () => '提交后会立即创建资源包并进入结果页，生成内容会持续实时更新。',
    [],
  )

  const toggleType = (resourceType: ResourceType) => {
    setSelectedTypes((current) =>
      current.includes(resourceType)
        ? current.filter((item) => item !== resourceType)
        : [...current, resourceType],
    )
  }

  const toggleChapter = (chapterId: string) => {
    setSelectedChapterIds((current) => {
      const next = new Set(current)
      if (next.has(chapterId)) next.delete(chapterId)
      else next.add(chapterId)
      return next
    })
  }

  const handleGenerate = async () => {
    if (!topic.trim() || selectedTypes.length === 0) return

    const knowledgePointIds =
      courseOutline?.knowledgePoints
        .filter(
          (point) =>
            point.chapter_id && selectedChapterIds.has(point.chapter_id),
        )
        .map((point) => point.id) ?? []

    setIsSubmitting(true)
    setSelectedPackage(null)
    try {
      const resourcePackage = await generateResourcePackage({
        projectId,
        title: title.trim() || undefined,
        target_topic: topic.trim(),
        custom_instructions: instructions.trim() || undefined,
        chapter_ids: Array.from(selectedChapterIds),
        knowledge_point_ids: knowledgePointIds,
        resource_types: selectedTypes,
        difficulty_level: difficulty,
        generation_params: {
          launch_context: 'resource package page',
          quiz_count: selectedTypes.includes('practice_set') ? 10 : undefined,
        },
      })

      setSelectedPackage(resourcePackage)
      await navigate({
        to: '/dashboard/p/$projectId/resource-packages',
        params: { projectId },
        search: { packageId: resourcePackage.id },
        replace: true,
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="flex h-full max-h-screen flex-col">
      <ProjectHeader projectId={projectId} />

      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
        <div className="flex w-full max-w-none flex-1 flex-col gap-6 px-4 py-6">
          <div className="space-y-2">
            <h1 className="text-2xl font-semibold">资源包生成</h1>
            <p className="text-sm text-muted-foreground">{helperText}</p>
          </div>

          {packageProgress?.status === 'generating' &&
          packageProgress.packageId ? (
            <div className="flex flex-col gap-3 rounded-xl border border-primary/20 bg-primary/5 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="text-sm font-medium">
                  已进入新资源包，内容正在生成
                </div>
                <div className="mt-0.5 text-xs text-muted-foreground">
                  该链接从任务开始阶段即可打开，生成进度会持续更新。
                </div>
              </div>
              <Button variant="outline" size="sm" asChild>
                <Link
                  to="/dashboard/p/$projectId/resource-packages"
                  params={{ projectId }}
                  search={{ packageId: packageProgress.packageId }}
                >
                  打开对应资源包
                  <ExternalLinkIcon className="size-4" />
                </Link>
              </Button>
            </div>
          ) : null}

          <div className="grid min-h-0 flex-1 gap-6 xl:grid-cols-2 xl:items-start">
            <div className="rounded-2xl border bg-card text-card-foreground">
              <div className="border-b px-5 py-4">
                <div className="text-base font-medium">生成资源包</div>
                <div className="mt-1 text-sm text-muted-foreground">
                  可选资源类型与项目概览里的 AI 生成保持一致。
                </div>
              </div>

              <div className="space-y-5 p-5">
                <div className="overflow-hidden rounded-lg border">
                  <div className="grid gap-2 border-b p-3 md:grid-cols-[7rem_minmax(0,1fr)] md:items-center">
                    <Label htmlFor="resource-package-title">资源包标题</Label>
                    <Input
                      id="resource-package-title"
                      value={title}
                      onChange={(event) => setTitle(event.target.value)}
                      placeholder="可选：给这组资源起一个标题"
                    />
                  </div>

                  <div className="grid gap-2 border-b p-3 md:grid-cols-[7rem_minmax(0,1fr)] md:items-center">
                    <Label htmlFor="resource-package-topic">目标主题</Label>
                    <Input
                      id="resource-package-topic"
                      value={topic}
                      onChange={(event) => setTopic(event.target.value)}
                      placeholder="这组资源希望重点围绕什么内容生成？"
                    />
                  </div>

                  <div className="grid gap-2 border-b p-3 md:grid-cols-[7rem_minmax(0,1fr)] md:items-center">
                    <Label htmlFor="resource-package-instructions">
                      自定义要求
                    </Label>
                    <Input
                      id="resource-package-instructions"
                      value={instructions}
                      onChange={(event) => setInstructions(event.target.value)}
                      placeholder="可选：补充这次多 Agent 生成的风格、重点或限制"
                    />
                  </div>

                  <div className="grid gap-2 p-3 md:grid-cols-[7rem_minmax(0,1fr)] md:items-center">
                    <Label htmlFor="resource-package-difficulty">
                      难度等级
                    </Label>
                    <div className="space-y-2">
                      <div className="relative flex h-8 items-center">
                        <div className="absolute inset-x-0 h-6 overflow-hidden rounded-[3px] border border-blue-200/60 bg-muted">
                          <div
                            className="difficulty-slider-exhaust relative h-full overflow-hidden transition-[width] duration-200 ease-out"
                            style={{
                              width: `${Math.max(difficultyProgress, 4)}%`,
                              backgroundImage: `linear-gradient(90deg, #93c5fd 0%, ${selectedDifficultyStage.color} 72%, #dbeafe 94%, #ffffff 100%)`,
                            }}
                          >
                            <span
                              aria-hidden="true"
                              className="difficulty-slider-stars"
                              style={{
                                animationDuration:
                                  selectedDifficultyStage.animationDuration,
                              }}
                            >
                              ✦ · ✧ · ✦ · ✶ · ✧ · ✦ · ✧ · ✶
                            </span>
                          </div>
                        </div>
                        <input
                          id="resource-package-difficulty"
                          type="range"
                          min={0}
                          max={DIFFICULTY_STAGES.length - 1}
                          step={1}
                          value={difficultyStage}
                          aria-valuetext={selectedDifficultyStage.label}
                          onChange={(event) =>
                            setDifficultyStage(Number(event.target.value))
                          }
                          className="absolute inset-0 h-8 w-full cursor-grab appearance-none bg-transparent outline-none active:cursor-grabbing focus-visible:ring-2 focus-visible:ring-blue-500/40 focus-visible:ring-offset-2 [&::-moz-range-thumb]:h-6 [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:rounded-[2px] [&::-moz-range-thumb]:border-2 [&::-moz-range-thumb]:border-blue-700 [&::-moz-range-thumb]:bg-white [&::-moz-range-thumb]:shadow-md [&::-moz-range-track]:h-6 [&::-moz-range-track]:bg-transparent [&::-webkit-slider-runnable-track]:h-6 [&::-webkit-slider-runnable-track]:bg-transparent [&::-webkit-slider-thumb]:h-6 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-[2px] [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-blue-700 [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:shadow-md"
                        />
                      </div>
                      <div className="flex justify-between text-xs">
                        {DIFFICULTY_STAGES.map((option, index) => (
                          <span
                            key={option.label}
                            className={cn(
                              'transition-colors',
                              difficultyStage === index
                                ? 'font-medium text-blue-700 dark:text-blue-300'
                                : 'text-muted-foreground',
                            )}
                          >
                            {option.label}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="space-y-3">
                  <Label>资源类型</Label>
                  <div className="grid auto-rows-fr grid-cols-3 gap-1.5">
                    {RESOURCE_TYPE_OPTIONS.map((option) => {
                      const checked = selectedTypes.includes(option.value)
                      return (
                        <label
                          key={option.value}
                          className={cn(
                            'flex h-full w-full min-w-0 cursor-pointer items-start gap-2 rounded-md border px-2.5 py-2 transition-colors',
                            checked
                              ? 'border-primary bg-primary/5'
                              : 'hover:bg-muted/40',
                          )}
                        >
                          <Checkbox
                            checked={checked}
                            onCheckedChange={() => toggleType(option.value)}
                          />
                          <div className="min-w-0 space-y-0.5">
                            <div className="text-sm font-medium">
                              {option.label}
                            </div>
                            <div className="text-xs leading-4 text-muted-foreground">
                              {option.description}
                            </div>
                          </div>
                        </label>
                      )
                    })}
                  </div>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <Label>课程章节</Label>
                    <div className="text-xs text-muted-foreground">
                      已选择 {selectedChapterIds.size} 个
                    </div>
                  </div>

                  {courseOutlineResult.waiting ? (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Loader2Icon className="size-4 animate-spin" />
                      <span>正在加载课程章节...</span>
                    </div>
                  ) : !Result.isSuccess(courseOutlineResult) ? (
                    <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-3 text-sm text-destructive">
                      课程章节加载失败。
                    </div>
                  ) : !courseOutline?.courseId ? (
                    <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
                      当前项目尚未绑定课程，请先编辑项目并选择所属课程。
                    </div>
                  ) : courseOutline.chapters.length === 0 ? (
                    <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
                      当前课程暂无可选章节。
                    </div>
                  ) : (
                    <div className="max-h-60 space-y-2 overflow-y-auto rounded-xl border p-3">
                      {courseOutline.chapters.map((chapter) => {
                        const checked = selectedChapterIds.has(chapter.id)
                        const knowledgePointCount =
                          courseOutline.knowledgePoints.filter(
                            (point) => point.chapter_id === chapter.id,
                          ).length
                        return (
                          <label
                            key={chapter.id}
                            className="flex cursor-pointer items-start gap-3 rounded-lg px-2 py-2 transition-colors hover:bg-muted/40"
                          >
                            <Checkbox
                              checked={checked}
                              onCheckedChange={() => toggleChapter(chapter.id)}
                            />
                            <div className="space-y-1 text-sm">
                              <div className="font-medium">{chapter.title}</div>
                              <div className="text-muted-foreground">
                                {knowledgePointCount} 个知识点
                                {chapter.estimated_minutes
                                  ? ` · 预计 ${chapter.estimated_minutes} 分钟`
                                  : ''}
                              </div>
                            </div>
                          </label>
                        )
                      })}
                    </div>
                  )}
                </div>

                <Button
                  onClick={handleGenerate}
                  disabled={isGenerateDisabled}
                  className="w-full"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2Icon className="mr-2 size-4 animate-spin" />
                      生成中...
                    </>
                  ) : (
                    '生成资源包'
                  )}
                </Button>
              </div>
            </div>

            <div className="flex min-h-0 flex-col gap-4 xl:sticky xl:top-6 xl:max-h-[calc(100vh-3rem)]">
              <div className="rounded-xl border bg-card p-4 text-card-foreground">
                <div className="flex flex-col gap-4">
                  <div>
                    <div className="text-base font-medium">资源包列表</div>
                    <div className="text-sm text-muted-foreground">
                      查看当前项目下已生成的资源包。
                    </div>
                  </div>
                  <ResourcePackageSelector
                    projectId={projectId}
                    selectedPackageId={
                      selectedPackage?.id ?? packageProgress?.packageId ?? null
                    }
                    livePackage={packageProgress?.package}
                    onSelect={(resourcePackage) => {
                      setSelectedPackage(resourcePackage)
                      if (!resourcePackage) return
                      void navigate({
                        to: '/dashboard/p/$projectId/resource-packages',
                        params: { projectId },
                        search: { packageId: resourcePackage.id },
                        replace: true,
                      })
                    }}
                  />
                </div>
              </div>

              <div className="min-h-0 overflow-y-auto rounded-xl border bg-card p-4 text-card-foreground">
                <div className="mb-4">
                  <div className="text-base font-medium">生成结果</div>
                  <div className="text-sm text-muted-foreground">
                    预览统一 AI 生成链路产出的资源内容。
                  </div>
                </div>
                <div>
                  <ResourcePreviewPanel
                    projectId={projectId}
                    resourcePackage={selectedPackage}
                    streamingResources={packageProgress?.resources ?? []}
                    streamingStatuses={packageProgress?.resourceStatuses ?? {}}
                    courseOutline={courseOutline}
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
