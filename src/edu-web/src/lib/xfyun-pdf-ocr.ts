import { env } from '@/env'
import { authClient } from '@/lib/auth-client'

export type PdfOcrExportFormat = 'word' | 'markdown' | 'json'
export type PdfOcrStatus =
  | 'CREATE'
  | 'WAITING'
  | 'DOING'
  | 'FINISH'
  | 'FAILED'
  | 'ANY_FAILED'
  | 'STOP'

export type PdfOcrPage = {
  page_number: number | null
  source_url: string | null
  download_url: string | null
  status: string
  tip: string | null
}

export type PdfOcrTask = {
  task_no: string
  export_format: PdfOcrExportFormat | null
  status: PdfOcrStatus
  download_url: string | null
  tip: string | null
  pages: Array<PdfOcrPage>
}

export type PdfOcrText = {
  content_text: string
  truncated: boolean
}

export type ChatPdfAttachment = {
  file_name: string
  file_type: 'application/pdf'
  file_url: string
}

const getHeaders = async (): Promise<HeadersInit> => {
  const {
    data: { session },
  } = await authClient.auth.getSession()
  return session?.access_token
    ? { Authorization: `Bearer ${session.access_token}` }
    : {}
}

const getErrorMessage = async (response: Response) => {
  try {
    const body = (await response.json()) as { detail?: string }
    return body.detail ?? `请求失败（${response.status}）`
  } catch {
    return `请求失败（${response.status}）`
  }
}

const taskUrl = (projectId: string, taskNo?: string) => {
  const baseUrl = env.VITE_SERVER_URL ?? 'http://localhost:8000'
  const root = `${baseUrl}/api/v1/projects/${encodeURIComponent(projectId)}/pdf-ocr/tasks`
  return taskNo ? `${root}/${encodeURIComponent(taskNo)}` : root
}

export const startPdfOcrTask = async ({
  projectId,
  file,
  exportFormat,
}: {
  projectId: string
  file: File
  exportFormat: PdfOcrExportFormat
}): Promise<PdfOcrTask> => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('export_format', exportFormat)
  const response = await fetch(taskUrl(projectId), {
    method: 'POST',
    headers: await getHeaders(),
    body: formData,
  })
  if (!response.ok) throw new Error(await getErrorMessage(response))
  return response.json()
}

export const getPdfOcrTask = async ({
  projectId,
  taskNo,
}: {
  projectId: string
  taskNo: string
}): Promise<PdfOcrTask> => {
  const response = await fetch(taskUrl(projectId, taskNo), {
    headers: await getHeaders(),
  })
  if (!response.ok) throw new Error(await getErrorMessage(response))
  return response.json()
}

export const getPdfOcrText = async ({
  projectId,
  taskNo,
}: {
  projectId: string
  taskNo: string
}): Promise<PdfOcrText> => {
  const response = await fetch(`${taskUrl(projectId, taskNo)}/text`, {
    headers: await getHeaders(),
  })
  if (!response.ok) throw new Error(await getErrorMessage(response))
  return response.json()
}

export const uploadChatPdfAttachment = async ({
  projectId,
  chatId,
  file,
}: {
  projectId: string
  chatId: string
  file: File
}): Promise<ChatPdfAttachment> => {
  const baseUrl = env.VITE_SERVER_URL ?? 'http://localhost:8000'
  const formData = new FormData()
  formData.append('file', file)
  const response = await fetch(
    `${baseUrl}/api/v1/projects/${encodeURIComponent(projectId)}/chats/${encodeURIComponent(chatId)}/files`,
    {
      method: 'POST',
      headers: await getHeaders(),
      body: formData,
    },
  )
  if (!response.ok) throw new Error(await getErrorMessage(response))
  return response.json()
}
