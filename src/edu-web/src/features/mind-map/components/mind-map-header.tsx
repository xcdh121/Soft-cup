import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import { ArrowLeft, Loader2Icon, PlusIcon } from 'lucide-react'
import { Link } from '@tanstack/react-router'
import { format } from 'date-fns'
import { useState } from 'react'
import { SidebarTrigger } from '@/components/ui/sidebar'
import { Separator } from '@/components/ui/separator'
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
} from '@/components/ui/breadcrumb'
import { generateMindMapAtom, mindMapAtom } from '@/data-acess/mind-map'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'

const MindMapHeaderContent = ({
  mindMapId,
  projectId,
}: {
  mindMapId: string
  projectId: string
}) => {
  const mindMapsResult = useAtomValue(mindMapAtom(`${projectId}:${mindMapId}`))

  return Result.builder(mindMapsResult)
    .onSuccess((mindMap) => {
      if (!mindMap) {
        return (
          <Breadcrumb>
            <BreadcrumbList>
              <BreadcrumbItem>
                <BreadcrumbPage className="line-clamp-1 font-medium">
                  思维导图
                </BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
        )
      }

      return (
        <div className="flex items-center gap-4">
          <Breadcrumb>
            <BreadcrumbList>
              <BreadcrumbItem>
                <BreadcrumbPage className="line-clamp-1 font-medium">
                  {mindMap.title}
                </BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
          <span className="text-xs text-muted-foreground">
            生成时间：{' '}
            {format(new Date(mindMap.generated_at), 'MMM dd, yyyy HH:mm')}
          </span>
        </div>
      )
    })
    .onInitialOrWaiting(() => <Skeleton className="w-72 h-7" />)
    .onFailure(() => (
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbPage className="line-clamp-1 font-medium">
              思维导图
            </BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
    ))
    .render()
}

type MindMapHeaderProps = {
  projectId: string
  mindMapId: string
}

export const MindMapHeader = ({ projectId, mindMapId }: MindMapHeaderProps) => {
  const generateMap = useAtomSet(generateMindMapAtom, { mode: 'promise' })
  const [isGenerating, setIsGenerating] = useState(false)
  const [customInstructions, setCustomInstructions] = useState('')
  const [isDialogOpen, setIsDialogOpen] = useState(false)

  const handleGenerate = async () => {
    setIsGenerating(true)
    try {
      await generateMap({
        projectId,
        customInstructions: customInstructions || undefined,
      })
      setCustomInstructions('')
      setIsDialogOpen(false)
    } finally {
      setIsGenerating(false)
    }
  }

  return (
    <header className="bg-background sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 border-b px-2">
      <div className="flex flex-1 items-center gap-2 px-3">
        <SidebarTrigger />
        <Button variant="ghost" size="icon" className="size-7" asChild>
          <Link to="/dashboard/p/$projectId" params={{ projectId }}>
            <ArrowLeft className="size-4" />
            <span className="sr-only">返回项目</span>
          </Link>
        </Button>
        <Separator
          orientation="vertical"
          className="mr-2 data-[orientation=vertical]:h-4"
        />
        <MindMapHeaderContent mindMapId={mindMapId} projectId={projectId} />
      </div>
      <div className="flex items-center gap-2 px-3">
        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogTrigger asChild>
            <Button variant="default" size="sm">
              <PlusIcon className="size-4 mr-2" />
              <span>生成思维导图</span>
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>生成思维导图</DialogTitle>
              <DialogDescription>
                根据项目文档创建新的思维导图。也可以指定主题或关注方向。
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="customInstructions">
                  自定义要求（可选）
                </Label>
                <Textarea
                  id="customInstructions"
                  placeholder="例如：机器学习、数据结构、艺术史... 也可以说明结构、详细程度等格式偏好。"
                  value={customInstructions}
                  onChange={(e) => setCustomInstructions(e.target.value)}
                  rows={3}
                />
              </div>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setIsDialogOpen(false)}
                disabled={isGenerating}
              >
                取消
              </Button>
              <Button onClick={handleGenerate} disabled={isGenerating}>
                {isGenerating ? (
                  <>
                    <Loader2Icon className="size-4 mr-2 animate-spin" />
                    <span>正在生成...</span>
                  </>
                ) : (
                  <span>生成</span>
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </header>
  )
}
