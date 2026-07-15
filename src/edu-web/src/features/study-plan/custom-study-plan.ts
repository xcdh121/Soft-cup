export type CustomStudyPlanEntry = {
  date: string
  topic: string
  task: string
  startTime: string
  duration: string
  goal: string
}

const storageKey = (projectId: string) => `edu-custom-study-plan:${projectId}`

export const loadCustomStudyPlan = (
  projectId: string,
): Array<CustomStudyPlanEntry> => {
  if (typeof window === 'undefined') return []

  try {
    const stored = window.localStorage.getItem(storageKey(projectId))
    if (!stored) return []

    const parsed = JSON.parse(stored)
    if (!Array.isArray(parsed)) return []

    return parsed.filter(
      (entry): entry is CustomStudyPlanEntry =>
        typeof entry?.date === 'string' &&
        typeof entry?.topic === 'string' &&
        typeof entry?.task === 'string' &&
        typeof entry?.startTime === 'string' &&
        typeof entry?.duration === 'string' &&
        typeof entry?.goal === 'string',
    )
  } catch {
    return []
  }
}

export const saveCustomStudyPlan = (
  projectId: string,
  entries: Array<CustomStudyPlanEntry>,
) => {
  window.localStorage.setItem(storageKey(projectId), JSON.stringify(entries))
}
