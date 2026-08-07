import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import { Link } from '@tanstack/react-router'
import { formatDistanceToNow } from 'date-fns'
import { zhCN } from 'date-fns/locale'
import {
  CheckCircle2Icon,
  Clock3Icon,
  FlameIcon,
  FolderIcon,
  HeartIcon,
  Loader2Icon,
  MessageCircleIcon,
  PlusIcon,
  ReplyIcon,
  SendIcon,
  SquarePenIcon,
  Trash2Icon,
  TrophyIcon,
  WrenchIcon,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import dashboardSlideOne from '../../../../source/1.png'
import dashboardSlideTwo from '../../../../source/2.png'
import dashboardSlideThree from '../../../../source/3.png'
import type { CarouselApi } from '@/components/ui/carousel'
import { deleteProjectAtom, projectsAtom } from '@/data-acess/project'
import { useCreateProjectDialog } from '@/features/project/components/upsert-project-dialog'
import { useConfirmationDialog } from '@/components/confirmation-dialog'
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
import { authClient } from '@/lib/auth-client'

type StudyShortcutContentProps = {
  label: string
  description: string
}

type DashboardComment = {
  id: string
  user_id: string
  user_name: string
  parent_id: string | null
  content: string
  created_at: string
  like_count: number
  is_liked: boolean
  replies: Array<DashboardComment>
}

type LeaderboardEntry = {
  user_id: string
  user_name: string
  study_count: number
}

const serverUrl = import.meta.env.VITE_SERVER_URL ?? window.location.origin

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

const todayStudyStats = [
  {
    label: '学习时长',
    value: '2.5 小时',
    icon: Clock3Icon,
    className:
      'border-primary/20 bg-gradient-to-br from-[#e7f1fd] to-[#d3e5fa] text-[#155ba8] shadow-[#8db8e4]/15 dark:border-primary/30 dark:from-[#173353] dark:to-[#244b76] dark:text-[#b9d9fb]',
  },
  {
    label: '练习题目',
    value: '18 道',
    icon: SquarePenIcon,
    className:
      'border-[#d4635d]/20 bg-gradient-to-br from-[#fbeceb] to-[#f5d9d6] text-[#ad4843] shadow-[#d98b85]/15 dark:border-[#dc7a74]/30 dark:from-[#442725] dark:to-[#59302d] dark:text-[#f0b0ab]',
  },
  {
    label: '工具调用',
    value: '12 次',
    icon: WrenchIcon,
    className:
      'border-warning/25 bg-gradient-to-br from-[#fbf3df] to-[#f4e3b4] text-[#825912] shadow-[#d9ad55]/15 dark:border-warning/30 dark:from-[#3a2d18] dark:to-[#4b391b] dark:text-[#e6c27a]',
  },
  {
    label: '今日计划',
    value: '已完成',
    icon: CheckCircle2Icon,
    className:
      'border-[#6d98c2]/25 bg-gradient-to-br from-[#edf3fa] to-[#d9e6f3] text-[#315f8e] shadow-[#8cabc8]/15 dark:border-[#78afe8]/25 dark:from-[#203044] dark:to-[#2d435b] dark:text-[#b7cfe5]',
  },
]

const studyShortcutClassName =
  'group flex min-h-0 w-full items-center bg-card/85 px-3 py-2 text-left transition-colors hover:bg-muted/60'

const TodayStudyStats = () => (
  <div className="grid w-full grid-cols-2 gap-2">
    {todayStudyStats.map((stat) => {
      const Icon = stat.icon

      return (
        <div
          key={stat.label}
          className={`min-w-0 rounded-xl border p-2.5 shadow-md ${stat.className}`}
        >
          <div className="flex min-w-0 items-center gap-1.5">
            <span className="flex size-6 shrink-0 items-center justify-center rounded-md bg-white/70 ring-1 ring-current/10">
              <Icon className="size-3.5" aria-hidden="true" />
            </span>
            <p className="truncate text-[11px] font-medium opacity-75">
              {stat.label}
            </p>
          </div>
          <p className="mt-1 truncate text-sm font-bold tracking-tight">
            {stat.value}
          </p>
        </div>
      )
    })}
  </div>
)

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
  } = await authClient.auth.getSession()
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
  const palette = ['#eef5fd', '#d8e8fa', '#f7edcf', '#e5b858', '#c95d57']
  const borderPalette = ['#d6e5f5', '#bdd5ee', '#ead9a8', '#d1a044', '#b94f4a']
  const paletteIndex = Math.min(
    palette.length - 1,
    Math.floor(intensity * palette.length),
  )

  return {
    backgroundColor: palette[paletteIndex],
    borderColor: borderPalette[paletteIndex],
    color: intensity > 0.8 ? '#ffffff' : '#20324b',
  }
}

const CommunitySection = () => {
  const [comments, setComments] = useState<Array<DashboardComment>>([])
  const [leaderboard, setLeaderboard] = useState<Array<LeaderboardEntry>>([])
  const [content, setContent] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [replyingTo, setReplyingTo] = useState<string | null>(null)
  const [replyContent, setReplyContent] = useState('')
  const [submittingReplyId, setSubmittingReplyId] = useState<string | null>(
    null,
  )
  const [likingIds, setLikingIds] = useState<Set<string>>(() => new Set())
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

  const updateComment = (
    items: Array<DashboardComment>,
    commentId: string,
    update: (comment: DashboardComment) => DashboardComment,
  ): Array<DashboardComment> =>
    items.map((comment) => {
      if (comment.id === commentId) return update(comment)
      if (comment.replies.some((reply) => reply.id === commentId)) {
        return {
          ...comment,
          replies: comment.replies.map((reply) =>
            reply.id === commentId ? update(reply) : reply,
          ),
        }
      }
      return comment
    })

  const toggleLike = async (commentId: string) => {
    if (likingIds.has(commentId)) return
    setLikingIds((current) => new Set(current).add(commentId))
    try {
      const authHeaders = await getAuthHeaders()
      const response = await fetch(
        `${serverUrl}/api/v1/dashboard/comments/${encodeURIComponent(commentId)}/like`,
        { method: 'POST', headers: authHeaders },
      )
      if (!response.ok) throw new Error('点赞操作失败')
      const result = (await response.json()) as {
        like_count: number
        is_liked: boolean
      }
      setComments((current) =>
        updateComment(current, commentId, (comment) => ({
          ...comment,
          like_count: result.like_count,
          is_liked: result.is_liked,
        })),
      )
    } catch {
      setError('点赞操作失败，请稍后再试。')
    } finally {
      setLikingIds((current) => {
        const next = new Set(current)
        next.delete(commentId)
        return next
      })
    }
  }

  const submitReply = async (commentId: string) => {
    const trimmedContent = replyContent.trim()
    if (!trimmedContent || submittingReplyId) return
    setSubmittingReplyId(commentId)
    setError(null)
    try {
      const authHeaders = await getAuthHeaders()
      const response = await fetch(
        `${serverUrl}/api/v1/dashboard/comments/${encodeURIComponent(commentId)}/replies`,
        {
          method: 'POST',
          headers: { ...authHeaders, 'Content-Type': 'application/json' },
          body: JSON.stringify({ content: trimmedContent }),
        },
      )
      if (!response.ok) throw new Error('回复发布失败')
      const reply = (await response.json()) as DashboardComment
      const parentId = reply.parent_id ?? commentId
      setComments((current) =>
        updateComment(current, parentId, (comment) => ({
          ...comment,
          replies: [...comment.replies, reply],
        })),
      )
      setReplyContent('')
      setReplyingTo(null)
    } catch {
      setError('回复没有发出去，请稍后再试。')
    } finally {
      setSubmittingReplyId(null)
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
                  className="rounded-2xl px-3 py-4 transition-colors hover:bg-muted/40"
                >
                  <div className="flex gap-3">
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
                      <div className="mt-2 flex items-center gap-1">
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          className={comment.is_liked ? 'text-rose-600' : ''}
                          disabled={likingIds.has(comment.id)}
                          aria-pressed={comment.is_liked}
                          onClick={() => void toggleLike(comment.id)}
                        >
                          <HeartIcon
                            className={`mr-1 size-4 ${comment.is_liked ? 'fill-current' : ''}`}
                          />
                          {comment.like_count > 0 ? comment.like_count : '点赞'}
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          onClick={() => {
                            setReplyingTo((current) =>
                              current === comment.id ? null : comment.id,
                            )
                            setReplyContent('')
                          }}
                        >
                          <ReplyIcon className="mr-1 size-4" />
                          回复
                        </Button>
                      </div>
                    </div>
                  </div>

                  {comment.replies.length > 0 ? (
                    <div className="mt-3 ml-12 space-y-2 border-l pl-3">
                      {comment.replies.map((reply) => (
                        <div
                          key={reply.id}
                          className="flex gap-2 rounded-xl bg-muted/35 p-3"
                        >
                          <Avatar className="size-7 shrink-0">
                            <AvatarFallback className="text-[10px]">
                              {getInitials(reply.user_name)}
                            </AvatarFallback>
                          </Avatar>
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-baseline gap-2 text-sm">
                              <span className="font-medium">
                                {reply.user_name}
                              </span>
                              <time className="text-xs text-muted-foreground">
                                {formatDistanceToNow(
                                  new Date(reply.created_at),
                                  {
                                    addSuffix: true,
                                    locale: zhCN,
                                  },
                                )}
                              </time>
                            </div>
                            <p className="mt-1 whitespace-pre-wrap break-words text-sm leading-6">
                              {reply.content}
                            </p>
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              className={`mt-1 ${reply.is_liked ? 'text-rose-600' : ''}`}
                              disabled={likingIds.has(reply.id)}
                              aria-pressed={reply.is_liked}
                              onClick={() => void toggleLike(reply.id)}
                            >
                              <HeartIcon
                                className={`mr-1 size-3.5 ${reply.is_liked ? 'fill-current' : ''}`}
                              />
                              {reply.like_count > 0 ? reply.like_count : '点赞'}
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : null}

                  {replyingTo === comment.id ? (
                    <div className="mt-3 ml-12 rounded-xl border bg-card p-3 text-card-foreground">
                      <Textarea
                        autoFocus
                        value={replyContent}
                        onChange={(event) =>
                          setReplyContent(event.target.value)
                        }
                        onKeyDown={(event) => {
                          if (
                            (event.ctrlKey || event.metaKey) &&
                            event.key === 'Enter'
                          ) {
                            event.preventDefault()
                            void submitReply(comment.id)
                          }
                        }}
                        maxLength={500}
                        rows={2}
                        className="resize-none"
                        placeholder={`回复 ${comment.user_name}…`}
                      />
                      <div className="mt-2 flex justify-end gap-2">
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          onClick={() => {
                            setReplyingTo(null)
                            setReplyContent('')
                          }}
                        >
                          取消
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          disabled={
                            !replyContent.trim() || Boolean(submittingReplyId)
                          }
                          onClick={() => void submitReply(comment.id)}
                        >
                          {submittingReplyId === comment.id ? (
                            <Loader2Icon className="mr-2 size-4 animate-spin" />
                          ) : (
                            <SendIcon className="mr-2 size-4" />
                          )}
                          发布回复
                        </Button>
                      </div>
                    </div>
                  ) : null}
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
  const deleteProject = useAtomSet(deleteProjectAtom, { mode: 'promise' })
  const openCreateProjectDialog = useCreateProjectDialog((state) => state.open)
  const confirmationDialog = useConfirmationDialog()
  const [deletingProjectId, setDeletingProjectId] = useState<string | null>(
    null,
  )

  const hasProjects =
    Result.isSuccess(projectsResult) && projectsResult.value.length > 0
  const firstProjectId = Result.isSuccess(projectsResult)
    ? projectsResult.value[0]?.id
    : undefined

  const handleDeleteProject = async (
    projectId: string,
    projectName: string,
  ) => {
    const confirmed = await confirmationDialog.open({
      title: '删除项目',
      description: `确定要删除“${projectName}”吗？此操作无法撤销，并会删除项目中的聊天、文档和 AI 内容。`,
      confirmLabel: '删除',
      cancelLabel: '取消',
      variant: 'destructive',
    })

    if (!confirmed) return

    setDeletingProjectId(projectId)
    try {
      await deleteProject(projectId)
    } finally {
      setDeletingProjectId(null)
    }
  }

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

        <div className="grid items-stretch gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(270px,1fr)]">
          <div className="grid items-stretch sm:grid-cols-[minmax(0,4fr)_minmax(130px,1fr)]">
            <StudyOverviewCarousel />

            <div className="grid grid-cols-2 overflow-hidden border sm:grid-cols-1 sm:grid-rows-4 sm:border-l-0 [&>*:nth-child(even)]:border-l [&>*:nth-child(n+3)]:border-t sm:[&>*:nth-child(even)]:border-l-0 sm:[&>*:nth-child(n+2)]:border-t">
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

          <Card className="rounded-none border-primary/15 bg-card shadow-sm">
            <CardHeader className="gap-2 px-4">
              <CardTitle className="text-xl">今日学习概览</CardTitle>
              <CardDescription>汇总今天的学习投入与计划进度。</CardDescription>
            </CardHeader>
            <CardContent className="px-4">
              <TodayStudyStats />
            </CardContent>
          </Card>
        </div>

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
                  <CardContent className="flex gap-2">
                    <Button asChild variant="outline" className="flex-1">
                      <Link
                        to="/dashboard/p/$projectId"
                        params={{ projectId: project.id }}
                      >
                        打开项目
                      </Link>
                    </Button>
                    <Button
                      variant="destructive"
                      size="icon"
                      disabled={deletingProjectId === project.id}
                      aria-label={`删除项目 ${project.name}`}
                      title="删除项目"
                      onClick={() =>
                        void handleDeleteProject(project.id, project.name)
                      }
                    >
                      {deletingProjectId === project.id ? (
                        <Loader2Icon className="size-4 animate-spin" />
                      ) : (
                        <Trash2Icon className="size-4" />
                      )}
                    </Button>
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
