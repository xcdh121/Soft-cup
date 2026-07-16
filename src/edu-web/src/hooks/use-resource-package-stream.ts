import { useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import { useEffect, useRef } from 'react'
import type {
  ResourcePackage,
  ResourcePackageProgress,
  ResourcePackageStreamEvent,
} from '@/data-acess/resource-package'
import {
  applyResourcePackageStreamEvent,
  resourcePackageProgressAtom,
} from '@/data-acess/resource-package'
import { env } from '@/env'
import { authClient } from '@/lib/auth-client'
import { appendSseChunk } from '@/lib/sse'

const serverUrl = (env.VITE_SERVER_URL ?? window.location.origin).replace(
  /\/$/,
  '',
)

export const useResourcePackageStream = ({
  projectId,
  packageId,
}: {
  projectId: string
  packageId?: string
}) => {
  const progress = useAtomValue(resourcePackageProgressAtom)
  const setProgress = useAtomSet(resourcePackageProgressAtom)
  const progressRef = useRef<ResourcePackageProgress | null>(progress)

  useEffect(() => {
    if (
      progress?.projectId === projectId &&
      (!packageId || !progress.packageId || progress.packageId === packageId)
    ) {
      progressRef.current = progress
    }
  }, [packageId, progress, projectId])

  useEffect(() => {
    if (!packageId) return

    const controller = new AbortController()
    let cancelled = false

    const applyEvent = (event: ResourcePackageStreamEvent) => {
      if (cancelled || event.package_id !== packageId) return
      const next = applyResourcePackageStreamEvent(progressRef.current, event, {
        projectId,
      })
      progressRef.current = next
      setProgress(next)
    }

    const getHeaders = async () => {
      const { data } = await authClient.auth.getSession()
      return {
        Accept: 'text/event-stream',
        ...(data.session?.access_token
          ? { Authorization: `Bearer ${data.session.access_token}` }
          : {}),
      }
    }

    const refreshSnapshot = async (headers: Record<string, string>) => {
      const response = await fetch(
        `${serverUrl}/api/v1/projects/${projectId}/resource-packages/${packageId}`,
        { headers, signal: controller.signal },
      )
      if (!response.ok) return
      const resourcePackage = (await response.json()) as ResourcePackage
      applyEvent({
        event: 'package_snapshot',
        package_id: packageId,
        payload: { package: resourcePackage },
      })
    }

    const connect = async () => {
      while (!cancelled) {
        const headers = await getHeaders()
        try {
          const response = await fetch(
            `${serverUrl}/api/v1/projects/${projectId}/resource-packages/${packageId}/stream`,
            { headers, signal: controller.signal },
          )
          if (!response.ok || !response.body) {
            await refreshSnapshot(headers)
          } else {
            const reader = response.body.getReader()
            const decoder = new TextDecoder()
            let buffer = ''
            for (;;) {
              const { done, value } = await reader.read()
              if (done) break
              const parsed = appendSseChunk(
                buffer,
                decoder.decode(value, { stream: true }),
              )
              buffer = parsed.buffer
              for (const block of parsed.blocks) {
                const data = block
                  .split('\n')
                  .filter((line) => line.startsWith('data: '))
                  .map((line) => line.slice(6))
                  .join('\n')
                if (data)
                  applyEvent(JSON.parse(data) as ResourcePackageStreamEvent)
              }
            }
          }
        } catch {
          if (controller.signal.aborted) return
          await refreshSnapshot(headers).catch(() => undefined)
        }

        const current = progressRef.current
        if (
          current?.packageId === packageId &&
          (current.status === 'completed' || current.status === 'failed')
        ) {
          return
        }
        await new Promise((resolve) => window.setTimeout(resolve, 750))
      }
    }

    void connect()
    return () => {
      cancelled = true
      controller.abort()
    }
  }, [packageId, projectId, setProgress])
}
