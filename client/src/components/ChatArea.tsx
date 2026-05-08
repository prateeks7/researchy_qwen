import { useEffect, useRef, useState, useCallback } from 'react'
import { Telescope, Volume2, VolumeX } from 'lucide-react'
import { MessageBubble, TypingIndicator, type ToolLogEntry } from '@/components/MessageBubble'
import { ChatInput } from '@/components/ChatInput'
import type { Conversation } from '@/types'
import chatBg from '../../utils/backgrounds/chat.jpg'
import { randomVibe, nextVibe, type Vibe } from '@/lib/vibes'

interface ChatAreaProps {
  conversation: Conversation | null
  onSendMessage: (content: string) => void
  isLoading?: boolean
  toolLog?: ToolLogEntry[]
  isMuted?: boolean
  onToggleMute?: () => void
}

export function ChatArea({
  conversation,
  onSendMessage,
  isLoading = false,
  toolLog = [],
  isMuted = false,
  onToggleMute,
}: ChatAreaProps) {
  const bottomRef   = useRef<HTMLDivElement>(null)
  const audioRef    = useRef<HTMLAudioElement | null>(null)
  const [vibe, setVibe] = useState<Vibe>(randomVibe)

  // ── Pick a fresh random vibe each time loading starts ──────────────────────
  useEffect(() => {
    if (isLoading) {
      const v = randomVibe()
      setVibe(v)

      const audio = new Audio(v.music)
      audio.currentTime = v.musicStartAt
      audio.loop        = true
      audio.volume      = isMuted ? 0 : v.musicVolume
      audio.play().catch(() => {})
      audioRef.current = audio
    } else {
      audioRef.current?.pause()
      audioRef.current = null
    }
    return () => { audioRef.current?.pause() }
  }, [isLoading])  // intentionally omit isMuted — synced below

  // ── Sync mute toggle to currently playing audio ────────────────────────────
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.volume = isMuted ? 0 : vibe.musicVolume
    }
  }, [isMuted])

  // ── Cycle to next vibe (new gif + music) without stopping ──────────────────
  const handleNextVibe = useCallback(() => {
    const next = nextVibe(vibe)
    setVibe(next)

    // Swap music on the fly if loading is active
    if (audioRef.current) {
      audioRef.current.pause()
    }
    if (isLoading) {
      const audio = new Audio(next.music)
      audio.currentTime = next.musicStartAt
      audio.loop        = true
      audio.volume      = isMuted ? 0 : next.musicVolume
      audio.play().catch(() => {})
      audioRef.current = audio
    }
  }, [vibe, isLoading, isMuted])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [conversation?.messages, isLoading])

  const isEmpty = !conversation || conversation.messages.length === 0

  return (
    <main
      className="relative flex flex-col flex-1 h-full overflow-hidden"
      style={{
        backgroundImage: `url(${chatBg})`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      }}
    >
      {/* Overlay */}
      <div className="absolute inset-0 bg-transparent" />

      {/* Content */}
      <div className="relative z-10 flex flex-col h-full">
        {/* Header */}
        <header className="flex items-center justify-between px-6 py-4 border-b border-black/10 bg-white/20 backdrop-blur-sm">
          <div className="flex items-center gap-2">
            <Telescope className="w-4 h-4 text-black/50" />
            <h2 className="text-black font-sans text-sm font-medium truncate max-w-md">
              {conversation?.title ?? 'Researchy Berg'}
            </h2>
          </div>
          <div className="flex items-center gap-2">
            <button
              id="mute-toggle-btn"
              onClick={onToggleMute}
              title={isMuted ? 'Unmute music' : 'Mute music'}
              className="flex items-center justify-center w-7 h-7 rounded-full bg-black/10 hover:bg-black/20 transition-colors"
            >
              {isMuted
                ? <VolumeX className="w-3.5 h-3.5 text-black/60" />
                : <Volume2 className="w-3.5 h-3.5 text-black/60" />}
            </button>
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-black/50 font-sans text-xs">Berg Agent</span>
          </div>
        </header>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto">
          {isEmpty ? (
            <EmptyState />
          ) : (
            <div className="flex flex-col gap-6 px-6 py-6 max-w-4xl mx-auto w-full">
              {(conversation?.messages ?? []).map((msg) => (
                <MessageBubble key={msg.id} message={msg} />
              ))}
              {isLoading && (
                <TypingIndicator
                  toolLog={toolLog}
                  vibe={vibe}
                  isMuted={isMuted}
                  onNextVibe={handleNextVibe}
                  onToggleMute={onToggleMute}
                />
              )}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        {/* Input */}
        <div className="max-w-4xl mx-auto w-full">
          <ChatInput onSend={onSendMessage} disabled={isLoading} />
        </div>
      </div>
    </main>
  )
}

function EmptyState() {
  const suggestions = [
    'Summarize recent papers on RAG architectures',
    'Find citations for the original BERT paper',
    'What are the key findings in chain-of-thought research?',
    'Compare GPT-4 and Llama 3 on reasoning benchmarks',
  ]

  return (
    <div className="flex flex-col items-center justify-center h-full gap-8 px-6 py-10">
      <div className="text-center space-y-3">
        <div className="w-16 h-16 rounded-2xl bg-white/30 border border-black/10 flex items-center justify-center mx-auto backdrop-blur-sm">
          <Telescope className="w-8 h-8 text-black/60" />
        </div>
        <h2 className="text-black font-sans text-xl font-semibold">Researchy Berg</h2>
        <p className="text-black/55 font-sans text-sm max-w-sm">
          Your AI-powered research assistant. Ask me about academic papers, citations, and research topics.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-2xl">
        {suggestions.map((s) => (
          <SuggestionCard key={s} text={s} />
        ))}
      </div>
    </div>
  )
}

function SuggestionCard({ text }: { text: string }) {
  return (
    <button className="text-left px-4 py-3 rounded-xl bg-white/25 border border-black/10 hover:bg-white/40 hover:border-black/20 transition-all duration-150 backdrop-blur-sm group">
      <p className="text-black/65 font-sans group-hover:text-black text-sm leading-snug transition-colors">
        {text}
      </p>
    </button>
  )
}
