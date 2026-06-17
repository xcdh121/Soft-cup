import { create } from 'zustand'
import { useMemo, useState } from 'react'
import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import { FileTextIcon, Loader2Icon, SparklesIcon } from 'lucide-react'
import { indexedDocumentsAtom } from '@/data-acess/document'
import {
  type DifficultyLevel,
  type GeneratedResource,
  type ResourcePackage,
  type ResourceType,
  generateResourcePackageAtom,
  generatedResourcesAtom,
  resourcePackagesAtom,
} from '@/data-acess/resource-package'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'

type ResourcePackageSheetStore = {
  isOpen: boolean
  projectId: string | null
  contextLabel?: string
  open: (projectId: string, contextLabel?: string) => void
  close: () => void
}

export const useResourcePackageSheet = create<ResourcePackageSheetStore>(
  (set) => ({
    isOpen: false,
    projectId: null,
    contextLabel: undefined,
    open: (projectId: string, contextLabel?: string) =>
      set({ isOpen: true, projectId, contextLabel }),
    close: () =>
      set({ isOpen: false, projectId: null, contextLabel: undefined }),
  }),
)

const RESOURCE_TYPE_OPTIONS: Array<{
  value: ResourceType
  label: string
  description: string
}> = [
  {
    value: 'lecture_note',
    label: 'Lecture note',
    description: 'Structured explanation document',
  },
  {
    value: 'mind_map',
    label: 'Mind map',
    description: 'Visual concept structure',
  },
  {
    value: 'practice_set',
    label: 'Practice set',
    description: 'Layered practice questions',
  },
  {
    value: 'flashcards',
    label: 'Flashcards',
    description: 'Queued flashcard group generation',
  },
  {
    value: 'ppt_outline',
    label: 'PPT outline',
    description: 'Slide-by-slide speaking outline',
  },
  {
    value: 'pptx',
    label: 'PPTX',
    description: 'Generated presentation file link',
  },
]

const difficultyOptions: Array<{
  value: DifficultyLevel
  label: string
}> = [
  { value: 'beginner', label: 'Beginner' },
  { value: 'intermediate', label: 'Intermediate' },
  { value: 'advanced', label: 'Advanced' },
]

const resourceTypeLabelMap = new Map(
  RESOURCE_TYPE_OPTIONS.map((option) => [option.value, option.label]),
)

const statusToneMap: Record<
  ResourcePackage['status'] | GeneratedResource['status'],
  'default' | 'secondary' | 'destructive' | 'outline'
> = {
  draft: 'outline',
  generating: 'secondary',
  completed: 'default',
  failed: 'destructive',
  pending: 'outline',
}

const ResourcePackageList = ({
  projectId,
  selectedPackageId,
  onSelect,
}: {
  projectId: string
  selectedPackageId: string | null
  onSelect: (resourcePackage: ResourcePackage) => void
}) => {
  const packagesResult = useAtomValue(resourcePackagesAtom(projectId))
  const packages = Result.isSuccess(packagesResult) ? packagesResult.value : []

  if (packagesResult.waiting) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2Icon className="size-4 animate-spin" />
        <span>Loading packages...</span>
      </div>
    )
  }

  if (!Result.isSuccess(packagesResult)) {
    return (
      <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-3 text-sm text-destructive">
        Failed to load resource packages.
      </div>
    )
  }

  if (packages.length === 0) {
    return (
      <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
        No resource packages yet. Generate one from the panel above.
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {packages.map((resourcePackage: ResourcePackage) => {
        const isActive = resourcePackage.id === selectedPackageId
        return (
          <button
            key={resourcePackage.id}
            type="button"
            onClick={() => onSelect(resourcePackage)}
            className={cn(
              'w-full rounded-xl border p-3 text-left transition-colors',
              isActive
                ? 'border-primary bg-primary/5'
                : 'hover:bg-muted/40 hover:border-muted-foreground/30',
            )}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-1">
                <div className="font-medium">{resourcePackage.title}</div>
                <div className="text-sm text-muted-foreground">
                  {resourcePackage.target_topic}
                </div>
              </div>
              <Badge variant={statusToneMap[resourcePackage.status]}>
                {resourcePackage.status}
              </Badge>
            </div>
            <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
              <span>
                {resourcePackage.completed_resource_count}/
                {resourcePackage.resource_count} resources
              </span>
              {resourcePackage.estimated_minutes ? (
                <span>{resourcePackage.estimated_minutes} min</span>
              ) : null}
              <span>{resourcePackage.difficulty_level}</span>
            </div>
          </button>
        )
      })}
    </div>
  )
}

const ResourcePreview = ({
  projectId,
  resourcePackage,
}: {
  projectId: string
  resourcePackage: ResourcePackage
}) => {
  const resourcesResult = useAtomValue(
    generatedResourcesAtom(`${projectId}:${resourcePackage.id}`),
  )
  const resources = Result.isSuccess(resourcesResult) ? resourcesResult.value : []

  if (resourcesResult.waiting) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2Icon className="size-4 animate-spin" />
        <span>Loading resources...</span>
      </div>
    )
  }

  if (!Result.isSuccess(resourcesResult)) {
    return (
      <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-3 text-sm text-destructive">
        Failed to load generated resources.
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {resources.map((resource: GeneratedResource) => (
        <div key={resource.id} className="rounded-xl border p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="font-medium">{resource.title}</div>
              <div className="mt-1 text-sm text-muted-foreground">
                {resource.summary ?? 'No summary yet.'}
              </div>
            </div>
            <Badge variant={statusToneMap[resource.status]}>
              {resource.status}
            </Badge>
          </div>

          <div className="mt-3 flex flex-wrap gap-2">
            <Badge variant="outline">
              {resourceTypeLabelMap.get(resource.resource_type) ??
                resource.resource_type}
            </Badge>
            <Badge variant="outline">{resource.format}</Badge>
            <Badge variant="outline">{resource.difficulty_level}</Badge>
          </div>

          {resource.file_url ? (
            <div className="mt-3">
              <a
                href={resource.file_url}
                target="_blank"
                rel="noreferrer"
                className="text-sm text-primary underline underline-offset-4"
              >
                Open generated PPT
              </a>
            </div>
          ) : resource.content_text ? (
            <div className="mt-3 rounded-lg bg-muted/40 p-3 text-sm whitespace-pre-wrap">
              {resource.content_text.slice(0, 600)}
              {resource.content_text.length > 600 ? '...' : ''}
            </div>
          ) : resource.content_json ? (
            <pre className="mt-3 overflow-x-auto rounded-lg bg-muted/40 p-3 text-xs">
              {JSON.stringify(resource.content_json, null, 2)}
            </pre>
          ) : null}
        </div>
      ))}
    </div>
  )
}

const ResourcePreviewPanel = ({
  projectId,
  resourcePackage,
}: {
  projectId: string
  resourcePackage: ResourcePackage | null
}) => {
  if (!resourcePackage) {
    return (
      <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
        Select a package to preview its generated resources.
      </div>
    )
  }

  return (
    <ResourcePreview projectId={projectId} resourcePackage={resourcePackage} />
  )
}

const ResourcePackageSheetBody = ({
  projectId,
  contextLabel,
  onClose,
}: {
  projectId: string
  contextLabel?: string
  onClose: () => void
}) => {
  const generateResourcePackage = useAtomSet(generateResourcePackageAtom, {
    mode: 'promise',
  })
  const documentsResult = useAtomValue(indexedDocumentsAtom(projectId))

  const [title, setTitle] = useState('')
  const [topic, setTopic] = useState('')
  const [goal, setGoal] = useState('')
  const [instructions, setInstructions] = useState('')
  const [difficulty, setDifficulty] =
    useState<DifficultyLevel>('intermediate')
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<Set<string>>(
    new Set(),
  )
  const [selectedTypes, setSelectedTypes] = useState<Array<ResourceType>>([
    'lecture_note',
    'mind_map',
    'practice_set',
    'flashcards',
    'ppt_outline',
    'pptx',
  ])
  const [selectedPackage, setSelectedPackage] = useState<ResourcePackage | null>(
    null,
  )
  const [isSubmitting, setIsSubmitting] = useState(false)

  const indexedDocuments =
    documentsResult._tag === 'Success' ? documentsResult.value : []

  const isGenerateDisabled =
    !topic.trim() || selectedTypes.length === 0 || isSubmitting

  const helperText = useMemo(() => {
    if (!contextLabel) return 'Create a package of resources for the current project.'
    return `Opened from ${contextLabel}. You can turn the current learning moment into a targeted resource package.`
  }, [contextLabel])

  const toggleType = (resourceType: ResourceType) => {
    setSelectedTypes((current) =>
      current.includes(resourceType)
        ? current.filter((item) => item !== resourceType)
        : [...current, resourceType],
    )
  }

  const toggleDocument = (documentId: string) => {
    setSelectedDocumentIds((current) => {
      const next = new Set(current)
      if (next.has(documentId)) next.delete(documentId)
      else next.add(documentId)
      return next
    })
  }

  const handleGenerate = async () => {
    if (!topic.trim() || selectedTypes.length === 0) return

    setIsSubmitting(true)
    try {
      const resourcePackage = await generateResourcePackage({
        projectId,
        title: title.trim() || undefined,
        target_topic: topic.trim(),
        target_goal: goal.trim() || undefined,
        custom_instructions: instructions.trim() || undefined,
        source_document_ids: Array.from(selectedDocumentIds),
        resource_types: selectedTypes,
        difficulty_level: difficulty,
        generation_params: contextLabel ? { launch_context: contextLabel } : {},
      })

      setSelectedPackage(resourcePackage)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <>
      <SheetHeader className="border-b">
        <SheetTitle className="flex items-center gap-2">
          <SparklesIcon className="size-5 text-primary" />
          Resource Package Generator
        </SheetTitle>
        <SheetDescription>{helperText}</SheetDescription>
      </SheetHeader>

      <div className="grid min-h-0 flex-1 gap-0 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="flex min-h-0 flex-col border-r">
          <div className="space-y-5 overflow-y-auto p-4">
            <div className="space-y-2">
              <Label htmlFor="resource-package-title">Package title</Label>
              <Textarea
                id="resource-package-title"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="Optional title for this package"
                className="min-h-20 resize-none"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="resource-package-topic">Target topic</Label>
              <Textarea
                id="resource-package-topic"
                value={topic}
                onChange={(event) => setTopic(event.target.value)}
                placeholder="What should this package focus on?"
                className="min-h-24 resize-none"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="resource-package-goal">Learning goal</Label>
              <Textarea
                id="resource-package-goal"
                value={goal}
                onChange={(event) => setGoal(event.target.value)}
                placeholder="Optional goal, for example: prepare for gradient descent errors"
                className="min-h-20 resize-none"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="resource-package-difficulty">Difficulty</Label>
              <Select
                value={difficulty}
                onValueChange={(value) => setDifficulty(value as DifficultyLevel)}
              >
                <SelectTrigger id="resource-package-difficulty">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {difficultyOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-3">
              <Label>Resource types</Label>
              <div className="grid gap-2">
                {RESOURCE_TYPE_OPTIONS.map((option) => {
                  const checked = selectedTypes.includes(option.value)
                  return (
                    <label
                      key={option.value}
                      className={cn(
                        'flex cursor-pointer items-start gap-3 rounded-xl border p-3 transition-colors',
                        checked
                          ? 'border-primary bg-primary/5'
                          : 'hover:bg-muted/40',
                      )}
                    >
                      <Checkbox
                        checked={checked}
                        onCheckedChange={() => toggleType(option.value)}
                      />
                      <div className="space-y-1">
                        <div className="font-medium">{option.label}</div>
                        <div className="text-sm text-muted-foreground">
                          {option.description}
                        </div>
                      </div>
                    </label>
                  )
                })}
              </div>
            </div>

            <div className="space-y-3">
              <Label>Source documents</Label>
              <div className="space-y-2 rounded-xl border p-3">
                {documentsResult.waiting ? (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2Icon className="size-4 animate-spin" />
                    <span>Loading indexed documents...</span>
                  </div>
                ) : indexedDocuments.length === 0 ? (
                  <div className="text-sm text-muted-foreground">
                    No indexed documents available yet.
                  </div>
                ) : (
                  indexedDocuments.map((document) => (
                    <label
                      key={document.id}
                      className="flex cursor-pointer items-start gap-3 rounded-lg p-2 hover:bg-muted/40"
                    >
                      <Checkbox
                        checked={selectedDocumentIds.has(document.id)}
                        onCheckedChange={() => toggleDocument(document.id)}
                      />
                      <div className="min-w-0">
                        <div className="truncate text-sm font-medium">
                          {document.file_name}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {document.file_type?.toUpperCase()}
                        </div>
                      </div>
                    </label>
                  ))
                )}
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="resource-package-instructions">
                Custom instructions
              </Label>
              <Textarea
                id="resource-package-instructions"
                value={instructions}
                onChange={(event) => setInstructions(event.target.value)}
                placeholder="Optional guidance for how the resources should be generated"
                className="min-h-28 resize-none"
              />
            </div>
          </div>
        </div>

        <div className="flex min-h-0 flex-col">
          <div className="border-b p-4">
            <div className="text-sm font-medium">Recent packages</div>
            <div className="mt-1 text-sm text-muted-foreground">
              Review the latest generated packages and preview their resources.
            </div>
          </div>

          <div className="grid min-h-0 flex-1 grid-rows-[auto_1fr]">
            <div className="overflow-y-auto p-4">
              <ResourcePackageList
                projectId={projectId}
                selectedPackageId={selectedPackage?.id ?? null}
                onSelect={setSelectedPackage}
              />
            </div>

            <div className="min-h-0 border-t p-4">
              <div className="mb-3 flex items-center gap-2 text-sm font-medium">
                <FileTextIcon className="size-4" />
                Resource preview
              </div>
              <div className="max-h-full overflow-y-auto">
                <ResourcePreviewPanel
                  projectId={projectId}
                  resourcePackage={selectedPackage}
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      <SheetFooter className="border-t">
        <Button variant="outline" onClick={onClose} disabled={isSubmitting}>
          Close
        </Button>
        <Button onClick={handleGenerate} disabled={isGenerateDisabled}>
          {isSubmitting ? (
            <>
              <Loader2Icon className="size-4 animate-spin" />
              Generating
            </>
          ) : (
            <>
              <SparklesIcon className="size-4" />
              Generate package
            </>
          )}
        </Button>
      </SheetFooter>
    </>
  )
}

export function ResourcePackageSheet() {
  const { isOpen, projectId, contextLabel, close } = useResourcePackageSheet()

  return (
    <Sheet open={isOpen} onOpenChange={(open) => !open && close()}>
      <SheetContent side="right" className="w-full sm:max-w-2xl">
        {!projectId ? (
          <>
            <SheetHeader className="border-b">
              <SheetTitle>Resource Package Generator</SheetTitle>
              <SheetDescription>
                Open a project-scoped page before generating a resource package.
              </SheetDescription>
            </SheetHeader>
            <div className="p-4 text-sm text-muted-foreground">
              This launcher only works inside pages that belong to a specific
              project.
            </div>
          </>
        ) : (
          <ResourcePackageSheetBody
            projectId={projectId}
            contextLabel={contextLabel}
            onClose={close}
          />
        )}
      </SheetContent>
    </Sheet>
  )
}
