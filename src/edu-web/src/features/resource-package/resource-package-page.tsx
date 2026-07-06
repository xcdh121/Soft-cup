import { useMemo, useState } from 'react'
import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import { Loader2Icon, SparklesIcon } from 'lucide-react'
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
  type DifficultyLevel,
  type GeneratedResource,
  type ResourcePackage,
  type ResourceType,
  generateResourcePackageAtom,
  generatedResourcesAtom,
  resourcePackagesAtom,
} from '@/data-acess/resource-package'
import { ProjectHeader } from '@/features/project/components/project-header'
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

const ResourcePackageList = ({
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
    <div className="space-y-2">
      {packages.map((resourcePackage) => {
        const isActive = resourcePackage.id === selectedPackageId

        return (
          <button
            key={resourcePackage.id}
            type="button"
            onClick={() => onSelect(resourcePackage)}
            className={cn(
              'w-full rounded-xl border p-3 text-left transition-colors',
              isActive
                ? 'border-primary bg-primary/5'
                : 'hover:border-muted-foreground/30 hover:bg-muted/40',
            )}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-1">
                <div className="font-medium">{resourcePackage.title}</div>
                <div className="text-sm text-muted-foreground">
                  {resourcePackage.target_topic}
                </div>
              </div>
              <Badge variant={statusToneMap[resourcePackage.status]}>
                {resourcePackage.status}
              </Badge>
            </div>
            <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
              <span>
                {resourcePackage.completed_resource_count}/
                {resourcePackage.resource_count} 个资源
              </span>
              {resourcePackage.estimated_minutes ? (
                <span>{resourcePackage.estimated_minutes} 分钟</span>
              ) : null}
              <span>{resourcePackage.difficulty_level}</span>
            </div>
          </button>
        )
      })}
    </div>
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

          {resource.content_text ? (
            <div className="mt-3 rounded-lg bg-muted/40 p-3 text-sm whitespace-pre-wrap">
              {resource.content_text.slice(0, 800)}
              {resource.content_text.length > 800 ? '...' : ''}
            </div>
          ) : null}

          {!resource.content_text && resource.content_json ? (
            <pre className="mt-3 overflow-x-auto rounded-lg bg-muted/40 p-3 text-xs">
              {JSON.stringify(resource.content_json, null, 2)}
            </pre>
          ) : null}
        </div>
      ))}
    </div>
  )
}

const ResourcePreviewPanel = ({
  projectId,
  resourcePackage,
}: {
  projectId: string
  resourcePackage: ResourcePackage | null
}) => {
  if (!resourcePackage) {
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

  const [title, setTitle] = useState('')
  const [topic, setTopic] = useState('')
  const [goal, setGoal] = useState('')
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
        target_goal: goal.trim() || undefined,
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

          <div className="grid min-h-0 flex-1 gap-6 xl:grid-cols-[1.05fr_0.95fr]">
            <div className="rounded-2xl border bg-background">
              <div className="border-b px-5 py-4">
                <div className="text-base font-medium">生成资源包</div>
                <div className="mt-1 text-sm text-muted-foreground">
                  可选资源类型与项目概览里的 AI 生成保持一致。
                </div>
              </div>

              <div className="space-y-5 p-5">
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
                  <Label htmlFor="resource-package-goal">学习目标</Label>
                  <Textarea
                    id="resource-package-goal"
                    value={goal}
                    onChange={(event) => setGoal(event.target.value)}
                    placeholder="可选：例如考前复习、查漏补缺、知识串讲"
                    className="min-h-20 resize-none"
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

                <div className="space-y-3">
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

                <div className="space-y-2">
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

            <div className="grid min-h-0 gap-6 xl:grid-rows-[auto_1fr]">
              <div className="rounded-2xl border bg-background p-5">
                <div className="mb-4 flex items-center justify-between gap-3">
                  <div>
                    <div className="text-base font-medium">资源包列表</div>
                    <div className="text-sm text-muted-foreground">
                      查看当前项目下已生成的资源包。
                    </div>
                  </div>
                </div>
                <ResourcePackageList
                  projectId={projectId}
                  selectedPackageId={selectedPackage?.id ?? null}
                  onSelect={setSelectedPackage}
                />
              </div>

              <div className="min-h-0 rounded-2xl border bg-background p-5">
                <div className="mb-4">
                  <div className="text-base font-medium">生成结果</div>
                  <div className="text-sm text-muted-foreground">
                    预览统一 AI 生成链路产出的资源内容。
                  </div>
                </div>
                <div className="max-h-[calc(100vh-22rem)] overflow-y-auto pr-1">
                  <ResourcePreviewPanel
                    projectId={projectId}
                    resourcePackage={selectedPackage}
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
