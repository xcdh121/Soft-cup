import { Result, useAtomValue } from '@effect-atom/atom-react'
import { Activity, BrainCircuit, Loader2, ShieldCheck } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { ktMetricSummaryAtom } from '@/data-acess/learning-closed-loop'

const decimal = (value: number | null) =>
  value == null ? '证据不足' : value.toFixed(3)

const percent = (value: number) => `${Math.round(value * 100)}%`

export const KTModelMetricsCard = ({ projectId }: { projectId: string }) => {
  const result = useAtomValue(ktMetricSummaryAtom(projectId))

  if (Result.isInitial(result) || Result.isWaiting(result)) {
    return (
      <Card>
        <CardContent className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" /> 正在计算 BKT 模型指标…
        </CardContent>
      </Card>
    )
  }
  if (Result.isFailure(result)) return null

  const metrics = result.value
  const hasComparison =
    metrics.legacy_brier_score != null && metrics.brier_score != null

  return (
    <Card className="border-primary/20" data-testid="kt-model-metrics">
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2 text-lg">
              <BrainCircuit className="size-5 text-primary" />
              专家参数 BKT 模型验证
            </CardTitle>
            {/* <CardDescription className="mt-1">
              使用真实学习事件评估下一题预测、知识点映射覆盖率和证据充分程度。
            </CardDescription> */}
          </div>
          <Badge variant="outline">{metrics.event_count} 条有效事件</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-lg border bg-muted/20 p-4">
            <div className="text-xs text-muted-foreground">Brier Score</div>
            <div className="mt-1 text-xl font-semibold tabular-nums">
              {decimal(metrics.brier_score)}
            </div>
            <div className="mt-1 text-[11px] text-muted-foreground">
              越低越好
              {hasComparison
                ? ` · 旧模型 ${decimal(metrics.legacy_brier_score)}`
                : ''}
            </div>
          </div>
          <div className="rounded-lg border bg-muted/20 p-4">
            <div className="text-xs text-muted-foreground">LogLoss</div>
            <div className="mt-1 text-xl font-semibold tabular-nums">
              {decimal(metrics.log_loss)}
            </div>
            <div className="mt-1 text-[11px] text-muted-foreground">
              越低越好
              {metrics.legacy_log_loss != null
                ? ` · 旧模型 ${decimal(metrics.legacy_log_loss)}`
                : ''}
            </div>
          </div>
          <div className="rounded-lg border bg-muted/20 p-4">
            <div className="text-xs text-muted-foreground">校准误差 ECE</div>
            <div className="mt-1 text-xl font-semibold tabular-nums">
              {decimal(metrics.expected_calibration_error)}
            </div>
            <div className="mt-1 text-[11px] text-muted-foreground">
              预测概率与实际正确率的偏差
            </div>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2 rounded-lg border p-4">
            <div className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-2">
                <Activity className="size-4 text-primary" /> 知识点映射覆盖率
              </span>
              <span className="font-medium">
                {percent(metrics.mapping_coverage)}
              </span>
            </div>
            <Progress value={metrics.mapping_coverage * 100} />
            <p className="text-xs text-muted-foreground">
              未可靠映射的练习会保留记录，但不会直接更新 BKT。
            </p>
          </div>
          <div className="space-y-2 rounded-lg border p-4">
            <div className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-2">
                <ShieldCheck className="size-4 text-primary" /> 低证据状态占比
              </span>
              <span className="font-medium">
                {percent(metrics.low_evidence_ratio)}
              </span>
            </div>
            <Progress value={metrics.low_evidence_ratio * 100} />
            <p className="text-xs text-muted-foreground">
              低证据知识点只给出谨慎提示，不输出高置信度根因。
            </p>
          </div>
        </div>

        {metrics.brier_score_improvement != null && (
          <div className="rounded-lg border border-primary/20 bg-primary/5 px-4 py-3 text-sm">
            相比旧指数平滑模型，Brier Score
            {metrics.brier_score_improvement >= 0 ? ' 改善 ' : ' 变化 '}
            <span className="font-semibold">
              {Math.abs(metrics.brier_score_improvement).toFixed(3)}
            </span>
            。
          </div>
        )}
      </CardContent>
    </Card>
  )
}
