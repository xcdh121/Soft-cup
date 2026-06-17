import { create } from 'zustand'
import { useState } from 'react'
import { Loader2Icon } from 'lucide-react'
import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import { toast } from 'sonner'
import type { DocumentDto } from '@/integrations/api/client'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { indexedDocumentsAtom } from '@/data-acess/document'
import { generateResourcePackageAtom } from '@/data-acess/resource-package'

type GenerationDialogStore = {
  isOpen: boolean
  projectId: string | null
  open: (projectId: string) => void
  close: () => void
}

export const useGenerationDialog = create<GenerationDialogStore>((set) => ({
  isOpen: false,
  projectId: null,
  open: (projectId: string) => set({ isOpen: true, projectId }),
  close: () => set({ isOpen: false, projectId: null }),
}))

type GenerationType =
  | 'quiz'
  | 'flashcard'
  | 'note'
  | 'mindmap'
  | 'ppt_outline'
  | 'pptx'
type LengthOption = 'less' | 'normal' | 'more'
type DifficultyOption = 'easy' | 'medium' | 'hard'

export function GenerationDialog() {
  const { isOpen, projectId, close } = useGenerationDialog()
  const [customInstructions, setCustomInstructions] = useState('')
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<Set<string>>(
    new Set(),
  )
  const [selectedType, setSelectedType] = useState<GenerationType>('note')
  const [length, setLength] = useState<LengthOption>('normal')
  const [difficulty, setDifficulty] = useState<DifficultyOption>('medium')
  const [isGenerating, setIsGenerating] = useState(false)

  const documentsResult = useAtomValue(indexedDocumentsAtom(projectId || ''))
  const generateResourcePackage = useAtomSet(generateResourcePackageAtom, {
    mode: 'promise',
  })

  const handleToggleDocument = (documentId: string) => {
    setSelectedDocumentIds((prev) => {
      const next = new Set(prev)
      if (next.has(documentId)) {
        next.delete(documentId)
      } else {
        next.add(documentId)
      }
      return next
    })
  }

  const handleSelectAll = () => {
    if (!Result.isSuccess(documentsResult)) return
    setSelectedDocumentIds(new Set(documentsResult.value.map((doc) => doc.id)))
  }

  const handleDeselectAll = () => {
    setSelectedDocumentIds(new Set())
  }

  const handleGenerate = async () => {
    if (!projectId) return

    const instructions = customInstructions.trim()
    if (!instructions) {
      toast.error('请输入生成要求后再试。')
      return
    }

    setIsGenerating(true)
    try {
      await generateResourcePackage({
        projectId,
        target_topic: instructions,
        title: buildGeneratedTitle(actionLabel, instructions),
        source_document_ids: Array.from(selectedDocumentIds),
        resource_types: [toResourcePackageType(selectedType)],
        difficulty_level: toDifficultyLevel(difficulty),
        custom_instructions: instructions,
        generation_params: {
          launch_context: 'project overview ai content',
          quiz_count: selectedType === 'quiz' ? 30 : undefined,
          flashcard_count: selectedType === 'flashcard' ? 30 : undefined,
          preferred_length: selectedType === 'flashcard' ? length : undefined,
        },
      })

      if (selectedDocumentIds.size > 0) {
        toast.info('已将所选文档一并作为统一资源生成链路的上下文。')
      }
      toast.success(`${actionLabel} 已提交到统一多 Agent 生成链路。`)

      setTimeout(() => {
        handleClose()
      }, 500)
    } catch (error) {
      console.error('Generation failed:', error)
      toast.error(error instanceof Error ? error.message : '生成失败，请稍后重试。')
    } finally {
      setIsGenerating(false)
    }
  }

  const handleClose = () => {
    if (isGenerating) return
    close()
    setCustomInstructions('')
    setSelectedDocumentIds(new Set())
    setSelectedType('note')
    setLength('normal')
    setDifficulty('medium')
  }

  const hasSelectedDocuments = selectedDocumentIds.size > 0
  const allDocumentsSelected =
    Result.isSuccess(documentsResult) &&
    documentsResult.value.length > 0 &&
    selectedDocumentIds.size === documentsResult.value.length

  const hasCustomSettings =
    selectedType === 'quiz' ||
    selectedType === 'flashcard' ||
    selectedType === 'note' ||
    selectedType === 'ppt_outline' ||
    selectedType === 'pptx'

  const actionLabel =
    selectedType === 'note'
      ? '笔记'
      : selectedType === 'quiz'
        ? '测验'
        : selectedType === 'flashcard'
          ? '闪卡'
          : selectedType === 'mindmap'
            ? '思维导图'
            : selectedType === 'ppt_outline'
              ? 'PPT 大纲'
              : 'PPT'

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && handleClose()}>
      <DialogContent className="sm:max-w-[600px] max-h-[85vh] flex flex-col overflow-hidden">
        <DialogHeader className="shrink-0">
          <DialogTitle>生成 AI 内容</DialogTitle>
          <DialogDescription>
            这里会统一走资源包与多 Agent 编排链路，再按你选择的资源类型落到具体资源。
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4 flex-1 min-h-0 overflow-hidden">
          <div className="space-y-2 shrink-0">
            <Label>资源类型</Label>
            <div className="grid grid-cols-2 gap-2">
              <Button
                type="button"
                variant={selectedType === 'note' ? 'default' : 'outline'}
                onClick={() => setSelectedType('note')}
                disabled={isGenerating}
              >
                笔记
              </Button>
              <Button
                type="button"
                variant={selectedType === 'quiz' ? 'default' : 'outline'}
                onClick={() => setSelectedType('quiz')}
                disabled={isGenerating}
              >
                测验
              </Button>
              <Button
                type="button"
                variant={selectedType === 'flashcard' ? 'default' : 'outline'}
                onClick={() => setSelectedType('flashcard')}
                disabled={isGenerating}
              >
                闪卡
              </Button>
              <Button
                type="button"
                variant={selectedType === 'mindmap' ? 'default' : 'outline'}
                onClick={() => setSelectedType('mindmap')}
                disabled={isGenerating}
              >
                思维导图
              </Button>
              <Button
                type="button"
                variant={selectedType === 'ppt_outline' ? 'default' : 'outline'}
                onClick={() => setSelectedType('ppt_outline')}
                disabled={isGenerating}
              >
                PPT 大纲
              </Button>
              <Button
                type="button"
                variant={selectedType === 'pptx' ? 'default' : 'outline'}
                onClick={() => setSelectedType('pptx')}
                disabled={isGenerating}
              >
                PPT
              </Button>
            </div>
          </div>

          <div className="space-y-2 shrink-0">
            <Label htmlFor="customInstructions">生成要求</Label>
            <Textarea
              id="customInstructions"
              placeholder="例如：生成一份面向入门学生的 Transformer 教学内容，突出核心概念、例子和总结。"
              value={customInstructions}
              onChange={(e) => setCustomInstructions(e.target.value)}
              className="min-h-[100px] resize-none"
              disabled={isGenerating}
            />
          </div>

          {hasCustomSettings && (
            <div className="space-y-3 shrink-0 border rounded-md p-4">
              <Label className="sr-only">自定义设置</Label>
              <div
                className={`grid gap-4 ${
                  selectedType === 'quiz' || selectedType === 'flashcard'
                    ? 'grid-cols-2'
                    : 'grid-cols-1'
                }`}
              >
                <div className="space-y-2">
                  <Label htmlFor="length">长度</Label>
                  <Select
                    value={length}
                    onValueChange={(value) => setLength(value as LengthOption)}
                    disabled={isGenerating}
                  >
                    <SelectTrigger id="length" className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="less">较短</SelectItem>
                      <SelectItem value="normal">标准</SelectItem>
                      <SelectItem value="more">较长</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                {(selectedType === 'quiz' ||
                  selectedType === 'flashcard' ||
                  selectedType === 'ppt_outline' ||
                  selectedType === 'pptx') && (
                  <div className="space-y-2">
                    <Label htmlFor="difficulty">难度</Label>
                    <Select
                      value={difficulty}
                      onValueChange={(value) =>
                        setDifficulty(value as DifficultyOption)
                      }
                      disabled={isGenerating}
                    >
                      <SelectTrigger id="difficulty" className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="easy">简单</SelectItem>
                        <SelectItem value="medium">中等</SelectItem>
                        <SelectItem value="hard">困难</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                )}
              </div>
            </div>
          )}

          <div className="space-y-2 flex-1 min-h-0 flex flex-col">
            <div className="flex items-center justify-between shrink-0">
              <Label>选择文档</Label>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={handleSelectAll}
                  disabled={
                    isGenerating ||
                    !Result.isSuccess(documentsResult) ||
                    documentsResult.value.length === 0 ||
                    allDocumentsSelected
                  }
                >
                  全选
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={handleDeselectAll}
                  disabled={isGenerating || !hasSelectedDocuments}
                >
                  取消全选
                </Button>
              </div>
            </div>

            <div className="flex-1 min-h-0 border rounded-md overflow-hidden flex flex-col">
              <div className="flex-1 overflow-y-auto p-4">
                {Result.builder(documentsResult)
                  .onInitialOrWaiting(() => (
                    <div className="flex items-center gap-2 text-muted-foreground py-4">
                      <Loader2Icon className="size-4 animate-spin" />
                      <span>正在加载文档...</span>
                    </div>
                  ))
                  .onFailure(() => (
                    <div className="text-destructive py-4">文档加载失败</div>
                  ))
                  .onSuccess((documents) => {
                    if (documents.length === 0) {
                      return (
                        <div className="text-muted-foreground py-4 text-center">
                          没有可用文档，请先上传文档。
                        </div>
                      )
                    }

                    return (
                      <div className="space-y-3">
                        {documents.map((document) => (
                          <DocumentCheckbox
                            key={document.id}
                            document={document}
                            checked={selectedDocumentIds.has(document.id)}
                            onCheckedChange={() =>
                              handleToggleDocument(document.id)
                            }
                            disabled={isGenerating}
                          />
                        ))}
                      </div>
                    )
                  })
                  .render()}
              </div>
            </div>
          </div>
        </div>

        <DialogFooter className="gap-2 shrink-0">
          <Button
            type="button"
            variant="outline"
            onClick={handleClose}
            disabled={isGenerating}
          >
            取消
          </Button>
          <Button
            type="button"
            onClick={handleGenerate}
            disabled={isGenerating}
          >
            {isGenerating ? (
              <>
                <Loader2Icon className="size-4 mr-2 animate-spin" />
                正在生成{actionLabel}...
              </>
            ) : !customInstructions.trim() ? (
              '填写要求后生成'
            ) : (
              `生成${actionLabel}`
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function buildGeneratedTitle(resourceLabel: string, instructions: string): string {
  const normalized = instructions.replace(/\s+/g, ' ').trim()
  const suffix =
    normalized.length > 24 ? `${normalized.slice(0, 24)}...` : normalized
  return suffix ? `AI ${resourceLabel}: ${suffix}` : `AI ${resourceLabel}`
}

function toResourcePackageType(selectedType: GenerationType) {
  switch (selectedType) {
    case 'note':
      return 'lecture_note'
    case 'quiz':
      return 'practice_set'
    case 'flashcard':
      return 'flashcards'
    case 'mindmap':
      return 'mind_map'
    case 'ppt_outline':
      return 'ppt_outline'
    case 'pptx':
      return 'pptx'
  }
}

function toDifficultyLevel(difficulty: DifficultyOption) {
  switch (difficulty) {
    case 'easy':
      return 'beginner'
    case 'hard':
      return 'advanced'
    default:
      return 'intermediate'
  }
}

type DocumentCheckboxProps = {
  document: DocumentDto
  checked: boolean
  onCheckedChange: (checked: boolean) => void
  disabled?: boolean
}

function DocumentCheckbox({
  document,
  checked,
  onCheckedChange,
  disabled,
}: DocumentCheckboxProps) {
  return (
    <div className="flex items-center gap-3 p-2 rounded-md hover:bg-muted/50">
      <Checkbox
        checked={checked}
        onCheckedChange={onCheckedChange}
        disabled={disabled}
        id={`doc-${document.id}`}
      />
      <Label
        htmlFor={`doc-${document.id}`}
        className="flex-1 cursor-pointer font-normal"
      >
        <div className="flex flex-col">
          <span className="text-sm">{document.file_name}</span>
          <span className="text-xs text-muted-foreground">
            {document.file_type?.toUpperCase()} | {formatFileSize(document.file_size)}
          </span>
        </div>
      </Label>
    </div>
  )
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i]
}
