import {
  ArrowRightIcon,
  CheckCircle2Icon,
  CopyIcon,
  DownloadIcon,
  FileTextIcon,
  LanguagesIcon,
  Loader2Icon,
  PackagePlusIcon,
  RotateCcwIcon,
  ShieldCheckIcon,
  UploadCloudIcon,
} from 'lucide-react'
import { useRef, useState } from 'react'
import { pdfjs } from 'react-pdf'
import { toast } from 'sonner'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { importResourcePackage } from '@/lib/resource-package-import'
import { translateDocument } from '@/lib/xfyun-translation'

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

const MAX_CHARACTERS = 50_000
const LANGUAGES = [
  { value: 'cn', label: '中文' },
  { value: 'en', label: '英语' },
  { value: 'ja', label: '日语' },
  { value: 'ko', label: '韩语' },
  { value: 'fr', label: '法语' },
  { value: 'de', label: '德语' },
  { value: 'es', label: '西班牙语' },
  { value: 'ru', label: '俄语' },
]

const languageLabel = (value: string) =>
  LANGUAGES.find((language) => language.value === value)?.label ?? value

const extractPdfText = async (file: File) => {
  const loadingTask = pdfjs.getDocument({ data: await file.arrayBuffer() })
  try {
    const document = await loadingTask.promise
    const pages: Array<string> = []
    for (let pageNumber = 1; pageNumber <= document.numPages; pageNumber += 1) {
      const page = await document.getPage(pageNumber)
      const content = await page.getTextContent()
      pages.push(
        content.items
          .map((item) => ('str' in item ? item.str : ''))
          .join(' ')
          .trim(),
      )
    }
    return pages.filter(Boolean).join('\n\n')
  } finally {
    await loadingTask.destroy()
  }
}

export const DocumentTranslationPage = ({
  projectId,
}: {
  projectId: string
}) => {
  const inputRef = useRef<HTMLInputElement>(null)
  const [sourceText, setSourceText] = useState('')
  const [translatedText, setTranslatedText] = useState('')
  const [sourceLanguage, setSourceLanguage] = useState('cn')
  const [targetLanguage, setTargetLanguage] = useState('en')
  const [fileName, setFileName] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isReading, setIsReading] = useState(false)
  const [isTranslating, setIsTranslating] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [savedPackageId, setSavedPackageId] = useState<string | null>(null)

  const selectFile = async (file?: File) => {
    if (!file) return
    const extension = file.name.split('.').pop()?.toLowerCase()
    if (!['txt', 'md', 'pdf'].includes(extension ?? '')) {
      setError('仅支持 TXT、Markdown 和可提取文字的 PDF 文档。')
      return
    }
    setIsReading(true)
    setError(null)
    try {
      const text =
        extension === 'pdf' ? await extractPdfText(file) : await file.text()
      if (!text.trim()) {
        throw new Error('未提取到文字；扫描版 PDF 请先使用“PDF 文档识别”。')
      }
      if (text.length > MAX_CHARACTERS) {
        throw new Error(
          `文档内容超过 ${MAX_CHARACTERS.toLocaleString()} 字符，请拆分后重试。`,
        )
      }
      setSourceText(text)
      setTranslatedText('')
      setFileName(file.name)
      setSavedPackageId(null)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '文档读取失败。')
    } finally {
      setIsReading(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  const reset = () => {
    setSourceText('')
    setTranslatedText('')
    setFileName(null)
    setError(null)
    setSavedPackageId(null)
  }

  const handleTranslate = async () => {
    if (!sourceText.trim() || isTranslating) return
    if (sourceLanguage === targetLanguage) {
      setError('请选择不同的源语言和目标语言。')
      return
    }
    setIsTranslating(true)
    setError(null)
    setSavedPackageId(null)
    try {
      const result = await translateDocument({
        projectId,
        text: sourceText,
        fromLanguage: sourceLanguage,
        toLanguage: targetLanguage,
      })
      setTranslatedText(result.translated_text)
      toast.success(
        result.chunk_count > 1
          ? `翻译完成，已安全处理 ${result.chunk_count} 个文本分段`
          : '翻译完成',
      )
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : '翻译失败，请稍后重试。',
      )
    } finally {
      setIsTranslating(false)
    }
  }

  const copyResult = async () => {
    await navigator.clipboard.writeText(translatedText)
    toast.success('译文已复制')
  }

  const saveToResourcePackage = async () => {
    if (!translatedText || isSaving || savedPackageId) return
    setIsSaving(true)
    try {
      const baseTitle = fileName?.replace(/\.[^.]+$/, '') || '文档翻译'
      const resourcePackage = await importResourcePackage({
        projectId,
        title: `${baseTitle} · ${languageLabel(targetLanguage)}译文`,
        summary: `${languageLabel(sourceLanguage)} → ${languageLabel(targetLanguage)}，由讯飞机器翻译生成`,
        origin: 'translation',
        resourceType: 'reading_material',
        contentFormat: 'text',
        contentText: translatedText,
      })
      setSavedPackageId(resourcePackage.id)
      toast.success('译文已存入资源包')
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : '存入资源包失败')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="h-full overflow-y-auto bg-slate-50/60 dark:bg-slate-950/20">
      <main className="mx-auto w-full max-w-7xl px-5 py-7 lg:px-8">
        <div className="mb-6 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div>
            <div className="mb-3 flex items-center gap-2">
              <div className="flex size-9 items-center justify-center rounded-lg bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900">
                <LanguagesIcon className="size-5" />
              </div>
              <Badge variant="outline" className="bg-background font-normal">
                讯飞机器翻译（新）
              </Badge>
            </div>
            <h1 className="text-2xl font-semibold tracking-tight">文档翻译</h1>
            <p className="mt-1.5 text-sm text-muted-foreground">
              面向学习资料与商务文档的简洁翻译工作台，支持长文自动分段处理。
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <ShieldCheckIcon className="size-4 text-emerald-600" />
            <span>鉴权与密钥仅在服务端处理</span>
          </div>
        </div>

        {error ? (
          <Alert variant="destructive" className="mb-5 bg-background">
            <AlertTitle>暂未完成翻译</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}

        <Card className="mb-5 gap-4 shadow-none">
          <CardContent className="flex flex-col gap-4 pt-6 lg:flex-row lg:items-center">
            <input
              ref={inputRef}
              type="file"
              accept=".txt,.md,.pdf,text/plain,text/markdown,application/pdf"
              className="hidden"
              onChange={(event) => void selectFile(event.target.files?.[0])}
            />
            <div className="flex flex-1 items-center gap-3">
              <Select value={sourceLanguage} onValueChange={setSourceLanguage}>
                <SelectTrigger className="w-full bg-background sm:w-44">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {LANGUAGES.map((language) => (
                    <SelectItem key={language.value} value={language.value}>
                      {language.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <ArrowRightIcon className="size-4 shrink-0 text-muted-foreground" />
              <Select value={targetLanguage} onValueChange={setTargetLanguage}>
                <SelectTrigger className="w-full bg-background sm:w-44">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {LANGUAGES.map((language) => (
                    <SelectItem key={language.value} value={language.value}>
                      {language.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                onClick={() => inputRef.current?.click()}
              >
                {isReading ? (
                  <Loader2Icon className="animate-spin" />
                ) : (
                  <UploadCloudIcon />
                )}
                导入文档
              </Button>
              <Button variant="ghost" onClick={reset} disabled={!sourceText}>
                <RotateCcwIcon />
                清空
              </Button>
              <Button
                className="min-w-32 bg-slate-900 dark:bg-slate-100"
                disabled={!sourceText.trim() || isTranslating || isReading}
                onClick={handleTranslate}
              >
                {isTranslating ? (
                  <Loader2Icon className="animate-spin" />
                ) : (
                  <LanguagesIcon />
                )}
                {isTranslating ? '翻译中' : '开始翻译'}
              </Button>
            </div>
          </CardContent>
        </Card>

        <div className="grid gap-5 lg:grid-cols-2">
          <Card className="min-h-[560px] gap-0 shadow-none">
            <CardHeader className="border-b pb-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <CardTitle className="text-base">原文</CardTitle>
                  <CardDescription className="mt-1.5">
                    {fileName ? `已导入 ${fileName}` : '粘贴文本或导入文档'}
                  </CardDescription>
                </div>
                <Badge variant="secondary">
                  {sourceText.length.toLocaleString()} /{' '}
                  {MAX_CHARACTERS.toLocaleString()}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="flex min-h-0 flex-1 flex-col p-0">
              <Textarea
                value={sourceText}
                maxLength={MAX_CHARACTERS}
                onChange={(event) => {
                  setSourceText(event.target.value)
                  setTranslatedText('')
                  setSavedPackageId(null)
                }}
                placeholder="在此粘贴需要翻译的文档内容……"
                className="min-h-[490px] flex-1 resize-none rounded-none border-0 p-6 text-[15px] leading-7 shadow-none focus-visible:ring-0"
              />
            </CardContent>
          </Card>

          <Card className="min-h-[560px] gap-0 border-slate-200 shadow-none dark:border-slate-800">
            <CardHeader className="border-b pb-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <CardTitle className="text-base">译文</CardTitle>
                  <CardDescription className="mt-1.5">
                    {translatedText
                      ? `${languageLabel(targetLanguage)}译文已生成`
                      : '翻译结果将在此显示'}
                  </CardDescription>
                </div>
                {translatedText ? (
                  <CheckCircle2Icon className="size-5 text-emerald-600" />
                ) : null}
              </div>
            </CardHeader>
            <CardContent className="flex min-h-0 flex-1 flex-col p-0">
              {translatedText ? (
                <>
                  <Textarea
                    value={translatedText}
                    readOnly
                    aria-label="文档翻译结果"
                    className="min-h-[430px] flex-1 resize-none rounded-none border-0 p-6 text-[15px] leading-7 shadow-none focus-visible:ring-0"
                  />
                  <div className="flex flex-wrap items-center justify-between gap-3 border-t px-5 py-4">
                    <span className="text-xs text-muted-foreground">
                      译文可复制、下载或归档到资源包
                    </span>
                    <div className="flex flex-wrap gap-2">
                      <Button variant="outline" size="sm" onClick={copyResult}>
                        <CopyIcon />
                        复制
                      </Button>
                      <Button variant="outline" size="sm" asChild>
                        <a
                          href={`data:text/plain;charset=utf-8,${encodeURIComponent(translatedText)}`}
                          download={`${fileName?.replace(/\.[^.]+$/, '') || '文档'}-${targetLanguage}.txt`}
                        >
                          <DownloadIcon />
                          下载
                        </a>
                      </Button>
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
                    </div>
                  </div>
                </>
              ) : (
                <div className="flex flex-1 flex-col items-center justify-center px-8 text-center">
                  <div className="mb-4 flex size-14 items-center justify-center rounded-full bg-slate-100 text-slate-500 dark:bg-slate-900">
                    <FileTextIcon className="size-7" />
                  </div>
                  <div className="text-sm font-medium">等待翻译</div>
                  <p className="mt-2 max-w-72 text-sm leading-6 text-muted-foreground">
                    选择语言并提交原文，系统会在服务端安全调用讯飞机器翻译。
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
