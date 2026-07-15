import { Result, useAtomValue } from '@effect-atom/atom-react'
import {
  ActivityIcon,
  BrainCircuitIcon,
  CheckCircle2Icon,
  FileTextIcon,
  GaugeIcon,
  Loader2Icon,
  MessageSquareIcon,
  MoonIcon,
  PaletteIcon,
  ShieldAlertIcon,
  SparklesIcon,
  SunIcon,
  Trash2Icon,
  UserRoundIcon,
  WrenchIcon,
  XCircleIcon,
} from 'lucide-react'
import { useState } from 'react'

import { useConfirmationDialog } from '@/components/confirmation-dialog'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
} from '@/components/ui/breadcrumb'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { SidebarTrigger } from '@/components/ui/sidebar'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { currentUserAtom } from '@/data-acess/auth'
import { usageAtom } from '@/data-acess/usage'
import { useTheme } from '@/providers/theme-provider'

const toolDisplayNames: Record<string, string> = {
  search_project_documents: '检索项目资料',
  resource_package_generate: '生成学习资源包',
  study_plan_get_latest: '读取学习计划',
  flashcards_list_groups: '查看闪卡组',
  flashcards_get: '读取闪卡',
  flashcards_delete_group: '删除闪卡组',
  flashcards_update_group: '更新闪卡组',
  quiz_list: '查看测验',
  quiz_get_questions: '读取测验题目',
  quiz_delete: '删除测验',
  note_list: '查看笔记',
  note_get: '读取笔记',
  note_delete: '删除笔记',
  mindmap_list: '查看思维导图',
  mindmap_get: '读取思维导图',
  get_learner_profile: '读取学习者画像',
  get_knowledge_states: '查询知识状态',
  get_recent_practice_records: '读取近期练习',
  get_knowledge_graph: '读取知识图谱',
  search_course_materials: '检索课程资料',
  generate_diagnostic_quiz_draft: '生成诊断测验草稿',
  draft_learning_path: '生成学习路径草稿',
}

const getToolCategory = (toolName: string) => {
  if (toolName.includes('search') || toolName.includes('document'))
    return '检索'
  if (toolName.includes('plan') || toolName.includes('path')) return '规划'
  if (toolName.includes('diagnostic') || toolName.includes('practice'))
    return '诊断'
  if (toolName.includes('knowledge') || toolName.includes('learner'))
    return '学情'
  if (
    toolName.includes('flashcard') ||
    toolName.includes('quiz') ||
    toolName.includes('note') ||
    toolName.includes('mindmap') ||
    toolName.includes('resource')
  )
    return '内容'
  return '通用'
}

const formatTime = (value: string | null) => {
  if (!value) return '—'
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

const UserSection = () => {
  const currentUserResult = useAtomValue(currentUserAtom)

  return Result.builder(currentUserResult)
    .onSuccess((user) => (
      <Card className="gap-5 py-5 shadow-none">
        <CardHeader className="gap-1 px-5">
          <div className="flex items-center gap-2">
            <UserRoundIcon className="size-4 text-muted-foreground" />
            <CardTitle className="text-sm">账户信息</CardTitle>
          </div>
          <CardDescription>当前登录账户</CardDescription>
        </CardHeader>
        <CardContent className="px-5">
          <div className="flex items-center gap-3">
            <Avatar className="size-11 rounded-lg">
              <AvatarFallback className="rounded-lg bg-primary/10 font-semibold text-primary">
                {user.initials}
              </AvatarFallback>
            </Avatar>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold">{user.name}</p>
              <p className="truncate text-xs text-muted-foreground">
                @{user.username}
              </p>
            </div>
            <Badge
              variant="outline"
              className="ml-auto bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300"
            >
              正常
            </Badge>
          </div>
        </CardContent>
      </Card>
    ))
    .onInitialOrWaiting(() => (
      <Card className="gap-5 py-5 shadow-none">
        <CardHeader className="gap-1 px-5">
          <CardTitle className="text-sm">账户信息</CardTitle>
          <CardDescription>正在加载账户信息</CardDescription>
        </CardHeader>
        <CardContent className="flex items-center gap-3 px-5 text-sm text-muted-foreground">
          <Loader2Icon className="size-4 animate-spin" />
          正在加载...
        </CardContent>
      </Card>
    ))
    .onFailure(() => (
      <Card className="gap-4 py-5 shadow-none">
        <CardHeader className="px-5">
          <CardTitle className="text-sm">账户信息</CardTitle>
          <CardDescription className="text-destructive">
            账户信息加载失败
          </CardDescription>
        </CardHeader>
      </Card>
    ))
    .render()
}

export function SettingsPage() {
  const { theme, setTheme } = useTheme()
  const confirmationDialog = useConfirmationDialog()
  const usageResult = useAtomValue(usageAtom)
  const [isDeletingAllChats, setIsDeletingAllChats] = useState(false)

  const handleDeleteAllChats = async () => {
    const confirmed = await confirmationDialog.open({
      title: '删除所有聊天',
      description:
        '此功能尚在建设中，本次操作不会删除数据。是否继续查看模拟流程？',
      confirmLabel: '继续',
      cancelLabel: '取消',
      variant: 'destructive',
    })

    if (!confirmed) return
    setIsDeletingAllChats(true)
    await new Promise((resolve) => setTimeout(resolve, 800))
    alert('删除聊天功能尚未开放。')
    setIsDeletingAllChats(false)
  }

  const handleDeleteAccount = async () => {
    const confirmed = await confirmationDialog.open({
      title: '删除账户',
      description:
        '此功能尚在建设中，本次操作不会删除账户。是否继续查看模拟流程？',
      confirmLabel: '继续',
      cancelLabel: '取消',
      variant: 'destructive',
    })

    if (confirmed) alert('删除账户功能尚未开放。')
  }

  return (
    <div className="flex h-full flex-col bg-muted/20">
      <header className="sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 border-b bg-background/95 px-2 backdrop-blur">
        <div className="flex flex-1 items-center gap-2 px-3">
          <SidebarTrigger />
          <Separator
            orientation="vertical"
            className="mr-2 data-[orientation=vertical]:h-4"
          />
          <Breadcrumb>
            <BreadcrumbList>
              <BreadcrumbItem>
                <BreadcrumbPage className="font-medium">设置</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <main className="mx-auto w-full max-w-6xl space-y-6 p-4 sm:p-6 lg:p-8">
          <div className="flex flex-col gap-1">
            <h1 className="text-2xl font-semibold tracking-tight">系统设置</h1>
            <p className="text-sm text-muted-foreground">
              管理账户偏好，并查看今日平台额度与全部工具调用情况。
            </p>
          </div>

          <section className="grid gap-4 md:grid-cols-2" aria-label="基础设置">
            <UserSection />

            <Card className="gap-5 py-5 shadow-none">
              <CardHeader className="gap-1 px-5">
                <div className="flex items-center gap-2">
                  <PaletteIcon className="size-4 text-muted-foreground" />
                  <CardTitle className="text-sm">外观偏好</CardTitle>
                </div>
                <CardDescription>选择适合当前环境的显示主题</CardDescription>
              </CardHeader>
              <CardContent className="px-5">
                <Select
                  value={theme}
                  onValueChange={(value) => setTheme(value as typeof theme)}
                >
                  <SelectTrigger
                    className="w-full sm:w-56"
                    aria-label="显示主题"
                  >
                    <SelectValue placeholder="选择主题" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="light">
                      <span className="flex items-center gap-2">
                        <SunIcon className="size-4" />
                        浅色
                      </span>
                    </SelectItem>
                    <SelectItem value="dark">
                      <span className="flex items-center gap-2">
                        <MoonIcon className="size-4" />
                        深色
                      </span>
                    </SelectItem>
                    <SelectItem value="system">
                      <span className="flex items-center gap-2">
                        <ActivityIcon className="size-4" />
                        跟随系统
                      </span>
                    </SelectItem>
                  </SelectContent>
                </Select>
              </CardContent>
            </Card>
          </section>

          <Card className="gap-0 py-0 shadow-none">
            <CardHeader className="gap-1 border-b px-5 py-5 sm:px-6">
              <div className="flex items-center gap-2">
                <GaugeIcon className="size-4 text-muted-foreground" />
                <CardTitle>今日使用情况</CardTitle>
              </div>
              <CardDescription>
                每日额度按自然日重置，工具调用覆盖 AI 导师与多智能体能力。
              </CardDescription>
            </CardHeader>
            <CardContent className="p-5 sm:p-6">
              {Result.builder(usageResult)
                .onInitialOrWaiting(() => (
                  <div className="flex min-h-48 items-center justify-center gap-2 text-sm text-muted-foreground">
                    <Loader2Icon className="size-4 animate-spin" />
                    正在加载使用统计...
                  </div>
                ))
                .onFailure(() => (
                  <div className="flex min-h-48 items-center justify-center text-sm text-destructive">
                    使用统计加载失败，请稍后重试。
                  </div>
                ))
                .onSuccess((usage) => {
                  const quotaItems = [
                    {
                      label: 'AI 对话',
                      icon: MessageSquareIcon,
                      value: usage.chat_messages,
                    },
                    {
                      label: '闪卡生成',
                      icon: BrainCircuitIcon,
                      value: usage.flashcard_generations,
                    },
                    {
                      label: '测验生成',
                      icon: SparklesIcon,
                      value: usage.quiz_generations,
                    },
                    {
                      label: '思维导图',
                      icon: ActivityIcon,
                      value: usage.mindmap_generations,
                    },
                    {
                      label: '文档上传',
                      icon: FileTextIcon,
                      value: usage.document_uploads,
                    },
                  ]
                  const totalCalls = usage.tool_usage.reduce(
                    (sum, tool) => sum + tool.total,
                    0,
                  )
                  const successfulCalls = usage.tool_usage.reduce(
                    (sum, tool) => sum + tool.successful,
                    0,
                  )
                  const failedCalls = usage.tool_usage.reduce(
                    (sum, tool) => sum + tool.failed,
                    0,
                  )
                  const successRate = totalCalls
                    ? Math.round((successfulCalls / totalCalls) * 100)
                    : 0

                  return (
                    <div className="space-y-7">
                      <div className="grid gap-3 sm:grid-cols-3">
                        <div className="rounded-lg border bg-muted/20 p-4">
                          <p className="text-xs font-medium text-muted-foreground">
                            统计工具
                          </p>
                          <p className="mt-1 text-2xl font-semibold tabular-nums">
                            {usage.tool_usage.length}
                          </p>
                        </div>
                        <div className="rounded-lg border bg-muted/20 p-4">
                          <p className="text-xs font-medium text-muted-foreground">
                            今日调用
                          </p>
                          <p className="mt-1 text-2xl font-semibold tabular-nums">
                            {totalCalls}
                          </p>
                        </div>
                        <div className="rounded-lg border bg-muted/20 p-4">
                          <p className="text-xs font-medium text-muted-foreground">
                            调用成功率
                          </p>
                          <p className="mt-1 text-2xl font-semibold tabular-nums">
                            {successRate}%
                          </p>
                        </div>
                      </div>

                      <section aria-labelledby="quota-heading">
                        <div className="mb-4 flex items-end justify-between gap-4">
                          <div>
                            <h2
                              id="quota-heading"
                              className="text-sm font-semibold"
                            >
                              每日额度
                            </h2>
                            <p className="mt-1 text-xs text-muted-foreground">
                              各项能力今日已用与可用上限
                            </p>
                          </div>
                          <Badge variant="outline">
                            共 {quotaItems.length} 项
                          </Badge>
                        </div>
                        <div className="grid gap-x-8 gap-y-5 md:grid-cols-2">
                          {quotaItems.map((item) => {
                            const percentage = item.value.limit
                              ? Math.min(
                                  100,
                                  (item.value.used / item.value.limit) * 100,
                                )
                              : 0
                            const Icon = item.icon
                            return (
                              <div key={item.label} className="space-y-2">
                                <div className="flex items-center gap-2 text-sm">
                                  <Icon className="size-4 text-muted-foreground" />
                                  <span className="font-medium">
                                    {item.label}
                                  </span>
                                  <span className="ml-auto tabular-nums text-muted-foreground">
                                    {item.value.used} / {item.value.limit}
                                  </span>
                                </div>
                                <Progress
                                  value={percentage}
                                  className="h-1.5"
                                />
                              </div>
                            )
                          })}
                        </div>
                      </section>

                      <Separator />

                      <section aria-labelledby="tool-usage-heading">
                        <div className="mb-3 flex items-end justify-between gap-4">
                          <div>
                            <h2
                              id="tool-usage-heading"
                              className="flex items-center gap-2 text-sm font-semibold"
                            >
                              <WrenchIcon className="size-4 text-muted-foreground" />
                              全部工具调用
                            </h2>
                            <p className="mt-1 text-xs text-muted-foreground">
                              汇总当前账户今日产生的每一种工具调用
                            </p>
                          </div>
                          {failedCalls > 0 && (
                            <Badge
                              variant="outline"
                              className="text-destructive"
                            >
                              {failedCalls} 次失败
                            </Badge>
                          )}
                        </div>

                        {usage.tool_usage.length === 0 ? (
                          <div className="rounded-lg border border-dashed py-10 text-center">
                            <WrenchIcon className="mx-auto size-5 text-muted-foreground" />
                            <p className="mt-2 text-sm font-medium">
                              今日暂无工具调用
                            </p>
                            <p className="mt-1 text-xs text-muted-foreground">
                              使用 AI 导师或智能体能力后，记录会显示在这里。
                            </p>
                          </div>
                        ) : (
                          <div className="overflow-hidden rounded-lg border">
                            <Table>
                              <TableHeader className="bg-muted/40">
                                <TableRow className="hover:bg-transparent">
                                  <TableHead className="pl-4">工具</TableHead>
                                  <TableHead>分类</TableHead>
                                  <TableHead className="text-right">
                                    调用
                                  </TableHead>
                                  <TableHead className="hidden text-right sm:table-cell">
                                    成功 / 失败
                                  </TableHead>
                                  <TableHead className="hidden pr-4 text-right md:table-cell">
                                    最近使用
                                  </TableHead>
                                </TableRow>
                              </TableHeader>
                              <TableBody>
                                {usage.tool_usage.map((tool) => (
                                  <TableRow key={tool.tool_name}>
                                    <TableCell className="pl-4 font-medium">
                                      <div>
                                        <p>
                                          {toolDisplayNames[tool.tool_name] ??
                                            tool.tool_name.replaceAll('_', ' ')}
                                        </p>
                                        <p className="mt-0.5 max-w-52 truncate font-mono text-[10px] font-normal text-muted-foreground sm:max-w-none">
                                          {tool.tool_name}
                                        </p>
                                      </div>
                                    </TableCell>
                                    <TableCell>
                                      <Badge
                                        variant="outline"
                                        className="font-normal"
                                      >
                                        {getToolCategory(tool.tool_name)}
                                      </Badge>
                                    </TableCell>
                                    <TableCell className="text-right font-semibold tabular-nums">
                                      {tool.total}
                                    </TableCell>
                                    <TableCell className="hidden text-right sm:table-cell">
                                      <span className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
                                        <CheckCircle2Icon className="size-3.5" />
                                        {tool.successful}
                                      </span>
                                      <span className="ml-3 inline-flex items-center gap-1 text-muted-foreground">
                                        <XCircleIcon className="size-3.5" />
                                        {tool.failed}
                                      </span>
                                    </TableCell>
                                    <TableCell className="hidden pr-4 text-right text-muted-foreground md:table-cell">
                                      {formatTime(tool.last_used_at)}
                                    </TableCell>
                                  </TableRow>
                                ))}
                              </TableBody>
                            </Table>
                          </div>
                        )}
                      </section>
                    </div>
                  )
                })
                .render()}
            </CardContent>
          </Card>

          <Card className="gap-0 border-destructive/25 py-0 shadow-none">
            <CardHeader className="gap-1 border-b border-destructive/15 px-5 py-5 sm:px-6">
              <div className="flex items-center gap-2">
                <ShieldAlertIcon className="size-4 text-destructive" />
                <CardTitle className="text-base">数据与账户</CardTitle>
              </div>
              <CardDescription>
                以下能力尚在建设中，不会实际删除数据。
              </CardDescription>
            </CardHeader>
            <CardContent className="divide-y px-5 sm:px-6">
              <div className="flex flex-col gap-3 py-5 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-sm font-medium">删除所有聊天</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    清除当前账户下的全部对话记录
                  </p>
                </div>
                <Button
                  variant="outline"
                  onClick={handleDeleteAllChats}
                  disabled={isDeletingAllChats}
                  className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                >
                  {isDeletingAllChats ? (
                    <Loader2Icon className="size-4 animate-spin" />
                  ) : (
                    <Trash2Icon className="size-4" />
                  )}
                  删除聊天
                </Button>
              </div>
              <div className="flex flex-col gap-3 py-5 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-sm font-medium">删除账户</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    移除账户及其关联数据
                  </p>
                </div>
                <Button
                  variant="outline"
                  onClick={handleDeleteAccount}
                  className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                >
                  <Trash2Icon className="size-4" />
                  删除账户
                </Button>
              </div>
            </CardContent>
          </Card>
        </main>
      </div>
    </div>
  )
}
