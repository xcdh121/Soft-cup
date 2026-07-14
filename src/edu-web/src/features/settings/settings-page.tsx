import { Result, useAtomValue } from '@effect-atom/atom-react'
import { Loader2Icon, Trash2Icon } from 'lucide-react'
import { useState } from 'react'

import { useConfirmationDialog } from '@/components/confirmation-dialog'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
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
import { currentUserAtom } from '@/data-acess/auth'
import { usageAtom } from '@/data-acess/usage'
import { useTheme } from '@/providers/theme-provider'

const UserSection = () => {
  const currentUserResult = useAtomValue(currentUserAtom)

  return Result.builder(currentUserResult)
    .onSuccess((user) => {
      return (
        <Card>
          <CardHeader>
            <CardTitle>账号</CardTitle>
            <CardDescription>你的账号信息</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-4">
              <Avatar className="size-16">
                <AvatarFallback>{user.initials}</AvatarFallback>
              </Avatar>
              <div className="flex-1">
                <p className="font-semibold">{user.name}</p>
                <p className="text-sm text-muted-foreground">
                  @{user.username}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )
    })
    .onInitialOrWaiting(() => {
      return (
        <Card>
          <CardHeader>
            <CardTitle>账号</CardTitle>
            <CardDescription>你的账号信息</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-4">
              <Avatar className="size-16">
                <AvatarFallback>
                  <Loader2Icon className="size-4 animate-spin" />
                </AvatarFallback>
              </Avatar>
              <div className="flex-1">
                <p className="font-semibold">正在加载...</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )
    })
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
      description: '这是一个模拟操作。你的聊天不会真的被删除。确定要继续吗？',
      confirmLabel: '全部删除',
      cancelLabel: '取消',
      variant: 'destructive',
    })

    if (!confirmed) return

    setIsDeletingAllChats(true)

    // Mock action - simulate delay
    await new Promise((resolve) => setTimeout(resolve, 1500))

    alert('删除所有聊天尚未实现。这是一个模拟操作。')
    setIsDeletingAllChats(false)
  }

  const handleDeleteAccount = async () => {
    const confirmed = await confirmationDialog.open({
      title: '删除账号',
      description: '这是一个模拟操作。你的账号不会真的被删除。确定要继续吗？',
      confirmLabel: '删除',
      cancelLabel: '取消',
      variant: 'destructive',
    })

    if (confirmed) {
      // Mock action - just show an alert
      alert('删除账号尚未实现。这是一个模拟操作。')
    }
  }

  return (
    <div className="flex h-full flex-col">
      <header className="bg-background sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 border-b px-2">
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

      <div className="flex flex-1 flex-col min-h-0 overflow-y-auto">
        <div className="max-w-4xl mx-auto w-full p-4 space-y-6">
          <UserSection />

          <Card>
            <CardHeader>
              <CardTitle>外观</CardTitle>
              <CardDescription>选择你偏好的主题</CardDescription>
            </CardHeader>
            <CardContent>
              <Select
                value={theme}
                onValueChange={(value) => setTheme(value as typeof theme)}
              >
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="选择主题" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="light">浅色</SelectItem>
                  <SelectItem value="dark">深色</SelectItem>
                  <SelectItem value="system">跟随系统</SelectItem>
                </SelectContent>
              </Select>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>使用情况</CardTitle>
              <CardDescription>你的每日使用统计和限制</CardDescription>
            </CardHeader>
            <CardContent>
              {Result.builder(usageResult)
                .onInitialOrWaiting(() => (
                  <div className="text-muted-foreground text-sm">
                    正在加载使用统计...
                  </div>
                ))
                .onFailure(() => (
                  <div className="text-destructive text-sm">
                    使用统计加载失败
                  </div>
                ))
                .onSuccess((usage) => (
                  <div className="space-y-6">
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-sm">
                        <span className="font-medium">聊天消息</span>
                        <span className="text-muted-foreground">
                          {usage.chat_messages.used} /{' '}
                          {usage.chat_messages.limit}
                        </span>
                      </div>
                      <Progress
                        value={
                          (usage.chat_messages.used /
                            usage.chat_messages.limit) *
                          100
                        }
                      />
                    </div>

                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-sm">
                        <span className="font-medium">闪卡生成</span>
                        <span className="text-muted-foreground">
                          {usage.flashcard_generations.used} /{' '}
                          {usage.flashcard_generations.limit}
                        </span>
                      </div>
                      <Progress
                        value={
                          (usage.flashcard_generations.used /
                            usage.flashcard_generations.limit) *
                          100
                        }
                      />
                    </div>

                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-sm">
                        <span className="font-medium">测验生成</span>
                        <span className="text-muted-foreground">
                          {usage.quiz_generations.used} /{' '}
                          {usage.quiz_generations.limit}
                        </span>
                      </div>
                      <Progress
                        value={
                          (usage.quiz_generations.used /
                            usage.quiz_generations.limit) *
                          100
                        }
                      />
                    </div>

                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-sm">
                        <span className="font-medium">思维导图生成</span>
                        <span className="text-muted-foreground">
                          {usage.mindmap_generations.used} /{' '}
                          {usage.mindmap_generations.limit}
                        </span>
                      </div>
                      <Progress
                        value={
                          (usage.mindmap_generations.used /
                            usage.mindmap_generations.limit) *
                          100
                        }
                      />
                    </div>

                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-sm">
                        <span className="font-medium">文档上传</span>
                        <span className="text-muted-foreground">
                          {usage.document_uploads.used} /{' '}
                          {usage.document_uploads.limit}
                        </span>
                      </div>
                      <Progress
                        value={
                          (usage.document_uploads.used /
                            usage.document_uploads.limit) *
                          100
                        }
                      />
                    </div>
                  </div>
                ))
                .render()}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>危险操作</CardTitle>
              <CardDescription>不可撤销的破坏性操作</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">删除所有聊天</p>
                    <p className="text-sm text-muted-foreground">
                      永久删除你的所有聊天对话（模拟）
                    </p>
                  </div>
                  <Button
                    variant="destructive"
                    onClick={handleDeleteAllChats}
                    disabled={isDeletingAllChats}
                  >
                    {isDeletingAllChats ? (
                      <>
                        <Loader2Icon className="size-4 mr-2 animate-spin" />
                        正在删除...
                      </>
                    ) : (
                      <>
                        <Trash2Icon className="size-4 mr-2" />
                        全部删除
                      </>
                    )}
                  </Button>
                </div>
              </div>

              <Separator />

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">删除账号</p>
                    <p className="text-sm text-muted-foreground">
                      永久删除你的账号和所有关联数据（模拟）
                    </p>
                  </div>
                  <Button variant="destructive" onClick={handleDeleteAccount}>
                    <Trash2Icon className="size-4 mr-2" />
                    删除账号
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
