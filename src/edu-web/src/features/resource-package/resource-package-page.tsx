import { useMemo, useState } from 'react'
import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import {
  FileTextIcon,
  Loader2Icon,
  MapIcon,
  PresentationIcon,
  SparklesIcon,
} from 'lucide-react'
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
import { indexedDocumentsAtom } from '@/data-acess/document'
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

type MindMapJson = {
  root?: string
  nodes?: Array<{ id?: string; label?: string }>
  edges?: Array<{ source?: string; target?: string }>
  notes?: {
    goal?: string
    weak_points?: Array<string>
    knowledge_points?: Array<string>
  }
}

type PracticeSetJson = {
  topic?: string
  difficulty_level?: string
  questions?: Array<{ level?: string; question?: string }>
}

type PptxJson = {
  provider?: string
  sid?: string
  title?: string
  subTitle?: string
  theme?: string
  export_status?: string
  notes?: string
  pptStatus?: string
  totalPages?: number
  donePages?: number
  pptUrl?: string
  coverImgSrc?: string
  slides?: Array<{
    page?: number
    title?: string
    bullets?: Array<string>
  }>
}

const RESOURCE_TYPE_OPTIONS: Array<{
  value: ResourceType
  label: string
  description: string
}> = [
  {
    value: 'lecture_note',
    label: '讲解文档',
    description: '结构化知识讲解材料',
  },
  {
    value: 'mind_map',
    label: '思维导图',
    description: '可视化知识结构梳理',
  },
  {
    value: 'practice_set',
    label: '分层练习题',
    description: '按难度分层的练习内容',
  },
  {
    value: 'ppt_outline',
    label: 'PPT 大纲',
    description: '逐页演示讲稿提纲',
  },
  {
    value: 'pptx',
    label: 'PPTX',
    description: '可导出的演示文稿结构',
  },
  {
    value: 'code_lab',
    label: '代码实操',
    description: '动手实践的编程任务',
  },
  {
    value: 'reading_material',
    label: '拓展阅读',
    description: '延伸阅读与补充材料',
  },
  {
    value: 'video_script',
    label: '视频脚本',
    description: '短视频/分镜讲解脚本',
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

const splitMarkdownSections = (content: string) =>
  content
    .split(/\n(?=## )/g)
    .map((section) => section.trim())
    .filter(Boolean)

const parsePptOutline = (content: string) =>
  content
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => /^\d+\./.test(line))

const renderLectureNote = (resource: GeneratedResource) => {
  const sections = splitMarkdownSections(resource.content_text ?? '')

  return (
    <div className="mt-4 space-y-3">
      {sections.map((section) => {
        const [heading, ...bodyLines] = section.split('\n')
        const title = heading.replace(/^##\s*/, '').replace(/^#\s*/, '')

        return (
          <section key={heading} className="rounded-xl border bg-muted/20 p-4">
            <h4 className="font-medium">{title}</h4>
            <div className="mt-2 space-y-2 text-sm text-muted-foreground whitespace-pre-wrap">
              {bodyLines.join('\n').trim()}
            </div>
          </section>
        )
      })}
    </div>
  )
}

const renderMindMap = (resource: GeneratedResource) => {
  const content = (resource.content_json ?? {}) as MindMapJson
  const nodes = content.nodes ?? []
  const notes = content.notes

  return (
    <div className="mt-4 space-y-4">
      <div className="rounded-xl border bg-muted/20 p-4">
        <div className="flex items-center gap-2 font-medium">
          <MapIcon className="size-4" />
          <span>{content.root ?? resource.title}</span>
        </div>
        <div className="mt-3 grid gap-2 md:grid-cols-2">
          {nodes.map((node, index) => (
            <div key={`${node.id ?? index}-${node.label ?? ''}`} className="rounded-lg border bg-background p-3 text-sm">
              {node.label ?? `节点 ${index + 1}`}
            </div>
          ))}
        </div>
      </div>

      {notes ? (
        <div className="grid gap-3 md:grid-cols-3">
          <div className="rounded-xl border p-4">
            <div className="text-sm font-medium">学习目标</div>
            <div className="mt-2 text-sm text-muted-foreground">
              {notes.goal ?? '暂无'}
            </div>
          </div>
          <div className="rounded-xl border p-4">
            <div className="text-sm font-medium">薄弱点</div>
            <div className="mt-2 text-sm text-muted-foreground">
              {(notes.weak_points ?? []).join('、') || '暂无'}
            </div>
          </div>
          <div className="rounded-xl border p-4">
            <div className="text-sm font-medium">知识点</div>
            <div className="mt-2 text-sm text-muted-foreground">
              {(notes.knowledge_points ?? []).join('、') || '暂无'}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}

const renderPracticeSet = (resource: GeneratedResource) => {
  const content = (resource.content_json ?? {}) as PracticeSetJson
  const questions = content.questions ?? []

  return (
    <div className="mt-4 space-y-3">
      {questions.map((question, index) => (
        <div key={`${question.level ?? index}-${question.question ?? ''}`} className="rounded-xl border p-4">
          <div className="flex items-center gap-2">
            <Badge variant="outline">{question.level ?? `题目 ${index + 1}`}</Badge>
            {content.difficulty_level ? (
              <span className="text-xs text-muted-foreground">
                难度：{content.difficulty_level}
              </span>
            ) : null}
          </div>
          <div className="mt-3 text-sm leading-6">
            {question.question ?? '暂无题目内容'}
          </div>
        </div>
      ))}
    </div>
  )
}

const renderPptOutline = (resource: GeneratedResource) => {
  const slides = parsePptOutline(resource.content_text ?? '')
  const outline =
    ((resource.content_json ?? {}) as { outline?: { title?: string } }).outline ?? {}

  return (
    <div className="mt-4 rounded-xl border bg-muted/20 p-4">
      <div className="flex items-center gap-2 font-medium">
        <PresentationIcon className="size-4" />
        <span>{outline.title ?? '演示结构'}</span>
      </div>
      {slides.length > 0 ? (
        <ol className="mt-3 space-y-2 text-sm leading-6">
          {slides.map((slide) => (
            <li key={slide} className="rounded-lg border bg-background px-3 py-2">
              {slide}
            </li>
          ))}
        </ol>
      ) : (
        <div className="mt-3 text-sm text-muted-foreground">
          暂无可展示的大纲内容。
        </div>
      )}
    </div>
  )
}

const renderPptx = (resource: GeneratedResource) => {
  const content = (resource.content_json ?? {}) as PptxJson
  const slides = content.slides ?? []
  const isExternalPpt = Boolean(resource.file_url ?? content.pptUrl)
  const downloadUrl = resource.file_url ?? content.pptUrl

  return (
    <div className="mt-4 space-y-3">
      <div className="rounded-xl border bg-muted/20 p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="font-medium">{content.title ?? resource.title}</div>
            <div className="mt-1 text-sm text-muted-foreground">
              主题：{content.theme ?? '默认'} | 导出状态：{content.export_status ?? '未知'}
            </div>
          </div>
          <Badge variant="outline">PPTX 结构</Badge>
        </div>
        {content.subTitle ? (
          <div className="mt-2 text-sm text-muted-foreground">{content.subTitle}</div>
        ) : null}
        {content.coverImgSrc || resource.cover_image_url ? (
          <img
            src={resource.cover_image_url ?? content.coverImgSrc}
            alt={content.title ?? resource.title}
            className="mt-3 max-h-56 rounded-lg border object-cover"
          />
        ) : null}
        {isExternalPpt ? (
          <div className="mt-3 space-y-2 text-sm text-muted-foreground">
            <div>
              状态：{content.pptStatus ?? resource.status}
              {content.totalPages
                ? ` | 页数：${content.donePages ?? content.totalPages}/${content.totalPages}`
                : ''}
            </div>
            {downloadUrl ? (
              <a
                href={downloadUrl}
                target="_blank"
                rel="noreferrer"
                className="text-primary underline underline-offset-4"
              >
                下载生成的 PPT
              </a>
            ) : null}
          </div>
        ) : null}
        {content.notes ? (
          <div className="mt-3 text-sm text-muted-foreground">{content.notes}</div>
        ) : null}
      </div>

      {!isExternalPpt
        ? slides.map((slide, index) => (
            <div key={`${slide.page ?? index}-${slide.title ?? ''}`} className="rounded-xl border p-4">
              <div className="font-medium">
                第 {slide.page ?? index + 1} 页：{slide.title ?? '未命名页'}
              </div>
              <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                {(slide.bullets ?? []).map((bullet) => (
                  <li key={bullet}>{bullet}</li>
                ))}
              </ul>
            </div>
          ))
        : null}
    </div>
  )
}

const renderFallback = (resource: GeneratedResource) => {
  if (resource.content_text) {
    return (
      <div className="mt-4 rounded-lg bg-muted/40 p-3 text-sm whitespace-pre-wrap">
        {resource.content_text}
      </div>
    )
  }

  if (resource.content_json) {
    return (
      <pre className="mt-4 overflow-x-auto rounded-lg bg-muted/40 p-3 text-xs">
        {JSON.stringify(resource.content_json, null, 2)}
      </pre>
    )
  }

  return null
}

const ResourceContent = ({ resource }: { resource: GeneratedResource }) => {
  switch (resource.resource_type) {
    case 'lecture_note':
      return renderLectureNote(resource)
    case 'mind_map':
      return renderMindMap(resource)
    case 'practice_set':
      return renderPracticeSet(resource)
    case 'ppt_outline':
      return renderPptOutline(resource)
    case 'pptx':
      return renderPptx(resource)
    default:
      return renderFallback(resource)
  }
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
                : 'hover:bg-muted/40 hover:border-muted-foreground/30',
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
                {resourcePackage.resource_count} 项
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
  const resources = Result.isSuccess(resourcesResult) ? resourcesResult.value : []

  if (resourcesResult.waiting) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2Icon className="size-4 animate-spin" />
        <span>正在加载资源内容...</span>
      </div>
    )
  }

  if (!Result.isSuccess(resourcesResult)) {
    return (
      <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-3 text-sm text-destructive">
        资源内容加载失败。
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {resources.map((resource) => (
        <div key={resource.id} className="rounded-2xl border p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="font-medium">{resource.title}</div>
              <div className="mt-1 text-sm text-muted-foreground">
                {resource.summary ?? '暂无摘要。'}
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

          <ResourceContent resource={resource} />
        </div>
      ))}
    </div>
  )
}

export const ResourcePackagePage = ({ projectId }: { projectId: string }) => {
  const generateResourcePackage = useAtomSet(generateResourcePackageAtom, {
    mode: 'promise',
  })
  const documentsResult = useAtomValue(indexedDocumentsAtom(projectId))

  const [title, setTitle] = useState('')
  const [topic, setTopic] = useState('')
  const [goal, setGoal] = useState('')
  const [instructions, setInstructions] = useState('')
  const [difficulty, setDifficulty] =
    useState<DifficultyLevel>('intermediate')
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<Set<string>>(
    new Set(),
  )
  const [selectedTypes, setSelectedTypes] = useState<Array<ResourceType>>([
    'lecture_note',
    'mind_map',
    'practice_set',
    'ppt_outline',
    'pptx',
  ])
  const [selectedPackage, setSelectedPackage] = useState<ResourcePackage | null>(
    null,
  )
  const [isSubmitting, setIsSubmitting] = useState(false)

  const indexedDocuments =
    documentsResult._tag === 'Success' ? documentsResult.value : []

  const isGenerateDisabled =
    !topic.trim() || selectedTypes.length === 0 || isSubmitting

  const helperText = useMemo(
    () => '围绕当前项目生成讲解、导图、练习和演示材料等资源包。',
    [],
  )

  const toggleType = (resourceType: ResourceType) => {
    setSelectedTypes((current) =>
      current.includes(resourceType)
        ? current.filter((item) => item !== resourceType)
        : [...current, resourceType],
    )
  }

  const toggleDocument = (documentId: string) => {
    setSelectedDocumentIds((current) => {
      const next = new Set(current)
      if (next.has(documentId)) next.delete(documentId)
      else next.add(documentId)
      return next
    })
  }

  const handleGenerate = async () => {
    if (!topic.trim() || selectedTypes.length === 0) return

    setIsSubmitting(true)
    try {
      const resourcePackage = await generateResourcePackage({
        projectId,
        title: title.trim() || undefined,
        target_topic: topic.trim(),
        target_goal: goal.trim() || undefined,
        custom_instructions: instructions.trim() || undefined,
        source_document_ids: Array.from(selectedDocumentIds),
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
    <div className="flex h-full flex-col max-h-screen">
      <ProjectHeader projectId={projectId} />

      <div className="flex flex-1 flex-col min-h-0 overflow-y-auto">
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
                  为当前项目配置一组聚焦主题的学习资源。
                </div>
              </div>

              <div className="space-y-5 p-5">
                <div className="space-y-2">
                  <Label htmlFor="resource-package-title">资源包标题</Label>
                  <Textarea
                    id="resource-package-title"
                    value={title}
                    onChange={(event) => setTitle(event.target.value)}
                    placeholder="可选：为这组资源填写一个标题"
                    className="min-h-20 resize-none"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="resource-package-topic">目标主题</Label>
                  <Textarea
                    id="resource-package-topic"
                    value={topic}
                    onChange={(event) => setTopic(event.target.value)}
                    placeholder="这组资源要重点围绕什么内容？"
                    className="min-h-24 resize-none"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="resource-package-goal">学习目标</Label>
                  <Textarea
                    id="resource-package-goal"
                    value={goal}
                    onChange={(event) => setGoal(event.target.value)}
                    placeholder="可选：例如用于考前复习、补齐薄弱点"
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

                <div className="space-y-3">
                  <Label>来源文档</Label>
                  <div className="space-y-2 rounded-xl border p-3">
                    {documentsResult.waiting ? (
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Loader2Icon className="size-4 animate-spin" />
                        <span>正在加载已索引文档...</span>
                      </div>
                    ) : indexedDocuments.length === 0 ? (
                      <div className="text-sm text-muted-foreground">
                        目前还没有可用的索引文档。
                      </div>
                    ) : (
                      indexedDocuments.map((document) => (
                        <label
                          key={document.id}
                          className="flex cursor-pointer items-start gap-3 rounded-lg p-2 hover:bg-muted/40"
                        >
                          <Checkbox
                            checked={selectedDocumentIds.has(document.id)}
                            onCheckedChange={() => toggleDocument(document.id)}
                          />
                          <div className="min-w-0">
                            <div className="truncate text-sm font-medium">
                              {document.file_name}
                            </div>
                            <div className="text-xs text-muted-foreground">
                              {document.file_type?.toUpperCase()}
                            </div>
                          </div>
                        </label>
                      ))
                    )}
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="resource-package-instructions">
                    补充要求
                  </Label>
                  <Textarea
                    id="resource-package-instructions"
                    value={instructions}
                    onChange={(event) => setInstructions(event.target.value)}
                    placeholder="可选：补充生成风格、重点、表达方式等要求"
                    className="min-h-28 resize-none"
                  />
                </div>

                <div className="flex justify-end">
                  <Button
                    onClick={handleGenerate}
                    disabled={isGenerateDisabled}
                    size="lg"
                  >
                    {isSubmitting ? (
                      <>
                        <Loader2Icon className="size-4 animate-spin" />
                        生成中
                      </>
                    ) : (
                      <>
                        <SparklesIcon className="size-4" />
                        生成资源包
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </div>

            <div className="grid min-h-0 gap-6">
              <div className="rounded-2xl border bg-background">
                <div className="border-b px-5 py-4">
                  <div className="text-base font-medium">最近生成</div>
                  <div className="mt-1 text-sm text-muted-foreground">
                    选择一个资源包查看其中的生成结果。
                  </div>
                </div>
                <div className="max-h-[320px] overflow-y-auto p-5">
                  <ResourcePackageList
                    projectId={projectId}
                    selectedPackageId={selectedPackage?.id ?? null}
                    onSelect={setSelectedPackage}
                  />
                </div>
              </div>

              <div className="min-h-0 rounded-2xl border bg-background">
                <div className="border-b px-5 py-4">
                  <div className="flex items-center gap-2 text-base font-medium">
                    <FileTextIcon className="size-4" />
                    <span>资源预览</span>
                  </div>
                  <div className="mt-1 text-sm text-muted-foreground">
                    预览当前选中资源包中的内容。
                  </div>
                </div>
                <div className="max-h-[640px] overflow-y-auto p-5">
                  {selectedPackage ? (
                    <ResourcePreview
                      projectId={projectId}
                      resourcePackage={selectedPackage}
                    />
                  ) : (
                    <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
                      请选择一个资源包查看生成内容。
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
