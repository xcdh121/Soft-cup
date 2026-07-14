import { Result, useAtomValue } from '@effect-atom/atom-react'
import { Link } from '@tanstack/react-router'
import { addDays, format } from 'date-fns'
import { zhCN } from 'date-fns/locale'
import {
  ArrowLeft,
  CalendarRange,
  CheckCircle2,
  Lightbulb,
  Save,
  Target,
} from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { StudyPlanHeader } from './components/study-plan-header'
import { loadCustomStudyPlan, saveCustomStudyPlan } from './custom-study-plan'
import type { CustomStudyPlanEntry } from './custom-study-plan'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { latestStudyPlanRemoteAtom } from '@/data-acess/study-plan'

type CustomStudyPlanPageProps = {
  projectId: string
}

const createSevenDayPlan = (
  storedEntries: Array<CustomStudyPlanEntry>,
): Array<CustomStudyPlanEntry> => {
  const storedByDate = new Map(
    storedEntries.map((entry) => [entry.date, entry]),
  )

  return Array.from({ length: 7 }, (_, index) => {
    const date = format(addDays(new Date(), index), 'yyyy-MM-dd')
    return (
      storedByDate.get(date) ?? {
        date,
        topic: '',
        task: '',
        startTime: '',
        duration: '',
        goal: '',
      }
    )
  })
}

export const CustomStudyPlanPage = ({
  projectId,
}: CustomStudyPlanPageProps) => {
  const latestPlanResult = useAtomValue(latestStudyPlanRemoteAtom(projectId))
  const weakTopics = Result.isSuccess(latestPlanResult)
    ? (latestPlanResult.value?.weak_topics ?? [])
    : []

  const [entries, setEntries] = useState(() =>
    createSevenDayPlan(loadCustomStudyPlan(projectId)),
  )

  const updateEntry = (
    index: number,
    field: keyof Omit<CustomStudyPlanEntry, 'date'>,
    value: string,
  ) => {
    setEntries((current) =>
      current.map((entry, entryIndex) =>
        entryIndex === index ? { ...entry, [field]: value } : entry,
      ),
    )
  }

  const useWeakTopic = (topic: string) => {
    const firstEmptyIndex = entries.findIndex((entry) => !entry.topic.trim())
    const targetIndex = firstEmptyIndex === -1 ? 0 : firstEmptyIndex
    updateEntry(targetIndex, 'topic', topic)
    toast.success(`已将“${topic}”添加到第 ${targetIndex + 1} 天`)
  }

  const handleSave = () => {
    saveCustomStudyPlan(projectId, entries)
    toast.success('未来 7 天学习计划已保存')
  }

  const completedDays = entries.filter(
    (entry) => entry.topic.trim() || entry.task.trim(),
  ).length

  return (
    <div className="flex h-full max-h-screen flex-col">
      <StudyPlanHeader projectId={projectId} pageTitle="自定义学习计划" />
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="container mx-auto max-w-7xl space-y-6 px-4 py-8">
          <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
            <div>
              <div className="mb-2 flex items-center gap-2 text-sm font-medium text-primary">
                <CalendarRange className="size-4" />
                未来 7 天
              </div>
              <h1 className="text-3xl font-bold tracking-tight">
                自定义学习计划
              </h1>
              <p className="mt-2 text-muted-foreground">
                把目标拆进每天的时间表，学习主题与任务均可自由填写。
              </p>
            </div>
            <div className="flex items-center gap-3">
              <div className="text-sm text-muted-foreground">
                已安排{' '}
                <span className="font-semibold text-foreground">
                  {completedDays}
                </span>{' '}
                / 7 天
              </div>
              <Button variant="outline" asChild>
                <Link
                  to="/dashboard/p/$projectId/study-plan"
                  params={{ projectId }}
                >
                  <ArrowLeft className="size-4" />
                  返回计划
                </Link>
              </Button>
              <Button onClick={handleSave}>
                <Save className="size-4" />
                保存计划
              </Button>
            </div>
          </div>

          <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_280px]">
            <div className="min-w-0 border bg-background">
              <div className="w-full overflow-hidden">
                <table className="w-full table-fixed border-collapse text-sm">
                  <colgroup>
                    <col className="w-[11%]" />
                    <col className="w-[16%]" />
                    <col className="w-[24%]" />
                    <col className="w-[13%]" />
                    <col className="w-[13%]" />
                    <col className="w-[23%]" />
                  </colgroup>
                  <thead>
                    <tr className="bg-muted/60">
                      <th className="border-b border-r px-2 py-3 text-left font-semibold">
                        日期
                      </th>
                      <th className="border-b border-r px-2 py-3 text-left font-semibold">
                        薄弱项 / 主题
                      </th>
                      <th className="border-b border-r px-2 py-3 text-left font-semibold">
                        学习任务
                      </th>
                      <th className="border-b border-r px-2 py-3 text-left font-semibold">
                        开始时间
                      </th>
                      <th className="border-b border-r px-2 py-3 text-left font-semibold">
                        预计时长
                      </th>
                      <th className="border-b px-2 py-3 text-left font-semibold">
                        当日目标
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {entries.map((entry, index) => {
                      const date = new Date(`${entry.date}T00:00:00`)
                      const isToday = index === 0

                      return (
                        <tr
                          key={entry.date}
                          className="group align-top hover:bg-muted/20"
                        >
                          <td className="border-b border-r px-2 py-3">
                            <p className="font-semibold">
                              {format(date, 'M月d日', { locale: zhCN })}
                            </p>
                            <p className="mt-1 text-xs text-muted-foreground">
                              {format(date, 'EEEE', { locale: zhCN })}
                              {isToday && (
                                <span className="ml-1 text-primary">
                                  · 今天
                                </span>
                              )}
                            </p>
                          </td>
                          <td className="border-b border-r p-0">
                            <Input
                              value={entry.topic}
                              onChange={(event) =>
                                updateEntry(index, 'topic', event.target.value)
                              }
                              placeholder="如：动态规划"
                              className="h-20 min-w-0 rounded-none border-0 bg-transparent px-2 shadow-none focus-visible:ring-2 focus-visible:ring-inset"
                              aria-label={`${entry.date} 学习主题`}
                            />
                          </td>
                          <td className="border-b border-r p-0">
                            <Textarea
                              value={entry.task}
                              onChange={(event) =>
                                updateEntry(index, 'task', event.target.value)
                              }
                              placeholder="填写资料阅读、习题练习或复习任务"
                              className="min-h-20 min-w-0 resize-none rounded-none border-0 bg-transparent px-2 py-3 shadow-none focus-visible:ring-2 focus-visible:ring-inset"
                              aria-label={`${entry.date} 学习任务`}
                            />
                          </td>
                          <td className="border-b border-r p-0">
                            <Input
                              type="time"
                              value={entry.startTime}
                              onChange={(event) =>
                                updateEntry(
                                  index,
                                  'startTime',
                                  event.target.value,
                                )
                              }
                              className="h-20 min-w-0 rounded-none border-0 bg-transparent px-2 shadow-none focus-visible:ring-2 focus-visible:ring-inset"
                              aria-label={`${entry.date} 开始时间`}
                            />
                          </td>
                          <td className="border-b border-r p-0">
                            <div className="flex h-20 min-w-0 items-center">
                              <Input
                                type="number"
                                min="0"
                                step="5"
                                value={entry.duration}
                                onChange={(event) =>
                                  updateEntry(
                                    index,
                                    'duration',
                                    event.target.value,
                                  )
                                }
                                placeholder="45"
                                className="h-20 min-w-0 rounded-none border-0 bg-transparent px-2 shadow-none focus-visible:ring-2 focus-visible:ring-inset"
                                aria-label={`${entry.date} 预计时长（分钟）`}
                              />
                              <span className="pr-2 text-xs text-muted-foreground">
                                分钟
                              </span>
                            </div>
                          </td>
                          <td className="border-b p-0">
                            <Textarea
                              value={entry.goal}
                              onChange={(event) =>
                                updateEntry(index, 'goal', event.target.value)
                              }
                              placeholder="完成后应达到什么结果"
                              className="min-h-20 min-w-0 resize-none rounded-none border-0 bg-transparent px-2 py-3 shadow-none focus-visible:ring-2 focus-visible:ring-inset"
                              aria-label={`${entry.date} 当日目标`}
                            />
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
              <div className="flex items-center justify-between border-t bg-muted/30 px-4 py-3 text-xs text-muted-foreground">
                <span>计划仅保存在当前设备，可随时回来修改。</span>
                <span>
                  {completedDays === 7
                    ? '7 天计划已完整安排'
                    : `还有 ${7 - completedDays} 天待安排`}
                </span>
              </div>
            </div>

            <aside className="space-y-4 xl:sticky xl:top-20">
              <div className="border bg-background">
                <div className="border-b px-4 py-4">
                  <h2 className="flex items-center gap-2 font-semibold">
                    <Target className="size-4 text-destructive" />
                    系统薄弱项提示
                  </h2>
                  <p className="mt-1 text-xs text-muted-foreground">
                    点击主题，可自动填入第一个空白日期。
                  </p>
                </div>
                <div className="space-y-2 p-4">
                  {weakTopics.length > 0 ? (
                    weakTopics.map((topic) => (
                      <button
                        key={topic}
                        type="button"
                        onClick={() => useWeakTopic(topic)}
                        className="flex w-full items-center justify-between border px-3 py-2.5 text-left text-sm transition-colors hover:border-primary hover:bg-primary/5"
                      >
                        <span>{topic}</span>
                        <span className="text-xs text-primary">加入计划</span>
                      </button>
                    ))
                  ) : (
                    <div className="border border-dashed px-3 py-5 text-center text-sm text-muted-foreground">
                      系统暂未识别薄弱项，你仍可自由填写学习主题。
                    </div>
                  )}
                </div>
              </div>

              <div className="border bg-muted/30 p-4">
                <h3 className="flex items-center gap-2 text-sm font-semibold">
                  <Lightbulb className="size-4 text-amber-500" />
                  填写建议
                </h3>
                <ul className="mt-3 space-y-2 text-xs leading-5 text-muted-foreground">
                  <li>· 每天优先安排 1 个薄弱主题，避免目标过多。</li>
                  <li>· 任务尽量具体，例如“完成 10 道动态规划题”。</li>
                  <li>· 用当日目标定义完成标准，便于复盘。</li>
                </ul>
              </div>

              {completedDays === 7 && (
                <div className="flex items-start gap-3 border border-emerald-500/30 bg-emerald-500/5 p-4 text-sm">
                  <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-600" />
                  <p>未来 7 天均已安排，保存后可在学习日历中逐日查看。</p>
                </div>
              )}
            </aside>
          </div>
        </div>
      </div>
    </div>
  )
}
