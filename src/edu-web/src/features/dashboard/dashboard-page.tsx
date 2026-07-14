import { Result, useAtomValue } from '@effect-atom/atom-react'
import { Link } from '@tanstack/react-router'
import { formatDistanceToNow } from 'date-fns'
import { zhCN } from 'date-fns/locale'
import {
  FlameIcon,
  FolderIcon,
  Loader2Icon,
  MessageCircleIcon,
  PlusIcon,
  SendIcon,
  TrophyIcon,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import dashboardSlideOne from '../../../../source/1.png'
import dashboardSlideTwo from '../../../../source/2.png'
import dashboardSlideThree from '../../../../source/3.png'
import type { CarouselApi } from '@/components/ui/carousel'
import { projectsAtom } from '@/data-acess/project'
import { useCreateProjectDialog } from '@/features/project/components/upsert-project-dialog'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Carousel,
  CarouselContent,
  CarouselItem,
  CarouselNext,
  CarouselPrevious,
} from '@/components/ui/carousel'
import { Textarea } from '@/components/ui/textarea'
import { supabase } from '@/lib/supabase'

type StudyShortcutContentProps = {
  label: string
  description: string
}

type DashboardComment = {
  id: string
  user_id: string
  user_name: string
  content: string
  created_at: string
}

type LeaderboardEntry = {
  user_id: string
  user_name: string
  study_count: number
}

const serverUrl = import.meta.env.VITE_SERVER_URL ?? 'http://localhost:8000'

const dashboardSlides = [
  {
    src: dashboardSlideOne,
    alt: '数据结构知识体系可视化插画',
    position: 'object-right',
  },
  {
    src: dashboardSlideTwo,
    alt: '同学们一起学习数据结构',
    position: 'object-center',
  },
  {
    src: dashboardSlideThree,
    alt: '在资料库中学习数据结构',
    position: 'object-center',
  },
]

const studyShortcutClassName =
  'group flex min-h-0 w-full items-center bg-card/85 px-4 py-3 text-left transition-colors hover:bg-muted/60'

const StudyShortcutContent = ({
  label,
  description,
}: StudyShortcutContentProps) => (
  <div className="min-w-0 flex-1">
    <div className="font-medium leading-5">{label}</div>
    <div className="mt-0.5 truncate text-xs text-muted-foreground">
      {description}
    </div>
  </div>
)

const StudyOverviewCarousel = () => {
  const [api, setApi] = useState<CarouselApi>()
  const [current, setCurrent] = useState(0)

  useEffect(() => {
    if (!api) return

    const updateCurrentSlide = () => setCurrent(api.selectedScrollSnap())
    updateCurrentSlide()
    api.on('select', updateCurrentSlide)
    api.on('reInit', updateCurrentSlide)

    return () => {
      api.off('select', updateCurrentSlide)
      api.off('reInit', updateCurrentSlide)
    }
  }, [api])

  useEffect(() => {
    if (!api || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      return
    }

    const interval = window.setInterval(() => api.scrollNext(), 5000)
    return () => window.clearInterval(interval)
  }, [api])

  return (
    <Carousel
      setApi={setApi}
      opts={{ loop: true }}
      className="min-w-0 overflow-hidden border bg-slate-950 shadow-sm"
      aria-label="数据结构学习图片"
    >
      <CarouselContent className="-ml-0">
        {dashboardSlides.map((slide) => (
          <CarouselItem key={slide.src} className="pl-0">
            <div className="aspect-video overflow-hidden">
              <img
                src={slide.src}
                alt={slide.alt}
                className={`h-full w-full object-cover ${slide.position}`}
              />
            </div>
          </CarouselItem>
        ))}
      </CarouselContent>

      <CarouselPrevious
        variant="secondary"
        className="left-3 border-white/20 bg-black/35 text-white shadow-md backdrop-blur-sm hover:bg-black/55 hover:text-white"
      />
      <CarouselNext
        variant="secondary"
        className="right-3 border-white/20 bg-black/35 text-white shadow-md backdrop-blur-sm hover:bg-black/55 hover:text-white"
      />

      <div className="absolute inset-x-0 bottom-3 flex justify-center gap-2">
        {dashboardSlides.map((slide, index) => (
          <button
            key={slide.src}
            type="button"
            aria-label={`切换到第 ${index + 1} 张图片`}
            aria-current={current === index ? 'true' : undefined}
            onClick={() => api?.scrollTo(index)}
            className={`h-2 rounded-full shadow-sm transition-all ${
              current === index
                ? 'w-6 bg-white'
                : 'w-2 bg-white/55 hover:bg-white/80'
            }`}
          />
        ))}
      </div>
    </Carousel>
  )
}

const getAuthHeaders = async (): Promise<Record<string, string>> => {
  const {
    data: { session },
  } = await supabase.auth.getSession()
  return session?.access_token
    ? { Authorization: `Bearer ${session.access_token}` }
    : {}
}

const getInitials = (name: string) =>
  name
    .trim()
    .split(/\s+/)
    .map((part) => part[0])
    .join('')
    .toUpperCase()
    .slice(0, 2) || '同学'

const heatStyle = (count: number, maxCount: number) => {
  const intensity = maxCount === 0 ? 0 : count / maxCount
  const palette = ['#eaf6ff', '#c1e8ff', '#7da0ca', '#5483b3', '#052659']
  const paletteIndex = Math.min(
    palette.length - 1,
    Math.floor(intensity * palette.length),
  )

  return {
    backgroundColor: palette[paletteIndex],
    borderColor: intensity > 0.5 ? '#5483b3' : '#c1e8ff',
    color: intensity > 0.62 ? '#ffffff' : '#021024',
  }
}

const CommunitySection = () => {
  const [comments, setComments] = useState<Array<DashboardComment>>([])
  const [leaderboard, setLeaderboard] = useState<Array<LeaderboardEntry>>([])
  const [content, setContent] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadCommunity = useCallback(async () => {
    try {
      setError(null)
      const headers = await getAuthHeaders()
      const [commentsResponse, leaderboardResponse] = await Promise.all([
        fetch(`${serverUrl}/api/v1/dashboard/comments`, { headers }),
        fetch(`${serverUrl}/api/v1/dashboard/leaderboard`, { headers }),
      ])
      if (!commentsResponse.ok || !leaderboardResponse.ok) {
        throw new Error('社区内容加载失败')
      }
      const [nextComments, nextLeaderboard] = await Promise.all([
        commentsResponse.json() as Promise<Array<DashboardComment>>,
        leaderboardResponse.json() as Promise<Array<LeaderboardEntry>>,
      ])
      setComments(nextComments)
      setLeaderboard(nextLeaderboard)
    } catch {
      setError('暂时无法加载评论区，请稍后重试。')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadCommunity()
  }, [loadCommunity])

  const submitComment = async () => {
    const trimmedContent = content.trim()
    if (!trimmedContent || isSubmitting) return

    try {
      setIsSubmitting(true)
      setError(null)
      const authHeaders = await getAuthHeaders()
      const response = await fetch(`${serverUrl}/api/v1/dashboard/comments`, {
        method: 'POST',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: trimmedContent }),
      })
      if (!response.ok) throw new Error('评论发布失败')
      const newComment = (await response.json()) as DashboardComment
      setComments((current) => [newComment, ...current])
      setContent('')
    } catch {
      setError('评论没有发出去，请稍后再试。')
    } finally {
      setIsSubmitting(false)
    }
  }

  const maxCount = Math.max(...leaderboard.map((entry) => entry.study_count), 0)

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
      <Card className="min-w-0">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MessageCircleIcon className="h-5 w-5 text-primary" />
            学习交流区
          </CardTitle>
          <CardDescription>
            分享学习心得、提问，和大家一起交流进步。
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="rounded-2xl border bg-muted/25 p-4">
            <Textarea
              value={content}
              onChange={(event) => setContent(event.target.value)}
              onKeyDown={(event) => {
                if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
                  event.preventDefault()
                  void submitComment()
                }
              }}
              maxLength={500}
              rows={3}
              placeholder="说说你今天学到了什么……"
              className="resize-none bg-background"
            />
            <div className="mt-3 flex items-center justify-between gap-3">
              <span className="text-xs text-muted-foreground">
                {content.length}/500 · Ctrl/⌘ + Enter 发送
              </span>
              <Button
                size="sm"
                disabled={!content.trim() || isSubmitting}
                onClick={() => void submitComment()}
              >
                {isSubmitting ? (
                  <Loader2Icon className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <SendIcon className="mr-2 h-4 w-4" />
                )}
                发布评论
              </Button>
            </div>
          </div>

          {error && (
            <div className="rounded-xl bg-destructive/10 px-4 py-3 text-sm text-destructive">
              {error}
            </div>
          )}

          <div className="max-h-[520px] space-y-1 overflow-y-auto pr-1">
            {isLoading ? (
              <div className="flex justify-center py-12 text-muted-foreground">
                <Loader2Icon className="h-5 w-5 animate-spin" />
              </div>
            ) : comments.length === 0 ? (
              <div className="py-12 text-center text-sm text-muted-foreground">
                还没有评论，来做第一个发言的人吧。
              </div>
            ) : (
              comments.map((comment) => (
                <article
                  key={comment.id}
                  className="flex gap-3 rounded-2xl px-3 py-4 transition-colors hover:bg-muted/40"
                >
                  <Avatar className="h-9 w-9 shrink-0">
                    <AvatarFallback className="bg-primary/10 text-xs text-primary">
                      {getInitials(comment.user_name)}
                    </AvatarFallback>
                  </Avatar>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                      <span className="font-medium">{comment.user_name}</span>
                      <time className="text-xs text-muted-foreground">
                        {formatDistanceToNow(new Date(comment.created_at), {
                          addSuffix: true,
                          locale: zhCN,
                        })}
                      </time>
                    </div>
                    <p className="mt-1 whitespace-pre-wrap break-words text-sm leading-6 text-foreground/85">
                      {comment.content}
                    </p>
                  </div>
                </article>
              ))
            )}
          </div>
        </CardContent>
      </Card>

      <Card className="h-fit lg:sticky lg:top-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrophyIcon className="h-5 w-5 text-[#5483B3]" />
            学习次数榜
          </CardTitle>
          <CardDescription>练习越多，榜单颜色越红。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {isLoading ? (
            <div className="flex justify-center py-10 text-muted-foreground">
              <Loader2Icon className="h-5 w-5 animate-spin" />
            </div>
          ) : leaderboard.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              暂无学习记录
            </p>
          ) : (
            leaderboard.map((entry, index) => (
              <div
                key={entry.user_id}
                className="flex items-center gap-3 rounded-xl border px-3 py-3 transition-transform hover:-translate-y-0.5"
                style={heatStyle(entry.study_count, maxCount)}
              >
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-white/80 text-sm font-bold text-slate-700 shadow-sm">
                  {index + 1}
                </span>
                <span className="min-w-0 flex-1 truncate text-sm font-medium">
                  {entry.user_name}
                </span>
                <span className="flex shrink-0 items-center gap-1 text-sm font-semibold">
                  <FlameIcon className="h-4 w-4" />
                  {entry.study_count}
                </span>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  )
}

export const DashboardPage = () => {
  const projectsResult = useAtomValue(projectsAtom)
  const openCreateProjectDialog = useCreateProjectDialog((state) => state.open)

  const hasProjects =
    Result.isSuccess(projectsResult) && projectsResult.value.length > 0
  const firstProjectId = Result.isSuccess(projectsResult)
    ? projectsResult.value[0]?.id
    : undefined

  return (
    <div className="min-h-screen bg-background p-8">
      <div className="mx-auto max-w-7xl space-y-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">仪表盘</h1>
            <p className="mt-2 text-muted-foreground">
              管理项目，并快速查看今天的学习进展。
            </p>
          </div>
          {hasProjects && (
            <Button onClick={() => openCreateProjectDialog()}>
              <PlusIcon className="mr-2 h-4 w-4" />
              新建项目
            </Button>
          )}
        </div>

        <Card className="rounded-none border-primary/15 bg-gradient-to-br from-primary/8 via-background to-background shadow-sm">
          <CardHeader className="space-y-2">
            <CardTitle className="text-xl">今日学习概览</CardTitle>
            <CardDescription>
              从常用入口快速进入 AI 指导、题库、课程资料和知识图谱。
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid items-stretch lg:grid-cols-[minmax(0,4fr)_minmax(180px,1fr)]">
              <StudyOverviewCarousel />

              <div className="grid grid-cols-2 overflow-hidden border lg:grid-cols-1 lg:grid-rows-4 lg:border-l-0 [&>*:nth-child(even)]:border-l [&>*:nth-child(n+3)]:border-t lg:[&>*:nth-child(even)]:border-l-0 lg:[&>*:nth-child(n+2)]:border-t">
                {firstProjectId ? (
                  <Link
                    to="/dashboard/p/$projectId"
                    params={{ projectId: firstProjectId }}
                    className={studyShortcutClassName}
                  >
                    <StudyShortcutContent
                      label="AI 指导"
                      description="获取个性化学习建议"
                    />
                  </Link>
                ) : (
                  <button
                    type="button"
                    onClick={() => openCreateProjectDialog()}
                    className={studyShortcutClassName}
                  >
                    <StudyShortcutContent
                      label="AI 指导"
                      description="创建项目后开始使用"
                    />
                  </button>
                )}

                {firstProjectId ? (
                  <Link
                    to="/dashboard/p/$projectId/learning-evaluation/practice"
                    params={{ projectId: firstProjectId }}
                    className={studyShortcutClassName}
                  >
                    <StudyShortcutContent
                      label="学习题库"
                      description="练习并巩固知识点"
                    />
                  </Link>
                ) : (
                  <button
                    type="button"
                    onClick={() => openCreateProjectDialog()}
                    className={studyShortcutClassName}
                  >
                    <StudyShortcutContent
                      label="学习题库"
                      description="创建项目后开始练习"
                    />
                  </button>
                )}

                <Link
                  to="/dashboard/course-library"
                  className={studyShortcutClassName}
                >
                  <StudyShortcutContent
                    label="课程资料"
                    description="浏览数据结构资料库"
                  />
                </Link>

                {firstProjectId ? (
                  <Link
                    to="/dashboard/p/$projectId/knowledge-graph"
                    params={{ projectId: firstProjectId }}
                    className={studyShortcutClassName}
                  >
                    <StudyShortcutContent
                      label="知识图谱"
                      description="查看知识关联脉络"
                    />
                  </Link>
                ) : (
                  <button
                    type="button"
                    onClick={() => openCreateProjectDialog()}
                    className={studyShortcutClassName}
                  >
                    <StudyShortcutContent
                      label="知识图谱"
                      description="创建项目后查看图谱"
                    />
                  </button>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        <CommunitySection />

        {Result.isSuccess(projectsResult) ? (
          projectsResult.value.length === 0 ? (
            <Card>
              <CardHeader>
                <CardTitle>还没有项目</CardTitle>
                <CardDescription>
                  创建第一个项目，开始整理你的学习资料。
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Button onClick={() => openCreateProjectDialog()}>
                  <PlusIcon className="mr-2 h-4 w-4" />
                  创建项目
                </Button>
              </CardContent>
            </Card>
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
              {projectsResult.value.map((project) => (
                <Card
                  key={project.id}
                  className="transition-shadow hover:shadow-md"
                >
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <FolderIcon className="h-5 w-5" />
                      <Link
                        to="/dashboard/p/$projectId"
                        params={{ projectId: project.id }}
                        className="hover:underline"
                      >
                        {project.name}
                      </Link>
                    </CardTitle>
                    {project.description && (
                      <CardDescription>{project.description}</CardDescription>
                    )}
                  </CardHeader>
                  <CardContent>
                    <Link
                      to="/dashboard/p/$projectId"
                      params={{ projectId: project.id }}
                    >
                      <Button variant="outline" className="w-full">
                        打开项目
                      </Button>
                    </Link>
                  </CardContent>
                </Card>
              ))}
            </div>
          )
        ) : Result.isFailure(projectsResult) ? (
          <div className="py-12 text-center">
            <p className="text-destructive">项目加载失败</p>
          </div>
        ) : (
          <div className="py-12 text-center">
            <p className="text-muted-foreground">正在加载项目...</p>
          </div>
        )}
      </div>
    </div>
  )
}
