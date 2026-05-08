import { useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { User, MessageCircle, ChevronRight, VolumeX, Volume2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Message } from '@/types'
import agentIcon from '../../utils/backgrounds/Icon.png'
import type { Vibe } from '@/lib/vibes'

interface ToolConfig { emoji: string; label: string }

const TOOL_CONFIG: Record<string, ToolConfig> = {
  search_internal_knowledge:                 { emoji: '⚡', label: 'Checking Vector DB' },
  search_paper_details:                      { emoji: '🔍', label: 'Reading paper details' },
  search_arxiv_papers:                       { emoji: '📡', label: 'Searching arXiv' },
  download_and_parse_arxiv_paper:            { emoji: '📥', label: 'Downloading & parsing paper' },
  search_semantic_scholar:                   { emoji: '🎓', label: 'Searching Semantic Scholar' },
  get_paper_citations:                       { emoji: '🔗', label: 'Fetching citations' },
  get_author_papers:                         { emoji: '👤', label: 'Looking up author papers' },
  download_and_parse_semantic_scholar_paper: { emoji: '📥', label: 'Downloading & parsing paper' },
  search_pubmed:                             { emoji: '🧬', label: 'Searching PubMed' },
  download_pubmed_paper:                     { emoji: '📥', label: 'Downloading paper' },
  web_search_tool:                           { emoji: '🌐', label: 'Searching the web' },
  compare_papers:                            { emoji: '⚖️',  label: 'Comparing papers' },
}

export interface ToolLogEntry { name: string; done: boolean }

interface MessageBubbleProps { message: Message }

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

function AnimatedDots() {
  return (
    <span className="flex gap-0.5">
      {[0, 1, 2].map((j) => (
        <span
          key={j}
          className="w-1 h-1 rounded-full bg-black/40 animate-typing-dot"
          style={{ animationDelay: `${j * 0.15}s` }}
        />
      ))}
    </span>
  )
}

// ── Tenor GIF embed ──────────────────────────────────────────────────────────

function TenorGif({ vibe }: { vibe: Vibe }) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // Re-inject Tenor's embed script each time the GIF postId changes so it
    // processes the new .tenor-gif-embed div
    const old = document.querySelector('script[src*="tenor.com/embed.js"]')
    if (old) old.remove()

    const s = document.createElement('script')
    s.src   = 'https://tenor.com/embed.js'
    s.async = true
    document.head.appendChild(s)

    return () => { s.remove() }
  }, [vibe.gifPostId])

  return (
    <div ref={containerRef} className="w-full rounded-xl overflow-hidden">
      <div
        key={vibe.gifPostId}           // key forces React to remount when gif changes
        className="tenor-gif-embed"
        data-postid={vibe.gifPostId}
        data-share-method="host"
        data-aspect-ratio={vibe.gifAspectRatio}
        data-width="100%"
      >
        {/* Direct img fallback — shows instantly while Tenor JS loads */}
        <img
          src={`https://media.tenor.com/${vibe.gifPostId}/tenor.gif`}
          alt={`${vibe.label} vibe gif`}
          className="w-full object-cover"
          style={{ aspectRatio: vibe.gifAspectRatio }}
        />
      </div>
    </div>
  )
}

// ── TypingIndicator ──────────────────────────────────────────────────────────

interface TypingIndicatorProps {
  toolLog?:      ToolLogEntry[]
  vibe:          Vibe
  isMuted?:      boolean
  onNextVibe?:   () => void
  onToggleMute?: () => void
}

export function TypingIndicator({
  toolLog      = [],
  vibe,
  isMuted      = false,
  onNextVibe,
  onToggleMute,
}: TypingIndicatorProps) {
  const allDone = toolLog.length > 0 && toolLog.every((e) => e.done)

  return (
    <div className="flex gap-3 animate-fade-in">
      <div className="flex-shrink-0 w-8 h-8 rounded-full overflow-hidden border border-gray-300/50 mt-1">
        <img src={agentIcon} alt="Berg Agent" className="w-full h-full object-cover" />
      </div>

      <div className="px-4 py-3 rounded-2xl rounded-tl-sm bg-transparent border border-gray-400/40 backdrop-blur-md min-w-[260px] max-w-[340px]">

        {/* Tool log */}
        {toolLog.length === 0 ? (
          <div className="flex items-center gap-2 text-[12px] text-black/50">
            <span className="font-medium">Thinking</span>
            <AnimatedDots />
          </div>
        ) : (
          <div className="flex flex-col gap-1">
            <span className="text-[10px] font-semibold text-black/35 uppercase tracking-wider mb-1.5">
              Researching
            </span>
            {toolLog.map((entry, i) => {
              const cfg      = TOOL_CONFIG[entry.name] ?? { emoji: '🔧', label: entry.name.replace(/_/g, ' ') }
              const isActive = i === toolLog.length - 1 && !entry.done
              return (
                <div
                  key={i}
                  className={cn(
                    'flex items-center gap-2 text-[12px] transition-opacity duration-300',
                    entry.done ? 'opacity-25' : 'opacity-90',
                  )}
                >
                  <span className="text-sm leading-none">{cfg.emoji}</span>
                  <span className={cn('font-medium', entry.done ? 'text-black/50' : 'text-black/80')}>
                    {cfg.label}
                  </span>
                  {isActive && <AnimatedDots />}
                </div>
              )
            })}
            {allDone && (
              <div className="flex items-center gap-2 text-[12px] text-black/40 mt-0.5">
                <span className="font-medium">Processing</span>
                <AnimatedDots />
              </div>
            )}
          </div>
        )}

        {/* GIF */}
        <div className="mt-3">
          <TenorGif vibe={vibe} />
        </div>

        {/* Controls row: vibe label | mute button | next-vibe arrow */}
        <div className="flex items-center justify-between mt-2">
          <span className="text-[10px] text-black/35 font-medium tracking-wide uppercase">
            {vibe.label}
          </span>
          <div className="flex items-center gap-1">
            {/* Mute / unmute — separate from next-vibe */}
            <button
              id="typing-mute-btn"
              onClick={onToggleMute}
              title={isMuted ? 'Unmute' : 'Mute'}
              className="flex items-center justify-center w-6 h-6 rounded-lg bg-black/8 hover:bg-black/15 transition-colors"
            >
              {isMuted
                ? <VolumeX className="w-3 h-3 text-black/50" />
                : <Volume2 className="w-3 h-3 text-black/50" />}
            </button>
            {/* Next vibe arrow */}
            <button
              id="next-vibe-btn"
              onClick={onNextVibe}
              title="Next vibe"
              className="flex items-center justify-center w-6 h-6 rounded-lg bg-black/8 hover:bg-black/15 transition-colors"
            >
              <ChevronRight className="w-3.5 h-3.5 text-black/50 hover:text-black/70 transition-colors" />
            </button>
          </div>
        </div>

      </div>
    </div>
  )
}
