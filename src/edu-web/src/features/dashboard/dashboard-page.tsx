import { Result, useAtomValue } from '@effect-atom/atom-react'
import { Link } from '@tanstack/react-router'
import { formatDistanceToNow } from 'date-fns'
import { zhCN } from 'date-fns/locale'
import {
  BookOpenIcon,
  Clock3Icon,
  FlameIcon,
  FolderIcon,
  GraduationCapIcon,
  Loader2Icon,
  MessageCircleIcon,
  PlusIcon,
  SendIcon,
  TrophyIcon,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { projectsAtom } from '@/data-acess/project'
import { usageAtom } from '@/data-acess/usage'
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
import { Textarea } from '@/components/ui/textarea'
import { supabase } from '@/lib/supabase'

type StudyStat = {
  label: string
  value: string
  description: string
  icon: typeof BookOpenIcon
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

const formatStudyDuration = (minutes: number) => {
  if (minutes < 60) return `${minutes} 分钟`
  const hours = Math.floor(minutes / 60)
  const remainingMinutes = minutes % 60
  return remainingMinutes === 0
    ? `${hours} 小时`
    : `${hours} 小时 ${remainingMinutes} 分钟`
}

const heatStyle = (count: number, maxCount: number) => {
  const intensity = maxCount === 0 ? 0 : count / maxCount
  return {
    backgroundColor: `hsl(0 84% ${96 - intensity * 43}%)`,
    borderColor: `hsl(0 72% ${90 - intensity * 38}%)`,
    color: intensity > 0.62 ? 'white' : `hsl(0 72% ${42 - intensity * 12}%)`,
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
            <TrophyIcon className="h-5 w-5 text-amber-500" />
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
  const usageResult = useAtomValue(usageAtom)
  const openCreateProjectDialog = useCreateProjectDialog((state) => state.open)

  const hasProjects =
    Result.isSuccess(projectsResult) && projectsResult.value.length > 0

  const todayStudyStats: Array<StudyStat> = Result.isSuccess(usageResult)
    ? (() => {
        const activityCount =
          usageResult.value.chat_messages.used +
          usageResult.value.flashcard_generations.used +
          usageResult.value.quiz_generations.used +
          usageResult.value.mindmap_generations.used
        const estimatedMinutes =
          usageResult.value.chat_messages.used * 6 +
          usageResult.value.flashcard_generations.used * 12 +
          usageResult.value.quiz_generations.used * 15 +
          usageResult.value.mindmap_generations.used * 10
        const masteredKnowledgePoints =
          usageResult.value.flashcard_generations.used * 3 +
          usageResult.value.quiz_generations.used * 2 +
          usageResult.value.mindmap_generations.used * 4

        return [
          {
            label: '已学内容',
            value: `${activityCount} 项`,
            description: '按今日学习活动汇总',
            icon: BookOpenIcon,
          },
          {
            label: '学习时长',
            value: formatStudyDuration(estimatedMinutes),
            description: '依据今日学习活动估算',
            icon: Clock3Icon,
          },
          {
            label: '掌握知识点',
            value: `${masteredKnowledgePoints} 个`,
            description: '依据今日练习与内容生成估算',
            icon: GraduationCapIcon,
          },
        ]
      })()
    : [
        {
          label: '已学内容',
          value: Result.isFailure(usageResult) ? '0 项' : '--',
          description: Result.isFailure(usageResult)
            ? '暂时无法获取今日学习数据'
            : '正在加载今日学习概览',
          icon: BookOpenIcon,
        },
        {
          label: '学习时长',
          value: Result.isFailure(usageResult) ? '0 分钟' : '--',
          description: Result.isFailure(usageResult)
            ? '暂时无法获取今日学习数据'
            : '正在整理学习时长',
          icon: Clock3Icon,
        },
        {
          label: '掌握知识点',
          value: Result.isFailure(usageResult) ? '0 个' : '--',
          description: Result.isFailure(usageResult)
            ? '暂时无法获取今日学习数据'
            : '正在汇总掌握情况',
          icon: GraduationCapIcon,
        },
      ]

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

        <Card className="border-primary/15 bg-gradient-to-br from-primary/8 via-background to-background shadow-sm">
          <CardHeader className="space-y-2">
            <CardTitle className="text-xl">今日学习概览</CardTitle>
            <CardDescription>
              集中展示你今天已经学习的内容、投入的时间和掌握情况。
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-3">
            {todayStudyStats.map((stat) => {
              const Icon = stat.icon
              return (
                <div
                  key={stat.label}
                  className="rounded-2xl border bg-card/80 p-5 backdrop-blur"
                >
                  <div className="mb-4 flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">
                      {stat.label}
                    </span>
                    <div className="rounded-full bg-primary/10 p-2 text-primary">
                      <Icon className="h-4 w-4" />
                    </div>
                  </div>
                  <div className="text-3xl font-semibold tracking-tight">
                    {stat.value}
                  </div>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">
                    {stat.description}
                  </p>
                </div>
              )
            })}
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
