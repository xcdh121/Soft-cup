import { env } from '@/env'
import { authClient } from '@/lib/auth-client'

export type ImportedResourcePackage = {
  id: string
  title: string
}

type ImportResourceInput = {
  projectId: string
  title: string
  summary: string
  origin: 'handwriting' | 'pdf_ocr' | 'translation'
  resourceType: 'lecture_note' | 'reading_material'
  contentFormat: string
  contentText?: string
  fileUrl?: string
}

const getErrorMessage = async (response: Response) => {
  try {
    const body = (await response.json()) as { detail?: string }
    return body.detail ?? `保存失败（${response.status}）`
  } catch {
    return `保存失败（${response.status}）`
  }
}

export const importResourcePackage = async (
  input: ImportResourceInput,
): Promise<ImportedResourcePackage> => {
  const {
    data: { session },
  } = await authClient.auth.getSession()
  const baseUrl = env.VITE_SERVER_URL ?? 'http://localhost:8000'
  const response = await fetch(
    `${baseUrl}/api/v1/projects/${encodeURIComponent(input.projectId)}/resource-packages/import`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(session?.access_token
          ? { Authorization: `Bearer ${session.access_token}` }
          : {}),
      },
      body: JSON.stringify({
        title: input.title,
        summary: input.summary,
        origin: input.origin,
        resource_type: input.resourceType,
        content_format: input.contentFormat,
        content_text: input.contentText,
        file_url: input.fileUrl,
      }),
    },
  )
  if (!response.ok) throw new Error(await getErrorMessage(response))
  return response.json()
}
