import { create } from 'zustand'
import { useState } from 'react'
import { Loader2Icon } from 'lucide-react'
import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import { useNavigate } from '@tanstack/react-router'
import { toast } from 'sonner'
import type { CourseChapter } from '@/data-acess/course-library'
import type { GenerateResourcePackageInput } from '@/data-acess/resource-package'
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
import { projectCourseOutlineAtom } from '@/data-acess/course-library'
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
  | 'image'
  | 'pptx'
  | 'programming_questions'
  | 'video_recommendations'
type LengthOption = 'less' | 'normal' | 'more'
type DifficultyOption = 'easy' | 'medium' | 'hard'

export function GenerationDialog() {
  const navigate = useNavigate()
  const { isOpen, projectId, close } = useGenerationDialog()
  const [customInstructions, setCustomInstructions] = useState('')
  const [selectedChapterIds, setSelectedChapterIds] = useState<Set<string>>(
    new Set(),
  )
  const [selectedType, setSelectedType] = useState<GenerationType>('note')
  const [length, setLength] = useState<LengthOption>('normal')
  const [difficulty, setDifficulty] = useState<DifficultyOption>('medium')
  const [isGenerating, setIsGenerating] = useState(false)

  const courseOutlineResult = useAtomValue(
    projectCourseOutlineAtom(projectId || ''),
  )
  const generateResourcePackage = useAtomSet(generateResourcePackageAtom, {
    mode: 'promise',
  })

  const handleToggleChapter = (chapterId: string) => {
    setSelectedChapterIds((prev) => {
      const next = new Set(prev)
      if (next.has(chapterId)) {
        next.delete(chapterId)
      } else {
        next.add(chapterId)
      }
      return next
    })
  }

  const handleSelectAll = () => {
    if (!Result.isSuccess(courseOutlineResult)) return
    setSelectedChapterIds(
      new Set(courseOutlineResult.value.chapters.map((chapter) => chapter.id)),
    )
  }

  const handleDeselectAll = () => {
    setSelectedChapterIds(new Set())
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
      const knowledgePointIds = Result.isSuccess(courseOutlineResult)
        ? courseOutlineResult.value.knowledgePoints
            .filter(
              (point) =>
                point.chapter_id && selectedChapterIds.has(point.chapter_id),
            )
            .map((point) => point.id)
        : []

      const generationInput: GenerateResourcePackageInput = {
        projectId,
        target_topic: instructions,
        title: buildGeneratedTitle(actionLabel, instructions),
        chapter_ids: Array.from(selectedChapterIds),
        knowledge_point_ids: knowledgePointIds,
        resource_types: [toResourcePackageType(selectedType)],
        difficulty_level: toDifficultyLevel(difficulty),
        custom_instructions: instructions,
        generation_params: {
          launch_context: 'project overview ai content',
          quiz_count: selectedType === 'quiz' ? 10 : undefined,
          flashcard_count: selectedType === 'flashcard' ? 30 : undefined,
          preferred_length: selectedType === 'flashcard' ? length : undefined,
        },
      }
      setIsGenerating(false)
      close()
      await navigate({
        to: '/dashboard/p/$projectId/resource-packages',
        params: { projectId },
      })
      void generateResourcePackage(generationInput).catch((error) => {
        console.error('Generation failed:', error)
      })

      if (selectedChapterIds.size > 0) {
        toast.info('已将所选章节及其知识点作为统一资源生成链路的上下文。')
      }
      toast.success(`${actionLabel} 已提交到统一多 Agent 生成链路。`)

      setTimeout(() => {
        handleClose()
      }, 500)
    } catch (error) {
      console.error('Generation failed:', error)
      toast.error(
        error instanceof Error ? error.message : '生成失败，请稍后重试。',
      )
    } finally {
      setIsGenerating(false)
    }
  }

  const handleClose = () => {
    if (isGenerating) return
    close()
    setCustomInstructions('')
    setSelectedChapterIds(new Set())
    setSelectedType('note')
    setLength('normal')
    setDifficulty('medium')
  }

  const hasSelectedChapters = selectedChapterIds.size > 0
  const allChaptersSelected =
    Result.isSuccess(courseOutlineResult) &&
    courseOutlineResult.value.chapters.length > 0 &&
    selectedChapterIds.size === courseOutlineResult.value.chapters.length

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
              : selectedType === 'image'
                ? 'AI 图片'
                : selectedType === 'pptx'
                  ? 'PPT'
                  : selectedType === 'programming_questions'
                    ? '编程练习'
                    : '视频推荐'

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && handleClose()}>
      <DialogContent className="sm:max-w-[600px] max-h-[85vh] flex flex-col overflow-hidden">
        <DialogHeader className="shrink-0">
          <DialogTitle>生成 AI 内容</DialogTitle>
          <DialogDescription>
            这里会统一走资源包与多 Agent
            编排链路，再按你选择的资源类型落到具体资源。
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4 flex-1 min-h-0 overflow-hidden">
          <div className="space-y-2 shrink-0">
            <Label>资源类型</Label>
            <div className="grid grid-cols-3 gap-2">
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
                variant={selectedType === 'image' ? 'default' : 'outline'}
                onClick={() => setSelectedType('image')}
                disabled={isGenerating}
              >
                AI 图片
              </Button>
              <Button
                type="button"
                variant={selectedType === 'pptx' ? 'default' : 'outline'}
                onClick={() => setSelectedType('pptx')}
                disabled={isGenerating}
              >
                PPT
              </Button>
              <Button
                type="button"
                variant={
                  selectedType === 'programming_questions'
                    ? 'default'
                    : 'outline'
                }
                onClick={() => setSelectedType('programming_questions')}
                disabled={isGenerating}
              >
                编程练习
              </Button>
              <Button
                type="button"
                variant={
                  selectedType === 'video_recommendations'
                    ? 'default'
                    : 'outline'
                }
                onClick={() => setSelectedType('video_recommendations')}
                disabled={isGenerating}
              >
                视频推荐
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
              <Label>选择课程章节</Label>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={handleSelectAll}
                  disabled={
                    isGenerating ||
                    !Result.isSuccess(courseOutlineResult) ||
                    courseOutlineResult.value.chapters.length === 0 ||
                    allChaptersSelected
                  }
                >
                  全选
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={handleDeselectAll}
                  disabled={isGenerating || !hasSelectedChapters}
                >
                  取消全选
                </Button>
              </div>
            </div>

            <div className="flex-1 min-h-0 border rounded-md overflow-hidden flex flex-col">
              <div className="flex-1 overflow-y-auto p-4">
                {Result.builder(courseOutlineResult)
                  .onInitialOrWaiting(() => (
                    <div className="flex items-center gap-2 text-muted-foreground py-4">
                      <Loader2Icon className="size-4 animate-spin" />
                      <span>正在加载课程章节...</span>
                    </div>
                  ))
                  .onFailure(() => (
                    <div className="text-destructive py-4">
                      课程章节加载失败
                    </div>
                  ))
                  .onSuccess((outline) => {
                    if (!outline.courseId) {
                      return (
                        <div className="text-muted-foreground py-4 text-center">
                          当前项目尚未绑定课程，请先编辑项目并选择所属课程。
                        </div>
                      )
                    }
                    if (outline.chapters.length === 0) {
                      return (
                        <div className="text-muted-foreground py-4 text-center">
                          当前课程暂无可选章节。
                        </div>
                      )
                    }

                    return (
                      <div className="space-y-3">
                        {outline.chapters.map((chapter) => (
                          <ChapterCheckbox
                            key={chapter.id}
                            chapter={chapter}
                            knowledgePointCount={
                              outline.knowledgePoints.filter(
                                (point) => point.chapter_id === chapter.id,
                              ).length
                            }
                            checked={selectedChapterIds.has(chapter.id)}
                            onCheckedChange={() =>
                              handleToggleChapter(chapter.id)
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

function buildGeneratedTitle(
  resourceLabel: string,
  instructions: string,
): string {
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
    case 'image':
      return 'image'
    case 'pptx':
      return 'pptx'
    case 'programming_questions':
      return 'programming_questions'
    case 'video_recommendations':
      return 'video_recommendations'
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

type ChapterCheckboxProps = {
  chapter: CourseChapter
  knowledgePointCount: number
  checked: boolean
  onCheckedChange: (checked: boolean) => void
  disabled?: boolean
}

function ChapterCheckbox({
  chapter,
  knowledgePointCount,
  checked,
  onCheckedChange,
  disabled,
}: ChapterCheckboxProps) {
  return (
    <div className="flex items-center gap-3 p-2 rounded-md hover:bg-muted/50">
      <Checkbox
        checked={checked}
        onCheckedChange={onCheckedChange}
        disabled={disabled}
        id={`chapter-${chapter.id}`}
      />
      <Label
        htmlFor={`chapter-${chapter.id}`}
        className="flex-1 cursor-pointer font-normal"
      >
        <div className="flex flex-col">
          <span className="text-sm">{chapter.title}</span>
          <span className="text-xs text-muted-foreground">
            {knowledgePointCount} 个知识点
            {chapter.estimated_minutes
              ? ` · 预计 ${chapter.estimated_minutes} 分钟`
              : ''}
          </span>
        </div>
      </Label>
    </div>
  )
}
