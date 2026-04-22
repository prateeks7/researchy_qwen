import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { User, MessageCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Message } from '@/types'
import agentIcon from '../../utils/backgrounds/Icon.png'

interface MessageBubbleProps {
  message: Message
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function splitFollowUp(content: string): { main: string; followUp: string | null } {
  const idx = content.indexOf('[FOLLOW_UP]')
  if (idx === -1) return { main: content, followUp: null }
  return {
    main: content.slice(0, idx).trimEnd(),
    followUp: content.slice(idx + '[FOLLOW_UP]'.length).trim(),
  }
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  const { main, followUp } = isUser
    ? { main: message.content, followUp: null }
    : splitFollowUp(message.content)

  return (
    <div className={cn('flex gap-3 animate-fade-in', isUser ? 'flex-row-reverse' : 'flex-row')}>
      {/* Avatar */}
      <div
        className={cn(
          'flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center mt-1 overflow-hidden',
          isUser ? 'bg-white-500/20 border border-brown-400/30' : 'border border-gray-300/50',
        )}
      >
        {isUser ? (
          <User className="w-4 h-4 text-black" />
        ) : (
          <img src={agentIcon} alt="Berg Agent" className="w-full h-full object-cover" />
        )}
      </div>

      {/* Bubbles */}
      <div className={cn('flex flex-col gap-2 max-w-[75%]', isUser ? 'items-end' : 'items-start')}>
        {/* Main bubble */}
        <div
          className={cn(
            'px-4 py-3 rounded-2xl font-sans text-sm leading-relaxed',
            'border backdrop-blur-md',
            isUser
              ? 'bg-transparent border-gray-400/40 text-black rounded-tr-sm'
              : 'bg-transparent border-gray-400/40 text-black rounded-tl-sm',
          )}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{main}</p>
          ) : (
            <div className="prose-chat">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{main}</ReactMarkdown>
            </div>
          )}
        </div>

        {/* Follow-up bubble */}
        {followUp && (
          <div className="flex items-start gap-2 px-3 py-2.5 rounded-xl rounded-tl-sm border border-black/10 bg-black/4 backdrop-blur-sm max-w-full">
            <MessageCircle className="w-3.5 h-3.5 text-black/35 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-black/55 italic leading-relaxed">{followUp}</p>
          </div>
        )}

        <span className="text-[10px] text-black/30 px-1">{formatTime(message.timestamp)}</span>
      </div>
    </div>
  )
}

export function TypingIndicator() {
  return (
    <div className="flex gap-3 animate-fade-in">
      <div className="flex-shrink-0 w-8 h-8 rounded-full overflow-hidden border border-gray-300/50 mt-1">
        <img src={agentIcon} alt="Berg Agent" className="w-full h-full object-cover" />
      </div>
      <div className="px-4 py-3 rounded-2xl rounded-tl-sm bg-transparent border border-gray-400/40 backdrop-blur-md">
        <div className="flex gap-1.5 items-center h-4">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="w-1.5 h-1.5 rounded-full bg-black/40 animate-typing-dot"
              style={{ animationDelay: `${i * 0.15}s` }}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
