import {
  FileImageIcon,
  Loader2Icon,
  UploadCloudIcon,
  XIcon,
} from 'lucide-react'
import { useRef, useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { adminApi } from '@/data-acess/billing-admin'

type CourseStatus = 'active' | 'draft' | 'archived'

const acceptedCoverTypes = new Set(['image/jpeg', 'image/png', 'image/webp'])
const maxCoverBytes = 5 * 1024 * 1024

type CourseCreateDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated: () => Promise<void> | void
}

const formatFileSize = (bytes: number) =>
  `${(bytes / 1024 / 1024).toFixed(1)} MB`

export function CourseCreateDialog({
  open,
  onOpenChange,
  onCreated,
}: CourseCreateDialogProps) {
  const coverInputRef = useRef<HTMLInputElement>(null)
  const [coverFile, setCoverFile] = useState<File | null>(null)
  const [status, setStatus] = useState<CourseStatus>('active')
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [summary, setSummary] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const reset = () => {
    setCoverFile(null)
    setStatus('active')
    setCode('')
    setName('')
    setSummary('')
    setError(null)
    if (coverInputRef.current) coverInputRef.current.value = ''
  }

  const changeOpen = (nextOpen: boolean) => {
    if (submitting) return
    if (!nextOpen) reset()
    onOpenChange(nextOpen)
  }

  const selectCover = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null
    if (!file) return
    if (!acceptedCoverTypes.has(file.type)) {
      setCoverFile(null)
      setError('课程封面仅支持 JPG、PNG 或 WebP 图片')
      event.target.value = ''
      return
    }
    if (file.size > maxCoverBytes) {
      setCoverFile(null)
      setError('课程封面不能超过 5MB')
      event.target.value = ''
      return
    }
    setCoverFile(file)
    setError(null)
  }

  const removeCover = () => {
    setCoverFile(null)
    if (coverInputRef.current) coverInputRef.current.value = ''
  }

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const courseName = name.trim()
    if (!coverFile) {
      setError('请从本地选择课程封面')
      return
    }
    if (!courseName) {
      setError('请填写课程名称')
      return
    }

    setSubmitting(true)
    setError(null)
    try {
      const cover = await adminApi.uploadCourseCover(coverFile)
      await adminApi.createCourse({
        cover_url: cover.url,
        status,
        code: code.trim() || undefined,
        name: courseName,
        description: summary.trim() || undefined,
      })
      await onCreated()
      reset()
      onOpenChange(false)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '创建课程失败')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={changeOpen}>
      <DialogContent className="max-h-[90svh] overflow-y-auto p-0 sm:max-w-xl">
        <form onSubmit={(event) => void submit(event)}>
          <DialogHeader className="border-b px-6 py-5 pr-14">
            <DialogTitle>新建平台课程</DialogTitle>
            <DialogDescription>
              填写学生端“我的课程”卡片所展示的课程信息。
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-5 p-6">
            {error && (
              <div
                role="alert"
                className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"
              >
                {error}
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="course-cover">
                课程封面 <span className="text-destructive">*</span>
              </Label>
              <input
                ref={coverInputRef}
                id="course-cover"
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="sr-only"
                onChange={selectCover}
                disabled={submitting}
              />
              {coverFile ? (
                <div className="flex items-center gap-3 rounded-lg border bg-muted/30 p-3">
                  <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-background text-primary shadow-sm">
                    <FileImageIcon className="size-5" />
                  </div>
                  <button
                    type="button"
                    className="min-w-0 flex-1 text-left"
                    onClick={() => coverInputRef.current?.click()}
                    disabled={submitting}
                  >
                    <span className="block truncate text-sm font-medium">
                      {coverFile.name}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {formatFileSize(coverFile.size)} · 点击重新选择
                    </span>
                  </button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    aria-label="移除课程封面"
                    onClick={removeCover}
                    disabled={submitting}
                  >
                    <XIcon className="size-4" />
                  </Button>
                </div>
              ) : (
                <label
                  htmlFor="course-cover"
                  className="flex cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed px-5 py-8 text-center transition hover:border-primary/60 hover:bg-primary/5"
                >
                  <UploadCloudIcon className="mb-3 size-8 text-muted-foreground" />
                  <span className="text-sm font-medium">
                    点击从本地选择封面
                  </span>
                  <span className="mt-1 text-xs text-muted-foreground">
                    JPG、PNG 或 WebP，最大 5MB
                  </span>
                </label>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="course-status">课程状态</Label>
              <Select
                value={status}
                onValueChange={(value) => setStatus(value as CourseStatus)}
                disabled={submitting}
              >
                <SelectTrigger id="course-status" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">进行中</SelectItem>
                  <SelectItem value="draft">待开始</SelectItem>
                  <SelectItem value="archived">已归档</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                这是学生端卡片状态；新建的平台课程发布状态仍为草稿。
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="course-code">课程代码</Label>
              <Input
                id="course-code"
                value={code}
                onChange={(event) => setCode(event.target.value)}
                placeholder="例如：DSA-101"
                maxLength={100}
                disabled={submitting}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="course-name">
                课程名称 <span className="text-destructive">*</span>
              </Label>
              <Input
                id="course-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="例如：数据结构与算法"
                maxLength={200}
                required
                disabled={submitting}
              />
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between gap-3">
                <Label htmlFor="course-summary">
                  一句话简介 <span className="text-destructive">*</span>
                </Label>
                <span className="text-xs text-muted-foreground">
                  {summary.length}/120
                </span>
              </div>
              <Textarea
                id="course-summary"
                value={summary}
                onChange={(event) => setSummary(event.target.value)}
                placeholder="用一句话概括课程内容和学习目标"
                className="min-h-20 resize-none"
                maxLength={120}
                required
                disabled={submitting}
              />
            </div>
          </div>

          <DialogFooter className="border-t bg-muted/30 px-6 py-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => changeOpen(false)}
              disabled={submitting}
            >
              取消
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting && <Loader2Icon className="size-4 animate-spin" />}
              {submitting ? '正在上传并创建…' : '创建课程草稿'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
