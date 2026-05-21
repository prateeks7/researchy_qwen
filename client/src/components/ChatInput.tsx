import { useState, useRef, KeyboardEvent } from 'react'
import { Send } from 'lucide-react'
import { cn } from '@/lib/utils'

interface ChatInputProps {
  onSend: (message: string) => void
  disabled?: boolean
}

export function ChatInput({ onSend, disabled = false }: ChatInputProps) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const canSend = value.trim().length > 0 && !disabled

  function handleSend() {
    if (!canSend) return
    onSend(value.trim())
    setValue('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  function handleInput() {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 180) + 'px'
  }

  return (
    <div className="px-4 pb-5 pt-3">
      <div
        className={cn(
          'flex items-end gap-2 px-4 py-3 rounded-2xl',
          'bg-white/30 border border-gray-300/50 backdrop-blur-md',
          'focus-within:border-gray-400/60 focus-within:bg-white/40 transition-all duration-150',
        )}
      >
        {/* Textarea */}
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onInput={handleInput}
          placeholder="Ask anything about research..."
          rows={1}
          disabled={disabled}
          className={cn(
            'flex-1 resize-none bg-transparent text-black font-sans text-sm',
            'placeholder:text-black/35 outline-none leading-relaxed',
            'min-h-[24px] max-h-[180px] py-0.5',
            'disabled:opacity-50',
          )}
        />

        {/* Send button */}
        <button
          onClick={handleSend}
          disabled={!canSend}
          className={cn(
            'flex-shrink-0 w-8 h-8 rounded-xl flex items-center justify-center transition-all duration-150 mb-0.5',
            canSend
              ? 'bg-blue-500 hover:bg-blue-400 text-white shadow-lg shadow-blue-500/25'
              : 'bg-black/10 text-black/25 cursor-not-allowed',
          )}
        >
          <Send className="w-3.5 h-3.5" />
        </button>
      </div>

      <p className="text-center text-[10px] font-sans text-black/30 mt-2">
        Press <kbd className="font-mono">Enter</kbd> to send · <kbd className="font-mono">Shift+Enter</kbd> for new line
      </p>
    </div>
  )
}
