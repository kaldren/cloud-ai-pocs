import { useEffect, useRef } from 'react'

import type { Message } from './useChat'

type MessageListProps = {
  messages: readonly Message[]
  isThinking: boolean
}

export function MessageList({ messages, isThinking }: MessageListProps) {
  const logRef = useRef<HTMLDivElement>(null)

  // Keep the newest content in view as messages arrive and replies stream in.
  useEffect(() => {
    const log = logRef.current
    if (log) log.scrollTop = log.scrollHeight
  }, [messages, isThinking])

  return (
    <div ref={logRef} className="log" role="log" aria-live="polite" aria-label="Conversation">
      {messages.length === 0 && !isThinking ? (
        <div className="empty">
          <p className="empty-title">How can I help?</p>
          <p>Ask a question below. Press Enter to send and Shift+Enter for a new line.</p>
        </div>
      ) : (
        <ol className="messages">
          {messages.map((message) => (
            <li key={message.id} className={`message message-${message.role}`}>
              <span className="sr-only">{message.role === 'user' ? 'You:' : 'Assistant:'} </span>
              {message.content}
            </li>
          ))}
          {isThinking && (
            <li className="message message-assistant thinking">
              Thinking
              <span className="dots" aria-hidden="true" />
            </li>
          )}
        </ol>
      )}
    </div>
  )
}
