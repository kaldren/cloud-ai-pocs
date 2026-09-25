import { useRef, useState, type KeyboardEvent, type SubmitEvent } from 'react'

import { MAX_CONTENT_LENGTH } from '../../api/chat'

type ComposerProps = {
  isBusy: boolean
  onSend: (content: string) => void
}

export function Composer({ isBusy, onSend }: ComposerProps) {
  const [draft, setDraft] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const content = draft.trim()
  const isTooLong = content.length > MAX_CONTENT_LENGTH
  const canSend = !isBusy && content.length > 0 && !isTooLong

  function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!canSend) return
    onSend(content)
    setDraft('')
    textareaRef.current?.focus()
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      event.currentTarget.form?.requestSubmit()
    }
  }

  return (
    <form className="composer" onSubmit={handleSubmit}>
      <label htmlFor="composer-input" className="sr-only">
        Message
      </label>
      <textarea
        ref={textareaRef}
        id="composer-input"
        name="message"
        rows={1}
        placeholder="Type a message…"
        value={draft}
        onChange={(event) => {
          setDraft(event.target.value)
        }}
        onKeyDown={handleKeyDown}
        aria-invalid={isTooLong}
        aria-describedby={isTooLong ? 'composer-error' : undefined}
      />
      <button type="submit" className="button button-primary" disabled={!canSend}>
        Send
      </button>
      {isTooLong && (
        <p id="composer-error" className="composer-error">
          Message is too long ({content.length.toLocaleString()} of{' '}
          {MAX_CONTENT_LENGTH.toLocaleString()} characters).
        </p>
      )}
    </form>
  )
}
