import { documentsAtom, refreshDocumentAtom } from '@/data-acess/document'
import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import { useEffect, useMemo } from 'react'

const POLL_INTERVAL_MS = 3000 // Poll every 3 seconds

/**
 * Hook that automatically polls for document status updates when there are
 * documents that are not yet ready.
 */
export const useDocumentPolling = (projectId: string) => {
  const documentsResult = useAtomValue(documentsAtom(projectId))
  const refreshDocument = useAtomSet(refreshDocumentAtom, {
    mode: 'promise',
  })

  // Get list of unready document IDs
  const unreadyDocumentIds = useMemo(() => {
    if (Result.isSuccess(documentsResult)) {
      return documentsResult.value
        .filter(
          (doc) =>
            doc.status !== 'processed' &&
            doc.status !== 'indexed' &&
            doc.status !== 'failed',
        )
        .map((doc) => doc.id)
    }
    return []
  }, [documentsResult])

  useEffect(() => {
    if (projectId.length === 0 || unreadyDocumentIds.length === 0) return

    let cancelled = false
    let timeoutId: ReturnType<typeof setTimeout> | undefined
    const pendingDocumentIds = new Set(unreadyDocumentIds)

    const poll = async () => {
      await Promise.all(
        [...pendingDocumentIds].map(async (documentId) => {
          try {
            const document = await refreshDocument({ projectId, documentId })
            if (
              document.status === 'processed' ||
              document.status === 'indexed' ||
              document.status === 'failed'
            ) {
              pendingDocumentIds.delete(documentId)
            }
          } catch {
            // Keep transient failures pending. The next scheduled poll can retry.
          }
        }),
      )

      if (!cancelled && pendingDocumentIds.size > 0) {
        timeoutId = setTimeout(() => void poll(), POLL_INTERVAL_MS)
      }
    }

    // Check immediately so a ready document can open without an extra delay.
    void poll()

    return () => {
      cancelled = true
      if (timeoutId !== undefined) clearTimeout(timeoutId)
    }
  }, [unreadyDocumentIds, projectId, refreshDocument])
}
