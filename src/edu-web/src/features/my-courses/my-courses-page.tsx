import { Result, useAtomValue } from '@effect-atom/atom-react'
import { Link } from '@tanstack/react-router'
import {
  ArrowUpRightIcon,
  BookOpenIcon,
  GraduationCapIcon,
  Layers3Icon,
  Loader2Icon,
} from 'lucide-react'
import courseStructureCover from '../../../../source/1.png'
import courseClassroomCover from '../../../../source/2.png'
import courseLearningCover from '../../../../source/3.png'
import machineLearningCover from '../../../../source/6.png'
import type { Course } from '@/data-acess/course-library'
import { coursesAtom } from '@/data-acess/course-library'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { SidebarTrigger } from '@/components/ui/sidebar'

const courseCovers = [
  courseStructureCover,
  courseClassroomCover,
  courseLearningCover,
]

const serverUrl = (
  import.meta.env.VITE_SERVER_URL ?? window.location.origin
).replace(/\/$/, '')

const resolveCourseCover = (url: string) =>
  /^(?:https?:|data:|blob:)/i.test(url)
    ? url
    : `${serverUrl}${url.startsWith('/') ? '' : '/'}${url}`

const getFallbackCourseCover = (course: Course) => {
  if (course.code === 'ML-DEMO') return machineLearningCover

  const seed = `${course.id}${course.code ?? ''}`
  const hash = Array.from(seed).reduce(
    (total, character) => total + character.charCodeAt(0),
    0,
  )

  return courseCovers[hash % courseCovers.length]
}

const getCourseCover = (course: Course) =>
  course.cover_url?.trim()
    ? resolveCourseCover(course.cover_url.trim())
    : getFallbackCourseCover(course)

const statusLabel: Record<string, string> = {
  active: '进行中',
  archived: '已归档',
  draft: '待开始',
}

const CourseCard = ({ course }: { course: Course }) => (
  <Link
    to="/dashboard/course-library"
    search={{ courseId: course.id }}
    className="group block rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
    aria-label={`打开${course.name}课程资料库`}
  >
    <article className="h-full overflow-hidden rounded-xl border border-slate-200/90 bg-white shadow-[0_1px_2px_rgba(15,23,42,0.04)] transition duration-200 group-hover:-translate-y-0.5 group-hover:border-slate-300 group-hover:shadow-[0_12px_30px_rgba(15,23,42,0.09)] dark:border-border dark:bg-card">
      <div className="relative aspect-[16/9] overflow-hidden bg-slate-950">
        <img
          src={getCourseCover(course)}
          alt=""
          className="size-full object-cover transition duration-500 group-hover:scale-[1.025]"
          onError={(event) => {
            event.currentTarget.src = getFallbackCourseCover(course)
          }}
        />
        <div className="absolute inset-0 bg-gradient-to-t from-slate-950/45 via-transparent to-transparent" />
        <Badge className="absolute left-4 top-4 border-white/20 bg-slate-950/70 text-white shadow-sm backdrop-blur-sm hover:bg-slate-950/70">
          {statusLabel[course.status] ?? course.status}
        </Badge>
      </div>

      <div className="flex min-h-48 flex-col p-5">
        <div className="mb-3 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.14em] text-slate-500 dark:text-muted-foreground">
          <BookOpenIcon className="size-3.5" />
          {course.code || '专业课程'}
        </div>
        <h2 className="text-lg font-semibold tracking-tight text-slate-950 dark:text-card-foreground">
          {course.name}
        </h2>
        <p className="mt-2 line-clamp-2 text-sm leading-6 text-slate-600 dark:text-muted-foreground">
          {course.description || '查看课程章节、知识点与相关学习资料。'}
        </p>

        <div className="mt-auto flex items-center justify-between border-t border-slate-100 pt-4 text-sm font-medium text-slate-700 dark:border-border dark:text-foreground">
          <span>进入课程资料库</span>
          <ArrowUpRightIcon className="size-4 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
        </div>
      </div>
    </article>
  </Link>
)

const EmptyState = () => (
  <Card className="border-dashed bg-white/80 shadow-none dark:bg-card/80">
    <CardContent className="flex flex-col items-center px-6 py-16 text-center">
      <div className="mb-4 flex size-12 items-center justify-center rounded-xl bg-slate-100 text-slate-700 dark:bg-muted dark:text-foreground">
        <Layers3Icon className="size-6" />
      </div>
      <h2 className="font-semibold">暂无课程</h2>
      <p className="mt-2 max-w-md text-sm leading-6 text-muted-foreground">
        课程创建并关联到当前账户后，会自动显示在这里。
      </p>
    </CardContent>
  </Card>
)

export const MyCoursesPage = () => {
  const coursesResult = useAtomValue(coursesAtom)

  return (
    <div className="min-h-full bg-slate-50/70 dark:bg-background">
      <header className="sticky top-0 z-10 flex h-14 items-center border-b bg-background/95 px-5 backdrop-blur sm:px-8">
        <SidebarTrigger />
        <Separator
          orientation="vertical"
          className="mx-3 data-[orientation=vertical]:h-4"
        />
        <span className="text-sm font-medium">我的课程</span>
      </header>

      <main className="mx-auto w-full max-w-7xl px-5 py-8 sm:px-8 lg:px-10 lg:py-10">
        <section className="mb-8 flex flex-col justify-between gap-5 border-b border-slate-200 pb-7 sm:flex-row sm:items-end dark:border-border">
          <div>
            <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-muted-foreground">
              <GraduationCapIcon className="size-4" />
              Course workspace
            </div>
            <h1 className="text-3xl font-semibold tracking-tight text-slate-950 dark:text-foreground">
              我的课程
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600 dark:text-muted-foreground">
              集中查看已加入的课程，进入对应课程资料库继续学习。
            </p>
          </div>

          {Result.isSuccess(coursesResult) ? (
            <div className="shrink-0 text-sm text-slate-500 dark:text-muted-foreground">
              共{' '}
              <span className="font-semibold text-slate-900 dark:text-foreground">
                {coursesResult.value.length}
              </span>{' '}
              门课程
            </div>
          ) : null}
        </section>

        {Result.isSuccess(coursesResult) ? (
          coursesResult.value.length > 0 ? (
            <section className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
              {coursesResult.value.map((course) => (
                <CourseCard key={course.id} course={course} />
              ))}
            </section>
          ) : (
            <EmptyState />
          )
        ) : Result.isFailure(coursesResult) ? (
          <Card className="border-destructive/30 bg-white shadow-none dark:bg-card">
            <CardContent className="px-6 py-10 text-center text-sm text-destructive">
              课程加载失败，请确认服务已启动后重试。
            </CardContent>
          </Card>
        ) : (
          <Card className="bg-white shadow-none dark:bg-card">
            <CardContent className="flex items-center justify-center gap-3 px-6 py-12 text-sm text-muted-foreground">
              <Loader2Icon className="size-4 animate-spin" />
              正在加载课程...
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  )
}
