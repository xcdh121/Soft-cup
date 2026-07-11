import { useLocation } from '@tanstack/react-router'
import { SparklesIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useResourcePackageSheet } from './resource-package-sheet'

const projectRoutePattern = /^\/dashboard\/p\/([^/]+)(?:\/([^/]+)\/([^/]+))?/

const getLaunchContext = (pathname: string) => {
  if (pathname.includes('/q/')) return 'quiz practice'
  if (pathname.includes('/f/')) return 'flashcard practice'
  if (pathname.includes('/c/')) return 'chat session'
  if (pathname.includes('/d/')) return 'document review'
  if (pathname.includes('/n/')) return 'note review'
  if (pathname.includes('/m/')) return 'mind map review'
  return 'project workspace'
}

export const ResourcePackageFloatingButton = () => {
  const location = useLocation()
  const openSheet = useResourcePackageSheet((state) => state.open)

  const match = location.pathname.match(projectRoutePattern)
  const projectId = match?.[1]
  const isDocumentReviewRoute = location.pathname.includes('/d/')

  if (!projectId || isDocumentReviewRoute) return null

  return (
    <div className="pointer-events-none fixed right-6 bottom-6 z-40">
      <Button
        type="button"
        size="lg"
        className="pointer-events-auto h-14 rounded-full px-5 shadow-xl"
        onClick={() => openSheet(projectId, getLaunchContext(location.pathname))}
      >
        <SparklesIcon className="size-5" />
        <span>Resource Pack</span>
      </Button>
    </div>
  )
}
