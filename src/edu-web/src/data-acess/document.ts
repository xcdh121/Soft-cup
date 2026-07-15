import {
  DocumentIdSchema,
  ProjectIdSchema,
  type DocumentId,
} from '@/data-acess/shared'
import { usageAtom } from '@/data-acess/usage'
import type { DocumentDto } from '@/integrations/api'
import { ApiClientService } from '@/integrations/api/http'
import { makeAtomRuntime } from '@/lib/make-atom-runtime'
import { withToast } from '@/lib/with-toast'
import { HttpBody } from '@effect/platform'
import { Atom, Registry, Result } from '@effect-atom/atom-react'
import { BrowserKeyValueStore } from '@effect/platform-browser'
import { Data, Effect, Layer, Schema } from 'effect'

const runtime = makeAtomRuntime(
  Layer.mergeAll(
    BrowserKeyValueStore.layerLocalStorage,
    ApiClientService.Default,
  ),
)

const isSuccessStatus = (status: number) => status >= 200 && status < 300

const getResponseErrorDetail = (payload: unknown) => {
  if (!payload || typeof payload !== 'object') return ''

  const detail = (payload as { detail?: unknown }).detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === 'string') return item
        try {
          return JSON.stringify(item)
        } catch {
          return String(item)
        }
      })
      .join('; ')
  }
  if (detail) {
    try {
      return JSON.stringify(detail)
    } catch {
      return String(detail)
    }
  }
  return ''
}

export type CourseBook = {
  resource_id: string
  document_id: string
  chapter_id: string | null
  title: string
  author: string | null
  cover_url: string | null
  file_url: string
  status: DocumentDto['status']
  license: string | null
  source_url: string | null
  start_page: number | null
  end_page: number | null
  metadata: Record<string, unknown>
}

export type DocumentCitation = {
  document_id: string
  segment_id: string | null
  title: string
  page_number: number | null
  score: number | null
  excerpt: string | null
}

export type DocumentQuestionResponse = {
  answer: string
  citations: Array<DocumentCitation>
}

export type AskDocumentQuestionInput = {
  projectId: string
  documentId: string
  question: string
  selectedText?: string
  pageNumber?: number
  chapterId?: string | null
  topK?: number
}

export type BindCourseBookInput = {
  projectId: string
  courseId: string
  chapterId: string
  documentId: string
  title: string
  chapterTitle?: string
}

type DocumentsAction = Data.TaggedEnum<{
  Del: { readonly documentId: DocumentId }
  Update: {
    readonly document: Result.Result<DocumentDto>
  }
}>
const DocumentsAction = Data.taggedEnum<DocumentsAction>()

export const documentsRemoteAtom = Atom.family((projectId: string) =>
  runtime.atom(
    Effect.fn(function* () {
      const { apiClient } = yield* ApiClientService

      const parsedProjectId = yield* Schema.decode(ProjectIdSchema)(projectId)

      return yield* apiClient.listDocumentsApiV1ProjectsProjectIdDocumentsGet(
        parsedProjectId,
      )
    }),
  ),
)

export const documentsAtom = Atom.family((projectId: string) =>
  Object.assign(
    Atom.writable(
      (get: Atom.Context) => get(documentsRemoteAtom(projectId)),
      (ctx, action: DocumentsAction) => {
        const result = ctx.get(documentsAtom(projectId))
        if (!Result.isSuccess(result)) return

        const update = DocumentsAction.$match(action, {
          Del: ({ documentId }) => {
            return result.value.filter((d) => d.id !== documentId)
          },
          Update: ({ document }) => {
            if (!Result.isSuccess(document)) return result.value
            return result.value.map((d) =>
              d.id === document.value.id ? document.value : d,
            )
          },
        })

        ctx.setSelf(Result.success(update))
      },
    ),
    {
      remote: documentsRemoteAtom(projectId),
    },
  ),
)

export const indexedDocumentsAtom = Atom.family((projectId: string) =>
  Atom.make((get) =>
    get(documentsRemoteAtom(projectId)).pipe(
      Result.map((d) => d.filter((d) => d.status === 'indexed')),
    ),
  ),
)

export const courseBooksAtom = Atom.family((projectId: string) =>
  runtime
    .atom(
      Effect.fn(function* () {
        const { httpClient } = yield* ApiClientService
        const parsedProjectId = yield* Schema.decode(ProjectIdSchema)(projectId)
        const response = yield* httpClient.get(
          `/api/v1/projects/${parsedProjectId}/course-books`,
        )
        if (!isSuccessStatus(response.status)) {
          return yield* Effect.fail(
            new Error(
              `Course books request failed with status ${response.status}`,
            ),
          )
        }
        return (yield* response.json) as Array<CourseBook>
      })(),
    )
    .pipe(Atom.keepAlive),
)

export const bindCourseBookAtom = runtime.fn(
  Effect.fn(function* (input: BindCourseBookInput) {
    const registry = yield* Registry.AtomRegistry
    const { httpClient } = yield* ApiClientService
    const parsed = yield* Schema.decode(
      Schema.Struct({
        projectId: ProjectIdSchema,
        courseId: Schema.String,
        chapterId: Schema.String,
        documentId: DocumentIdSchema,
        title: Schema.String,
        chapterTitle: Schema.optional(Schema.String),
      }),
    )(input)

    const response = yield* httpClient.post(
      `/api/v1/courses/${parsed.courseId}/resources`,
      {
        body: HttpBody.unsafeJson({
          chapter_id: parsed.chapterId,
          document_id: parsed.documentId,
          generated_resource_id: null,
          resource_type: 'pdf',
          title: parsed.title,
          description: `${parsed.chapterTitle ?? '章节'}配套 PDF 阅读材料`,
          source_type: 'uploaded',
          source_url: null,
          difficulty_level: 'medium',
          estimated_minutes: null,
          license_info: null,
          target_audiences: ['student'],
          metadata: {
            chapter_title: parsed.chapterTitle,
            display_title: parsed.title,
          },
          knowledge_point_ids: [],
        }),
      },
    )
    if (!isSuccessStatus(response.status)) {
      const payload = yield* response.json.pipe(
        Effect.catchAll(() => Effect.succeed(null)),
      )
      const detail = getResponseErrorDetail(payload)
      return yield* Effect.fail(
        new Error(
          detail
            ? `Course PDF bind failed with status ${response.status}: ${detail}`
            : `Course PDF bind failed with status ${response.status}`,
        ),
      )
    }

    registry.refresh(courseBooksAtom(parsed.projectId))
    return yield* response.json
  }),
)

export const documentAtom = Atom.family((input: string) => {
  const [projectId, documentId] = input.split(':')

  return Atom.make(
    Effect.fn(function* () {
      const { apiClient } = yield* ApiClientService

      const parsed = yield* Schema.decode(
        Schema.Struct({
          projectId: ProjectIdSchema,
          documentId: DocumentIdSchema,
        }),
      )({ projectId, documentId })

      return yield* apiClient.getDocumentApiV1ProjectsProjectIdDocumentsDocumentIdGet(
        parsed.projectId,
        parsed.documentId,
      )
    })().pipe(Effect.provide(ApiClientService.Default)),
  )
})

export const documentFileBufferAtom = Atom.family((input: string) => {
  const [projectId, documentId] = input.split(':')
  return runtime.atom(
    Effect.fn(function* () {
      const { httpClient } = yield* ApiClientService
      const parsed = yield* Schema.decode(
        Schema.Struct({
          projectId: ProjectIdSchema,
          documentId: DocumentIdSchema,
        }),
      )({ projectId, documentId })

      const response = yield* httpClient.get(
        `/api/v1/projects/${parsed.projectId}/documents/${parsed.documentId}/file`,
      )
      if (!isSuccessStatus(response.status)) {
        return yield* Effect.fail(
          new Error(
            `Document file request failed with status ${response.status}`,
          ),
        )
      }
      return yield* response.arrayBuffer
    })(),
  )
})

export const uploadDocumentAtom = runtime.fn(
  Effect.fn(function* (input: { projectId: string; files: Array<Blob> }) {
    const registry = yield* Registry.AtomRegistry
    const { apiClient } = yield* ApiClientService

    const parsedProjectId = yield* Schema.decode(ProjectIdSchema)(
      input.projectId,
    )

    yield* apiClient.uploadDocumentApiV1ProjectsProjectIdDocumentsUploadPost(
      parsedProjectId,
      {
        files: input.files,
      },
    )

    registry.refresh(documentsRemoteAtom(input.projectId))
    registry.refresh(usageAtom)
  }),
)

export const deleteDocumentAtom = runtime.fn(
  Effect.fn(
    function* (input: { documentId: string; projectId: string }) {
      const registry = yield* Registry.AtomRegistry
      const { apiClient } = yield* ApiClientService

      const parsed = yield* Schema.decode(
        Schema.Struct({
          projectId: ProjectIdSchema,
          documentId: DocumentIdSchema,
        }),
      )(input)

      yield* apiClient.deleteDocumentApiV1ProjectsProjectIdDocumentsDocumentIdDelete(
        parsed.projectId,
        parsed.documentId,
      )

      registry.set(
        documentsAtom(parsed.projectId),
        DocumentsAction.Del({ documentId: parsed.documentId }),
      )
    },
    withToast({
      onWaiting: () => '正在删除文档...',
      onSuccess: '文档已删除',
      onFailure: '文档删除失败',
    }),
  ),
)

export const refreshDocumentsAtom = runtime.fn(
  Effect.fn(function* (projectId: string) {
    const registry = yield* Registry.AtomRegistry
    registry.refresh(documentsRemoteAtom(projectId))
  }),
)

export const refreshDocumentAtom = runtime.fn(
  Effect.fn(function* (input: { projectId: string; documentId: string }) {
    const registry = yield* Registry.AtomRegistry
    const { apiClient } = yield* ApiClientService

    const parsed = yield* Schema.decode(
      Schema.Struct({
        projectId: ProjectIdSchema,
        documentId: DocumentIdSchema,
      }),
    )(input)

    // Fetch the latest document data
    const document =
      yield* apiClient.getDocumentApiV1ProjectsProjectIdDocumentsDocumentIdGet(
        parsed.projectId,
        parsed.documentId,
      )

    registry.refresh(documentAtom(`${parsed.projectId}:${parsed.documentId}`))

    // Update the document in the documents list atom
    registry.set(
      documentsAtom(parsed.projectId),
      DocumentsAction.Update({
        document: Result.success(document),
      }),
    )
  }),
)

export const reprocessDocumentAtom = runtime.fn(
  Effect.fn(function* (input: { projectId: string; documentId: string }) {
    const registry = yield* Registry.AtomRegistry
    const { httpClient } = yield* ApiClientService
    const parsed = yield* Schema.decode(
      Schema.Struct({
        projectId: ProjectIdSchema,
        documentId: DocumentIdSchema,
      }),
    )(input)

    const response = yield* httpClient.post(
      `/api/v1/projects/${parsed.projectId}/documents/${parsed.documentId}/process`,
    )
    if (!isSuccessStatus(response.status)) {
      return yield* Effect.fail(
        new Error(
          `Document process request failed with status ${response.status}`,
        ),
      )
    }

    registry.refresh(documentAtom(`${parsed.projectId}:${parsed.documentId}`))
    registry.refresh(documentsRemoteAtom(parsed.projectId))
  }),
)

export const askDocumentQuestionAtom = runtime.fn(
  Effect.fn(function* (input: AskDocumentQuestionInput) {
    const { httpClient } = yield* ApiClientService
    const parsed = yield* Schema.decode(
      Schema.Struct({
        projectId: ProjectIdSchema,
        documentId: DocumentIdSchema,
      }),
    )({
      projectId: input.projectId,
      documentId: input.documentId,
    })

    const response = yield* httpClient.post(
      `/api/v1/projects/${parsed.projectId}/documents/${parsed.documentId}/ask`,
      {
        body: HttpBody.unsafeJson({
          question: input.question,
          selected_text: input.selectedText,
          page_number: input.pageNumber,
          chapter_id: input.chapterId,
          top_k: input.topK ?? 5,
        }),
      },
    )
    if (!isSuccessStatus(response.status)) {
      const payload = yield* response.json.pipe(
        Effect.catchAll(() => Effect.succeed(null)),
      )
      const detail = getResponseErrorDetail(payload)
      return yield* Effect.fail(
        new Error(
          detail
            ? `Document AI request failed with status ${response.status}: ${detail}`
            : `Document AI request failed with status ${response.status}`,
        ),
      )
    }
    return (yield* response.json) as DocumentQuestionResponse
  }),
)

export const documentPreviewAtom = Atom.family((input: string) => {
  const [projectId, documentId] = input.split(':')
  return runtime.atom(
    Effect.fn(function* () {
      const { httpClient } = yield* ApiClientService

      const parsed = yield* Schema.decode(
        Schema.Struct({
          projectId: ProjectIdSchema,
          documentId: DocumentIdSchema,
        }),
      )({ projectId, documentId })

      const response = yield* httpClient.get(
        `/api/v1/projects/${parsed.projectId}/documents/${parsed.documentId}/preview`,
      )
      const json = yield* response.json

      return json as { url: string }
    }),
  )
})
