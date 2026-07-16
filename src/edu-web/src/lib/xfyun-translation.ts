import { env } from '@/env'
import { authClient } from '@/lib/auth-client'

export type TranslationResult = {
  source_text: string
  translated_text: string
  from_language: string
  to_language: string
  sid: string | null
  chunk_count: number
}

const getErrorMessage = async (response: Response) => {
  try {
    const body = (await response.json()) as { detail?: string }
    return body.detail ?? `翻译失败（${response.status}）`
  } catch {
    return `翻译失败（${response.status}）`
  }
}

export const translateDocument = async ({
  projectId,
  text,
  fromLanguage,
  toLanguage,
}: {
  projectId: string
  text: string
  fromLanguage: string
  toLanguage: string
}): Promise<TranslationResult> => {
  const {
    data: { session },
  } = await authClient.auth.getSession()
  const baseUrl = env.VITE_SERVER_URL ?? window.location.origin
  const response = await fetch(
    `${baseUrl}/api/v1/projects/${encodeURIComponent(projectId)}/document-translation/translate`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(session?.access_token
          ? { Authorization: `Bearer ${session.access_token}` }
          : {}),
      },
      body: JSON.stringify({
        text,
        from_language: fromLanguage,
        to_language: toLanguage,
      }),
    },
  )
  if (!response.ok) throw new Error(await getErrorMessage(response))
  return response.json()
}
