import { describe, expect, it } from 'vitest'

import { buildHistory, MAX_CONTENT_LENGTH, MAX_MESSAGES, type ChatMessage } from './chat'

describe('buildHistory', () => {
  it('keeps only the last 50 messages, newest last', () => {
    const messages: ChatMessage[] = Array.from({ length: 60 }, (_, index) => ({
      role: index % 2 === 0 ? 'user' : 'assistant',
      content: `message ${String(index)}`,
    }))

    const history = buildHistory(messages)

    expect(history).toHaveLength(MAX_MESSAGES)
    expect(history[0]?.content).toBe('message 10')
    expect(history.at(-1)?.content).toBe('message 59')
  })

  it('drops empty turns and clips overlong ones to the backend limit', () => {
    const history = buildHistory([
      { role: 'user', content: 'hi' },
      { role: 'assistant', content: '   ' },
      { role: 'assistant', content: 'x'.repeat(MAX_CONTENT_LENGTH + 10) },
    ])

    expect(history).toHaveLength(2)
    expect(history[1]?.content).toHaveLength(MAX_CONTENT_LENGTH)
  })
})
