import { useState } from 'react'
import {
  ArrowDownIcon,
  ArrowUpIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  TrashIcon,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { cn, truncate } from '@/lib/utils'

type QuizQuestionEditorProps = {
  question: {
    id: string
    question_text: string
    option_a: string
    option_b: string
    option_c: string
    option_d: string
    correct_option: string
    explanation?: string | null
    difficulty_level: string
    position: number
  }
  onQuestionTextChange: (value: string) => void
  onOptionAChange: (value: string) => void
  onOptionBChange: (value: string) => void
  onOptionCChange: (value: string) => void
  onOptionDChange: (value: string) => void
  onCorrectOptionChange: (value: string) => void
  onExplanationChange: (value: string) => void
  onDifficultyChange: (value: string) => void
  onDelete: () => void
  onMoveUp: () => void
  onMoveDown: () => void
  canMoveUp: boolean
  canMoveDown: boolean
  isDeleted?: boolean
}

export const QuizQuestionEditor = ({
  question,
  onQuestionTextChange,
  onOptionAChange,
  onOptionBChange,
  onOptionCChange,
  onOptionDChange,
  onCorrectOptionChange,
  onExplanationChange,
  onDifficultyChange,
  onDelete,
  onMoveUp,
  onMoveDown,
  canMoveUp,
  canMoveDown,
  isDeleted = false,
}: QuizQuestionEditorProps) => {
  const [isOpen, setIsOpen] = useState(false)

  if (isDeleted) {
    return (
      <Card className="opacity-50 border-dashed">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">
                第 {question.position + 1} 题（已删除）
              </span>
            </div>
          </div>
        </CardHeader>
      </Card>
    )
  }

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <Card className="hover:shadow-md transition-shadow gap-0">
        <CollapsibleTrigger asChild>
          <CardHeader className="cursor-pointer hover:bg-muted/50 transition-colors pt-2">
            <div className="flex items-center justify-between w-full">
              <div className="flex items-center gap-3 flex-1 min-w-0">
                {isOpen ? (
                  <ChevronUpIcon className="h-4 w-4 text-muted-foreground shrink-0" />
                ) : (
                  <ChevronDownIcon className="h-4 w-4 text-muted-foreground shrink-0" />
                )}
                <span className="text-sm text-muted-foreground shrink-0">
                  第 {question.position + 1} 题
                </span>
                {!isOpen && question.question_text && (
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span className="text-sm text-foreground truncate ml-2 block">
                        {truncate(question.question_text, 120)}
                      </span>
                    </TooltipTrigger>
                    <TooltipContent
                      side="bottom"
                      align="start"
                      className="max-w-md"
                    >
                      <p className="whitespace-normal break-words">
                        {question.question_text}
                      </p>
                    </TooltipContent>
                  </Tooltip>
                )}
              </div>
              <div
                className="flex items-center gap-2 shrink-0"
                onClick={(e) => e.stopPropagation()}
              >
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onMoveUp}
                  disabled={!canMoveUp}
                  title="上移"
                >
                  <ArrowUpIcon className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onMoveDown}
                  disabled={!canMoveDown}
                  title="下移"
                >
                  <ArrowDownIcon className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onDelete}
                  title="删除"
                >
                  <TrashIcon className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </CardHeader>
        </CollapsibleTrigger>
        <CollapsibleContent
          className={cn(
            'overflow-hidden',
            'data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:slide-out-to-top-2',
            'data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:slide-in-from-top-2',
            'transition-all duration-300 ease-in-out',
          )}
        >
          <CardContent className="space-y-4 pt-0">
            <div className="space-y-2">
              <label className="text-sm font-medium">题目</label>
              <Textarea
                value={question.question_text}
                onChange={(e) => onQuestionTextChange(e.target.value)}
                placeholder="请输入题目..."
                className="min-h-20"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">选项 A</label>
                <Input
                  value={question.option_a}
                  onChange={(e) => onOptionAChange(e.target.value)}
                  placeholder="选项 A"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">选项 B</label>
                <Input
                  value={question.option_b}
                  onChange={(e) => onOptionBChange(e.target.value)}
                  placeholder="选项 B"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">选项 C</label>
                <Input
                  value={question.option_c}
                  onChange={(e) => onOptionCChange(e.target.value)}
                  placeholder="选项 C"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">选项 D</label>
                <Input
                  value={question.option_d}
                  onChange={(e) => onOptionDChange(e.target.value)}
                  placeholder="选项 D"
                />
              </div>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">正确选项</label>
              <Select
                value={question.correct_option}
                onValueChange={onCorrectOptionChange}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="a">A</SelectItem>
                  <SelectItem value="b">B</SelectItem>
                  <SelectItem value="c">C</SelectItem>
                  <SelectItem value="d">D</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">
                解析（可选）
              </label>
              <Textarea
                value={question.explanation || ''}
                onChange={(e) => onExplanationChange(e.target.value)}
                placeholder="请输入解析..."
                className="min-h-20"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">难度</label>
              <Select
                value={question.difficulty_level}
                onValueChange={onDifficultyChange}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="easy">简单</SelectItem>
                  <SelectItem value="medium">中等</SelectItem>
                  <SelectItem value="hard">困难</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  )
}
