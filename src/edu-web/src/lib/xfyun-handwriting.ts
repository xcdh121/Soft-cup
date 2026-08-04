import { env } from '@/env'
import { authClient } from '@/lib/auth-client'

export type HandwritingRecognitionLine = {
  text: string
  confidence: number | null
  location: Record<string, unknown> | null
}

export type HandwritingRecognitionResult = {
  text: string
  lines: Array<HandwritingRecognitionLine>
  sid: string | null
}

const getErrorMessage = async (response: Response) => {
  try {
    const body = (await response.json()) as { detail?: string }
    return body.detail ?? `识别失败（${response.status}）`
  } catch {
    return `识别失败（${response.status}）`
  }
}

export const recognizeHandwriting = async ({
  projectId,
  image,
  language,
}: {
  projectId: string
  image: File
  language: 'cn|en' | 'en'
}): Promise<HandwritingRecognitionResult> => {
  const {
    data: { session },
  } = await authClient.auth.getSession()
  const headers: HeadersInit = {}
  if (session?.access_token) {
    headers.Authorization = `Bearer ${session.access_token}`
  }

  const formData = new FormData()
  formData.append('image', image)
  formData.append('language', language)
  formData.append('include_location', 'false')

  const baseUrl = env.VITE_SERVER_URL ?? window.location.origin
  const response = await fetch(
    `${baseUrl}/api/v1/projects/${encodeURIComponent(projectId)}/handwriting-recognition/recognize`,
    {
      method: 'POST',
      headers,
      body: formData,
    },
  )

  if (!response.ok) {
    throw new Error(await getErrorMessage(response))
  }
  return response.json()
}
