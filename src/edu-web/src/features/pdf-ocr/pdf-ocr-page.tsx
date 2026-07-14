import {
  CheckCircle2Icon,
  CircleAlertIcon,
  Clock3Icon,
  DownloadIcon,
  FileCheck2Icon,
  FileTextIcon,
  Loader2Icon,
  LockKeyholeIcon,
  RotateCcwIcon,
  ScanLineIcon,
  ShieldCheckIcon,
  UploadCloudIcon,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { pdfjs } from 'react-pdf'
import { toast } from 'sonner'
import type {
  PdfOcrExportFormat,
  PdfOcrStatus,
  PdfOcrTask,
} from '@/lib/xfyun-pdf-ocr'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'
import { getPdfOcrTask, startPdfOcrTask } from '@/lib/xfyun-pdf-ocr'

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

const MAX_PDF_BYTES = 100 * 1024 * 1024
const FINAL_STATUSES = new Set<PdfOcrStatus>([
  'FINISH',
  'FAILED',
  'ANY_FAILED',
  'STOP',
])

const FORMAT_LABELS: Record<PdfOcrExportFormat, string> = {
  word: 'Word 文档',
  markdown: 'Markdown',
  json: 'JSON 数据',
}

const STATUS_META: Record<
  PdfOcrStatus,
  { label: string; description: string; progress: number }
> = {
  CREATE: { label: '任务已创建', description: '文档已安全提交', progress: 22 },
  WAITING: { label: '等待处理', description: '正在排队等待识别', progress: 38 },
  DOING: { label: '正在识别', description: '正在解析版面与文字', progress: 72 },
  FINISH: { label: '识别完成', description: '结果文件已生成', progress: 100 },
  FAILED: { label: '识别失败', description: '任务未能完成', progress: 100 },
  ANY_FAILED: {
    label: '部分页面失败',
    description: '可下载已完成内容',
    progress: 100,
  },
  STOP: { label: '任务已暂停', description: '识别任务已停止', progress: 100 },
}

const formatFileSize = (bytes: number) => {
  if (bytes < 1024 * 1024) return `${Math.ceil(bytes / 1024)} KB`
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}

const validatePdf = async (file: File) => {
  if (
    file.type !== 'application/pdf' &&
    !file.name.toLowerCase().endsWith('.pdf')
  ) {
    throw new Error('请选择 PDF 文件。')
  }
  if (file.size > MAX_PDF_BYTES) throw new Error('PDF 文件大小不能超过 100MB。')
  let loadingTask: ReturnType<typeof pdfjs.getDocument> | null = null
  try {
    loadingTask = pdfjs.getDocument({ data: await file.arrayBuffer() })
    const document = await loadingTask.promise
    const pageCount = document.numPages
    if (pageCount > 100) {
      throw new Error(
        `当前文档共 ${pageCount} 页，单个 PDF 最多支持 100 页。请按章节拆分后重试。`,
      )
    }
    return pageCount
  } catch (error) {
    const message = error instanceof Error ? error.message : ''
    if (message.includes('password') || message.includes('Password')) {
      throw new Error('暂不支持带密码保护或权限加密的 PDF 文件。')
    }
    if (message.includes('最多支持')) throw error
    throw new Error('PDF 文件损坏、已加密或无法读取。')
  } finally {
    void loadingTask?.destroy()
  }
}

export const PdfOcrPage = ({ projectId }: { projectId: string }) => {
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [pageCount, setPageCount] = useState<number | null>(null)
  const [format, setFormat] = useState<PdfOcrExportFormat>('word')
  const [task, setTask] = useState<PdfOcrTask | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [isReading, setIsReading] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const isProcessing = task ? !FINAL_STATUSES.has(task.status) : false

  useEffect(() => {
    if (!task || FINAL_STATUSES.has(task.status)) return
    let active = true
    let requestInFlight = false
    const poll = () => {
      if (requestInFlight) return
      requestInFlight = true
      void getPdfOcrTask({ projectId, taskNo: task.task_no })
        .then((nextTask) => {
          if (!active) return
          setError(null)
          setTask(nextTask)
          if (nextTask.status === 'FINISH') toast.success('PDF 文档识别完成')
        })
        .catch((caught) => {
          if (!active) return
          setError(
            caught instanceof Error ? caught.message : '查询识别进度失败。',
          )
        })
        .finally(() => {
          requestInFlight = false
        })
    }
    const interval = window.setInterval(poll, 5000)
    return () => {
      active = false
      window.clearInterval(interval)
    }
  }, [projectId, task])

  const selectFile = async (nextFile?: File) => {
    if (!nextFile || isProcessing) return
    setIsReading(true)
    setError(null)
    setTask(null)
    try {
      const pages = await validatePdf(nextFile)
      setFile(nextFile)
      setPageCount(pages)
    } catch (caught) {
      setFile(null)
      setPageCount(null)
      setError(caught instanceof Error ? caught.message : 'PDF 文件无法读取。')
      if (inputRef.current) inputRef.current.value = ''
    } finally {
      setIsReading(false)
    }
  }

  const reset = () => {
    setFile(null)
    setPageCount(null)
    setTask(null)
    setError(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  const startRecognition = async () => {
    if (!file || isSubmitting || isProcessing) return
    setIsSubmitting(true)
    setError(null)
    try {
      const nextTask = await startPdfOcrTask({
        projectId,
        file,
        exportFormat: format,
      })
      setTask(nextTask)
      toast.success('文档已提交，正在识别')
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : '任务创建失败，请稍后重试。',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  const statusMeta = task ? STATUS_META[task.status] : null
  const failed = task?.status === 'FAILED' || task?.status === 'STOP'

  return (
    <div className="h-full overflow-y-auto bg-muted/20">
      <main className="mx-auto w-full max-w-7xl px-5 py-7 lg:px-8">
        <div className="mb-7 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <div className="flex size-9 items-center justify-center rounded-lg bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900">
                <ScanLineIcon className="size-5" />
              </div>
              <Badge variant="outline" className="bg-background font-normal">
                讯飞 OCR 大模型
              </Badge>
            </div>
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">
                PDF 文档识别
              </h1>
              <p className="mt-1.5 text-sm text-muted-foreground">
                提取扫描版 PDF 的文字与版面结构，生成可编辑、可检索的文档。
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <ShieldCheckIcon className="size-4 text-emerald-600" />
            <span>密钥仅由服务端安全调用</span>
          </div>
        </div>

        {error ? (
          <Alert variant="destructive" className="mb-5 bg-background">
            <CircleAlertIcon />
            <AlertTitle>暂未完成处理</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}

        <div className="grid gap-5 lg:grid-cols-[minmax(0,1.08fr)_minmax(360px,0.92fr)]">
          <div className="space-y-5">
            <Card className="gap-4 shadow-none">
              <CardHeader>
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <CardTitle className="text-base">上传文档</CardTitle>
                    <CardDescription className="mt-1.5">
                      仅支持 PDF，单份最多 100 页；建议按章节整理文档。
                    </CardDescription>
                  </div>
                  <Badge variant="secondary">01</Badge>
                </div>
              </CardHeader>
              <CardContent>
                <input
                  ref={inputRef}
                  type="file"
                  accept=".pdf,application/pdf"
                  className="hidden"
                  disabled={isProcessing}
                  onChange={(event) => void selectFile(event.target.files?.[0])}
                />
                {file ? (
                  <div className="rounded-xl border bg-muted/20">
                    <div className="flex min-h-52 flex-col items-center justify-center px-6 py-8 text-center sm:flex-row sm:text-left">
                      <div className="mb-4 flex size-16 shrink-0 items-center justify-center rounded-2xl border bg-background text-slate-700 shadow-sm sm:mb-0 sm:mr-5 dark:text-slate-200">
                        <FileTextIcon className="size-8" />
                      </div>
                      <div className="min-w-0">
                        <div className="max-w-lg truncate font-medium">
                          {file.name}
                        </div>
                        <div className="mt-2 flex flex-wrap justify-center gap-2 text-xs text-muted-foreground sm:justify-start">
                          <span>{formatFileSize(file.size)}</span>
                          <span>·</span>
                          <span>{pageCount} 页</span>
                          <span>·</span>
                          <span>PDF 文档</span>
                        </div>
                        <div className="mt-4 flex justify-center gap-2 sm:justify-start">
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={isProcessing}
                            onClick={() => inputRef.current?.click()}
                          >
                            更换文档
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={isProcessing}
                            onClick={reset}
                          >
                            <RotateCcwIcon />
                            清除
                          </Button>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <button
                    type="button"
                    className={cn(
                      'flex min-h-64 w-full flex-col items-center justify-center rounded-xl border border-dashed bg-muted/20 px-6 text-center transition-colors',
                      isDragging
                        ? 'border-slate-500 bg-slate-100/70 dark:bg-slate-900/50'
                        : 'hover:border-slate-400 hover:bg-muted/40',
                    )}
                    onClick={() => inputRef.current?.click()}
                    onDragEnter={(event) => {
                      event.preventDefault()
                      setIsDragging(true)
                    }}
                    onDragOver={(event) => event.preventDefault()}
                    onDragLeave={() => setIsDragging(false)}
                    onDrop={(event) => {
                      event.preventDefault()
                      setIsDragging(false)
                      void selectFile(event.dataTransfer.files[0])
                    }}
                  >
                    <div className="mb-4 flex size-14 items-center justify-center rounded-full border bg-background text-slate-700 shadow-sm dark:text-slate-200">
                      {isReading ? (
                        <Loader2Icon className="size-6 animate-spin" />
                      ) : (
                        <UploadCloudIcon className="size-6" />
                      )}
                    </div>
                    <div className="font-medium">
                      {isReading ? '正在读取文档…' : '点击或拖拽 PDF 到这里'}
                    </div>
                    <div className="mt-2 text-sm text-muted-foreground">
                      系统会在上传前检查页数与文件有效性
                    </div>
                  </button>
                )}
              </CardContent>
            </Card>

            <Card className="gap-4 shadow-none">
              <CardHeader>
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <CardTitle className="text-base">输出设置</CardTitle>
                    <CardDescription className="mt-1.5">
                      选择识别结果的文件格式。
                    </CardDescription>
                  </div>
                  <Badge variant="secondary">02</Badge>
                </div>
              </CardHeader>
              <CardContent className="flex flex-col gap-4 sm:flex-row sm:items-end">
                <div className="flex-1 space-y-2">
                  <Label htmlFor="pdf-ocr-format">导出格式</Label>
                  <Select
                    value={format}
                    disabled={isProcessing}
                    onValueChange={(value) =>
                      setFormat(value as PdfOcrExportFormat)
                    }
                  >
                    <SelectTrigger id="pdf-ocr-format" className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="word">
                        Word 文档（通用编辑）
                      </SelectItem>
                      <SelectItem value="markdown">
                        Markdown（公式文档推荐）
                      </SelectItem>
                      <SelectItem value="json">JSON（结构化处理）</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <Button
                  size="lg"
                  className="bg-slate-900 sm:min-w-44 dark:bg-slate-100"
                  disabled={!file || isReading || isSubmitting || isProcessing}
                  onClick={startRecognition}
                >
                  {isSubmitting || isProcessing ? (
                    <>
                      <Loader2Icon className="animate-spin" />
                      识别处理中
                    </>
                  ) : (
                    <>
                      <ScanLineIcon />
                      开始识别
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>

            <Alert className="bg-background text-muted-foreground">
              <LockKeyholeIcon />
              <AlertTitle className="text-foreground">文档要求</AlertTitle>
              <AlertDescription>
                暂不支持密码保护或权限加密的 PDF。包含数学公式时，建议选择
                Markdown 格式。
              </AlertDescription>
            </Alert>
          </div>

          <Card className="min-h-[560px] gap-0 shadow-none lg:sticky lg:top-0 lg:max-h-[calc(100vh-5.5rem)]">
            <CardHeader className="border-b pb-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <CardTitle className="text-base">处理进度</CardTitle>
                  <CardDescription className="mt-1.5">
                    任务状态每 5 秒自动更新
                  </CardDescription>
                </div>
                {task ? (
                  <Badge
                    variant={
                      failed
                        ? 'destructive'
                        : task.status === 'FINISH'
                          ? 'default'
                          : 'secondary'
                    }
                  >
                    {statusMeta?.label}
                  </Badge>
                ) : null}
              </div>
            </CardHeader>
            <CardContent className="flex flex-1 flex-col p-6">
              {task && statusMeta ? (
                <div className="flex h-full flex-col">
                  <div className="rounded-xl border bg-muted/20 p-5">
                    <div className="flex items-center gap-4">
                      <div
                        className={cn(
                          'flex size-11 items-center justify-center rounded-full bg-background shadow-sm',
                          failed
                            ? 'text-destructive'
                            : task.status === 'FINISH'
                              ? 'text-emerald-600'
                              : 'text-slate-700 dark:text-slate-200',
                        )}
                      >
                        {failed ? (
                          <CircleAlertIcon />
                        ) : task.status === 'FINISH' ? (
                          <CheckCircle2Icon />
                        ) : (
                          <Loader2Icon className="animate-spin" />
                        )}
                      </div>
                      <div>
                        <div className="font-medium">{statusMeta.label}</div>
                        <div className="mt-1 text-sm text-muted-foreground">
                          {task.tip || statusMeta.description}
                        </div>
                      </div>
                    </div>
                    <Progress
                      value={statusMeta.progress}
                      className="mt-5 h-1.5"
                    />
                  </div>

                  <div className="mt-6 space-y-0">
                    {[
                      ['文档上传', true],
                      ['版面与文字识别', task.status !== 'CREATE'],
                      [
                        '生成结果文件',
                        task.status === 'FINISH' ||
                          task.status === 'ANY_FAILED',
                      ],
                    ].map(([label, complete], index) => (
                      <div key={String(label)} className="flex gap-3">
                        <div className="flex flex-col items-center">
                          <div
                            className={cn(
                              'flex size-7 items-center justify-center rounded-full border text-xs',
                              complete
                                ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950'
                                : 'bg-background text-muted-foreground',
                            )}
                          >
                            {complete ? (
                              <CheckCircle2Icon className="size-4" />
                            ) : (
                              index + 1
                            )}
                          </div>
                          {index < 2 ? (
                            <div className="h-8 w-px bg-border" />
                          ) : null}
                        </div>
                        <div className="pt-1 text-sm">{label}</div>
                      </div>
                    ))}
                  </div>

                  <div className="mt-auto pt-8">
                    {task.download_url ? (
                      <Button className="w-full" size="lg" asChild>
                        <a
                          href={task.download_url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          <DownloadIcon />
                          下载
                          {FORMAT_LABELS[task.export_format ?? format]}结果
                        </a>
                      </Button>
                    ) : null}
                    <div className="mt-4 flex items-center justify-between gap-3 text-xs text-muted-foreground">
                      <span className="truncate">任务号：{task.task_no}</span>
                      {task.pages.length ? (
                        <span>{task.pages.length} 页已返回</span>
                      ) : null}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="flex flex-1 flex-col items-center justify-center px-5 text-center">
                  <div className="mb-4 flex size-14 items-center justify-center rounded-full bg-muted text-muted-foreground">
                    <Clock3Icon className="size-7" />
                  </div>
                  <div className="text-sm font-medium">等待提交文档</div>
                  <p className="mt-2 max-w-72 text-sm leading-6 text-muted-foreground">
                    上传 PDF 并选择输出格式后，识别进度与结果文件会显示在这里。
                  </p>
                  <div className="mt-6 flex items-center gap-2 text-xs text-muted-foreground">
                    <FileCheck2Icon className="size-4" />
                    最多 100 页
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  )
}
