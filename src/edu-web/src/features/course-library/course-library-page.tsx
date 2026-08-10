import { Result, useAtomValue } from '@effect-atom/atom-react'
import { Link } from '@tanstack/react-router'
import { useEffect, useMemo, useState } from 'react'
import {
  BookOpenIcon,
  ChevronDownIcon,
  ExternalLinkIcon,
  FileTextIcon,
  LibraryBigIcon,
  ListChecksIcon,
  Loader2Icon,
} from 'lucide-react'
import type {
  Course,
  CourseChapter,
  CourseQuestionLink,
  KnowledgePoint,
} from '@/data-acess/course-library'
import {
  courseChaptersAtom,
  courseKnowledgePointsAtom,
  courseQuestionsAtom,
  courseResourcesAtom,
  coursesAtom,
  knowledgePointResourcesAtom,
} from '@/data-acess/course-library'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Response } from '@/components/ai-elements/response'
import { ResourceResultPreview } from '@/features/resource-package/components/resource-result-preview'

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
  lecture_note: '讲解笔记',
  mind_map: '思维导图',
  practice_set: '分层练习',
  flashcards: '闪卡',
  ppt_outline: 'PPT 大纲',
  pptx: 'PPT',
  programming_questions: '编程练习',
  video_recommendations: '精准视频',
}

const LoadingCard = ({ text }: { text: string }) => (
  <Card>
    <CardContent className="flex items-center gap-3 p-6 text-sm text-muted-foreground">
      <Loader2Icon className="size-4 animate-spin" />
      {text}
    </CardContent>
  </Card>
)

const ResourceList = ({ knowledgePointId }: { knowledgePointId: string }) => {
  const resourcesResult = useAtomValue(
    knowledgePointResourcesAtom(knowledgePointId),
  )

  return Result.builder(resourcesResult)
    .onSuccess((resources) => (
      <div className="space-y-3">
        {resources.length === 0 ? (
          <div className="rounded-2xl bg-muted/40 p-4 text-sm text-muted-foreground">
            当前知识点还没有关联资料。
          </div>
        ) : (
          [...resources]
            .sort(
              (left, right) =>
                Number(Boolean(right.generated_resource)) -
                Number(Boolean(left.generated_resource)),
            )
            .map((resource) => (
              <div
                key={resource.id}
                className="rounded-2xl border bg-card p-4 text-card-foreground shadow-sm"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="secondary">
                        {resourceTypeLabel[resource.resource_type] ??
                          resource.resource_type}
                      </Badge>
                      {resource.generated_resource ? (
                        <Badge variant="outline">站内学习</Badge>
                      ) : null}
                      <span className="font-medium">{resource.title}</span>
                    </div>
                    {resource.description ? (
                      <Response className="text-sm leading-6 text-muted-foreground">
                        {resource.description}
                      </Response>
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
                        延伸阅读
                        <ExternalLinkIcon className="ml-2 size-3" />
                      </a>
                    </Button>
                  ) : null}
                </div>
                {resource.generated_resource &&
                resource.generated_resource.resource_type !== 'image' ? (
                  <div className="mt-4 border-t pt-4">
                    <ResourceResultPreview
                      projectId={resource.generated_resource.project_id}
                      resource={resource.generated_resource}
                      truncateText={false}
                    />
                  </div>
                ) : null}
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

const RelatedQuestionLink = ({ item }: { item: CourseQuestionLink }) => {
  const content = (
    <>
      去做题
      <ExternalLinkIcon className="ml-2 size-3" />
    </>
  )

  if (item.type === 'quiz') {
    return (
      <Button variant="outline" size="sm" asChild>
        <Link
          to="/dashboard/p/$projectId/q/$quizId"
          params={{ projectId: item.projectId, quizId: item.resourceId }}
        >
          {content}
        </Link>
      </Button>
    )
  }

  return (
    <Button variant="outline" size="sm" asChild>
      <Link
        to="/dashboard/p/$projectId/programming/$resourceId"
        params={{ projectId: item.projectId, resourceId: item.resourceId }}
      >
        {content}
      </Link>
    </Button>
  )
}

const RelatedQuestionList = ({
  courseId,
  knowledgePointId,
}: {
  courseId: string
  knowledgePointId: string
}) => {
  const questionsResult = useAtomValue(courseQuestionsAtom(courseId))

  return Result.builder(questionsResult)
    .onSuccess((courseQuestions) => {
      const questions = courseQuestions.filter((question) =>
        question.knowledgePointIds.includes(knowledgePointId),
      )

      return questions.length === 0 ? (
        <div className="rounded-2xl bg-muted/40 p-4 text-sm text-muted-foreground">
          当前知识点还没有关联题目。
        </div>
      ) : (
        <div className="space-y-3">
          {questions.map((item) => (
            <div
              key={`${item.projectId}-${item.type}-${item.resourceId}-${item.id}`}
              className="flex flex-col gap-3 rounded-2xl border bg-card p-4 text-card-foreground shadow-sm sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="min-w-0 space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="secondary">
                    {item.type === 'quiz' ? '选择题' : '编程题'}
                  </Badge>
                  <span className="font-medium">{item.title}</span>
                </div>
                <p className="text-xs text-muted-foreground">
                  来自项目：{item.projectName} · 题目组：{item.resourceName}
                </p>
              </div>
              <div className="shrink-0">
                <RelatedQuestionLink item={item} />
              </div>
            </div>
          ))}
        </div>
      )
    })
    .onInitialOrWaiting(() => <LoadingCard text="正在加载相关题目..." />)
    .onFailure(() => (
      <Card>
        <CardContent className="p-6 text-sm text-destructive">
          相关题目加载失败，请稍后重试。
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
              className="rounded-2xl border bg-card p-3 text-card-foreground shadow-sm"
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
                    <Response className="line-clamp-2 text-xs leading-5 text-muted-foreground">
                      {resource.description}
                    </Response>
                  ) : null}
                </div>

                {resource.document_project_id && resource.document_id ? (
                  <Button variant="outline" size="sm" asChild>
                    <Link
                      to="/dashboard/p/$projectId/d/$documentId"
                      params={{
                        projectId: resource.document_project_id,
                        documentId: resource.document_id,
                      }}
                    >
                      阅读
                    </Link>
                  </Button>
                ) : (
                  <Badge variant="outline">PDF 暂不可用</Badge>
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
  courses,
  course,
  selectedPointId,
  onSelectCourse,
  onSelectPoint,
}: {
  courses: Array<Course>
  course: Course
  selectedPointId: string | null
  onSelectCourse: (courseId: string) => void
  onSelectPoint: (pointId: string) => void
}) => {
  const chaptersResult = useAtomValue(courseChaptersAtom(course.id))
  const pointsResult = useAtomValue(courseKnowledgePointsAtom(course.id))

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
    ? (chapters.find((chapter) => chapter.id === selectedPoint.chapter_id) ??
      null)
    : null

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

  return (
    <>
      <Card className="flex h-full min-h-0 flex-col overflow-hidden">
        <CardHeader className="shrink-0 space-y-4">
          <div className="space-y-2">
            <div className="text-xs font-medium text-muted-foreground">
              选择课程
            </div>
            <Select value={course.id} onValueChange={onSelectCourse}>
              <SelectTrigger className="mx-auto w-full max-w-60 bg-background">
                <SelectValue placeholder="请选择课程" />
              </SelectTrigger>
              <SelectContent align="start">
                {courses.map((item) => (
                  <SelectItem key={item.id} value={item.id}>
                    {item.name}
                    {item.code ? ` · ${item.code}` : ''}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <CardTitle className="flex items-center gap-2">
            <BookOpenIcon className="size-5" />
            章节与知识点
          </CardTitle>
        </CardHeader>
        <CardContent className="min-h-0 flex-1 space-y-5 overflow-y-auto">
          {chapters.map((chapter: CourseChapter) => {
            const chapterPoints = pointsByChapter[chapter.id] ?? []

            return (
              <section key={chapter.id}>
                <div className="mb-2 flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="flex items-center gap-1.5 font-medium">
                      <ChevronDownIcon className="size-3.5 shrink-0 text-muted-foreground" />
                      第 {chapter.position} 章：{chapter.title}
                    </h3>
                  </div>
                  <span className="shrink-0 pt-0.5 text-xs text-muted-foreground">
                    {chapterPoints.length} 个知识点
                  </span>
                </div>

                <div className="space-y-0.5 pl-5">
                  {chapterPoints.map((point) => (
                    <button
                      key={point.id}
                      type="button"
                      onClick={() => onSelectPoint(point.id)}
                      className={`w-full px-2 py-2 text-left text-sm transition-colors ${
                        selectedPoint?.id === point.id
                          ? 'bg-primary/10 text-primary'
                          : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground'
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
              </section>
            )
          })}
        </CardContent>
      </Card>

      <Card className="flex h-full min-h-0 flex-col overflow-hidden">
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
        <CardContent className="min-h-0 flex-1 space-y-8 overflow-y-auto">
          {selectedPoint?.description ? (
            <section className="rounded-2xl bg-muted/30 p-4">
              <Response className="text-sm text-muted-foreground">
                {selectedPoint.description}
              </Response>
            </section>
          ) : (
            <div className="rounded-2xl bg-muted/40 p-5 text-sm text-muted-foreground">
              当前知识点还没有正文。初始化脚本会写入包含 5 个区块的 Markdown
              正文。
            </div>
          )}

          {selectedPoint ? (
            <section className="space-y-5 border-t pt-6">
              <div>
                <h2 className="font-semibold">相关资料/题目</h2>
              </div>
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
                <div className="text-sm font-medium">相关资料</div>
                <ResourceList knowledgePointId={selectedPoint.id} />
              </section>

              <section className="space-y-3">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <ListChecksIcon className="size-4" />
                  相关题目
                </div>
                <RelatedQuestionList
                  courseId={course.id}
                  knowledgePointId={selectedPoint.id}
                />
              </section>
            </section>
          ) : null}
        </CardContent>
      </Card>
    </>
  )
}

export const CourseLibraryPage = ({
  initialCourseId,
}: {
  initialCourseId?: string
}) => {
  const coursesResult = useAtomValue(coursesAtom)
  const [selectedCourseId, setSelectedCourseId] = useState<string | null>(
    initialCourseId ?? null,
  )
  const [selectedPointId, setSelectedPointId] = useState<string | null>(null)

  const courses = Result.isSuccess(coursesResult) ? coursesResult.value : []
  const selectedCourse =
    courses.find((course) => course.id === selectedCourseId) ??
    courses.at(0) ??
    null

  useEffect(() => {
    if (selectedCourse && selectedCourseId !== selectedCourse.id) {
      setSelectedCourseId(selectedCourse.id)
    }
  }, [selectedCourse, selectedCourseId])

  useEffect(() => {
    if (initialCourseId) {
      setSelectedCourseId(initialCourseId)
      setSelectedPointId(null)
    }
  }, [initialCourseId])

  const handleSelectCourse = (courseId: string) => {
    setSelectedCourseId(courseId)
    setSelectedPointId(null)
  }

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
        <div className="flex min-h-full flex-col gap-4 px-4 py-4">
          <section className="flex items-center gap-3 px-1 py-2">
            <LibraryBigIcon className="size-5 text-muted-foreground" />
            <div>
              <h1 className="text-xl font-semibold tracking-tight">
                课程资料库
              </h1>
              <p className="mt-0.5 text-sm text-muted-foreground">
                浏览课程章节、知识点正文与相关资料
              </p>
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
              <div className="sticky top-0 grid h-[calc(100svh-10rem)] min-h-[560px] grid-cols-1 grid-rows-[minmax(220px,1fr)_minmax(320px,2fr)] gap-4 overflow-hidden lg:grid-cols-[minmax(240px,4fr)_minmax(0,9fr)] lg:grid-rows-1">
                {selectedCourse ? (
                  <CourseBrowser
                    courses={courses}
                    course={selectedCourse}
                    selectedPointId={selectedPointId}
                    onSelectCourse={handleSelectCourse}
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
