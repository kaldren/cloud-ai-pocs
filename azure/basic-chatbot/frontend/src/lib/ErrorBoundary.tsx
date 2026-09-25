import { Component, type ReactNode } from 'react'

type ErrorBoundaryProps = {
  children: ReactNode
}

type ErrorBoundaryState = {
  hasError: boolean
}

// React still requires a class for error boundaries.
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  override state: ErrorBoundaryState = { hasError: false }

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true }
  }

  override render(): ReactNode {
    if (!this.state.hasError) return this.props.children
    return (
      <div className="fatal" role="alert">
        <p>Something went wrong.</p>
        <button
          type="button"
          className="button"
          onClick={() => {
            window.location.reload()
          }}
        >
          Reload
        </button>
      </div>
    )
  }
}
