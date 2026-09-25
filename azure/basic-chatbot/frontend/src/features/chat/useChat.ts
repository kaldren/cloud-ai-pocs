import { useEffect, useReducer, useRef } from 'react'

import { ChatRequestError, streamChat, type ChatMessage } from '../../api/chat'

export type Message = ChatMessage & { id: string }

/** `waiting`: request sent, no reply text yet. `streaming`: reply text arriving. */
export type ChatStatus = 'idle' | 'waiting' | 'streaming'

type ChatState = {
  messages: Message[]
  status: ChatStatus
  error: string | null
}

type ChatAction =
  | { type: 'send'; message: Message }
  | { type: 'retry' }
  | { type: 'chunk'; id: string; text: string }
  | { type: 'done' }
  | { type: 'fail'; error: string }
  | { type: 'reset' }

const initialState: ChatState = { messages: [], status: 'idle', error: null }

let lastId = 0
function nextId(): string {
  lastId += 1
  return `m${String(lastId)}`
}

/** Messages up to and including the last user turn (drops a partial reply before a retry). */
function upToLastUserMessage(messages: readonly Message[]): Message[] {
  const lastUser = messages.findLastIndex((message) => message.role === 'user')
  return messages.slice(0, lastUser + 1)
}

function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case 'send':
      return { messages: [...state.messages, action.message], status: 'waiting', error: null }
    case 'retry':
      return { messages: upToLastUserMessage(state.messages), status: 'waiting', error: null }
    case 'chunk': {
      const exists = state.messages.some((message) => message.id === action.id)
      const messages = exists
        ? state.messages.map((message) =>
            message.id === action.id
              ? { ...message, content: message.content + action.text }
              : message,
          )
        : [...state.messages, { id: action.id, role: 'assistant' as const, content: action.text }]
      return { ...state, messages, status: 'streaming' }
    }
    case 'done':
      return { ...state, status: 'idle' }
    case 'fail':
      return { ...state, status: 'idle', error: action.error }
    case 'reset':
      return initialState
  }
}

export function useChat() {
  const [state, dispatch] = useReducer(chatReducer, initialState)
  const controllerRef = useRef<AbortController | null>(null)

  // Abort an in-flight reply if the chat unmounts.
  useEffect(() => () => controllerRef.current?.abort(), [])

  async function run(history: readonly ChatMessage[]) {
    const controller = new AbortController()
    controllerRef.current = controller
    const replyId = nextId()
    try {
      await streamChat(history, {
        signal: controller.signal,
        onChunk: (text) => {
          if (!controller.signal.aborted) dispatch({ type: 'chunk', id: replyId, text })
        },
      })
      if (!controller.signal.aborted) dispatch({ type: 'done' })
    } catch (error) {
      if (controller.signal.aborted) return
      const message =
        error instanceof ChatRequestError
          ? error.message
          : 'Something went wrong. Please try again.'
      dispatch({ type: 'fail', error: message })
    } finally {
      if (controllerRef.current === controller) controllerRef.current = null
    }
  }

  const isBusy = state.status !== 'idle'

  function send(content: string) {
    if (isBusy) return
    const message: Message = { id: nextId(), role: 'user', content }
    dispatch({ type: 'send', message })
    void run([...state.messages, message])
  }

  function retry() {
    if (isBusy) return
    const history = upToLastUserMessage(state.messages)
    if (history.length === 0) return
    dispatch({ type: 'retry' })
    void run(history)
  }

  function reset() {
    controllerRef.current?.abort()
    controllerRef.current = null
    dispatch({ type: 'reset' })
  }

  return { ...state, isBusy, send, retry, reset }
}
