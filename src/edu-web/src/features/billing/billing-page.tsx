import { Check, CreditCard, Gauge, ShieldCheck } from 'lucide-react'
import { Link } from '@tanstack/react-router'
import { useEffect, useMemo, useState } from 'react'
import type {
  BillingPlan,
  ManualPaymentMethod,
} from '@/data-acess/billing-admin'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Progress } from '@/components/ui/progress'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { billingApi } from '@/data-acess/billing-admin'
import { authClient } from '@/lib/auth-client'

const quotaNames: Record<string, string> = {
  chat_message: 'AI 导师消息',
  document_upload: '文档解析',
  quiz_generation: '测验生成',
  flashcard_generation: '闪卡生成',
  mindmap_generation: '思维导图',
  agent_run: '多智能体运行',
  resource_package: '资源包',
  active_project: '活跃项目',
  storage_mb: '存储（MB）',
}

const statusNames: Record<string, string> = {
  created: '已创建',
  pending_payment: '待支付',
  paid: '已支付',
  closed: '已关闭',
  refunding: '退款中',
  refunded: '已退款',
  refund_failed: '退款失败',
}

const date = (value: unknown) =>
  value ? new Date(String(value)).toLocaleString('zh-CN') : '—'
const money = (value: unknown) => `¥${(Number(value ?? 0) / 100).toFixed(2)}`

export function BillingPage({ publicMode = false }: { publicMode?: boolean }) {
  const [plans, setPlans] = useState<Array<BillingPlan>>([])
  const [summary, setSummary] = useState<Record<string, any> | null>(null)
  const [orders, setOrders] = useState<Array<Record<string, any>>>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [checkoutPlan, setCheckoutPlan] = useState<BillingPlan | null>(null)
  const [paymentMethods, setPaymentMethods] = useState<
    Array<ManualPaymentMethod>
  >([])
  const [selectedProvider, setSelectedProvider] = useState<
    ManualPaymentMethod['provider'] | null
  >(null)
  const [checkoutOrder, setCheckoutOrder] = useState<Record<
    string,
    any
  > | null>(null)
  const [paymentClaimNote, setPaymentClaimNote] = useState('')
  const [paymentReference, setPaymentReference] = useState('')
  const [claimSubmitted, setClaimSubmitted] = useState(false)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const planRows = await billingApi.plans()
      setPlans(planRows.filter((plan) => plan.code !== 'trial'))
      if (!publicMode) {
        const [mySummary, myOrders] = await Promise.all([
          billingApi.summary(),
          billingApi.orders(),
        ])
        setSummary(mySummary)
        setOrders(myOrders)
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '加载计费信息失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [publicMode])

  const selectedMethod = useMemo(
    () =>
      paymentMethods.find((method) => method.provider === selectedProvider) ??
      null,
    [paymentMethods, selectedProvider],
  )

  const resetCheckout = () => {
    setCheckoutPlan(null)
    setPaymentMethods([])
    setSelectedProvider(null)
    setCheckoutOrder(null)
    setPaymentClaimNote('')
    setPaymentReference('')
    setClaimSubmitted(false)
  }

  const buy = async (plan: BillingPlan) => {
    const {
      data: { session },
    } = await authClient.auth.getSession()
    if (!session) {
      window.location.assign(
        `/sign-in?redirect=${encodeURIComponent('/dashboard/billing')}`,
      )
      return
    }
    setBusy(plan.id)
    setError(null)
    setMessage(null)
    try {
      const methods = await billingApi.paymentMethods()
      if (!methods.length)
        throw new Error('暂未配置比赛演示收款码，请联系管理员')
      setPaymentMethods(methods)
      setSelectedProvider(methods[0].provider)
      setCheckoutPlan(plan)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '加载收款方式失败')
    } finally {
      setBusy(null)
    }
  }

  const createOrder = async () => {
    if (!checkoutPlan || !selectedProvider) return
    setBusy(checkoutPlan.id)
    setError(null)
    try {
      const order = await billingApi.createOrder(
        checkoutPlan.code,
        selectedProvider,
      )
      setCheckoutOrder(order)
      if (!publicMode) await load()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '创建订单失败')
    } finally {
      setBusy(null)
    }
  }

  const submitPaymentClaim = async () => {
    if (!checkoutOrder || paymentClaimNote.trim().length < 2) {
      setError('请填写至少 2 个字符的付款账号昵称或核对信息')
      return
    }
    setBusy(String(checkoutOrder.id))
    setError(null)
    try {
      const updated = await billingApi.submitPaymentClaim(
        String(checkoutOrder.order_no),
        paymentClaimNote.trim(),
        paymentReference.trim(),
      )
      setCheckoutOrder(updated)
      setClaimSubmitted(true)
      setMessage(
        `订单 ${String(updated.order_no)} 已提交核对，确认到账后将自动开通权益。`,
      )
      if (!publicMode) await load()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '提交付款信息失败')
    } finally {
      setBusy(null)
    }
  }

  const quotas = (summary?.quotas ?? {}) as Record<
    string,
    { granted: number; used: number; reserved: number; remaining: number }
  >

  return (
    <main className="mx-auto w-full max-w-7xl space-y-8 px-5 py-8 lg:px-10">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Badge variant="secondary" className="mb-3">
            30 天阶段权益包 · 非自动续费
          </Badge>
          <h1 className="text-3xl font-semibold tracking-tight">套餐与额度</h1>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            透明的固定额度，到期前可叠加购买。历史学习内容始终保留。
          </p>
        </div>
        {publicMode && (
          <Button variant="outline" asChild>
            <Link to="/sign-in">登录后查看额度</Link>
          </Button>
        )}
      </header>

      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
          {error}
        </div>
      )}
      {message && (
        <div className="rounded-lg border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-800">
          {message}
        </div>
      )}

      {!publicMode && summary && (
        <section className="grid gap-4 lg:grid-cols-[1fr_2fr]">
          <Card>
            <CardHeader>
              <CardDescription>当前最高权益</CardDescription>
              <CardTitle>
                {summary.current_plan?.name ?? '暂无有效套餐'}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <p>有效期至：{date(summary.expires_at)}</p>
              <p className="text-muted-foreground">
                多个有效权益包的次数额度会自动累加。
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <Gauge className="size-5" />
                额度使用
              </CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              {Object.entries(quotas).map(([key, item]) => (
                <div key={key} className="space-y-1.5">
                  <div className="flex justify-between text-sm">
                    <span>{quotaNames[key] ?? key}</span>
                    <span className="text-muted-foreground">
                      {item.remaining} / {item.granted}
                    </span>
                  </div>
                  <Progress
                    value={
                      item.granted
                        ? ((item.used + item.reserved) / item.granted) * 100
                        : 0
                    }
                  />
                </div>
              ))}
              {!Object.keys(quotas).length && (
                <p className="text-sm text-muted-foreground">暂无有效额度</p>
              )}
            </CardContent>
          </Card>
        </section>
      )}

      <section className="grid gap-5 md:grid-cols-3">
        {plans.map((plan) => (
          <Card
            key={plan.id}
            className={
              plan.code === 'advanced_5990' ? 'border-primary shadow-md' : ''
            }
          >
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>{plan.name}</CardTitle>
                {plan.code === 'advanced_5990' && <Badge>推荐</Badge>}
              </div>
              <CardDescription>{plan.description}</CardDescription>
              <div className="pt-3">
                <span className="text-3xl font-semibold">
                  ¥{(plan.price_cents / 100).toFixed(1)}
                </span>
                <span className="text-sm text-muted-foreground">
                  {' '}
                  / {plan.duration_days} 天
                </span>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <ul className="space-y-2 text-sm">
                {Object.entries(plan.quotas)
                  .slice(0, 7)
                  .map(([key, value]) => (
                    <li key={key} className="flex gap-2">
                      <Check className="mt-0.5 size-4 text-emerald-600" />
                      {quotaNames[key] ?? key}：{value}
                    </li>
                  ))}
              </ul>
              <Button
                className="w-full"
                variant={plan.code === 'advanced_5990' ? 'default' : 'outline'}
                disabled={busy === plan.id || loading}
                onClick={() => void buy(plan)}
              >
                <CreditCard className="size-4" />
                {busy === plan.id ? '正在准备收款…' : '选择此套餐'}
              </Button>
            </CardContent>
          </Card>
        ))}
      </section>

      {!publicMode && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck className="size-5" />
              订单历史
            </CardTitle>
            <CardDescription>
              扫码付款不会自动开通；只有管理员核对实际收款后，服务端才会发放权益。
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>订单号</TableHead>
                  <TableHead>套餐</TableHead>
                  <TableHead>金额</TableHead>
                  <TableHead>渠道</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>创建时间</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {orders.map((order) => (
                  <TableRow key={String(order.id)}>
                    <TableCell className="font-mono text-xs">
                      {String(order.order_no)}
                    </TableCell>
                    <TableCell>
                      {String(order.plan_snapshot?.name ?? '—')}
                    </TableCell>
                    <TableCell>{money(order.amount_cents)}</TableCell>
                    <TableCell>{String(order.provider)}</TableCell>
                    <TableCell>
                      <Badge variant="outline">
                        {statusNames[String(order.status)] ??
                          String(order.status)}
                      </Badge>
                      {order.payment_claimed_at &&
                        order.status === 'pending_payment' && (
                          <p className="mt-1 text-xs text-amber-700">
                            已提交付款核对
                          </p>
                        )}
                    </TableCell>
                    <TableCell>{date(order.created_at)}</TableCell>
                  </TableRow>
                ))}
                {!orders.length && (
                  <TableRow>
                    <TableCell
                      colSpan={6}
                      className="py-8 text-center text-muted-foreground"
                    >
                      暂无订单
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      <Dialog
        open={checkoutPlan !== null}
        onOpenChange={(open) => {
          if (!open && !busy) resetCheckout()
        }}
      >
        <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>
              {checkoutOrder ? '扫码付款' : `购买${checkoutPlan?.name ?? ''}`}
            </DialogTitle>
            <DialogDescription>
              比赛演示人工收款。系统不会读取个人钱包记录，最终以管理员核对到账为准。
            </DialogDescription>
          </DialogHeader>

          {!checkoutOrder ? (
            <div className="space-y-4">
              <div className="rounded-lg border bg-muted/40 p-4 text-sm">
                <div className="flex justify-between">
                  <span>套餐</span>
                  <strong>{checkoutPlan?.name}</strong>
                </div>
                <div className="mt-2 flex justify-between">
                  <span>应付金额</span>
                  <strong className="text-lg">
                    {money(checkoutPlan?.price_cents)}
                  </strong>
                </div>
              </div>
              <div className="space-y-2">
                <p className="text-sm font-medium">选择收款方式</p>
                <div className="grid grid-cols-2 gap-3">
                  {paymentMethods.map((method) => (
                    <button
                      key={method.provider}
                      type="button"
                      onClick={() => setSelectedProvider(method.provider)}
                      className={`rounded-lg border p-3 text-left text-sm transition ${selectedProvider === method.provider ? 'border-primary bg-primary/5 ring-1 ring-primary' : 'hover:bg-muted'}`}
                    >
                      <span className="font-medium">{method.label}</span>
                      {method.recipient && (
                        <span className="mt-1 block text-xs text-muted-foreground">
                          收款人：{method.recipient}
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              </div>
              <p className="text-xs text-muted-foreground">
                点击“创建订单”即锁定服务端套餐价格。请勿直接转账后再下单。
              </p>
              <DialogFooter>
                <Button variant="outline" onClick={resetCheckout}>
                  取消
                </Button>
                <Button
                  onClick={() => void createOrder()}
                  disabled={!selectedProvider || Boolean(busy)}
                >
                  创建订单
                </Button>
              </DialogFooter>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-[230px_1fr]">
                <div className="rounded-xl border bg-white p-3">
                  {selectedMethod && (
                    <img
                      src={selectedMethod.qr_code_url}
                      alt={selectedMethod.label}
                      className="aspect-square w-full object-contain"
                      referrerPolicy="no-referrer"
                    />
                  )}
                </div>
                <div className="space-y-3 text-sm">
                  <div>
                    <p className="text-muted-foreground">应付金额</p>
                    <p className="text-3xl font-semibold text-primary">
                      {money(checkoutOrder.amount_cents)}
                    </p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">
                      订单号（建议填写为付款备注）
                    </p>
                    <p className="break-all font-mono text-xs">
                      {String(checkoutOrder.order_no)}
                    </p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">收款方式</p>
                    <p>
                      {selectedMethod?.label}
                      {selectedMethod?.recipient
                        ? ` · ${selectedMethod.recipient}`
                        : ''}
                    </p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">订单有效期</p>
                    <p>{date(checkoutOrder.expires_at)}</p>
                  </div>
                </div>
              </div>

              <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-xs leading-5 text-amber-900">
                请核对收款人并支付准确金额。不要在付款信息中填写密码、验证码或完整银行卡号。扫码本身不代表支付成功。
              </div>

              {!claimSubmitted && !checkoutOrder.payment_claimed_at ? (
                <div className="space-y-3">
                  <div>
                    <label
                      className="mb-1.5 block text-sm font-medium"
                      htmlFor="payment-claim-note"
                    >
                      付款账号昵称 / 核对信息
                    </label>
                    <Input
                      id="payment-claim-note"
                      value={paymentClaimNote}
                      maxLength={120}
                      onChange={(event) =>
                        setPaymentClaimNote(event.target.value)
                      }
                      placeholder="例如：微信昵称小明"
                    />
                  </div>
                  <div>
                    <label
                      className="mb-1.5 block text-sm font-medium"
                      htmlFor="payment-reference"
                    >
                      支付流水号尾号（选填）
                    </label>
                    <Input
                      id="payment-reference"
                      value={paymentReference}
                      maxLength={64}
                      onChange={(event) =>
                        setPaymentReference(event.target.value)
                      }
                      placeholder="建议填写账单流水号后 6～12 位"
                    />
                  </div>
                  <DialogFooter>
                    <Button variant="outline" onClick={resetCheckout}>
                      稍后处理
                    </Button>
                    <Button
                      onClick={() => void submitPaymentClaim()}
                      disabled={busy === String(checkoutOrder.id)}
                    >
                      我已付款，提交核对
                    </Button>
                  </DialogFooter>
                </div>
              ) : (
                <div className="rounded-lg border border-emerald-300 bg-emerald-50 p-4 text-sm text-emerald-900">
                  付款信息已提交，管理员核对实际到账后会开通权益。请勿重复付款。
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </main>
  )
}
