import { Result, useAtomValue } from '@effect-atom/atom-react'
import { Link } from '@tanstack/react-router'
import {
  type CSSProperties,
  type PointerEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react'
import {
  BookOpenIcon,
  ExternalLinkIcon,
  FileTextIcon,
  GripHorizontalIcon,
  GripVerticalIcon,
  LibraryBigIcon,
  Loader2Icon,
} from 'lucide-react'
import type {
  Course,
  CourseChapter,
  KnowledgePoint,
} from '@/data-acess/course-library'
import {
  courseChaptersAtom,
  courseKnowledgePointsAtom,
  courseResourcesAtom,
  coursesAtom,
  knowledgePointResourcesAtom,
} from '@/data-acess/course-library'
import { projectsAtom } from '@/data-acess/project'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { SidebarTrigger } from '@/components/ui/sidebar'
import { Separator } from '@/components/ui/separator'

type MarkdownSection = {
  title: string
  body: Array<string>
}

const difficultyLabel: Partial<Record<string, string>> = {
  beginner: '入门',
  intermediate: '进阶',
  advanced: '高级',
}

const resourceTypeLabel: Partial<Record<string, string>> = {
  article: '文章',
  pdf: 'PDF',
  video: '视频',
  code: '代码',
  problem: '题目',
  visualization: '可视化',
}

const DEFAULT_COURSE_PANEL_WIDTH = 280
const DEFAULT_OUTLINE_PANEL_WIDTH = 420
const MIN_COURSE_PANEL_WIDTH = 220
const MAX_COURSE_PANEL_WIDTH = 420
const MIN_OUTLINE_PANEL_WIDTH = 300
const MAX_OUTLINE_PANEL_WIDTH = 620
const MIN_DETAIL_SECTION_HEIGHT = 220
const MAX_DETAIL_SECTION_HEIGHT = 620
const DEFAULT_DETAIL_SECTION_HEIGHT = 360
const RESIZE_HANDLE_SIZE = 6

const clamp = (value: number, min: number, max: number) =>
  Math.min(Math.max(value, min), max)

const parseMarkdownSections = (markdown?: string | null) => {
  if (!markdown) return []

  return markdown.split('\n').reduce<Array<MarkdownSection>>((sections, line) => {
    if (line.startsWith('## ')) {
      sections.push({ title: line.replace(/^##\s+/, ''), body: [] })
      return sections
    }

    const current = sections.at(-1)
    if (current && line.trim()) {
      current.body.push(line.trim())
    }
    return sections
  }, [])
}

const renderMarkdownLine = (line: string) => {
  if (line.startsWith('- ')) {
    return (
      <li key={line} className="ml-5 list-disc">
        {line.slice(2)}
      </li>
    )
  }

  const numbered = line.match(/^\d+\.\s+(.*)$/)
  if (numbered) {
    return (
      <li key={line} className="ml-5 list-decimal">
        {numbered[1]}
      </li>
    )
  }

  return (
    <p key={line} className="leading-7">
      {line}
    </p>
  )
}

const LoadingCard = ({ text }: { text: string }) => (
  <Card>
    <CardContent className="flex items-center gap-3 p-6 text-sm text-muted-foreground">
      <Loader2Icon className="size-4 animate-spin" />
      {text}
    </CardContent>
  </Card>
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
    className="group hidden h-full cursor-col-resize touch-none items-center justify-center border-x bg-border/40 transition-colors hover:bg-primary/20 lg:flex"
    onPointerDown={onPointerDown}
  >
    <GripVerticalIcon className="size-3.5 text-muted-foreground opacity-60 group-hover:text-primary group-hover:opacity-100" />
  </div>
)

const RowResizeHandle = ({
  label,
  onPointerDown,
}: {
  label: string
  onPointerDown: (event: PointerEvent<HTMLDivElement>) => void
}) => (
  <div
    role="separator"
    aria-label={label}
    className="group flex w-full cursor-row-resize touch-none items-center justify-center border-y bg-border/40 transition-colors hover:bg-primary/20"
    onPointerDown={onPointerDown}
  >
    <GripHorizontalIcon className="size-3.5 text-muted-foreground opacity-60 group-hover:text-primary group-hover:opacity-100" />
  </div>
)

const ResourceList = ({ knowledgePointId }: { knowledgePointId: string }) => {
  const resourcesResult = useAtomValue(knowledgePointResourcesAtom(knowledgePointId))

  return Result.builder(resourcesResult)
    .onSuccess((resources) => (
      <div className="space-y-3">
        {resources.length === 0 ? (
          <div className="rounded-2xl bg-muted/40 p-4 text-sm text-muted-foreground">
            当前知识点还没有关联资料。
          </div>
        ) : (
          resources.map((resource) => (
            <div
              key={resource.id}
              className="rounded-2xl border bg-background p-4 shadow-sm"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="secondary">
                      {resourceTypeLabel[resource.resource_type] ??
                        resource.resource_type}
                    </Badge>
                    <span className="font-medium">{resource.title}</span>
                  </div>
                  {resource.description ? (
                    <p className="text-sm leading-6 text-muted-foreground">
                      {resource.description}
                    </p>
                  ) : null}
                  {resource.estimated_minutes ? (
                    <p className="text-xs text-muted-foreground">
                      预计 {resource.estimated_minutes} 分钟
                    </p>
                  ) : null}
                </div>

                {resource.source_url ? (
                  <Button variant="outline" size="sm" asChild>
                    <a
                      href={resource.source_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      打开
                      <ExternalLinkIcon className="ml-2 size-3" />
                    </a>
                  </Button>
                ) : null}
              </div>
            </div>
          ))
        )}
      </div>
    ))
    .onInitialOrWaiting(() => <LoadingCard text="正在加载知识点资源..." />)
    .onFailure(() => (
      <Card>
        <CardContent className="p-6 text-sm text-destructive">
          资源加载失败，请确认后端服务正常。
        </CardContent>
      </Card>
    ))
    .render()
}

const ChapterPdfList = ({
  courseId,
  chapterId,
}: {
  courseId: string
  chapterId: string | null
}) => {
  const resourcesResult = useAtomValue(courseResourcesAtom(courseId))
  const projectsResult = useAtomValue(projectsAtom)
  const project = Result.isSuccess(projectsResult)
    ? projectsResult.value.find((item) => item.course_id === courseId)
    : null

  return Result.builder(resourcesResult)
    .onSuccess((resources) => {
      const pdfResources = resources.filter(
        (resource) =>
          resource.document_id &&
          resource.chapter_id === chapterId &&
          resource.resource_type.toLowerCase() === 'pdf',
      )

      if (pdfResources.length === 0) {
        return (
          <div className="rounded-2xl bg-muted/40 p-4 text-sm text-muted-foreground">
            当前章节还没有绑定 PDF 文档。
          </div>
        )
      }

      return (
        <div className="space-y-2">
          {pdfResources.map((resource) => (
            <div
              key={resource.id}
              className="rounded-2xl border bg-background p-3 shadow-sm"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 space-y-1">
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary">PDF</Badge>
                    <span className="truncate text-sm font-medium">
                      {resource.title}
                    </span>
                  </div>
                  {resource.description ? (
                    <p className="line-clamp-2 text-xs leading-5 text-muted-foreground">
                      {resource.description}
                    </p>
                  ) : null}
                </div>

                {project && resource.document_id ? (
                  <Button variant="outline" size="sm" asChild>
                    <Link
                      to="/dashboard/p/$projectId/d/$documentId"
                      params={{
                        projectId: project.id,
                        documentId: resource.document_id,
                      }}
                    >
                      阅读
                    </Link>
                  </Button>
                ) : (
                  <Badge variant="outline">无项目入口</Badge>
                )}
              </div>
            </div>
          ))}
        </div>
      )
    })
    .onInitialOrWaiting(() => <LoadingCard text="正在加载章节 PDF..." />)
    .onFailure(() => (
      <Card>
        <CardContent className="p-6 text-sm text-destructive">
          章节 PDF 加载失败，请确认后端服务正常。
        </CardContent>
      </Card>
    ))
    .render()
}

const CourseBrowser = ({
  course,
  selectedPointId,
  onOutlineResize,
  onSelectPoint,
}: {
  course: Course
  selectedPointId: string | null
  onOutlineResize: (event: PointerEvent<HTMLDivElement>) => void
  onSelectPoint: (pointId: string) => void
}) => {
  const chaptersResult = useAtomValue(courseChaptersAtom(course.id))
  const pointsResult = useAtomValue(courseKnowledgePointsAtom(course.id))
  const [detailSectionHeight, setDetailSectionHeight] = useState(
    DEFAULT_DETAIL_SECTION_HEIGHT,
  )

  const chapters = Result.isSuccess(chaptersResult) ? chaptersResult.value : []
  const points = Result.isSuccess(pointsResult) ? pointsResult.value : []
  const selectedPoint =
    points.find((point) => point.id === selectedPointId) ?? points.at(0) ?? null

  useEffect(() => {
    if (!selectedPointId && selectedPoint) {
      onSelectPoint(selectedPoint.id)
    }
  }, [onSelectPoint, selectedPoint, selectedPointId])

  const pointsByChapter = useMemo(() => {
    return points.reduce<Partial<Record<string, Array<KnowledgePoint>>>>(
      (acc, point) => {
        const key = point.chapter_id ?? 'uncategorized'
        acc[key] = [...(acc[key] ?? []), point]
        return acc
      },
      {},
    )
  }, [points])

  const selectedChapter = selectedPoint?.chapter_id
    ? chapters.find((chapter) => chapter.id === selectedPoint.chapter_id) ?? null
    : null

  const startDetailResize = useCallback(
    (event: PointerEvent<HTMLDivElement>) => {
      event.preventDefault()
      event.currentTarget.setPointerCapture(event.pointerId)

      const startY = event.clientY
      const startHeight = detailSectionHeight

      const handlePointerMove = (moveEvent: globalThis.PointerEvent) => {
        setDetailSectionHeight(
          clamp(
            startHeight + moveEvent.clientY - startY,
            MIN_DETAIL_SECTION_HEIGHT,
            MAX_DETAIL_SECTION_HEIGHT,
          ),
        )
      }

      const handlePointerUp = () => {
        window.removeEventListener('pointermove', handlePointerMove)
        window.removeEventListener('pointerup', handlePointerUp)
        window.document.body.style.cursor = ''
        window.document.body.style.userSelect = ''
      }

      window.document.body.style.cursor = 'row-resize'
      window.document.body.style.userSelect = 'none'
      window.addEventListener('pointermove', handlePointerMove)
      window.addEventListener('pointerup', handlePointerUp, { once: true })
    },
    [detailSectionHeight],
  )

  if (!Result.isSuccess(chaptersResult) || !Result.isSuccess(pointsResult)) {
    if (Result.isFailure(chaptersResult) || Result.isFailure(pointsResult)) {
      return (
        <Card className="lg:col-span-3">
          <CardContent className="p-6 text-sm text-destructive">
            课程内容加载失败，请确认后端服务和数据库数据。
          </CardContent>
        </Card>
      )
    }

    return (
      <div className="lg:col-span-3">
        <LoadingCard text="正在加载课程章节和知识点..." />
      </div>
    )
  }

  const markdownSections = parseMarkdownSections(selectedPoint?.description)

  return (
    <>
      <Card className="flex h-full min-h-0 flex-col overflow-hidden">
        <CardHeader className="shrink-0">
          <CardTitle className="flex items-center gap-2">
            <BookOpenIcon className="size-5" />
            章节与知识点
          </CardTitle>
          <CardDescription>
            按章节浏览知识点，点击后查看正文和资源链接。
          </CardDescription>
        </CardHeader>
        <CardContent className="min-h-0 flex-1 space-y-4 overflow-y-auto">
          {chapters.map((chapter: CourseChapter) => {
            const chapterPoints = pointsByChapter[chapter.id] ?? []

            return (
              <div key={chapter.id} className="rounded-2xl border p-4">
                <div className="mb-3 flex items-start justify-between gap-3">
                  <div>
                    <h3 className="font-medium">
                      第 {chapter.position} 章：{chapter.title}
                    </h3>
                    {chapter.description ? (
                      <p className="mt-1 text-sm text-muted-foreground">
                        {chapter.description}
                      </p>
                    ) : null}
                  </div>
                  <Badge variant="outline">{chapterPoints.length} 个知识点</Badge>
                </div>

                <div className="space-y-2">
                  {chapterPoints.map((point) => (
                    <button
                      key={point.id}
                      type="button"
                      onClick={() => onSelectPoint(point.id)}
                      className={`w-full rounded-xl px-3 py-2 text-left text-sm transition ${
                        selectedPoint?.id === point.id
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-muted/40 hover:bg-muted'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span>{point.name}</span>
                        <span className="text-xs opacity-80">
                          {difficultyLabel[point.difficulty_level] ??
                            point.difficulty_level}
                        </span>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )
          })}
        </CardContent>
      </Card>

      <ColumnResizeHandle
        label="调整章节知识点区域宽度"
        onPointerDown={onOutlineResize}
      />

      <div className="flex h-full min-h-0 flex-col overflow-hidden">
        <Card
          className="flex min-h-0 flex-col overflow-hidden"
          style={{ height: detailSectionHeight }}
        >
          <CardHeader className="shrink-0">
            <CardTitle className="flex items-center gap-2">
              <FileTextIcon className="size-5" />
              {selectedPoint?.name ?? '请选择知识点'}
            </CardTitle>
            {selectedPoint ? (
              <CardDescription className="flex flex-wrap gap-2 pt-2">
                <Badge>
                  {difficultyLabel[selectedPoint.difficulty_level] ??
                    selectedPoint.difficulty_level}
                </Badge>
                {selectedPoint.tags.map((tag) => (
                  <Badge key={tag} variant="secondary">
                    {tag}
                  </Badge>
                ))}
              </CardDescription>
            ) : null}
          </CardHeader>
          <CardContent className="min-h-0 flex-1 overflow-y-auto">
            {markdownSections.length > 0 ? (
              <div className="space-y-5">
                {markdownSections.map((section) => (
                  <section key={section.title} className="rounded-2xl bg-muted/30 p-4">
                    <h3 className="mb-3 font-semibold">{section.title}</h3>
                    <div className="space-y-2 text-sm text-muted-foreground">
                      {section.body.map(renderMarkdownLine)}
                    </div>
                  </section>
                ))}
              </div>
            ) : (
              <div className="rounded-2xl bg-muted/40 p-5 text-sm text-muted-foreground">
                当前知识点还没有正文。初始化脚本会写入包含 5 个区块的
                Markdown 正文。
              </div>
            )}
          </CardContent>
        </Card>

        <RowResizeHandle
          label="调整知识点介绍和相关资料高度"
          onPointerDown={startDetailResize}
        />

        {selectedPoint ? (
          <Card className="flex min-h-0 flex-1 flex-col overflow-hidden">
            <CardHeader className="shrink-0">
              <CardTitle>相关资料/题目</CardTitle>
              <CardDescription>
                资料链接来自队长提供的数据库内容建议文档。
              </CardDescription>
            </CardHeader>
            <CardContent className="min-h-0 flex-1 space-y-5 overflow-y-auto">
              <section className="space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm font-medium">章节 PDF</div>
                  {selectedChapter ? (
                    <Badge variant="outline">{selectedChapter.title}</Badge>
                  ) : null}
                </div>
                <ChapterPdfList
                  courseId={course.id}
                  chapterId={selectedPoint.chapter_id}
                />
              </section>

              <section className="space-y-3">
                <div className="text-sm font-medium">相关资料/题目</div>
              <ResourceList knowledgePointId={selectedPoint.id} />
              </section>
            </CardContent>
          </Card>
        ) : null}
      </div>
    </>
  )
}

export const CourseLibraryPage = () => {
  const coursesResult = useAtomValue(coursesAtom)
  const [selectedCourseId, setSelectedCourseId] = useState<string | null>(null)
  const [selectedPointId, setSelectedPointId] = useState<string | null>(null)
  const [coursePanelWidth, setCoursePanelWidth] = useState(
    DEFAULT_COURSE_PANEL_WIDTH,
  )
  const [outlinePanelWidth, setOutlinePanelWidth] = useState(
    DEFAULT_OUTLINE_PANEL_WIDTH,
  )

  const courses = Result.isSuccess(coursesResult) ? coursesResult.value : []
  const selectedCourse =
    courses.find((course) => course.id === selectedCourseId) ??
    courses.at(0) ??
    null

  useEffect(() => {
    if (!selectedCourseId && selectedCourse) {
      setSelectedCourseId(selectedCourse.id)
    }
  }, [selectedCourse, selectedCourseId])

  const handleSelectCourse = (courseId: string) => {
    setSelectedCourseId(courseId)
    setSelectedPointId(null)
  }

  const startColumnResize = useCallback(
    (
      event: PointerEvent<HTMLDivElement>,
      side: 'course-panel' | 'outline-panel',
    ) => {
      event.preventDefault()
      event.currentTarget.setPointerCapture(event.pointerId)

      const startX = event.clientX
      const startCourseWidth = coursePanelWidth
      const startOutlineWidth = outlinePanelWidth

      const handlePointerMove = (moveEvent: globalThis.PointerEvent) => {
        const deltaX = moveEvent.clientX - startX
        if (side === 'course-panel') {
          setCoursePanelWidth(
            clamp(
              startCourseWidth + deltaX,
              MIN_COURSE_PANEL_WIDTH,
              MAX_COURSE_PANEL_WIDTH,
            ),
          )
          return
        }

        setOutlinePanelWidth(
          clamp(
            startOutlineWidth + deltaX,
            MIN_OUTLINE_PANEL_WIDTH,
            MAX_OUTLINE_PANEL_WIDTH,
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
    [coursePanelWidth, outlinePanelWidth],
  )

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <header className="sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 border-b bg-background px-2">
        <div className="flex flex-1 items-center gap-2 px-3">
          <SidebarTrigger />
          <Separator
            orientation="vertical"
            className="mr-2 data-[orientation=vertical]:h-4"
          />
          <div className="font-medium">课程资料库</div>
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex max-w-[1800px] flex-col gap-4 px-4 py-4">
          <section className="rounded-[30px] border bg-gradient-to-br from-sky-50 via-white to-amber-50 p-6 shadow-sm">
            <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <div className="rounded-2xl bg-primary/10 p-3 text-primary">
                    <LibraryBigIcon className="size-6" />
                  </div>
                  <div>
                    <h1 className="text-2xl font-semibold tracking-tight">
                      课程资料库
                    </h1>
                    <p className="mt-1 text-sm text-muted-foreground">
                      从课程进入章节、知识点正文和相关资料，验证 A 部分知识库浏览链路。
                    </p>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Badge variant="secondary">课程 → 章节 → 知识点</Badge>
                  <Badge variant="secondary">Markdown 正文</Badge>
                  <Badge variant="secondary">外部资料/题目链接</Badge>
                </div>
              </div>

              <div className="rounded-2xl bg-white/80 px-4 py-3 text-sm text-muted-foreground shadow-sm ring-1 ring-black/5">
                当前课程
                <div className="mt-1 text-lg font-semibold text-foreground">
                  {selectedCourse?.name ?? '等待初始化数据'}
                </div>
              </div>
            </div>
          </section>

          {Result.isSuccess(coursesResult) ? (
            courses.length === 0 ? (
              <Card>
                <CardContent className="p-8 text-center text-sm text-muted-foreground">
                  还没有课程数据。请先运行
                  <code className="mx-1 rounded bg-muted px-1 py-0.5">
                    python scripts/seed_dsa_course.py
                  </code>
                  初始化数据结构与算法知识库。
                </CardContent>
              </Card>
            ) : (
              <div
                className="sticky top-0 grid h-[calc(100svh-5.5rem)] min-h-0 gap-0 overflow-hidden lg:grid-cols-[var(--course-panel-width)_var(--resize-handle-size)_var(--outline-panel-width)_var(--resize-handle-size)_minmax(0,1fr)]"
                style={
                  {
                    '--course-panel-width': `${coursePanelWidth}px`,
                    '--outline-panel-width': `${outlinePanelWidth}px`,
                    '--resize-handle-size': `${RESIZE_HANDLE_SIZE}px`,
                  } as CSSProperties
                }
              >
                <Card className="flex min-h-0 flex-col overflow-hidden">
                  <CardHeader className="shrink-0">
                    <CardTitle>课程</CardTitle>
                    <CardDescription>选择要浏览的课程资料库。</CardDescription>
                  </CardHeader>
                  <CardContent className="min-h-0 flex-1 space-y-2 overflow-y-auto">
                    {courses.map((course) => (
                      <button
                        key={course.id}
                        type="button"
                        onClick={() => handleSelectCourse(course.id)}
                        className={`w-full rounded-2xl border px-4 py-3 text-left transition ${
                          selectedCourse?.id === course.id
                            ? 'border-primary bg-primary text-primary-foreground'
                            : 'bg-background hover:bg-muted/60'
                        }`}
                      >
                        <div className="font-medium">{course.name}</div>
                        <div className="mt-1 text-xs opacity-80">
                          {course.code ?? course.status}
                        </div>
                      </button>
                    ))}
                  </CardContent>
                </Card>

                <ColumnResizeHandle
                  label="调整课程区域宽度"
                  onPointerDown={(event) =>
                    startColumnResize(event, 'course-panel')
                  }
                />

                {selectedCourse ? (
                  <CourseBrowser
                    course={selectedCourse}
                    selectedPointId={selectedPointId}
                    onOutlineResize={(event) =>
                      startColumnResize(event, 'outline-panel')
                    }
                    onSelectPoint={setSelectedPointId}
                  />
                ) : null}
              </div>
            )
          ) : Result.isFailure(coursesResult) ? (
            <Card>
              <CardContent className="p-8 text-center text-sm text-destructive">
                课程加载失败，请确认后端服务已经启动。
              </CardContent>
            </Card>
          ) : (
            <LoadingCard text="正在加载课程资料库..." />
          )}
        </div>
      </div>
    </div>
  )
}
