export type LearningVerificationContext = {
  projectId: string
  recommendationId: string
  learningPathId: string
  learningPathStepId: string
  knowledgePointId: string
  objective: string
  activatedAt: string
}

const STORAGE_KEY = 'edu.learning-verification.v1'
const MAX_CONTEXT_AGE_MS = 24 * 60 * 60 * 1000

const getStorage = (): Storage | null => {
  if (typeof window === 'undefined') return null
  try {
    return window.sessionStorage
  } catch {
    return null
  }
}

export const activateLearningVerification = (
  context: Omit<LearningVerificationContext, 'activatedAt'>,
) => {
  getStorage()?.setItem(
    STORAGE_KEY,
    JSON.stringify({ ...context, activatedAt: new Date().toISOString() }),
  )
}

export const readLearningVerification = (
  projectId: string,
): LearningVerificationContext | null => {
  const storage = getStorage()
  const value = storage?.getItem(STORAGE_KEY)
  if (!storage || !value) return null
  try {
    const context = JSON.parse(value) as LearningVerificationContext
    const valid =
      context.projectId === projectId &&
      Boolean(context.recommendationId) &&
      Boolean(context.learningPathId) &&
      Boolean(context.learningPathStepId) &&
      Boolean(context.knowledgePointId) &&
      Date.now() - new Date(context.activatedAt).getTime() <= MAX_CONTEXT_AGE_MS
    if (valid) return context
  } catch {
    // Invalid context is discarded below.
  }
  storage.removeItem(STORAGE_KEY)
  return null
}

export const consumeLearningVerification = (
  projectId: string,
  knowledgePointId: string | null | undefined,
): LearningVerificationContext | null => {
  const context = readLearningVerification(projectId)
  if (!context || context.knowledgePointId !== knowledgePointId) return null
  getStorage()?.removeItem(STORAGE_KEY)
  return context
}
