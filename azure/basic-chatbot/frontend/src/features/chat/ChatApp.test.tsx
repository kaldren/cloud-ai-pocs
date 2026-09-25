import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { server } from '../../test/server'
import { ChatApp } from './ChatApp'

const encoder = new TextEncoder()
const textHeaders = { 'Content-Type': 'text/plain; charset=utf-8' }

/** A reply stream the test pushes chunks into, to observe the UI mid-stream. */
function controlledStream() {
  const { readable, writable } = new TransformStream<Uint8Array, Uint8Array>()
  const writer = writable.getWriter()
  return {
    readable,
    push: (text: string) => void writer.write(encoder.encode(text)),
    close: () => void writer.close(),
  }
}

function streamOf(...chunks: string[]) {
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk))
      controller.close()
    },
  })
}

function setup() {
  const user = userEvent.setup()
  render(<ChatApp />)
  return {
    user,
    input: screen.getByRole('textbox', { name: 'Message' }),
    sendButton: screen.getByRole('button', { name: 'Send' }),
    log: screen.getByRole('log', { name: 'Conversation' }),
  }
}

describe('ChatApp', () => {
  it('shows an empty state before the first message', () => {
    setup()
    expect(screen.getByText('How can I help?')).toBeInTheDocument()
  })

  it('streams the reply into the log and sends prior turns as history', async () => {
    const bodies: unknown[] = []
    const replies = [streamOf('Hel', 'lo ', 'there'), streamOf('Second ', 'answer')]
    server.use(
      http.post('/api/chat', async ({ request }) => {
        bodies.push(await request.json())
        return new HttpResponse(replies.shift(), { headers: textHeaders })
      }),
    )
    const { user, input, log } = setup()

    await user.type(input, 'Hi{Enter}')
    expect(await within(log).findByText('Hello there')).toBeInTheDocument()
    expect(within(log).getByText('Hi')).toBeInTheDocument()
    expect(input).toHaveValue('')

    await user.type(input, 'And again?{Enter}')
    expect(await within(log).findByText('Second answer')).toBeInTheDocument()

    expect(bodies).toEqual([
      { messages: [{ role: 'user', content: 'Hi' }] },
      {
        messages: [
          { role: 'user', content: 'Hi' },
          { role: 'assistant', content: 'Hello there' },
          { role: 'user', content: 'And again?' },
        ],
      },
    ])
  })

  it('shows thinking until the first chunk, renders incrementally and disables Send while streaming', async () => {
    const stream = controlledStream()
    server.use(
      http.post('/api/chat', () => new HttpResponse(stream.readable, { headers: textHeaders })),
    )
    const { user, input, sendButton, log } = setup()

    await user.type(input, 'Hi{Enter}')
    expect(await within(log).findByText('Thinking')).toBeInTheDocument()

    // Typing the next message is allowed, but it cannot be sent yet.
    await user.type(input, 'Next question')
    expect(sendButton).toBeDisabled()

    stream.push('Partial')
    expect(await within(log).findByText('Partial')).toBeInTheDocument()
    expect(within(log).queryByText('Thinking')).not.toBeInTheDocument()
    expect(sendButton).toBeDisabled()

    stream.push(' reply')
    stream.close()
    expect(await within(log).findByText('Partial reply')).toBeInTheDocument()
    expect(sendButton).toBeEnabled()
  })

  it('shows a friendly error on 502 and lets the user retry', async () => {
    let calls = 0
    server.use(
      http.post('/api/chat', () => {
        calls += 1
        if (calls === 1)
          return HttpResponse.json({ detail: 'Upstream model error' }, { status: 502 })
        return new HttpResponse(streamOf('Recovered'), { headers: textHeaders })
      }),
    )
    const { user, input, log } = setup()

    await user.type(input, 'Hi{Enter}')
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('The assistant is unavailable right now')
    expect(within(log).getByText('Hi')).toBeInTheDocument()

    await user.click(within(alert).getByRole('button', { name: 'Retry' }))
    expect(await within(log).findByText('Recovered')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows an error when the network request fails', async () => {
    server.use(http.post('/api/chat', () => HttpResponse.error()))
    const { user, input } = setup()

    await user.type(input, 'Hi{Enter}')
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not reach the server')
  })

  it('sends on Enter but inserts a newline on Shift+Enter', async () => {
    const bodies: unknown[] = []
    server.use(
      http.post('/api/chat', async ({ request }) => {
        bodies.push(await request.json())
        return new HttpResponse(streamOf('ok'), { headers: textHeaders })
      }),
    )
    const { user, input, log } = setup()

    await user.type(input, 'line one{Shift>}{Enter}{/Shift}line two')
    expect(input).toHaveValue('line one\nline two')
    expect(bodies).toHaveLength(0)

    await user.keyboard('{Enter}')
    expect(await within(log).findByText('ok')).toBeInTheDocument()
    expect(bodies).toEqual([{ messages: [{ role: 'user', content: 'line one\nline two' }] }])
  })

  it('blocks empty and overlong messages', async () => {
    const { user, input, sendButton } = setup()
    expect(sendButton).toBeDisabled()

    await user.type(input, '   ')
    expect(sendButton).toBeDisabled()

    await user.clear(input)
    await user.click(input)
    await user.paste('a'.repeat(8001))
    expect(sendButton).toBeDisabled()
    expect(input).toHaveAccessibleDescription(/too long/)
  })

  it('New chat aborts the in-flight reply and clears the conversation', async () => {
    const stream = controlledStream()
    server.use(
      http.post('/api/chat', () => new HttpResponse(stream.readable, { headers: textHeaders })),
    )
    const { user, input, log } = setup()

    await user.type(input, 'Hi{Enter}')
    stream.push('Partial')
    expect(await within(log).findByText('Partial')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'New chat' }))
    expect(screen.getByText('How can I help?')).toBeInTheDocument()
    expect(within(log).queryByText('Hi')).not.toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Message' })).toBeEnabled()
  })
})
