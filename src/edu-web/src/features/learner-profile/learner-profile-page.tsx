import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { ProjectHeader } from '@/features/project/components/project-header'

type LearnerMetric = {
  label: string
  value: number
  description: string
  colorClass: string
}

const learnerMetrics: Array<LearnerMetric> = [
  {
    label: '知识理解',
    value: 82,
    description: '基础概念掌握较稳定，能够复述核心知识点。',
    colorClass: 'bg-sky-500',
  },
  {
    label: '练习完成度',
    value: 74,
    description: '能够持续完成训练，但复杂题型仍有提升空间。',
    colorClass: 'bg-emerald-500',
  },
  {
    label: '应用能力',
    value: 68,
    description: '在真实场景中迁移知识时还需要更多案例支持。',
    colorClass: 'bg-amber-500',
  },
  {
    label: '表达清晰度',
    value: 77,
    description: '能较清楚地描述思路，汇报结构还有优化空间。',
    colorClass: 'bg-rose-500',
  },
  {
    label: '学习主动性',
    value: 86,
    description: '主动探索意愿较强，愿意反复尝试新的学习方式。',
    colorClass: 'bg-violet-500',
  },
]

const summaryTags = ['理解型学习者', '适合图示辅助', '需要案例巩固', '节奏稳定']

export const LearnerProfilePage = ({ projectId }: { projectId: string }) => {
  return (
    <div className="flex h-full flex-col max-h-screen">
      <ProjectHeader projectId={projectId} />

      <div className="flex flex-1 flex-col min-h-0 overflow-y-auto">
        <div className="container mx-auto flex max-w-6xl flex-1 flex-col gap-6 px-4 py-6">
          <section className="rounded-[28px] border bg-gradient-to-br from-slate-50 via-white to-amber-50 p-6 shadow-sm">
            <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
              <div className="flex items-center gap-4">
                <Avatar className="size-20 border-4 border-white shadow-md">
                  <AvatarFallback className="bg-slate-900 text-xl font-semibold text-white">
                    学生
                  </AvatarFallback>
                </Avatar>

                <div className="space-y-2">
                  <div>
                    <h1 className="text-2xl font-semibold tracking-tight">
                      学生画像
                    </h1>
                    <p className="text-sm text-muted-foreground">
                      汇总当前项目中的学习表现、能力倾向与内容偏好。
                    </p>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    {summaryTags.map((tag) => (
                      <Badge
                        key={tag}
                        variant="secondary"
                        className="rounded-full px-3 py-1"
                      >
                        {tag}
                      </Badge>
                    ))}
                  </div>
                </div>
              </div>

              <div className="rounded-2xl border bg-white/80 px-4 py-3 text-sm text-muted-foreground">
                当前项目画像
                <div className="mt-1 text-lg font-semibold text-foreground">
                  视觉化学习偏好明显
                </div>
              </div>
            </div>
          </section>

          <section className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
            <div className="rounded-[24px] border bg-background p-6 shadow-sm">
              <div className="mb-5">
                <h2 className="text-lg font-semibold">画像条形图</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  用条形图展示当前学生在各项能力维度上的相对水平。
                </p>
              </div>

              <div className="space-y-5">
                {learnerMetrics.map((metric) => (
                  <div key={metric.label} className="space-y-2">
                    <div className="flex items-end justify-between gap-4">
                      <div>
                        <div className="text-sm font-medium">{metric.label}</div>
                        <div className="text-xs text-muted-foreground">
                          {metric.description}
                        </div>
                      </div>
                      <div className="text-sm font-semibold">{metric.value}%</div>
                    </div>

                    <div className="h-4 rounded-full bg-muted/70">
                      <div
                        className={`h-4 rounded-full ${metric.colorClass} transition-all`}
                        style={{ width: `${metric.value}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-6">
              <section className="rounded-[24px] border bg-background p-6 shadow-sm">
                <h2 className="text-lg font-semibold">画像解读</h2>
                <div className="mt-4 space-y-3 text-sm leading-6 text-muted-foreground">
                  <p>
                    学生在知识理解和学习主动性上表现突出，说明其更适合先建立整体框架，再进入细节拆解。
                  </p>
                  <p>
                    应用能力相对较弱，建议在资源包中优先增加案例推演、代码实操和分层练习题。
                  </p>
                  <p>
                    由于表达清晰度中上，后续可以加入 PPT 大纲、讲解文档等内容，帮助其把理解进一步外化。
                  </p>
                </div>
              </section>

              <section className="rounded-[24px] border bg-background p-6 shadow-sm">
                <h2 className="text-lg font-semibold">推荐关注点</h2>
                <div className="mt-4 space-y-3">
                  <div className="rounded-2xl bg-muted/40 p-4">
                    <div className="text-sm font-medium">优先补强</div>
                    <div className="mt-1 text-sm text-muted-foreground">
                      场景应用、综合练习、从概念到解题的迁移过程。
                    </div>
                  </div>
                  <div className="rounded-2xl bg-muted/40 p-4">
                    <div className="text-sm font-medium">推荐资源形式</div>
                    <div className="mt-1 text-sm text-muted-foreground">
                      思维导图、讲解文档、PPT 大纲、分层练习题。
                    </div>
                  </div>
                  <div className="rounded-2xl bg-muted/40 p-4">
                    <div className="text-sm font-medium">学习节奏建议</div>
                    <div className="mt-1 text-sm text-muted-foreground">
                      先看结构图，再做例题，最后通过讲解输出进行巩固。
                    </div>
                  </div>
                </div>
              </section>
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}
