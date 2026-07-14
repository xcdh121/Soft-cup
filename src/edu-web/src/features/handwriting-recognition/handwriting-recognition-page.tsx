import {
  CheckCircle2Icon,
  CopyIcon,
  DownloadIcon,
  FileImageIcon,
  Loader2Icon,
  PackagePlusIcon,
  RotateCcwIcon,
  ScanTextIcon,
  ShieldCheckIcon,
  UploadCloudIcon,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import type { HandwritingRecognitionResult } from '@/lib/xfyun-handwriting'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import { recognizeHandwriting } from '@/lib/xfyun-handwriting'
import { importResourcePackage } from '@/lib/resource-package-import'

const MAX_IMAGE_BYTES = 4 * 1024 * 1024
const SUPPORTED_EXTENSIONS = ['jpg', 'jpeg', 'png', 'bmp']

const formatFileSize = (bytes: number) => {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}

const isSupportedImage = (file: File) => {
  const extension = file.name.split('.').pop()?.toLowerCase() ?? ''
  return SUPPORTED_EXTENSIONS.includes(extension)
}

const getImageDimensions = (file: File) =>
  new Promise<{ width: number; height: number }>((resolve, reject) => {
    const url = URL.createObjectURL(file)
    const image = new Image()
    image.onload = () => {
      URL.revokeObjectURL(url)
      resolve({ width: image.naturalWidth, height: image.naturalHeight })
    }
    image.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('图片无法读取，请更换文件。'))
    }
    image.src = url
  })

export const HandwritingRecognitionPage = ({
  projectId,
}: {
  projectId: string
}) => {
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [language, setLanguage] = useState<'cn|en' | 'en'>('cn|en')
  const [result, setResult] = useState<HandwritingRecognitionResult | null>(
    null,
  )
  const [error, setError] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [isRecognizing, setIsRecognizing] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [savedPackageId, setSavedPackageId] = useState<string | null>(null)

  useEffect(() => {
    if (!file) {
      setPreviewUrl(null)
      return
    }
    const nextUrl = URL.createObjectURL(file)
    setPreviewUrl(nextUrl)
    return () => URL.revokeObjectURL(nextUrl)
  }, [file])

  const selectFile = async (nextFile?: File) => {
    if (!nextFile) return
    if (!isSupportedImage(nextFile)) {
      setError('仅支持 JPG、PNG、BMP 图片。')
      return
    }
    if (nextFile.size > MAX_IMAGE_BYTES) {
      setError('图片大小不能超过 4MB。')
      return
    }
    try {
      const { width, height } = await getImageDimensions(nextFile)
      if (width < 15 || height < 15 || width > 4096 || height > 4096) {
        setError('图片边长需在 15px 至 4096px 之间。')
        return
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '图片无法读取。')
      return
    }
    setFile(nextFile)
    setResult(null)
    setSavedPackageId(null)
    setError(null)
  }

  const reset = () => {
    setFile(null)
    setResult(null)
    setSavedPackageId(null)
    setError(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  const handleRecognize = async () => {
    if (!file || isRecognizing) return
    setIsRecognizing(true)
    setError(null)
    try {
      const nextResult = await recognizeHandwriting({
        projectId,
        image: file,
        language,
      })
      setResult(nextResult)
      if (!nextResult.text) {
        setError('未识别到清晰文字，请尝试更换对比度更高的图片。')
      } else {
        toast.success('识别完成')
      }
    } catch (caught) {
      setResult(null)
      setError(
        caught instanceof Error ? caught.message : '识别失败，请稍后重试。',
      )
    } finally {
      setIsRecognizing(false)
    }
  }

  const copyResult = async () => {
    if (!result?.text) return
    await navigator.clipboard.writeText(result.text)
    toast.success('识别文字已复制')
  }

  const saveToResourcePackage = async () => {
    if (!result?.text || isSaving || savedPackageId) return
    setIsSaving(true)
    try {
      const resourcePackage = await importResourcePackage({
        projectId,
        title: file
          ? `${file.name.replace(/\.[^.]+$/, '')} · 手写笔记`
          : '手写笔记',
        summary: '由讯飞手写笔记识别生成的可检索文本',
        origin: 'handwriting',
        resourceType: 'lecture_note',
        contentFormat: 'text',
        contentText: result.text,
      })
      setSavedPackageId(resourcePackage.id)
      toast.success('已存入资源包')
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : '存入资源包失败')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="h-full overflow-y-auto bg-muted/20">
      <main className="mx-auto w-full max-w-7xl px-5 py-7 lg:px-8">
        <div className="mb-6 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <div className="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                <ScanTextIcon className="size-5" />
              </div>
              <Badge variant="secondary" className="font-normal">
                讯飞 OCR
              </Badge>
            </div>
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">
                手写笔记识别
              </h1>
              <p className="mt-1 text-sm text-muted-foreground">
                上传手写笔记或答题图片，快速提取可复制、可编辑的文字。
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <ShieldCheckIcon className="size-4 text-emerald-600" />
            <span>密钥由服务端安全调用</span>
          </div>
        </div>

        {error ? (
          <Alert variant="destructive" className="mb-5">
            <AlertTitle>暂未完成识别</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}

        <div className="grid gap-5 lg:grid-cols-[minmax(0,1.05fr)_minmax(380px,0.95fr)]">
          <div className="space-y-5">
            <Card className="gap-4 shadow-none">
              <CardHeader>
                <CardTitle className="text-base">上传图片</CardTitle>
                <CardDescription>
                  支持 JPG、PNG、BMP，文件不超过 4MB；建议图片清晰、光线均匀。
                </CardDescription>
              </CardHeader>
              <CardContent>
                <input
                  ref={inputRef}
                  type="file"
                  className="hidden"
                  accept=".jpg,.jpeg,.png,.bmp,image/jpeg,image/png,image/bmp"
                  onChange={(event) => {
                    void selectFile(event.target.files?.[0])
                  }}
                />
                {previewUrl && file ? (
                  <div className="overflow-hidden rounded-xl border bg-muted/30">
                    <div className="flex min-h-80 items-center justify-center p-4">
                      <img
                        src={previewUrl}
                        alt="待识别手写图片预览"
                        className="max-h-[440px] w-auto max-w-full rounded-md object-contain shadow-sm"
                      />
                    </div>
                    <div className="flex flex-col gap-3 border-t bg-background px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                      <div className="flex min-w-0 items-center gap-3">
                        <FileImageIcon className="size-5 shrink-0 text-muted-foreground" />
                        <div className="min-w-0">
                          <div className="truncate text-sm font-medium">
                            {file.name}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {formatFileSize(file.size)}
                          </div>
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => inputRef.current?.click()}
                        >
                          更换图片
                        </Button>
                        <Button variant="ghost" size="sm" onClick={reset}>
                          <RotateCcwIcon />
                          清除
                        </Button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <button
                    type="button"
                    className={cn(
                      'flex min-h-80 w-full flex-col items-center justify-center rounded-xl border border-dashed bg-muted/20 px-6 text-center transition-colors',
                      isDragging
                        ? 'border-primary bg-primary/5'
                        : 'hover:border-primary/60 hover:bg-muted/40',
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
                    <div className="mb-4 flex size-14 items-center justify-center rounded-full bg-primary/10 text-primary">
                      <UploadCloudIcon className="size-7" />
                    </div>
                    <div className="font-medium">点击或拖拽图片到这里</div>
                    <div className="mt-2 text-sm text-muted-foreground">
                      推荐使用扫描件或正面拍摄的手写内容
                    </div>
                  </button>
                )}
              </CardContent>
            </Card>

            <Card className="gap-4 shadow-none">
              <CardHeader>
                <CardTitle className="text-base">识别设置</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-4 sm:flex-row sm:items-end">
                <div className="flex-1 space-y-2">
                  <Label htmlFor="handwriting-language">文字语言</Label>
                  <Select
                    value={language}
                    onValueChange={(value) =>
                      setLanguage(value as 'cn|en' | 'en')
                    }
                  >
                    <SelectTrigger id="handwriting-language" className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="cn|en">中文 / 中英混合</SelectItem>
                      <SelectItem value="en">英文</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <Button
                  size="lg"
                  className="sm:min-w-40"
                  disabled={!file || isRecognizing}
                  onClick={handleRecognize}
                >
                  {isRecognizing ? (
                    <>
                      <Loader2Icon className="animate-spin" />
                      正在识别
                    </>
                  ) : (
                    <>
                      <ScanTextIcon />
                      开始识别
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>
          </div>

          <Card className="min-h-[620px] gap-0 shadow-none lg:sticky lg:top-0 lg:max-h-[calc(100vh-5.5rem)]">
            <CardHeader className="border-b pb-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <CardTitle className="text-base">识别结果</CardTitle>
                  <CardDescription className="mt-1.5">
                    {result?.text
                      ? `已识别 ${result.lines.length} 行文字`
                      : '识别完成后，文字将显示在这里。'}
                  </CardDescription>
                </div>
                {result?.text ? (
                  <CheckCircle2Icon className="size-5 text-emerald-600" />
                ) : null}
              </div>
            </CardHeader>
            <CardContent className="flex min-h-0 flex-1 flex-col p-0">
              {result?.text ? (
                <>
                  <Textarea
                    value={result.text}
                    readOnly
                    aria-label="手写笔记识别结果"
                    className="min-h-0 flex-1 resize-none rounded-none border-0 p-6 text-[15px] leading-7 shadow-none focus-visible:ring-0"
                  />
                  <div className="flex items-center justify-between gap-3 border-t px-5 py-4">
                    <span className="text-xs text-muted-foreground">
                      可直接复制到笔记或对话中继续使用
                    </span>
                    <div className="flex flex-wrap justify-end gap-2">
                      <Button
                        size="sm"
                        disabled={isSaving || Boolean(savedPackageId)}
                        onClick={saveToResourcePackage}
                      >
                        {isSaving ? (
                          <Loader2Icon className="animate-spin" />
                        ) : savedPackageId ? (
                          <CheckCircle2Icon />
                        ) : (
                          <PackagePlusIcon />
                        )}
                        {savedPackageId ? '已存入资源包' : '存入资源包'}
                      </Button>
                      <Button variant="outline" size="sm" onClick={copyResult}>
                        <CopyIcon />
                        复制
                      </Button>
                      <Button variant="outline" size="sm" asChild>
                        <a
                          href={`data:text/plain;charset=utf-8,${encodeURIComponent(result.text)}`}
                          download="手写笔记识别结果.txt"
                        >
                          <DownloadIcon />
                          下载
                        </a>
                      </Button>
                    </div>
                  </div>
                </>
              ) : (
                <div className="flex flex-1 flex-col items-center justify-center px-8 text-center">
                  <div className="mb-4 flex size-14 items-center justify-center rounded-full bg-muted text-muted-foreground">
                    <ScanTextIcon className="size-7" />
                  </div>
                  <div className="text-sm font-medium">等待识别</div>
                  <p className="mt-2 max-w-72 text-sm leading-6 text-muted-foreground">
                    在左侧上传一张包含手写笔记的图片，然后点击“开始识别”。
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  )
}
