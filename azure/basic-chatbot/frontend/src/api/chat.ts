// Client for the backend chat endpoint: POST /api/chat, reply streamed as text/plain chunks.

export type ChatRole = 'user' | 'assistant'

export type ChatMessage = {
  role: ChatRole
  content: string
}

/** Backend limits: 1-50 messages, each with 1-8000 characters of content. */
export const MAX_MESSAGES = 50
export const MAX_CONTENT_LENGTH = 8000

export class ChatRequestError extends Error {
  override readonly name = 'ChatRequestError'
  readonly status: number | undefined

  constructor(message: string, status?: number) {
    super(message)
    this.status = status
  }
}

/**
 * Shapes a conversation to what the backend accepts: drops empty turns, clips
 * overlong ones (assistant replies can exceed the limit), keeps the last 50.
 */
export function buildHistory(messages: readonly ChatMessage[]): ChatMessage[] {
  return messages
    .filter((message) => message.content.trim().length > 0)
    .map((message) => ({
      role: message.role,
      content: message.content.slice(0, MAX_CONTENT_LENGTH),
    }))
    .slice(-MAX_MESSAGES)
}

function messageForStatus(status: number): string {
  if (status === 422) return 'The server could not accept that message. Try a shorter one.'
  if (status === 502) return 'The assistant is unavailable right now. Please try again.'
  return `Something went wrong (HTTP ${String(status)}). Please try again.`
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

type StreamChatOptions = {
  signal: AbortSignal
  onChunk: (text: string) => void
}

/**
 * Sends the conversation (new user message last) and calls `onChunk` for each
 * decoded piece of the streamed reply. Rejects with ChatRequestError on HTTP or
 * network failure, or with the AbortError if `signal` is aborted.
 */
export async function streamChat(
  messages: readonly ChatMessage[],
  { signal, onChunk }: StreamChatOptions,
): Promise<void> {
  let response: Response
  try {
    response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: buildHistory(messages) }),
      signal,
    })
  } catch (error) {
    if (isAbortError(error)) throw error
    throw new ChatRequestError('Could not reach the server. Check your connection and try again.')
  }

  if (!response.ok) throw new ChatRequestError(messageForStatus(response.status), response.status)
  if (!response.body) throw new ChatRequestError('The server sent an empty response.')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      const text = decoder.decode(value, { stream: true })
      if (text) onChunk(text)
    }
    const tail = decoder.decode()
    if (tail) onChunk(tail)
  } catch (error) {
    if (isAbortError(error)) throw error
    throw new ChatRequestError('The response was interrupted. Please try again.')
  }
}
