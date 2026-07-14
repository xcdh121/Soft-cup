const TEXT_KEYS = ['displayContent', 'content', 'text'] as const
const NESTED_KEYS = ['answer', 'payload', 'nlp', 'asr', 'data'] as const

const extractText = (value: unknown, visited: Set<unknown>): string => {
  if (typeof value === 'string') {
    const text = value.trim()
    if (!text) return ''

    if (
      (text.startsWith('{') && text.endsWith('}')) ||
      (text.startsWith('[') && text.endsWith(']'))
    ) {
      try {
        return extractText(JSON.parse(text), visited) || text
      } catch {
        return text
      }
    }

    return text
  }

  if (!value || typeof value !== 'object' || visited.has(value)) return ''
  visited.add(value)

  const record = value as Record<string, unknown>
  for (const key of TEXT_KEYS) {
    const text = extractText(record[key], visited)
    if (text) return text
  }

  for (const key of NESTED_KEYS) {
    const text = extractText(record[key], visited)
    if (text) return text
  }

  return ''
}

export const getAvatarEventText = (event: unknown) =>
  extractText(event, new Set())

export const getAvatarEventStatus = (event: unknown) => {
  if (!event || typeof event !== 'object') return undefined
  const status = (event as Record<string, unknown>).status
  return typeof status === 'number' ? status : undefined
}
