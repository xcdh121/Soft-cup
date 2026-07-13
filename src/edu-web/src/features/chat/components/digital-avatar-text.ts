const MAX_SPEECH_CHUNK_LENGTH = 1800

export const prepareSpeechText = (text: string) =>
  text
    .replace(/```[\s\S]*?```/g, ' 代码内容已省略。 ')
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/^\s{0,3}#{1,6}\s+/gm, '')
    .replace(/^\s*[-*+]\s+/gm, '')
    .replace(/^\s*\d+[.)]\s+/gm, '')
    .replace(/[>*_~]/g, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim()

export const splitSpeechText = (
  text: string,
  maxLength = MAX_SPEECH_CHUNK_LENGTH,
) => {
  const chunks: Array<string> = []
  let remaining = text.trim()
  const sentenceBoundaries = [
    '\n',
    '。',
    '！',
    '？',
    '；',
    '. ',
    '! ',
    '? ',
    '; ',
  ]

  while (remaining.length > maxLength) {
    const candidate = remaining.slice(0, maxLength)
    const minimumBoundary = Math.floor(maxLength * 0.5)
    let splitAt = -1

    for (const boundary of sentenceBoundaries) {
      const boundaryIndex = candidate.lastIndexOf(boundary)
      if (boundaryIndex >= minimumBoundary) {
        splitAt = Math.max(splitAt, boundaryIndex + boundary.length)
      }
    }

    if (splitAt < 1) splitAt = maxLength

    const chunk = remaining.slice(0, splitAt).trim()
    if (chunk) chunks.push(chunk)
    remaining = remaining.slice(splitAt).trim()
  }

  if (remaining) chunks.push(remaining)
  return chunks
}
