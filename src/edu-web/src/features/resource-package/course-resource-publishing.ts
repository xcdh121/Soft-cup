import type {
  KnowledgePoint,
  ProjectCourseOutline,
} from '@/data-acess/course-library'
import type { GeneratedResource } from '@/data-acess/resource-package'

const normalize = (value: string) =>
  value.toLocaleLowerCase().replace(/[\s\p{P}\p{S}]+/gu, '')

const meaningfulParts = (value: string) =>
  value
    .toLocaleLowerCase()
    .split(/[\s、，,。；;：:·/\\|（）()【】与和及]+/u)
    .map(normalize)
    .filter((part) => part.length >= 2)

const scorePoint = (resourceText: string, point: KnowledgePoint) => {
  const normalizedName = normalize(point.name)
  let score = normalizedName && resourceText.includes(normalizedName) ? 100 : 0

  for (const part of meaningfulParts(point.name)) {
    if (resourceText.includes(part)) score += 12
  }
  for (const tag of point.tags) {
    const normalizedTag = normalize(tag)
    if (normalizedTag.length >= 2 && resourceText.includes(normalizedTag)) {
      score += 5
    }
  }

  return score
}

/**
 * Resolve one primary course knowledge point for a generated resource.
 *
 * Resource packages often inherit every knowledge-point id selected for the
 * generation request. Linking all of those ids would repeat the same content
 * across an entire chapter, so publishing deliberately chooses one strong
 * match and leaves ambiguous resources for manual review.
 */
export const resolveCoursePublishTarget = (
  resource: GeneratedResource,
  courseOutline: ProjectCourseOutline,
): KnowledgePoint | null => {
  const allowedIds = new Set(resource.knowledge_point_ids)
  const candidates = courseOutline.knowledgePoints.filter(
    (point) => allowedIds.size === 0 || allowedIds.has(point.id),
  )

  if (candidates.length === 1) return candidates[0]

  const resourceText = normalize(
    [resource.title, resource.summary ?? ''].join(' '),
  )
  const ranked = candidates
    .map((point) => ({ point, score: scorePoint(resourceText, point) }))
    .sort(
      (left, right) =>
        right.score - left.score || left.point.position - right.point.position,
    )

  return ranked[0]?.score > 0 ? ranked[0].point : null
}

export const getPublishableCourseResources = (
  resources: Array<GeneratedResource>,
  courseOutline: ProjectCourseOutline | null,
) => {
  if (!courseOutline?.courseId) return []

  return resources
    .filter((resource) => resource.status === 'completed')
    .map((resource) => ({
      resource,
      point: resolveCoursePublishTarget(resource, courseOutline),
    }))
}
