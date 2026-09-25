import { ChatApp } from './features/chat/ChatApp'
import { ErrorBoundary } from './lib/ErrorBoundary'

export function App() {
  return (
    <ErrorBoundary>
      <ChatApp />
    </ErrorBoundary>
  )
}
