import { Composer } from './Composer'
import { MessageList } from './MessageList'
import { useChat } from './useChat'

export function ChatApp() {
  const { messages, status, error, isBusy, send, retry, reset } = useChat()

  return (
    <div className="app">
      <header className="header">
        <h1>Basic Chatbot</h1>
        <button
          type="button"
          className="button"
          onClick={reset}
          disabled={messages.length === 0 && !isBusy && !error}
        >
          New chat
        </button>
      </header>

      <main className="main">
        <MessageList messages={messages} isThinking={status === 'waiting'} />

        {error && (
          <div className="error" role="alert">
            <p>{error}</p>
            <button type="button" className="button" onClick={retry}>
              Retry
            </button>
          </div>
        )}

        <Composer isBusy={isBusy} onSend={send} />
      </main>
    </div>
  )
}
