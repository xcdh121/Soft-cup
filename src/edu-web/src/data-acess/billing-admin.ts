import { authClient } from '@/lib/auth-client'

const baseUrl = import.meta.env.VITE_SERVER_URL ?? window.location.origin

export type BillingPlan = {
  id: string
  code: string
  name: string
  description?: string
  price_cents: number
  currency: string
  duration_days: number
  quotas: Record<string, number>
  features: Record<string, unknown>
  is_active: boolean
}

export type ManualPaymentMethod = {
  provider: 'manual_wechat' | 'manual_qq'
  label: string
  qr_code_url: string
  recipient: string
  instructions: string
}

export type Page<T> = {
  items: Array<T>
  total: number
  page: number
  page_size: number
  pages: number
}

const request = async <T>(path: string, init?: RequestInit): Promise<T> => {
  const {
    data: { session },
  } = await authClient.auth.getSession()
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: {
      ...(init?.body && !(init.body instanceof FormData)
        ? { 'Content-Type': 'application/json' }
        : {}),
      ...(session ? { Authorization: `Bearer ${session.access_token}` } : {}),
      ...init?.headers,
    },
  })
  const payload = (await response.json().catch(() => null)) as {
    detail?: string
    error?: { message?: string }
  } | null
  if (!response.ok) {
    throw new Error(
      payload?.error?.message ??
        payload?.detail ??
        `请求失败（${response.status}）`,
    )
  }
  return payload as T
}

export const billingApi = {
  plans: () => request<Array<BillingPlan>>('/api/v1/billing/plans'),
  summary: () => request<Record<string, unknown>>('/api/v1/billing/me'),
  orders: () =>
    request<Array<Record<string, unknown>>>('/api/v1/billing/orders'),
  paymentMethods: () =>
    request<Array<ManualPaymentMethod>>('/api/v1/billing/payment-methods'),
  createOrder: (planCode: string, provider: ManualPaymentMethod['provider']) =>
    request<Record<string, unknown>>('/api/v1/billing/orders', {
      method: 'POST',
      body: JSON.stringify({ plan_code: planCode, provider }),
    }),
  submitPaymentClaim: (
    orderNo: string,
    paymentClaimNote: string,
    paymentReference?: string,
  ) =>
    request<Record<string, unknown>>(
      `/api/v1/billing/orders/${orderNo}/payment-claim`,
      {
        method: 'POST',
        body: JSON.stringify({
          payment_claim_note: paymentClaimNote,
          payment_reference: paymentReference || null,
        }),
      },
    ),
}

export const adminApi = {
  overview: () => request<Record<string, any>>('/api/v1/admin/overview'),
  users: (search = '') =>
    request<Page<Record<string, any>>>(
      `/api/v1/admin/users?page_size=50&search=${encodeURIComponent(search)}`,
    ),
  user: (id: string) =>
    request<Record<string, any>>(`/api/v1/admin/users/${id}`),
  updateUser: (id: string, body: Record<string, unknown>) =>
    request(`/api/v1/admin/users/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  grant: (id: string, planId: string, reason: string) =>
    request(`/api/v1/admin/users/${id}/entitlements`, {
      method: 'POST',
      body: JSON.stringify({ plan_id: planId, reason }),
    }),
  orders: (search = '') =>
    request<Page<Record<string, any>>>(
      `/api/v1/admin/orders?page_size=50&search=${encodeURIComponent(search)}`,
    ),
  confirmOrder: (orderNo: string, reason: string) =>
    request(`/api/v1/admin/orders/${orderNo}/confirm-payment`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),
  refundOrder: (orderNo: string, reason: string) =>
    request(`/api/v1/admin/orders/${orderNo}/refund`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),
  runs: () =>
    request<Page<Record<string, any>>>('/api/v1/admin/agent-runs?page_size=50'),
  run: (id: string) =>
    request<Record<string, any>>(`/api/v1/admin/agent-runs/${id}`),
  handleRun: (id: string, reason: string) =>
    request(`/api/v1/admin/agent-runs/${id}/handling`, {
      method: 'PATCH',
      body: JSON.stringify({ handled: true, reason }),
    }),
  retryRun: (id: string, reason: string) =>
    request(`/api/v1/admin/agent-runs/${id}/retry`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),
  courses: () =>
    request<Page<Record<string, any>>>('/api/v1/admin/courses?page_size=50'),
  uploadCourseCover: (file: File) => {
    const body = new FormData()
    body.append('file', file)
    return request<{ url: string }>('/api/v1/admin/course-covers', {
      method: 'POST',
      body,
    })
  },
  createCourse: (body: {
    name: string
    code?: string
    description?: string
    cover_url?: string
    status: 'active' | 'draft' | 'archived'
  }) =>
    request('/api/v1/admin/courses', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  courseAction: (id: string, action: string, reason: string) =>
    request(`/api/v1/admin/courses/${id}/${action}`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),
  plans: () => request<Array<BillingPlan>>('/api/v1/admin/billing-plans'),
  updatePlan: (id: string, body: Record<string, unknown>) =>
    request(`/api/v1/admin/billing-plans/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  audits: () =>
    request<Page<Record<string, any>>>('/api/v1/admin/audit-logs?page_size=50'),
}
