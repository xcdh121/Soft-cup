import { create } from 'zustand'
import { useEffect, useState } from 'react'
import { Loader2Icon } from 'lucide-react'
import { Result, useAtom, useAtomValue } from '@effect-atom/atom-react'
import type { DocumentDto } from '@/integrations/api/client'
import type { ProgressStage } from '@/components/generation-progress'
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
import {
  createNoteAtom,
  createNoteStreamAtom,
  noteProgressAtom,
} from '@/data-acess/note'
import {
  createQuizAtom,
  createQuizStreamAtom,
  quizProgressAtom,
} from '@/data-acess/quiz'
import {
  createFlashcardGroupAtom,
  createFlashcardGroupStreamAtom,
  flashcardProgressAtom,
} from '@/data-acess/flashcard'
import {
  generateMindMapStreamAtom,
  mindMapProgressAtom,
} from '@/data-acess/mind-map'
import { GenerationProgress } from '@/components/generation-progress'

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

type GenerationType = 'quiz' | 'flashcard' | 'note' | 'mindmap'
type LengthOption = 'less' | 'normal' | 'more'
type DifficultyOption = 'easy' | 'medium' | 'hard'

export function GenerationDialog() {
  const { isOpen, projectId, close } = useGenerationDialog()
  const [customInstructions, setCustomInstructions] = useState('')
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<Set<string>>(
    new Set(),
  )
  const [isGenerating, setIsGenerating] = useState(false)
  const [selectedType, setSelectedType] = useState<GenerationType>('note')
  const [length, setLength] = useState<LengthOption>('normal')
  const [difficulty, setDifficulty] = useState<DifficultyOption>('medium')

  const documentsResult = useAtomValue(indexedDocumentsAtom(projectId || ''))

  // Streaming atoms
  const [createNoteStreamResult, createNoteStream] = useAtom(
    createNoteStreamAtom,
    {
      mode: 'promise',
    },
  )
  const [, createNote] = useAtom(createNoteAtom, {
    mode: 'promise',
  })
  const [createQuizStreamResult, createQuizStream] = useAtom(
    createQuizStreamAtom,
    {
      mode: 'promise',
    },
  )
  const [, createQuiz] = useAtom(createQuizAtom, {
    mode: 'promise',
  })
  const [createFlashcardStreamResult, createFlashcardStream] = useAtom(
    createFlashcardGroupStreamAtom,
    { mode: 'promise' },
  )
  const [, createFlashcardGroup] = useAtom(createFlashcardGroupAtom, {
    mode: 'promise',
  })
  const [generateMindMapStreamResult, generateMindMapStream] = useAtom(
    generateMindMapStreamAtom,
    { mode: 'promise' },
  )

  // Progress atoms
  const noteProgress = useAtomValue(noteProgressAtom)
  const quizProgress = useAtomValue(quizProgressAtom)
  const flashcardProgress = useAtomValue(flashcardProgressAtom)
  const mindMapProgress = useAtomValue(mindMapProgressAtom)

  // Get current progress based on selected type
  const currentProgress =
    selectedType === 'note'
      ? noteProgress
      : selectedType === 'quiz'
        ? quizProgress
        : selectedType === 'flashcard'
          ? flashcardProgress
          : mindMapProgress

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

    const allIds = new Set(documentsResult.value.map((doc) => doc.id))
    setSelectedDocumentIds(allIds)
  }

  const handleDeselectAll = () => {
    setSelectedDocumentIds(new Set())
  }

  // Update isGenerating based on streaming state
  useEffect(() => {
    const isStreaming =
      createNoteStreamResult.waiting ||
      createQuizStreamResult.waiting ||
      createFlashcardStreamResult.waiting ||
      generateMindMapStreamResult.waiting

    setIsGenerating(isStreaming)
  }, [
    createNoteStreamResult.waiting,
    createQuizStreamResult.waiting,
    createFlashcardStreamResult.waiting,
    generateMindMapStreamResult.waiting,
  ])

  const handleGenerate = async () => {
    if (!projectId || !customInstructions.trim()) return

    try {
      const instructions = customInstructions.trim()

      switch (selectedType) {
        case 'note': {
          const note = await createNote({
            projectId,
            title: buildGeneratedTitle('笔记', instructions),
            content: '',
            description: instructions,
          })
          await createNoteStream({
            projectId,
            customInstructions: instructions,
            noteId: note.id,
            count: 30,
            difficulty: difficulty !== 'medium' ? difficulty : undefined,
            topic: instructions,
          })
          break
        }
        case 'quiz': {
          const quiz = await createQuiz({
            projectId,
            name: buildGeneratedTitle('测验', instructions),
            description: instructions,
          })
          await createQuizStream({
            projectId,
            quizId: quiz.id,
            topic: instructions,
            questionCount: 30,
            customInstructions: instructions,
            difficulty: difficulty !== 'medium' ? difficulty : undefined,
          })
          break
        }
        case 'flashcard': {
          const group = await createFlashcardGroup({
            projectId,
            customInstructions: instructions,
          })
          await createFlashcardStream({
            projectId,
            groupId: group.id,
            flashcardCount: 30,
            customInstructions: instructions,
            length: length !== 'normal' ? length : undefined,
            difficulty: difficulty !== 'medium' ? difficulty : undefined,
          })
          break
        }
        case 'mindmap':
          await generateMindMapStream({
            projectId,
            title: buildGeneratedTitle('思维导图', instructions),
            customInstructions: instructions,
          })
          break
      }

      // Close dialog and reset state after a short delay to show completion
      setTimeout(() => {
        handleClose()
      }, 500)
    } catch (error) {
      console.error('Generation failed:', error)
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
    selectedType === 'note'

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && handleClose()}>
      <DialogContent className="sm:max-w-[600px] max-h-[85vh] flex flex-col overflow-hidden">
        <DialogHeader className="shrink-0">
          <DialogTitle>生成 AI 内容</DialogTitle>
          <DialogDescription>
            选择资源类型，输入自定义要求，并选择相关文档来生成内容。
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
            </div>
          </div>

          <div className="space-y-2 shrink-0">
            <Label htmlFor="customInstructions">自定义要求</Label>
            <Textarea
              id="customInstructions"
              placeholder="例如：解释机器学习的核心概念... 可说明格式偏好：长度（少、正常、多），难度（简单、中等、困难）"
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
                      <SelectItem value="less">少</SelectItem>
                      <SelectItem value="normal">正常</SelectItem>
                      <SelectItem value="more">多</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                {(selectedType === 'quiz' || selectedType === 'flashcard') && (
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
                    <div className="text-destructive py-4">
                      文档加载失败
                    </div>
                  ))
                  .onSuccess((documents) => {
                    if (documents.length === 0) {
                      return (
                        <div className="text-muted-foreground py-4 text-center">
                          没有可用文档。请先上传文档。
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

        {currentProgress && (
          <div className="shrink-0 px-4">
            <GenerationProgress
              status={currentProgress.status as ProgressStage}
              message={currentProgress.message}
              error={currentProgress.error}
            />
          </div>
        )}

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
            disabled={isGenerating || !customInstructions.trim()}
          >
            {isGenerating ? (
              <>
                <Loader2Icon className="size-4 mr-2 animate-spin" />
                正在生成
                {selectedType === 'note'
                  ? '笔记'
                  : selectedType === 'quiz'
                    ? '测验'
                    : selectedType === 'flashcard'
                      ? '闪卡'
                      : '思维导图'}
                ...
              </>
            ) : !customInstructions.trim() ? (
              '填写要求后生成'
            ) : (
              `生成${
                selectedType === 'note'
                  ? '笔记'
                  : selectedType === 'quiz'
                    ? '测验'
                    : selectedType === 'flashcard'
                      ? '闪卡'
                      : '思维导图'
              }`
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function buildGeneratedTitle(resourceLabel: string, instructions: string): string {
  const normalized = instructions.replace(/\s+/g, ' ').trim()
  const suffix = normalized.length > 24 ? `${normalized.slice(0, 24)}...` : normalized
  return suffix ? `AI ${resourceLabel}：${suffix}` : `AI ${resourceLabel}`
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
            {document.file_type?.toUpperCase()} •{' '}
            {formatFileSize(document.file_size)}
          </span>
        </div>
      </Label>
    </div>
  )
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 字节'
  const k = 1024
  const sizes = ['字节', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i]
}
