import { useMemo, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { ProjectHeader } from '@/features/project/components/project-header'
import { cn } from '@/lib/utils'

type QuestionOption = {
  id: string
  label: string
}

type EvaluationDimension =
  | '知识理解'
  | '迁移应用'
  | '分析判断'
  | '表达组织'

type PracticeQuestion = {
  id: string
  dimension: EvaluationDimension
  prompt: string
  options: Array<QuestionOption>
  correctOptionId: string
  explanation: string
}

type EvaluationMetric = {
  label: EvaluationDimension
  score: number
  summary: string
  colorClass: string
}

const practiceQuestions: Array<PracticeQuestion> = [
  {
    id: 'q1',
    dimension: '知识理解',
    prompt: '梯度下降中，学习率过大最常见的直接结果是什么？',
    options: [
      { id: 'a', label: '模型一定更快收敛到最优解' },
      { id: 'b', label: '参数更新可能震荡甚至无法收敛' },
      { id: 'c', label: '损失函数会自动变成凸函数' },
      { id: 'd', label: '训练集样本数量会自动增加' },
    ],
    correctOptionId: 'b',
    explanation:
      '学习率过大通常会让参数在最优点附近来回震荡，严重时会直接发散。',
  },
  {
    id: 'q2',
    dimension: '迁移应用',
    prompt: '当一个特征量纲远大于其他特征时，优先考虑的处理方式是什么？',
    options: [
      { id: 'a', label: '直接删除该特征' },
      { id: 'b', label: '增加更多同量纲特征' },
      { id: 'c', label: '进行归一化或标准化处理' },
      { id: 'd', label: '只保留这一列数据' },
    ],
    correctOptionId: 'c',
    explanation:
      '归一化或标准化可以避免不同量纲的特征对优化过程产生不合理影响。',
  },
  {
    id: 'q3',
    dimension: '分析判断',
    prompt: '如果训练误差很低、验证误差很高，最可能说明什么？',
    options: [
      { id: 'a', label: '模型欠拟合' },
      { id: 'b', label: '模型过拟合' },
      { id: 'c', label: '数据已经线性可分' },
      { id: 'd', label: '学习率一定过低' },
    ],
    correctOptionId: 'b',
    explanation: '训练误差低但验证误差高通常是过拟合的典型信号。',
  },
  {
    id: 'q4',
    dimension: '表达组织',
    prompt: '在向同学讲解逻辑回归时，最合理的表达顺序是什么？',
    options: [
      { id: 'a', label: '先给代码，再讲结论，最后说明任务目标' },
      { id: 'b', label: '先说明任务目标，再介绍核心公式和输出含义' },
      { id: 'c', label: '只讲损失函数，不解释分类边界' },
      { id: 'd', label: '直接给最终准确率即可' },
    ],
    correctOptionId: 'b',
    explanation:
      '面向学习者的讲解应先建立任务背景，再进入模型机制和结果解释。',
  },
]

const metricColorMap: Record<EvaluationMetric['label'], string> = {
  知识理解: 'bg-sky-500',
  迁移应用: 'bg-emerald-500',
  分析判断: 'bg-amber-500',
  表达组织: 'bg-rose-500',
}

const metricSummaryMap: Record<EvaluationMetric['label'], string> = {
  知识理解: '概念辨析和基础原理的掌握情况。',
  迁移应用: '把知识用到新场景中的能力。',
  分析判断: '基于现象定位问题和判断原因的能力。',
  表达组织: '把思路清楚讲出来、组织成结构化答案的能力。',
}

export const LearningEvaluationPage = ({
  projectId,
}: {
  projectId: string
}) => {
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [submitted, setSubmitted] = useState(false)
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0)

  const answeredCount = Object.keys(answers).length
  const progress = (answeredCount / practiceQuestions.length) * 100
  const currentQuestion = practiceQuestions[currentQuestionIndex]
  const selectedCurrentOption = answers[currentQuestion.id]
  const isLastQuestion = currentQuestionIndex === practiceQuestions.length - 1
  const currentQuestionCorrect =
    selectedCurrentOption === currentQuestion.correctOptionId

  const evaluation = useMemo(() => {
    if (!submitted) return null

    const correctCount = practiceQuestions.filter(
      (question) => answers[question.id] === question.correctOptionId,
    ).length

    const metrics = Array.from(
      practiceQuestions.reduce((map, question) => {
        const current = map.get(question.dimension) ?? { total: 0, correct: 0 }
        current.total += 1
        if (answers[question.id] === question.correctOptionId) {
          current.correct += 1
        }
        map.set(question.dimension, current)
        return map
      }, new Map<EvaluationMetric['label'], { total: number; correct: number }>()),
    ).map(([label, value]) => ({
      label,
      score: Math.round((value.correct / value.total) * 100),
      summary: metricSummaryMap[label],
      colorClass: metricColorMap[label],
    }))

    return {
      correctCount,
      total: practiceQuestions.length,
      overallScore: Math.round((correctCount / practiceQuestions.length) * 100),
      metrics,
    }
  }, [answers, submitted])

  const handleSelect = (questionId: string, optionId: string) => {
    setAnswers((current) => ({
      ...current,
      [questionId]: optionId,
    }))
  }

  const handleSubmit = () => {
    if (answeredCount !== practiceQuestions.length) return
    setSubmitted(true)
  }

  const handleReset = () => {
    setAnswers({})
    setSubmitted(false)
    setCurrentQuestionIndex(0)
  }

  const handlePreviousQuestion = () => {
    setCurrentQuestionIndex((current) => Math.max(current - 1, 0))
  }

  const handleNextQuestion = () => {
    setCurrentQuestionIndex((current) =>
      Math.min(current + 1, practiceQuestions.length - 1),
    )
  }

  return (
    <div className="flex h-full max-h-screen flex-col">
      <ProjectHeader projectId={projectId} />

      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
        <div className="container mx-auto flex max-w-7xl flex-1 flex-col gap-6 px-4 py-6">
          <section className="rounded-[28px] border bg-gradient-to-br from-cyan-50 via-white to-lime-50 p-6 shadow-sm">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div className="space-y-3">
                <div>
                  <h1 className="text-2xl font-semibold tracking-tight">
                    学习效果评估
                  </h1>
                  <p className="mt-1 text-sm text-muted-foreground">
                    通过练习测试快速评估当前项目中的掌握情况、迁移能力与讲解表达能力。
                  </p>
                </div>

                <div className="flex flex-wrap gap-2">
                  <Badge variant="secondary" className="rounded-full px-3 py-1">
                    前端原型页
                  </Badge>
                  <Badge variant="secondary" className="rounded-full px-3 py-1">
                    练习测试
                  </Badge>
                  <Badge variant="secondary" className="rounded-full px-3 py-1">
                    自动评分
                  </Badge>
                </div>
              </div>

              <div className="min-w-[260px] rounded-2xl border bg-white/85 px-4 py-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">作答进度</span>
                  <span className="font-medium">
                    {answeredCount}/{practiceQuestions.length}
                  </span>
                </div>
                <Progress value={progress} className="mt-3 h-3" />
              </div>
            </div>
          </section>

          <section className="grid gap-6 lg:grid-cols-[1.05fr_0.95fr]">
            <div className="space-y-6">
              <Card className="rounded-[24px]">
                <CardHeader>
                  <CardTitle>练习测试</CardTitle>
                  <CardDescription>
                    当前先用前端静态题目完成测试，后续可接项目题库和知识点。
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="rounded-2xl border p-5">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="outline">
                          第 {currentQuestionIndex + 1} 题
                        </Badge>
                        <Badge variant="secondary">
                          {currentQuestion.dimension}
                        </Badge>
                      </div>
                      <div className="text-sm text-muted-foreground">
                        {currentQuestionIndex + 1} / {practiceQuestions.length}
                      </div>
                    </div>

                    <div className="mt-3 text-sm font-medium leading-6">
                      {currentQuestion.prompt}
                    </div>

                    <div className="mt-4 grid gap-3">
                      {currentQuestion.options.map((option) => {
                        const active = selectedCurrentOption === option.id
                        const showResult = submitted && active

                        return (
                          <button
                            key={option.id}
                            type="button"
                            onClick={() =>
                              handleSelect(currentQuestion.id, option.id)
                            }
                            className={cn(
                              'rounded-xl border px-4 py-3 text-left text-sm transition-colors',
                              active
                                ? 'border-primary bg-primary/6'
                                : 'hover:bg-muted/40',
                              showResult &&
                                (currentQuestionCorrect
                                  ? 'border-emerald-500 bg-emerald-50'
                                  : 'border-rose-500 bg-rose-50'),
                            )}
                          >
                            <span className="font-medium">
                              {option.id.toUpperCase()}.
                            </span>{' '}
                            {option.label}
                          </button>
                        )
                      })}
                    </div>

                    {submitted ? (
                      <div className="mt-4 rounded-xl bg-muted/40 p-4 text-sm text-muted-foreground">
                        <div className="font-medium text-foreground">
                          {currentQuestionCorrect ? '回答正确' : '回答有误'}
                        </div>
                        <div className="mt-1">{currentQuestion.explanation}</div>
                      </div>
                    ) : null}
                  </div>

                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <Button variant="outline" onClick={handleReset}>
                      重新开始
                    </Button>

                    <div className="flex flex-wrap items-center gap-3">
                      <Button
                        variant="outline"
                        onClick={handlePreviousQuestion}
                        disabled={currentQuestionIndex === 0}
                      >
                        上一题
                      </Button>

                      {isLastQuestion ? (
                        <Button
                          onClick={handleSubmit}
                          disabled={answeredCount !== practiceQuestions.length}
                        >
                          提交并评估
                        </Button>
                      ) : (
                        <Button
                          onClick={handleNextQuestion}
                          disabled={!selectedCurrentOption}
                        >
                          下一题
                        </Button>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            <div className="space-y-6">
              <Card className="rounded-[24px]">
                <CardHeader>
                  <CardTitle>评估结果</CardTitle>
                  <CardDescription>
                    提交后展示整体成绩与分维度表现。
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {evaluation ? (
                    <div className="space-y-6">
                      <div className="rounded-2xl border bg-muted/30 p-5">
                        <div className="text-sm text-muted-foreground">
                          总评得分
                        </div>
                        <div className="mt-2 text-4xl font-semibold">
                          {evaluation.overallScore}
                          <span className="ml-1 text-xl text-muted-foreground">
                            分
                          </span>
                        </div>
                        <div className="mt-2 text-sm text-muted-foreground">
                          共答对 {evaluation.correctCount} / {evaluation.total} 题
                        </div>
                      </div>

                      <div className="space-y-4">
                        {evaluation.metrics.map((metric) => (
                          <div key={metric.label} className="space-y-2">
                            <div className="flex items-end justify-between gap-4">
                              <div>
                                <div className="text-sm font-medium">
                                  {metric.label}
                                </div>
                                <div className="text-xs text-muted-foreground">
                                  {metric.summary}
                                </div>
                              </div>
                              <div className="text-sm font-semibold">
                                {metric.score}%
                              </div>
                            </div>

                            <div className="h-4 rounded-full bg-muted/70">
                              <div
                                className={`h-4 rounded-full ${metric.colorClass}`}
                                style={{ width: `${metric.score}%` }}
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <div className="rounded-2xl border border-dashed p-5 text-sm text-muted-foreground">
                      完成练习测试后，这里会展示总分、维度得分和学习效果分析。
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card className="rounded-[24px]">
                <CardHeader>
                  <CardTitle>评估说明</CardTitle>
                  <CardDescription>
                    当前版本先验证页面流程，不依赖新增后端接口。
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                  <p>
                    1. 题目数据目前放在前端静态配置中，便于先完成交互与评估展示。
                  </p>
                  <p>
                    2. 分数先按答对题数和题目维度做简单计算，后续可以接知识点加权策略。
                  </p>
                  <p>
                    3. 结果当前只在前端展示，没有写回练习记录、诊断记录或评估报告。
                  </p>
                </CardContent>
              </Card>
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}
