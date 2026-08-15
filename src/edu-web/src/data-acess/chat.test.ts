// @vitest-environment jsdom

import { Registry, Result } from '@effect-atom/atom-react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  buildChatStreamRequestBody,
  chatAtom,
  chatRuntimeEventsAtom,
  chatStreamStatusAtom,
  streamMessageAtom,
} from './chat'

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('chat streaming state lifecycle', () => {
  it('includes the web search choice in the stream request', () => {
    expect(buildChatStreamRequestBody([], true)).toEqual({
      parts: [],
      web_search: true,
    })
    expect(buildChatStreamRequestBody([])).toEqual({
      parts: [],
      web_search: false,
    })
  })

  it('keeps per-chat state alive while its page is unmounted', () => {
    expect(chatAtom('project-1:chat-1').keepAlive).toBe(true)
    expect(chatStreamStatusAtom('chat-1').keepAlive).toBe(true)
    expect(chatRuntimeEventsAtom('chat-1').keepAlive).toBe(true)
    expect(streamMessageAtom('chat-1').keepAlive).toBe(true)
  })

  it('isolates concurrent conversations by chat id', () => {
    expect(chatAtom('project-1:chat-1')).not.toBe(chatAtom('project-1:chat-2'))
    expect(chatStreamStatusAtom('chat-1')).not.toBe(
      chatStreamStatusAtom('chat-2'),
    )
    expect(chatRuntimeEventsAtom('chat-1')).not.toBe(
      chatRuntimeEventsAtom('chat-2'),
    )
    expect(streamMessageAtom('chat-1')).not.toBe(streamMessageAtom('chat-2'))
  })

  it('continues the first SSE consumer after a second chat starts', async () => {
    const encoder = new TextEncoder()
    const controllers = new Map<
      string,
      ReadableStreamDefaultController<Uint8Array>
    >()
    const controllerReady = new Map<string, () => void>()
    const chat1Ready = new Promise<void>((resolve) =>
      controllerReady.set('chat-1', resolve),
    )
    const chat2Ready = new Promise<void>((resolve) =>
      controllerReady.set('chat-2', resolve),
    )

    vi.stubGlobal(
      'fetch',
      vi.fn((request: RequestInfo | URL) => {
        const url = typeof request === 'string' ? request : request.toString()
        const chatId = url.includes('/chat-1/') ? 'chat-1' : 'chat-2'
        const body = new ReadableStream<Uint8Array>({
          start(controller) {
            controllers.set(chatId, controller)
            controllerReady.get(chatId)?.()
          },
        })
        return Promise.resolve(
          new Response(body, {
            status: 200,
            headers: { 'Content-Type': 'text/event-stream' },
          }),
        )
      }),
    )

    const timestamp = '2026-08-14T08:00:00.000Z'
    const chat1Atom = chatAtom('project-1:chat-1')
    const chat2Atom = chatAtom('project-1:chat-2')
    const makeChat = (chatId: string) => ({
      id: chatId,
      project_id: 'project-1',
      user_id: 'user-1',
      title: chatId,
      created_at: timestamp,
      updated_at: timestamp,
      messages: [],
    })
    const makeUserMessage = (chatId: string, text: string) => ({
      id: `user-${chatId}`,
      chat_id: chatId,
      role: 'user',
      created_at: timestamp,
      parts: [{ type: 'text' as const, text_content: text, order: 0 }],
    })
    const registry = Registry.make({
      initialValues: [
        [chat1Atom, Result.success(makeChat('chat-1'))],
        [chat2Atom, Result.success(makeChat('chat-2'))],
      ],
    })
    registry.mount(streamMessageAtom('chat-1'))
    registry.mount(streamMessageAtom('chat-2'))

    registry.set(streamMessageAtom('chat-1'), {
      projectId: 'project-1',
      chatId: 'chat-1',
      message: makeUserMessage('chat-1', 'first question'),
      webSearch: true,
    })
    await chat1Ready

    const sendChat1Delta = (delta: string) =>
      controllers.get('chat-1')?.enqueue(
        encoder.encode(
          `data: ${JSON.stringify({
            message_id: 'assistant-chat-1',
            chat_id: 'chat-1',
            role: 'assistant',
            created_at: timestamp,
            delta,
            part_id: 'text-1',
            done: false,
          })}\n\n`,
        ),
      )

    sendChat1Delta('before switch')
    await vi.waitFor(() => {
      const result = registry.get(chat1Atom)
      expect(Result.isSuccess(result)).toBe(true)
      if (!Result.isSuccess(result)) return
      expect(result.value.messages?.at(-1)?.parts?.[0]).toMatchObject({
        type: 'text',
        text_content: 'before switch',
      })
    })

    registry.set(streamMessageAtom('chat-2'), {
      projectId: 'project-1',
      chatId: 'chat-2',
      message: makeUserMessage('chat-2', 'second question'),
    })
    await chat2Ready

    sendChat1Delta(' after switch')

    await vi.waitFor(() => {
      const result = registry.get(chat1Atom)
      expect(Result.isSuccess(result)).toBe(true)
      if (!Result.isSuccess(result)) return
      expect(result.value.messages?.at(-1)?.parts?.[0]).toMatchObject({
        type: 'text',
        text_content: 'before switch after switch',
      })
    })

    registry.dispose()
  })
})
