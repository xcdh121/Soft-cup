import { useEffect, useMemo, useState } from 'react'
import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import { CheckCircle2Icon, Loader2Icon, SparklesIcon } from 'lucide-react'
import type {
  AgentProgressStep,
  DifficultyLevel,
  GeneratedResource,
  GeneratedResourceStatus,
  ResourcePackage,
  ResourceType,
} from '@/data-acess/resource-package'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { projectCourseOutlineAtom } from '@/data-acess/course-library'
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

const RESOURCE_TYPE_OPTIONS: Array<{
  value: ResourceType
  label: string
  description: string
}> = [
  {
    value: 'lecture_note',
    label: '笔记',
    description: '结构化讲解文档',
  },
  {
    value: 'mind_map',
    label: '思维导图',
    description: '可视化知识结构',
  },
  {
    value: 'practice_set',
    label: '题库',
    description: '分层练习与题目生成',
  },
  {
    value: 'flashcards',
    label: '闪卡',
    description: '生成记忆卡片组',
  },
  {
    value: 'ppt_outline',
    label: 'PPT 大纲',
    description: '逐页演示讲稿大纲',
  },
  {
    value: 'pptx',
    label: 'PPTX',
    description: '导出演示文件',
  },
  {
    value: 'programming_questions',
    label: 'Coding Problems',
    description: 'Generate 3-5 coding assessment problems',
  },
  {
    value: 'video_recommendations',
    label: '视频推荐',
    description: '从哔哩哔哩检索相关学习视频',
  },
]

const difficultyOptions: Array<{
  value: DifficultyLevel
  label: string
}> = [
  { value: 'beginner', label: '入门' },
  { value: 'intermediate', label: '进阶' },
  { value: 'advanced', label: '高级' },
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

const agentLabelMap: Record<string, string> = {
  SupervisorAgent: '总控编排',
  ProfileAgent: '学习者画像',
  KTAgent: '知识状态评估',
  CollectiveInsightAgent: '群体学习洞察',
  DiagnosisAgent: '学习诊断',
  ResourceAgent: '资源规划与投递',
  PlannerAgent: '学习路径规划',
}

const AgentProgressPanel = ({ steps }: { steps: Array<AgentProgressStep> }) => {
  if (steps.length === 0) return null
  return (
    <div className="rounded-2xl border bg-background p-5">
      <div className="font-medium">多智能体生成过程</div>
      <div className="mt-1 text-sm text-muted-foreground">
        资源包正在依次完成画像、知识状态、诊断、资源规划与学习路径编排。
      </div>
      <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {steps.map((step, index) => (
          <div key={`${step.agentName}-${index}`} className="flex items-start gap-2 rounded-lg border p-3">
            {step.status === 'running' ? (
              <Loader2Icon className="mt-0.5 size-4 shrink-0 animate-spin text-primary" />
            ) : (
              <CheckCircle2Icon className="mt-0.5 size-4 shrink-0 text-emerald-600" />
            )}
            <div className="min-w-0">
              <div className="text-sm font-medium">
                {agentLabelMap[step.agentName] ?? step.agentName}
              </div>
              <div className="line-clamp-2 text-xs text-muted-foreground">
                {step.summary}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

const ResourcePackageSelector = ({
  projectId,
  selectedPackageId,
  onSelect,
}: {
  projectId: string
  selectedPackageId: string | null
  onSelect: (resourcePackage: ResourcePackage) => void
}) => {
  const packagesResult = useAtomValue(resourcePackagesAtom(projectId))
  const packages = Result.isSuccess(packagesResult) ? packagesResult.value : []

  if (packagesResult.waiting) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2Icon className="size-4 animate-spin" />
        <span>正在加载资源包...</span>
      </div>
    )
  }

  if (!Result.isSuccess(packagesResult)) {
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
    <Select
      value={selectedPackageId ?? undefined}
      onValueChange={(packageId) => {
        const resourcePackage = packages.find((item) => item.id === packageId)
        if (resourcePackage) onSelect(resourcePackage)
      }}
    >
      <SelectTrigger className="w-full md:w-80">
        <SelectValue placeholder="选择一个资源包" />
      </SelectTrigger>
      <SelectContent>
        {packages.map((resourcePackage) => (
          <SelectItem key={resourcePackage.id} value={resourcePackage.id}>
            {resourcePackage.title} · {resourcePackage.completed_resource_count}/
            {resourcePackage.resource_count}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

const ResourcePreview = ({
  projectId,
  resourcePackage,
}: {
  projectId: string
  resourcePackage: ResourcePackage
}) => {
  const resourcesResult = useAtomValue(
    generatedResourcesAtom(`${projectId}:${resourcePackage.id}`),
  )
  const resources = Result.isSuccess(resourcesResult)
    ? resourcesResult.value
    : []

  if (resourcesResult.waiting) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2Icon className="size-4 animate-spin" />
        <span>正在加载生成结果...</span>
      </div>
    )
  }

  if (!Result.isSuccess(resourcesResult)) {
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
                {resource.summary ?? '暂无摘要'}
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

          {resource.preview_url ? (
            <div className="mt-3">
              <a
                href={resource.preview_url}
                target="_blank"
                rel="noreferrer"
                className="text-sm text-primary underline underline-offset-4"
              >
                打开生成资源
              </a>
            </div>
          ) : null}

          {resource.file_url ? (
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
}: {
  projectId: string
  resourcePackage: ResourcePackage | null
  streamingResources: Array<GeneratedResource>
  streamingStatuses: Partial<Record<ResourceType, GeneratedResourceStatus>>
}) => {
  if (!resourcePackage) {
    if (Object.keys(streamingStatuses).length > 0) {
      return (
        <div className="space-y-3">
          {Object.entries(streamingStatuses)
            .filter(([type]) => !streamingResources.some((item) => item.resource_type === type))
            .map(([type, status]) => (
              <div key={type} className="flex items-center justify-between rounded-xl border p-4">
                <div className="font-medium">{resourceTypeLabelMap.get(type as ResourceType) ?? type}</div>
                <Badge variant={statusToneMap[status]}>{status}</Badge>
              </div>
            ))}
          {streamingResources.map((resource) => (
            <div key={resource.id} className="rounded-xl border p-4">
              <div className="flex items-center justify-between gap-3">
                <div className="font-medium">{resource.title}</div>
                <Badge variant={statusToneMap[resource.status]}>{resource.status}</Badge>
              </div>
              <div className="mt-3 rounded-lg bg-muted/40 p-3">
                <ResourceResultPreview projectId={projectId} resource={resource} />
              </div>
            </div>
          ))}
        </div>
      )
    }
    return (
      <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
        选择一个资源包以查看生成结果。
      </div>
    )
  }

  return (
    <ResourcePreview projectId={projectId} resourcePackage={resourcePackage} />
  )
}

export const ResourcePackagePage = ({ projectId }: { projectId: string }) => {
  const generateResourcePackage = useAtomSet(generateResourcePackageAtom, {
    mode: 'promise',
  })
  const courseOutlineResult = useAtomValue(projectCourseOutlineAtom(projectId))
  const packageProgress = useAtomValue(resourcePackageProgressAtom)
  const refreshResourcePackages = useAtomSet(refreshResourcePackagesAtom, {
    mode: 'promise',
  })

  useEffect(() => {
    void refreshResourcePackages(projectId)
  }, [projectId, refreshResourcePackages])

  const [title, setTitle] = useState('')
  const [topic, setTopic] = useState('')
  const [instructions, setInstructions] = useState('')
  const [difficulty, setDifficulty] = useState<DifficultyLevel>('intermediate')
  const [selectedChapterIds, setSelectedChapterIds] = useState<Set<string>>(
    new Set(),
  )
  const [selectedTypes, setSelectedTypes] = useState<Array<ResourceType>>([
    'lecture_note',
    'mind_map',
    'practice_set',
    'flashcards',
    'ppt_outline',
    'pptx',
    'programming_questions',
    'video_recommendations',
  ])
  const [selectedPackage, setSelectedPackage] =
    useState<ResourcePackage | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const courseOutline =
    courseOutlineResult._tag === 'Success' ? courseOutlineResult.value : null

  const isGenerateDisabled =
    !topic.trim() || selectedTypes.length === 0 || isSubmitting

  const helperText = useMemo(
    () =>
      '资源包生成已与项目概览中的 AI 生成统一，统一走同一条多 Agent 生成链路。',
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
        generation_params: { launch_context: 'resource package page' },
      })

      setSelectedPackage(resourcePackage)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="flex h-full max-h-screen flex-col">
      <ProjectHeader projectId={projectId} />

      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
        <div className="container mx-auto flex max-w-7xl flex-1 flex-col gap-6 px-4 py-6">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <SparklesIcon className="size-5 text-primary" />
              <h1 className="text-2xl font-semibold">资源包生成</h1>
            </div>
            <p className="text-sm text-muted-foreground">{helperText}</p>
          </div>

          <AgentProgressPanel steps={packageProgress?.agentSteps ?? []} />

          <div className="flex min-h-0 flex-1 flex-col gap-6">
            <div className="rounded-2xl border bg-background">
              <div className="border-b px-5 py-4">
                <div className="text-base font-medium">生成资源包</div>
                <div className="mt-1 text-sm text-muted-foreground">
                  可选资源类型与项目概览里的 AI 生成保持一致。
                </div>
              </div>

              <div className="grid gap-5 p-5 md:grid-cols-2 xl:grid-cols-4">
                <div className="space-y-2">
                  <Label htmlFor="resource-package-title">资源包标题</Label>
                  <Textarea
                    id="resource-package-title"
                    value={title}
                    onChange={(event) => setTitle(event.target.value)}
                    placeholder="可选：给这组资源起一个标题"
                    className="min-h-20 resize-none"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="resource-package-topic">目标主题</Label>
                  <Textarea
                    id="resource-package-topic"
                    value={topic}
                    onChange={(event) => setTopic(event.target.value)}
                    placeholder="这组资源希望重点围绕什么内容生成？"
                    className="min-h-24 resize-none"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="resource-package-difficulty">难度等级</Label>
                  <Select
                    value={difficulty}
                    onValueChange={(value) =>
                      setDifficulty(value as DifficultyLevel)
                    }
                  >
                    <SelectTrigger id="resource-package-difficulty">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {difficultyOptions.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-3 md:col-span-2 xl:col-span-2 xl:row-start-2">
                  <Label>资源类型</Label>
                  <div className="grid gap-2 md:grid-cols-2">
                    {RESOURCE_TYPE_OPTIONS.map((option) => {
                      const checked = selectedTypes.includes(option.value)
                      return (
                        <label
                          key={option.value}
                          className={cn(
                            'flex cursor-pointer items-start gap-3 rounded-xl border p-3 transition-colors',
                            checked
                              ? 'border-primary bg-primary/5'
                              : 'hover:bg-muted/40',
                          )}
                        >
                          <Checkbox
                            checked={checked}
                            onCheckedChange={() => toggleType(option.value)}
                          />
                          <div className="space-y-1">
                            <div className="font-medium">{option.label}</div>
                            <div className="text-sm text-muted-foreground">
                              {option.description}
                            </div>
                          </div>
                        </label>
                      )
                    })}
                  </div>
                </div>

                <div className="space-y-2 md:col-span-2 xl:col-span-1 xl:col-start-4 xl:row-start-1">
                  <Label htmlFor="resource-package-instructions">
                    自定义要求
                  </Label>
                  <Textarea
                    id="resource-package-instructions"
                    value={instructions}
                    onChange={(event) => setInstructions(event.target.value)}
                    placeholder="可选：补充这次多 Agent 生成的风格、重点或限制"
                    className="min-h-24 resize-none"
                  />
                </div>

                <div className="space-y-3 md:col-span-2 xl:col-span-2 xl:row-start-2">
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
                  className="w-full md:col-span-2 xl:col-span-4"
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

            <div className="flex min-h-0 flex-col gap-6">
              <div className="rounded-2xl border bg-background p-5">
                <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                  <div>
                    <div className="text-base font-medium">资源包列表</div>
                    <div className="text-sm text-muted-foreground">
                      查看当前项目下已生成的资源包。
                    </div>
                  </div>
                  <ResourcePackageSelector
                    projectId={projectId}
                    selectedPackageId={selectedPackage?.id ?? null}
                    onSelect={setSelectedPackage}
                  />
                </div>
              </div>

              <div className="min-h-0 rounded-2xl border bg-background p-5">
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
