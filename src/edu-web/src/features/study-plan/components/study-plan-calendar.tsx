import {
  addDays,
  addMonths,
  eachDayOfInterval,
  endOfMonth,
  endOfWeek,
  format,
  isSameDay,
  isSameMonth,
  isToday,
  startOfMonth,
  startOfWeek,
  subMonths,
} from 'date-fns'
import { zhCN } from 'date-fns/locale'
import { CalendarDays, ChevronLeft, ChevronRight, Clock3 } from 'lucide-react'
import { useMemo, useState } from 'react'
import type { CustomStudyPlanEntry } from '../custom-study-plan'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'

type AiScheduleDay = {
  day: string
  tasks: Array<string>
}

type StudyPlanCalendarProps = {
  generatedAt: string
  schedule: Array<AiScheduleDay>
  customEntries: Array<CustomStudyPlanEntry>
}

const weekDays = ['一', '二', '三', '四', '五', '六', '日']

export const StudyPlanCalendar = ({
  generatedAt,
  schedule,
  customEntries,
}: StudyPlanCalendarProps) => {
  const today = useMemo(() => new Date(), [])
  const [selectedDate, setSelectedDate] = useState(today)
  const [visibleMonth, setVisibleMonth] = useState(startOfMonth(today))

  const generatedStartDate = useMemo(() => {
    const parsed = new Date(generatedAt)
    return Number.isNaN(parsed.getTime()) ? today : parsed
  }, [generatedAt, today])

  const aiPlansByDate = useMemo(() => {
    const plans = new Map<string, AiScheduleDay>()
    schedule.forEach((item, index) => {
      plans.set(format(addDays(generatedStartDate, index), 'yyyy-MM-dd'), item)
    })
    return plans
  }, [generatedStartDate, schedule])

  const customPlansByDate = useMemo(
    () =>
      new Map(
        customEntries
          .filter((entry) =>
            [
              entry.topic,
              entry.task,
              entry.startTime,
              entry.duration,
              entry.goal,
            ].some((value) => value.trim()),
          )
          .map((entry) => [entry.date, entry]),
      ),
    [customEntries],
  )

  const calendarDays = useMemo(
    () =>
      eachDayOfInterval({
        start: startOfWeek(startOfMonth(visibleMonth), { weekStartsOn: 1 }),
        end: endOfWeek(endOfMonth(visibleMonth), { weekStartsOn: 1 }),
      }),
    [visibleMonth],
  )

  const selectedKey = format(selectedDate, 'yyyy-MM-dd')
  const selectedAiPlan = aiPlansByDate.get(selectedKey)
  const selectedCustomPlan = customPlansByDate.get(selectedKey)

  const selectDate = (date: Date) => {
    setSelectedDate(date)
    if (!isSameMonth(date, visibleMonth)) {
      setVisibleMonth(startOfMonth(date))
    }
  }

  return (
    <Card className="overflow-hidden border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-card">
      <CardHeader className="border-b bg-gradient-to-r from-[#eaf2f9] via-[#f4f8fb] to-white pb-4 dark:from-[#172b40] dark:via-[#142438] dark:to-card">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2 text-lg">
            <CalendarDays className="size-5 text-[#1f5b8f] dark:text-sky-300" />
            学习日历
          </CardTitle>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="size-8"
              onClick={() => setVisibleMonth((month) => subMonths(month, 1))}
              aria-label="上个月"
            >
              <ChevronLeft className="size-4" />
            </Button>
            <span className="min-w-24 rounded-md border border-[#c9d9e7] bg-white/75 px-2 py-1 text-center text-sm font-semibold text-[#173a5e] dark:border-slate-600 dark:bg-slate-900/40 dark:text-slate-100">
              {format(visibleMonth, 'yyyy年 M月', { locale: zhCN })}
            </span>
            <Button
              variant="ghost"
              size="icon"
              className="size-8"
              onClick={() => setVisibleMonth((month) => addMonths(month, 1))}
              aria-label="下个月"
            >
              <ChevronRight className="size-4" />
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-4">
        <div className="grid grid-cols-7 border-l border-t border-slate-200 text-center text-xs dark:border-slate-700">
          {weekDays.map((day, index) => (
            <div
              key={day}
              className={cn(
                'border-b border-r border-slate-200 bg-[#edf3f8] py-2 font-medium text-slate-600 dark:border-slate-700 dark:bg-slate-800/70 dark:text-slate-300',
                index >= 5 &&
                  '!bg-amber-50 text-amber-700 dark:!bg-amber-950/25 dark:text-amber-300',
              )}
            >
              {day}
            </div>
          ))}
          {calendarDays.map((date) => {
            const key = format(date, 'yyyy-MM-dd')
            const hasAiPlan = aiPlansByDate.has(key)
            const hasCustomPlan = customPlansByDate.has(key)
            const isSelected = isSameDay(date, selectedDate)
            const isCurrentDay = isToday(date)
            const isWeekend = date.getDay() === 0 || date.getDay() === 6

            return (
              <button
                key={key}
                type="button"
                onClick={() => selectDate(date)}
                className={cn(
                  'relative flex aspect-square min-h-10 items-center justify-center border-b border-r border-slate-200 bg-white text-sm transition-colors hover:bg-sky-50 dark:border-slate-700 dark:bg-card dark:hover:bg-slate-800',
                  isWeekend &&
                    '!bg-amber-50/40 text-amber-800 dark:!bg-amber-950/10 dark:text-amber-200',
                  !isSameMonth(date, visibleMonth) &&
                    '!bg-slate-50/60 text-muted-foreground/35 dark:!bg-slate-900/30',
                  isCurrentDay &&
                    !isSelected &&
                    'font-semibold text-sky-700 ring-1 ring-inset ring-sky-400 dark:text-sky-300',
                  isSelected &&
                    '!bg-[#1f5b8f] font-semibold !text-white hover:!bg-[#194d79] dark:!bg-sky-700 dark:hover:!bg-sky-700',
                )}
                aria-label={format(date, 'yyyy年M月d日', { locale: zhCN })}
              >
                {format(date, 'd')}
                {(hasAiPlan || hasCustomPlan) && (
                  <span className="absolute bottom-1.5 flex items-center gap-1">
                    {hasAiPlan && (
                      <span
                        className={cn(
                          'size-1.5 rounded-full bg-sky-500',
                          isSelected && 'bg-sky-100',
                        )}
                      />
                    )}
                    {hasCustomPlan && (
                      <span
                        className={cn(
                          'size-1.5 rounded-full bg-amber-500',
                          isSelected && 'bg-amber-300',
                        )}
                      />
                    )}
                  </span>
                )}
              </button>
            )
          })}
        </div>

        <div className="mt-5 border-t pt-4">
          <div className="mb-3 flex items-center justify-between gap-2">
            <div>
              <p className="font-semibold">
                {format(selectedDate, 'M月d日 EEEE', { locale: zhCN })}
              </p>
              <p className="text-xs text-muted-foreground">当日学习计划</p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="h-8"
              onClick={() => {
                setSelectedDate(today)
                setVisibleMonth(startOfMonth(today))
              }}
            >
              回到今天
            </Button>
          </div>

          {selectedCustomPlan && (
            <div className="mb-3 border-l-2 border-amber-500 bg-amber-500/5 px-3 py-2.5">
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-semibold">
                  {selectedCustomPlan.topic || '自定义学习'}
                </p>
                <span className="text-xs text-amber-700 dark:text-amber-300">
                  自定义
                </span>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                {selectedCustomPlan.task || '暂未填写具体任务'}
              </p>
              {(selectedCustomPlan.startTime ||
                selectedCustomPlan.duration) && (
                <p className="mt-2 flex items-center gap-1 text-xs text-muted-foreground">
                  <Clock3 className="size-3.5" />
                  {selectedCustomPlan.startTime || '时间待定'}
                  {selectedCustomPlan.duration &&
                    ` · ${selectedCustomPlan.duration} 分钟`}
                </p>
              )}
              {selectedCustomPlan.goal && (
                <p className="mt-2 text-xs">目标：{selectedCustomPlan.goal}</p>
              )}
            </div>
          )}

          {selectedAiPlan && (
            <div className="border-l-2 border-sky-600 bg-sky-50 px-3 py-2.5 dark:border-sky-400 dark:bg-sky-950/25">
              <p className="text-sm font-semibold">
                {selectedAiPlan.day || 'AI 推荐计划'}
              </p>
              <ul className="mt-1 space-y-1 text-sm text-muted-foreground">
                {selectedAiPlan.tasks.map((task) => (
                  <li key={task}>· {task}</li>
                ))}
              </ul>
            </div>
          )}

          {!selectedCustomPlan && !selectedAiPlan && (
            <div className="border border-dashed px-3 py-6 text-center text-sm text-muted-foreground">
              这一天还没有学习安排
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
