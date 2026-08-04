import {
  Activity,
  AlertTriangle,
  BarChart3,
  BookOpen,
  Bot,
  CircleDollarSign,
  CreditCard,
  Database,
  Gauge,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Package,
  RefreshCw,
  Shield,
  Timer,
  TrendingUp,
  UserCheck,
  Users,
} from 'lucide-react'
import { useNavigate } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import type { BillingPlan } from '@/data-acess/billing-admin'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { adminApi } from '@/data-acess/billing-admin'
import { CourseCreateDialog } from '@/features/admin/course-create-dialog'
import { authClient } from '@/lib/auth-client'

type Tab =
  | 'overview'
  | 'users'
  | 'orders'
  | 'runs'
  | 'courses'
  | 'plans'
  | 'audit'
type Row = Record<string, any>

const tabs: Array<{ id: Tab; label: string; icon: typeof Shield }> = [
  { id: 'overview', label: '经营概览', icon: LayoutDashboard },
  { id: 'users', label: '用户权益', icon: Users },
  { id: 'orders', label: '订单退款', icon: CreditCard },
  { id: 'runs', label: 'Agent 观测', icon: Activity },
  { id: 'courses', label: '课程运营', icon: BookOpen },
  { id: 'plans', label: '套餐配置', icon: Package },
  { id: 'audit', label: '审计日志', icon: ListChecks },
]

const date = (value: unknown) =>
  value ? new Date(String(value)).toLocaleString('zh-CN') : '—'
const money = (value: unknown) => `¥${(Number(value ?? 0) / 100).toFixed(2)}`
const number = (value: unknown) => Number(value ?? 0)
const compact = (value: unknown) =>
  new Intl.NumberFormat('zh-CN', {
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(number(value))
const percent = (value: unknown) => `${(number(value) * 100).toFixed(1)}%`
const duration = (value: unknown) =>
  number(value) >= 1000
    ? `${(number(value) / 1000).toFixed(1)} 秒`
    : `${Math.round(number(value))} 毫秒`
const bytes = (value: unknown) => {
  const size = number(value)
  if (size < 1024) return `${size} B`
  if (size < 1024 ** 2) return `${(size / 1024).toFixed(1)} KB`
  if (size < 1024 ** 3) return `${(size / 1024 ** 2).toFixed(1)} MB`
  return `${(size / 1024 ** 3).toFixed(1)} GB`
}

export function AdminPage() {
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>('overview')
  const [data, setData] = useState<Row | Array<Row> | null>(null)
  const [plans, setPlans] = useState<Array<BillingPlan>>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [courseDialogOpen, setCourseDialogOpen] = useState(false)

  const signOut = async () => {
    await authClient.auth.signOut()
    await navigate({ to: '/sign-in', replace: true })
  }

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const {
        data: { session },
      } = await authClient.auth.getSession()
      if (!session?.user.is_admin) throw new Error('当前账户没有管理员权限')
      const planRows = await adminApi.plans()
      setPlans(planRows)
      if (tab === 'overview') setData(await adminApi.overview())
      if (tab === 'users') setData(await adminApi.users(search))
      if (tab === 'orders') setData(await adminApi.orders(search))
      if (tab === 'runs') setData(await adminApi.runs())
      if (tab === 'courses') setData(await adminApi.courses())
      if (tab === 'plans') setData(planRows)
      if (tab === 'audit') setData(await adminApi.audits())
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [tab])

  const act = async (
    label: string,
    callback: (reason: string) => Promise<unknown>,
  ) => {
    const reason = window.prompt(`${label}：请输入操作原因（将写入审计日志）`)
    if (!reason?.trim()) return
    if (!window.confirm(`确认执行“${label}”？`)) return
    try {
      await callback(reason.trim())
      setNotice(`${label}已完成`)
      await load()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : `${label}失败`)
    }
  }

  const pageItems =
    !Array.isArray(data) && data && Array.isArray(data.items)
      ? (data.items as Array<Row>)
      : []
  const overview =
    tab === 'overview' && data && !Array.isArray(data) ? data : null

  return (
    <div className="min-h-svh bg-[#f5f7fb] dark:bg-background">
      <header className="sticky top-0 z-20 border-b bg-background/95 backdrop-blur">
        <div className="mx-auto flex max-w-[1500px] items-center justify-between px-5 py-3">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-primary p-2 text-primary-foreground">
              <Shield className="size-5" />
            </div>
            <div>
              <p className="font-semibold">万径管理后台</p>
              <p className="text-xs text-muted-foreground">
                运营、计费与运行观测
              </p>
            </div>
          </div>
          <Button variant="outline" onClick={() => void signOut()}>
            <LogOut className="size-4" />
            退出登录
          </Button>
        </div>
      </header>
      <div className="mx-auto grid max-w-[1500px] gap-6 px-5 py-6 lg:grid-cols-[220px_1fr]">
        <aside>
          <nav className="sticky top-24 space-y-1 rounded-xl border bg-card p-2 shadow-sm">
            {tabs.map((item) => (
              <button
                key={item.id}
                onClick={() => {
                  setTab(item.id)
                  setSearch('')
                  setNotice(null)
                }}
                className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition ${tab === item.id ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'}`}
              >
                <item.icon className="size-4" />
                {item.label}
              </button>
            ))}
          </nav>
        </aside>
        <main className="min-w-0 space-y-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold">
                {tabs.find((item) => item.id === tab)?.label}
              </h1>
              <p className="mt-1 text-sm text-muted-foreground">
                数据源为服务端聚合，敏感写操作均需原因并审计。
              </p>
            </div>
            <div className="flex gap-2">
              {tab === 'courses' && (
                <Button onClick={() => setCourseDialogOpen(true)}>
                  新建平台课程
                </Button>
              )}
              <Button
                variant="outline"
                onClick={() => void load()}
                disabled={loading}
              >
                <RefreshCw
                  className={`size-4 ${loading ? 'animate-spin' : ''}`}
                />
                刷新
              </Button>
            </div>
          </div>
          {error && (
            <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
              {error}
            </div>
          )}
          {notice && (
            <div className="rounded-lg border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-800">
              {notice}
            </div>
          )}

          {overview && <Overview data={overview} />}
          {(tab === 'users' || tab === 'orders') && (
            <div className="flex gap-2">
              <Input
                className="max-w-sm"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder={
                  tab === 'users'
                    ? '搜索用户名、姓名或邮箱'
                    : '搜索订单号、用户或渠道流水'
                }
                onKeyDown={(event) => {
                  if (event.key === 'Enter') void load()
                }}
              />
              <Button onClick={() => void load()}>搜索</Button>
            </div>
          )}
          {tab === 'users' && (
            <UsersTable rows={pageItems} plans={plans} act={act} />
          )}
          {tab === 'orders' && <OrdersTable rows={pageItems} act={act} />}
          {tab === 'runs' && <RunsTable rows={pageItems} act={act} />}
          {tab === 'courses' && <CoursesTable rows={pageItems} act={act} />}
          {tab === 'plans' && (
            <PlansTable rows={Array.isArray(data) ? data : []} act={act} />
          )}
          {tab === 'audit' && <AuditTable rows={pageItems} />}
        </main>
      </div>
      <CourseCreateDialog
        open={courseDialogOpen}
        onOpenChange={setCourseDialogOpen}
        onCreated={async () => {
          setNotice('平台课程草稿已创建')
          await load()
        }}
      />
    </div>
  )
}

function Overview({ data }: { data: Row }) {
  const daily: Array<Row> = Array.isArray(data.trends?.daily)
    ? data.trends.daily
    : []
  const totalTokens =
    number(data.agent_runs?.input_tokens) +
    number(data.agent_runs?.output_tokens)
  const periodTotals = daily.reduce(
    (totals, item) => ({
      newUsers: totals.newUsers + number(item.new_users),
      orders: totals.orders + number(item.orders),
      revenue: totals.revenue + number(item.revenue_cents),
      runs: totals.runs + number(item.agent_runs),
    }),
    { newUsers: 0, orders: 0, revenue: 0, runs: 0 },
  )
  const metrics = [
    {
      label: '注册用户',
      value: compact(data.users?.registered),
      hint: `今日新增 ${compact(data.users?.new_today)} · 启用 ${compact(data.users?.active)}`,
      icon: Users,
      tone: 'blue' as const,
    },
    {
      label: '今日实收',
      value: money(data.orders?.revenue_cents),
      hint: `${compact(data.orders?.today)} 笔订单 · 待处理 ${compact(data.orders?.pending_payment)}`,
      icon: CircleDollarSign,
      tone: 'emerald' as const,
    },
    {
      label: '付费转化率',
      value: percent(data.users?.paid_conversion_rate),
      hint: `${compact(data.users?.paid)} 位付费用户 · ${compact(data.users?.active_entitlements)} 份生效权益`,
      icon: UserCheck,
      tone: 'violet' as const,
    },
    {
      label: 'Agent 成功率',
      value: percent(data.agent_runs?.success_rate),
      hint: `今日 ${compact(data.agent_runs?.today)} 次 · 失败 ${compact(data.agent_runs?.failed)}`,
      icon: Bot,
      tone: 'cyan' as const,
    },
    {
      label: '今日 Token',
      value: compact(totalTokens),
      hint: `输入 ${compact(data.agent_runs?.input_tokens)} · 输出 ${compact(data.agent_runs?.output_tokens)}`,
      icon: Gauge,
      tone: 'amber' as const,
    },
    {
      label: '内容资产',
      value: compact(data.content?.documents),
      hint: `${compact(data.content?.projects)} 个项目 · 占用 ${bytes(data.content?.storage_bytes)}`,
      icon: Database,
      tone: 'slate' as const,
    },
  ]

  const planDistribution = normalizeDistribution(
    data.orders?.plan_distribution,
    'plan',
  )
  const orderDistribution = normalizeDistribution(
    data.orders?.status_distribution,
    'status',
  )
  const runDistribution = normalizeDistribution(
    data.agent_runs?.status_distribution,
    'status',
  )
  const courseDistribution = [
    { label: '已发布', count: number(data.courses?.published) },
    { label: '草稿', count: number(data.courses?.draft) },
    { label: '已下架', count: number(data.courses?.unpublished) },
    { label: '已归档', count: number(data.courses?.archived) },
  ]

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-gradient-to-r from-slate-950 to-slate-800 px-5 py-4 text-white shadow-sm">
        <div>
          <div className="flex items-center gap-2 text-sm font-medium text-slate-200">
            <TrendingUp className="size-4" />
            平台运营驾驶舱
          </div>
          <p className="mt-1 text-xs text-slate-400">
            用户、交易、智能体与内容资产的实时汇总
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <Badge className="border-emerald-400/30 bg-emerald-400/15 text-emerald-100">
            平台运行中
          </Badge>
          <span className="text-slate-400">
            更新于 {date(data.generated_at)}
          </span>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {metrics.map((metric) => (
          <MetricCard key={metric.label} {...metric} />
        ))}
      </div>

      <div className="grid gap-5 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader className="pb-2">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <CardTitle className="flex items-center gap-2 text-base">
                  <BarChart3 className="size-4 text-blue-600" />近{' '}
                  {number(data.trends?.period_days) || 14} 天业务活跃趋势
                </CardTitle>
                <CardDescription>
                  新增用户、订单与 Agent 运行次数
                </CardDescription>
              </div>
              <div className="flex gap-4 text-right text-xs">
                <Summary label="新增用户" value={periodTotals.newUsers} />
                <Summary label="订单" value={periodTotals.orders} />
                <Summary label="Agent" value={periodTotals.runs} />
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <TrendChart
              data={daily}
              series={[
                { key: 'new_users', label: '新增用户', color: '#2563eb' },
                { key: 'orders', label: '订单', color: '#8b5cf6' },
                { key: 'agent_runs', label: 'Agent 运行', color: '#06b6d4' },
              ]}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <AlertTriangle className="size-4 text-amber-500" />
              今日待办与健康度
            </CardTitle>
            <CardDescription>需要运营人员关注的关键事项</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <HealthRow
              label="待处理订单"
              value={number(data.orders?.pending_payment)}
              detail="待付款或等待人工确认"
              tone="amber"
            />
            <HealthRow
              label="疑似卡死任务"
              value={number(data.agent_runs?.suspected_stuck)}
              detail="运行中且 2 分钟无心跳"
              tone="red"
            />
            <HealthRow
              label="今日失败任务"
              value={number(data.agent_runs?.failed)}
              detail={`失败率 ${percent(data.agent_runs?.failure_rate)}`}
              tone="red"
            />
            <HealthRow
              label="课程草稿"
              value={number(data.courses?.draft)}
              detail="等待内容审核与发布"
              tone="blue"
            />
          </CardContent>
        </Card>

        <Card className="xl:col-span-2">
          <CardHeader className="pb-2">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <CardTitle className="flex items-center gap-2 text-base">
                  <CreditCard className="size-4 text-emerald-600" />
                  营收与退款趋势
                </CardTitle>
                <CardDescription>按实际支付与退款时间统计</CardDescription>
              </div>
              <div className="text-right">
                <p className="text-xs text-muted-foreground">周期实收</p>
                <p className="text-lg font-semibold text-emerald-700">
                  {money(periodTotals.revenue)}
                </p>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <TrendChart
              data={daily}
              valueFormatter={money}
              series={[
                { key: 'revenue_cents', label: '实收', color: '#059669' },
                { key: 'refund_cents', label: '退款', color: '#f97316' },
              ]}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <Package className="size-4 text-violet-600" />
              生效套餐结构
            </CardTitle>
            <CardDescription>当前有效用户权益分布</CardDescription>
          </CardHeader>
          <CardContent>
            <DonutChart items={planDistribution} centerLabel="生效权益" />
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
        <DistributionCard
          title="订单状态"
          description="全部历史订单结构"
          icon={CreditCard}
          items={orderDistribution}
        />
        <DistributionCard
          title="Agent 状态"
          description="近 14 天运行结构"
          icon={Activity}
          items={runDistribution}
        />
        <DistributionCard
          title="课程状态"
          description="平台课程发布结构"
          icon={BookOpen}
          items={courseDistribution}
        />
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <Timer className="size-4 text-cyan-600" />
              Agent 效率与成本
            </CardTitle>
            <CardDescription>今日智能体资源消耗</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <KeyValue
              label="平均耗时"
              value={duration(data.agent_runs?.average_duration_ms)}
            />
            <KeyValue
              label="输入 Token"
              value={compact(data.agent_runs?.input_tokens)}
            />
            <KeyValue
              label="输出 Token"
              value={compact(data.agent_runs?.output_tokens)}
            />
            <KeyValue
              label="估算成本"
              value={`${(number(data.agent_runs?.estimated_cost_micros) / 1_000_000).toFixed(4)} 成本单位`}
            />
            <KeyValue
              label="今日退款"
              value={money(data.orders?.refund_cents)}
              danger
            />
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

const metricTone = {
  blue: 'bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300',
  emerald:
    'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300',
  violet:
    'bg-violet-50 text-violet-700 dark:bg-violet-950/40 dark:text-violet-300',
  cyan: 'bg-cyan-50 text-cyan-700 dark:bg-cyan-950/40 dark:text-cyan-300',
  amber: 'bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300',
  slate: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200',
} as const

function MetricCard({
  label,
  value,
  hint,
  icon: Icon,
  tone,
}: {
  label: string
  value: string
  hint: string
  icon: typeof Users
  tone: keyof typeof metricTone
}) {
  return (
    <Card className="overflow-hidden">
      <CardContent className="flex items-start justify-between gap-4 p-5">
        <div className="min-w-0">
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="mt-1 truncate text-2xl font-semibold tracking-tight">
            {value}
          </p>
          <p className="mt-2 text-xs text-muted-foreground">{hint}</p>
        </div>
        <div className={`shrink-0 rounded-xl p-2.5 ${metricTone[tone]}`}>
          <Icon className="size-5" />
        </div>
      </CardContent>
    </Card>
  )
}

function Summary({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <p className="text-muted-foreground">{label}</p>
      <p className="mt-0.5 text-sm font-semibold">{compact(value)}</p>
    </div>
  )
}

type ChartSeries = { key: string; label: string; color: string }

function TrendChart({
  data,
  series,
  valueFormatter = compact,
}: {
  data: Array<Row>
  series: Array<ChartSeries>
  valueFormatter?: (value: unknown) => string
}) {
  const width = 760
  const height = 250
  const left = 48
  const right = 18
  const top = 20
  const bottom = 40
  const plotWidth = width - left - right
  const plotHeight = height - top - bottom
  const maxValue = Math.max(
    1,
    ...data.flatMap((item) => series.map((line) => number(item[line.key]))),
  )
  const points = (key: string) =>
    data.map((item, index) => {
      const x = left + (index / Math.max(data.length - 1, 1)) * plotWidth
      const y = top + plotHeight - (number(item[key]) / maxValue) * plotHeight
      return { x, y, value: number(item[key]), date: String(item.date ?? '') }
    })

  if (!data.length) {
    return (
      <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">
        暂无趋势数据
      </div>
    )
  }

  return (
    <div>
      <div className="mb-2 flex flex-wrap justify-end gap-4 text-xs text-muted-foreground">
        {series.map((line) => (
          <span key={line.key} className="flex items-center gap-1.5">
            <span
              className="size-2 rounded-full"
              style={{ backgroundColor: line.color }}
            />
            {line.label}
          </span>
        ))}
      </div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="h-auto w-full overflow-visible"
        role="img"
        aria-label={series.map((line) => line.label).join('、') + '趋势图'}
      >
        {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
          const y = top + plotHeight * ratio
          const value = maxValue * (1 - ratio)
          return (
            <g key={ratio}>
              <line
                x1={left}
                x2={width - right}
                y1={y}
                y2={y}
                stroke="currentColor"
                className="text-border"
                strokeDasharray="3 5"
              />
              <text
                x={left - 8}
                y={y + 4}
                textAnchor="end"
                className="fill-muted-foreground text-[10px]"
              >
                {valueFormatter(value)}
              </text>
            </g>
          )
        })}
        {series.map((line, seriesIndex) => {
          const linePoints = points(line.key)
          const polygon = `${left},${top + plotHeight} ${linePoints
            .map((point) => `${point.x},${point.y}`)
            .join(' ')} ${width - right},${top + plotHeight}`
          return (
            <g key={line.key}>
              {seriesIndex === 0 && (
                <polygon points={polygon} fill={line.color} opacity="0.08" />
              )}
              <polyline
                points={linePoints
                  .map((point) => `${point.x},${point.y}`)
                  .join(' ')}
                fill="none"
                stroke={line.color}
                strokeWidth="3"
                strokeLinejoin="round"
                strokeLinecap="round"
              />
              {linePoints.map((point, index) => (
                <circle
                  key={`${line.key}-${point.date}`}
                  cx={point.x}
                  cy={point.y}
                  r={index === linePoints.length - 1 ? 4 : 2.5}
                  fill={line.color}
                  stroke="white"
                  strokeWidth="1.5"
                >
                  <title>{`${point.date} · ${line.label} ${valueFormatter(point.value)}`}</title>
                </circle>
              ))}
            </g>
          )
        })}
        {data.map((item, index) => {
          if (index % 3 !== 0 && index !== data.length - 1) return null
          const x = left + (index / Math.max(data.length - 1, 1)) * plotWidth
          return (
            <text
              key={String(item.date)}
              x={x}
              y={height - 12}
              textAnchor="middle"
              className="fill-muted-foreground text-[10px]"
            >
              {String(item.date ?? '').slice(5)}
            </text>
          )
        })}
      </svg>
    </div>
  )
}

const chartColors = [
  '#2563eb',
  '#8b5cf6',
  '#06b6d4',
  '#10b981',
  '#f59e0b',
  '#f97316',
]

const distributionLabels: Record<string, string> = {
  created: '待付款',
  pending_payment: '待确认',
  paid: '已支付',
  refunding: '退款中',
  refunded: '已退款',
  closed: '已关闭',
  completed: '已完成',
  failed: '失败',
  running: '运行中',
  pending: '等待中',
  cancelled: '已取消',
}

function normalizeDistribution(value: unknown, labelKey: string) {
  if (!Array.isArray(value)) return []
  return value.map((item) => {
    const rawLabel = String((item as Row)[labelKey] ?? '未知')
    return {
      label: distributionLabels[rawLabel] ?? rawLabel,
      count: number((item as Row).count),
    }
  })
}

function DonutChart({
  items,
  centerLabel,
}: {
  items: Array<{ label: string; count: number }>
  centerLabel: string
}) {
  const total = items.reduce((sum, item) => sum + item.count, 0)
  let cursor = 0
  const gradient = total
    ? `conic-gradient(${items
        .map((item, index) => {
          const start = cursor
          cursor += (item.count / total) * 100
          return `${chartColors[index % chartColors.length]} ${start}% ${cursor}%`
        })
        .join(', ')})`
    : 'conic-gradient(#e2e8f0 0 100%)'
  return (
    <div className="flex flex-col items-center gap-5 py-2 sm:flex-row sm:items-center">
      <div
        className="relative size-36 shrink-0 rounded-full"
        style={{ background: gradient }}
      >
        <div className="absolute inset-[18px] flex flex-col items-center justify-center rounded-full bg-card shadow-inner">
          <span className="text-2xl font-semibold">{compact(total)}</span>
          <span className="text-[11px] text-muted-foreground">
            {centerLabel}
          </span>
        </div>
      </div>
      <div className="min-w-0 flex-1 space-y-2.5">
        {items.map((item, index) => (
          <div
            key={item.label}
            className="flex items-center justify-between gap-3 text-xs"
          >
            <span className="flex min-w-0 items-center gap-2">
              <span
                className="size-2.5 shrink-0 rounded-full"
                style={{
                  backgroundColor: chartColors[index % chartColors.length],
                }}
              />
              <span className="truncate">{item.label}</span>
            </span>
            <span className="font-medium tabular-nums">
              {item.count} ·{' '}
              {total ? `${((item.count / total) * 100).toFixed(0)}%` : '0%'}
            </span>
          </div>
        ))}
        {!items.length && (
          <p className="text-xs text-muted-foreground">暂无套餐数据</p>
        )}
      </div>
    </div>
  )
}

function DistributionCard({
  title,
  description,
  icon: Icon,
  items,
}: {
  title: string
  description: string
  icon: typeof Shield
  items: Array<{ label: string; count: number }>
}) {
  const total = Math.max(
    1,
    items.reduce((sum, item) => sum + item.count, 0),
  )
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Icon className="size-4 text-blue-600" />
          {title}
        </CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {items.map((item, index) => (
          <div key={item.label} className="space-y-1.5">
            <div className="flex justify-between text-xs">
              <span className="text-muted-foreground">{item.label}</span>
              <span className="font-medium tabular-nums">{item.count}</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full"
                style={{
                  width: `${(item.count / total) * 100}%`,
                  backgroundColor: chartColors[index % chartColors.length],
                }}
              />
            </div>
          </div>
        ))}
        {!items.length && (
          <p className="text-xs text-muted-foreground">暂无数据</p>
        )}
      </CardContent>
    </Card>
  )
}

function HealthRow({
  label,
  value,
  detail,
  tone,
}: {
  label: string
  value: number
  detail: string
  tone: 'amber' | 'red' | 'blue'
}) {
  const tones = {
    amber:
      'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200',
    red: 'border-red-200 bg-red-50 text-red-800 dark:border-red-900 dark:bg-red-950/30 dark:text-red-200',
    blue: 'border-blue-200 bg-blue-50 text-blue-800 dark:border-blue-900 dark:bg-blue-950/30 dark:text-blue-200',
  }
  return (
    <div
      className={`flex items-center justify-between gap-3 rounded-lg border px-3 py-2.5 ${tones[tone]}`}
    >
      <div className="min-w-0">
        <p className="text-sm font-medium">{label}</p>
        <p className="truncate text-[11px] opacity-70">{detail}</p>
      </div>
      <span className="text-xl font-semibold tabular-nums">{value}</span>
    </div>
  )
}

function KeyValue({
  label,
  value,
  danger = false,
}: {
  label: string
  value: string
  danger?: boolean
}) {
  return (
    <div className="flex items-center justify-between gap-3 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className={danger ? 'font-medium text-destructive' : 'font-medium'}>
        {value}
      </span>
    </div>
  )
}

function DataCard({ children }: { children: React.ReactNode }) {
  return (
    <Card>
      <CardContent className="pt-4">{children}</CardContent>
    </Card>
  )
}

function UsersTable({
  rows,
  plans,
  act,
}: {
  rows: Array<Row>
  plans: Array<BillingPlan>
  act: Action
}) {
  const recommended =
    plans.find((plan) => plan.code === 'advanced_5990') ??
    plans.find((plan) => plan.code !== 'trial')
  return (
    <DataCard>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>用户</TableHead>
            <TableHead>状态</TableHead>
            <TableHead>角色</TableHead>
            <TableHead>当前套餐</TableHead>
            <TableHead>到期</TableHead>
            <TableHead>注册时间</TableHead>
            <TableHead>操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.id}>
              <TableCell>
                <div className="font-medium">{row.name ?? row.username}</div>
                <div className="text-xs text-muted-foreground">
                  @{row.username}
                </div>
              </TableCell>
              <TableCell>
                <Badge variant={row.is_active ? 'secondary' : 'destructive'}>
                  {row.is_active ? '启用' : '停用'}
                </Badge>
              </TableCell>
              <TableCell>{row.is_admin ? '管理员' : '用户'}</TableCell>
              <TableCell>{row.current_plan ?? '—'}</TableCell>
              <TableCell>{date(row.plan_expires_at)}</TableCell>
              <TableCell>{date(row.created_at)}</TableCell>
              <TableCell>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      void act(
                        row.is_active ? '停用账户' : '启用账户',
                        (reason) =>
                          adminApi.updateUser(row.id, {
                            is_active: !row.is_active,
                            reason,
                          }),
                      )
                    }
                  >
                    {row.is_active ? '停用' : '启用'}
                  </Button>
                  {recommended && (
                    <Button
                      size="sm"
                      onClick={() =>
                        void act(`发放${recommended.name}`, (reason) =>
                          adminApi.grant(row.id, recommended.id, reason),
                        )
                      }
                    >
                      赠送套餐
                    </Button>
                  )}
                </div>
              </TableCell>
            </TableRow>
          ))}
          {!rows.length && <Empty columns={7} />}
        </TableBody>
      </Table>
    </DataCard>
  )
}

function OrdersTable({ rows, act }: { rows: Array<Row>; act: Action }) {
  return (
    <DataCard>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>订单号</TableHead>
            <TableHead>用户</TableHead>
            <TableHead>套餐</TableHead>
            <TableHead>金额</TableHead>
            <TableHead>渠道</TableHead>
            <TableHead>状态 / 付款申报</TableHead>
            <TableHead>时间</TableHead>
            <TableHead>操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.id}>
              <TableCell className="font-mono text-xs">
                {row.order_no}
              </TableCell>
              <TableCell>{row.username}</TableCell>
              <TableCell>{row.plan_snapshot?.name}</TableCell>
              <TableCell>{money(row.amount_cents)}</TableCell>
              <TableCell>{row.provider}</TableCell>
              <TableCell>
                <Badge variant="outline">{row.status}</Badge>
                {row.payment_claimed_at && (
                  <div className="mt-1 max-w-56 whitespace-normal text-xs">
                    <p className="font-medium text-amber-700">用户已申报付款</p>
                    <p>{row.payment_claim_note}</p>
                    {row.payment_reference && (
                      <p className="text-muted-foreground">
                        流水尾号：{row.payment_reference}
                      </p>
                    )}
                  </div>
                )}
                {row.exception_note && (
                  <p className="mt-1 max-w-48 whitespace-normal text-xs text-destructive">
                    {row.exception_note}
                  </p>
                )}
              </TableCell>
              <TableCell>
                <p>{date(row.created_at)}</p>
                {row.payment_claimed_at && (
                  <p className="text-xs text-muted-foreground">
                    申报 {date(row.payment_claimed_at)}
                  </p>
                )}
              </TableCell>
              <TableCell>
                <div className="flex gap-2">
                  {String(row.provider).startsWith('manual') &&
                    row.status === 'pending_payment' && (
                      <Button
                        size="sm"
                        onClick={() =>
                          void act('核对收款记录并确认到账', (reason) =>
                            adminApi.confirmOrder(row.order_no, reason),
                          )
                        }
                      >
                        确认到账
                      </Button>
                    )}
                  {row.status === 'paid' && (
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() =>
                        void act('记录已线下退款并撤销剩余额度', (reason) =>
                          adminApi.refundOrder(row.order_no, reason),
                        )
                      }
                    >
                      记录退款
                    </Button>
                  )}
                </div>
              </TableCell>
            </TableRow>
          ))}
          {!rows.length && <Empty columns={8} />}
        </TableBody>
      </Table>
    </DataCard>
  )
}

function RunsTable({ rows, act }: { rows: Array<Row>; act: Action }) {
  const [detail, setDetail] = useState<Row | null>(null)
  const openDetail = async (id: string) => {
    try {
      setDetail(await adminApi.run(id))
    } catch (cause) {
      window.alert(cause instanceof Error ? cause.message : '加载详情失败')
    }
  }
  return (
    <div className="space-y-4">
      <DataCard>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>运行 / 用户</TableHead>
              <TableHead>目标</TableHead>
              <TableHead>Agent</TableHead>
              <TableHead>状态</TableHead>
              <TableHead>耗时</TableHead>
              <TableHead>Token</TableHead>
              <TableHead>错误</TableHead>
              <TableHead>操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.id}>
                <TableCell>
                  <div className="font-mono text-xs">{row.id}</div>
                  <div className="text-xs text-muted-foreground">
                    {row.username}
                  </div>
                </TableCell>
                <TableCell className="max-w-56 whitespace-normal">
                  {row.goal}
                </TableCell>
                <TableCell>{row.current_agent_name ?? '—'}</TableCell>
                <TableCell>
                  <Badge
                    variant={row.suspected_stuck ? 'destructive' : 'outline'}
                  >
                    {row.suspected_stuck ? '疑似卡死' : row.status}
                  </Badge>
                </TableCell>
                <TableCell>
                  {row.duration_ms
                    ? `${(row.duration_ms / 1000).toFixed(1)}s`
                    : '—'}
                </TableCell>
                <TableCell>
                  {Number(row.input_tokens ?? 0) +
                    Number(row.output_tokens ?? 0)}
                </TableCell>
                <TableCell className="max-w-52 whitespace-normal text-xs text-destructive">
                  {row.error_summary ?? '—'}
                </TableCell>
                <TableCell>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => void openDetail(row.id)}
                    >
                      详情
                    </Button>
                    {!row.handled_at && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() =>
                          void act('标记已处理', (reason) =>
                            adminApi.handleRun(row.id, reason),
                          )
                        }
                      >
                        已处理
                      </Button>
                    )}
                    {row.status === 'failed' && (
                      <Button
                        size="sm"
                        onClick={() =>
                          void act('重试失败任务', (reason) =>
                            adminApi.retryRun(row.id, reason),
                          )
                        }
                      >
                        重试
                      </Button>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
            {!rows.length && <Empty columns={8} />}
          </TableBody>
        </Table>
      </DataCard>
      {detail && (
        <Card>
          <CardHeader>
            <div className="flex justify-between">
              <div>
                <CardTitle className="text-lg">运行详情</CardTitle>
                <CardDescription className="font-mono">
                  {detail.trace_id ?? detail.id}
                </CardDescription>
              </div>
              <Button size="sm" variant="ghost" onClick={() => setDetail(null)}>
                关闭
              </Button>
            </div>
          </CardHeader>
          <CardContent className="grid gap-5 lg:grid-cols-3">
            <DetailList
              title="事件时间线"
              rows={detail.events ?? []}
              primary="summary"
              secondary="event_type"
            />
            <DetailList
              title="Skill 执行"
              rows={detail.skill_executions ?? []}
              primary="skill_id"
              secondary="status"
            />
            <DetailList
              title="工具调用"
              rows={detail.tool_calls ?? []}
              primary="tool_name"
              secondary="status"
            />
          </CardContent>
        </Card>
      )}
    </div>
  )
}

function DetailList({
  title,
  rows,
  primary,
  secondary,
}: {
  title: string
  rows: Array<Row>
  primary: string
  secondary: string
}) {
  return (
    <section>
      <h3 className="mb-2 text-sm font-medium">{title}</h3>
      <div className="max-h-72 space-y-2 overflow-auto">
        {rows.map((row) => (
          <div key={row.id} className="rounded-lg border p-2 text-xs">
            <p className="font-medium">{String(row[primary] ?? '—')}</p>
            <p className="mt-1 text-muted-foreground">
              {String(row[secondary] ?? '—')}
              {row.duration_ms ? ` · ${row.duration_ms}ms` : ''}
            </p>
          </div>
        ))}
        {!rows.length && (
          <p className="text-xs text-muted-foreground">暂无记录</p>
        )}
      </div>
    </section>
  )
}

function CoursesTable({ rows, act }: { rows: Array<Row>; act: Action }) {
  return (
    <DataCard>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>课程</TableHead>
            <TableHead>可见性</TableHead>
            <TableHead>发布状态</TableHead>
            <TableHead>章节</TableHead>
            <TableHead>使用项目</TableHead>
            <TableHead>版本</TableHead>
            <TableHead>操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.id}>
              <TableCell>
                <div className="font-medium">{row.name}</div>
                <div className="text-xs text-muted-foreground">
                  {row.code ?? row.id}
                </div>
              </TableCell>
              <TableCell>{row.visibility}</TableCell>
              <TableCell>
                <Badge variant="outline">{row.publish_status}</Badge>
              </TableCell>
              <TableCell>{row.chapter_count}</TableCell>
              <TableCell>{row.project_count}</TableCell>
              <TableCell>v{row.version}</TableCell>
              <TableCell>
                <div className="flex gap-2">
                  {row.publish_status !== 'published' && (
                    <Button
                      size="sm"
                      onClick={() =>
                        void act('发布平台课程', (reason) =>
                          adminApi.courseAction(row.id, 'publish', reason),
                        )
                      }
                    >
                      发布
                    </Button>
                  )}
                  {row.publish_status === 'published' && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        void act('下架平台课程', (reason) =>
                          adminApi.courseAction(row.id, 'unpublish', reason),
                        )
                      }
                    >
                      下架
                    </Button>
                  )}
                  {row.publish_status !== 'archived' && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() =>
                        void act('归档课程', (reason) =>
                          adminApi.courseAction(row.id, 'archive', reason),
                        )
                      }
                    >
                      归档
                    </Button>
                  )}
                </div>
              </TableCell>
            </TableRow>
          ))}
          {!rows.length && <Empty columns={7} />}
        </TableBody>
      </Table>
    </DataCard>
  )
}

function PlansTable({ rows, act }: { rows: Array<Row>; act: Action }) {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {rows.map((row) => (
        <Card key={row.id}>
          <CardHeader>
            <div className="flex justify-between">
              <CardTitle>{row.name}</CardTitle>
              <Badge variant={row.is_active ? 'secondary' : 'outline'}>
                {row.is_active ? '展示中' : '已下架'}
              </Badge>
            </div>
            <CardDescription>{row.code}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-2xl font-semibold">
              {money(row.price_cents)}{' '}
              <span className="text-sm font-normal text-muted-foreground">
                / {row.duration_days} 天
              </span>
            </p>
            <p className="text-sm text-muted-foreground">
              {Object.keys(row.quotas ?? {}).length} 项额度配置 · 排序{' '}
              {row.sort_order}
            </p>
            <Button
              variant="outline"
              onClick={() =>
                void act(row.is_active ? '下架套餐' : '启用套餐', (reason) =>
                  adminApi.updatePlan(row.id, {
                    is_active: !row.is_active,
                    reason,
                  }),
                )
              }
            >
              {row.is_active ? '下架' : '启用'}
            </Button>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

function AuditTable({ rows }: { rows: Array<Row> }) {
  return (
    <DataCard>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>时间</TableHead>
            <TableHead>管理员</TableHead>
            <TableHead>动作</TableHead>
            <TableHead>目标</TableHead>
            <TableHead>原因</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.id}>
              <TableCell>{date(row.created_at)}</TableCell>
              <TableCell className="font-mono text-xs">
                {row.admin_user_id ?? 'system'}
              </TableCell>
              <TableCell>
                <Badge variant="outline">{row.action}</Badge>
              </TableCell>
              <TableCell>
                {row.target_type} /{' '}
                <span className="font-mono text-xs">{row.target_id}</span>
              </TableCell>
              <TableCell className="max-w-sm whitespace-normal">
                {row.reason}
              </TableCell>
            </TableRow>
          ))}
          {!rows.length && <Empty columns={5} />}
        </TableBody>
      </Table>
    </DataCard>
  )
}

type Action = (
  label: string,
  callback: (reason: string) => Promise<unknown>,
) => Promise<void>
function Empty({ columns }: { columns: number }) {
  return (
    <TableRow>
      <TableCell
        colSpan={columns}
        className="py-10 text-center text-muted-foreground"
      >
        暂无数据
      </TableCell>
    </TableRow>
  )
}
