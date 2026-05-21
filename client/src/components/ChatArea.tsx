import { useEffect, useRef, useState, useCallback } from 'react'
import type { ComponentType } from 'react'
import { Brain, Sparkles, Telescope, Volume2, VolumeX, Zap, HardDrive, KeyRound, X, Check, AlertCircle } from 'lucide-react'
import { MessageBubble, TypingIndicator, type ToolLogEntry } from '@/components/MessageBubble'
import { ChatInput } from '@/components/ChatInput'
import type { Conversation, ModelKey } from '@/types'
import chatBg from '../../utils/backgrounds/chat.jpg'
import { randomVibe, nextVibe, type Vibe } from '@/lib/vibes'
import { cn } from '@/lib/utils'

interface ModelDef {
  key: ModelKey
  label: string
  icon: ComponentType<{ className?: string }>
  requiresHfKey?: boolean
  local?: boolean
}

const MODELS: ModelDef[] = [
  { key: 'qwen7b',   label: 'Qwen 7B',        icon: Zap },
  { key: 'qwen72b',  label: 'HF Qwen 72B',    icon: Brain,     requiresHfKey: true },
  { key: 'local72b', label: 'Local Qwen 72B',  icon: HardDrive, local: true },
  { key: 'gemini',   label: 'Gemini Flash',    icon: Sparkles },
]

interface ChatAreaProps {
  conversation: Conversation | null
  onSendMessage: (content: string) => void
  isLoading?: boolean
  toolLog?: ToolLogEntry[]
  isMuted?: boolean
  onToggleMute?: () => void
  selectedModel: ModelKey
  onSelectModel: (model: ModelKey) => void
  hfToken: string
  onSetHfToken: (token: string) => void
  geminiToken: string
  onSetGeminiToken: (token: string) => void
  localAvailable: boolean | null
  onRecheckLocal: () => void
}

export function ChatArea({
  conversation,
  onSendMessage,
  isLoading = false,
  toolLog = [],
  isMuted = false,
  onToggleMute,
  selectedModel,
  onSelectModel,
  hfToken,
  onSetHfToken,
  geminiToken,
  onSetGeminiToken,
  localAvailable,
  onRecheckLocal,
}: ChatAreaProps) {
  const bottomRef   = useRef<HTMLDivElement>(null)
  const audioRef    = useRef<HTMLAudioElement | null>(null)
  const [vibe, setVibe] = useState<Vibe>(randomVibe)
  const [showKeyModal, setShowKeyModal] = useState(false)
  const [hfDraft, setHfDraft] = useState('')
  const [geminiDraft, setGeminiDraft] = useState('')

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
  }, [isLoading])

  // ── Sync mute toggle to currently playing audio ────────────────────────────
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.volume = isMuted ? 0 : vibe.musicVolume
    }
  }, [isMuted])

  // ── Cycle to next vibe ─────────────────────────────────────────────────────
  const handleNextVibe = useCallback(() => {
    const next = nextVibe(vibe)
    setVibe(next)
    if (audioRef.current) audioRef.current.pause()
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

  function openKeyModal() {
    setHfDraft(hfToken)
    setGeminiDraft(geminiToken)
    setShowKeyModal(true)
  }

  function saveKeys() {
    onSetHfToken(hfDraft.trim())
    onSetGeminiToken(geminiDraft.trim())
    setShowKeyModal(false)
  }

  function clearKeys() {
    onSetHfToken(''); onSetGeminiToken('')
    setHfDraft(''); setGeminiDraft('')
    setShowKeyModal(false)
  }

  function handleModelSelect(key: ModelKey) {
    if (key === 'local72b' && localAvailable === false) return
    onSelectModel(key)
    if (key === 'qwen72b' && !hfToken) {
      openKeyModal()
    }
  }

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

      {/* API Keys Modal */}
      {showKeyModal && (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="bg-white/90 backdrop-blur-md border border-black/10 rounded-2xl shadow-2xl p-6 w-full max-w-sm mx-4">
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                <KeyRound className="w-4 h-4 text-black/60" />
                <h3 className="text-sm font-semibold text-black">API Keys</h3>
              </div>
              <button onClick={() => setShowKeyModal(false)} className="p-1 rounded-lg hover:bg-black/10 transition-colors">
                <X className="w-4 h-4 text-black/50" />
              </button>
            </div>
            <p className="text-xs text-black/40 mb-4 leading-relaxed">
              Memory only — never saved. Re-enter after page refresh.
            </p>

            <label className="block text-xs font-medium text-black/50 mb-1">HuggingFace API Key</label>
            <input
              type="password"
              value={hfDraft}
              onChange={(e) => setHfDraft(e.target.value)}
              placeholder="hf_••••••••••••••••••••"
              autoFocus
              className="w-full px-3 py-2 rounded-xl bg-black/5 border border-black/10 text-sm font-mono text-black placeholder:text-black/30 outline-none focus:border-blue-400/60 focus:bg-white/60 transition-all mb-3"
            />

            <label className="block text-xs font-medium text-black/50 mb-1">Google Gemini API Key</label>
            <input
              type="password"
              value={geminiDraft}
              onChange={(e) => setGeminiDraft(e.target.value)}
              placeholder="AIza••••••••••••••••••••"
              className="w-full px-3 py-2 rounded-xl bg-black/5 border border-black/10 text-sm font-mono text-black placeholder:text-black/30 outline-none focus:border-purple-400/60 focus:bg-white/60 transition-all mb-3"
            />

            <div className="flex gap-2">
              <button
                onClick={saveKeys}
                className="flex-1 h-9 rounded-xl bg-blue-500 hover:bg-blue-400 text-white text-sm font-medium transition-colors flex items-center justify-center gap-1.5"
              >
                <Check className="w-3.5 h-3.5" /> Save for session
              </button>
              {(hfToken || geminiToken ) && (
                <button
                  onClick={clearKeys}
                  className="h-9 px-3 rounded-xl bg-red-100 hover:bg-red-200 text-red-600 text-sm font-medium transition-colors"
                >
                  Clear all
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Content */}
      <div className="relative z-10 flex flex-col h-full">
        {/* Header */}
        <header className="flex items-center justify-between px-6 py-4 border-b border-black/10 bg-white/20 backdrop-blur-sm">
          <div className="flex items-center gap-2 min-w-0">
            <Telescope className="w-4 h-4 text-black/50" />
            <h2 className="text-black font-sans text-sm font-medium truncate max-w-md">
              {conversation?.title ?? 'Researchy Berg'}
            </h2>
          </div>
          <div className="flex items-center gap-3">
            {/* Model selector */}
            <ModelPicker
              models={MODELS}
              selected={selectedModel}
              onSelect={handleModelSelect}
              disabled={isLoading}
              localAvailable={localAvailable}
              className="hidden sm:flex"
            />

            {/* HF Key button */}
            <button
              onClick={openKeyModal}
              title="Set API Keys (HuggingFace · Gemini)"
              className={cn(
                'flex items-center gap-1.5 h-7 px-2.5 rounded-lg text-[11px] font-medium transition-colors',
                (hfToken || geminiToken )
                  ? 'bg-emerald-100/80 text-emerald-700 hover:bg-emerald-200/80'
                  : 'bg-black/10 text-black/50 hover:bg-black/20 hover:text-black',
              )}
            >
              <KeyRound className="w-3 h-3" />
              <span>
                {[hfToken && 'HF', geminiToken && 'Gemini'].filter(Boolean).join(' · ') || 'API Keys'}
                {(hfToken || geminiToken ) ? ' ✓' : ''}
              </span>
            </button>

            {/* Mute */}
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
            <span className="text-black/50 font-sans text-xs hidden md:inline">Berg Agent</span>
          </div>
        </header>

        {/* HF key warning banner */}
        {selectedModel === 'qwen72b' && !hfToken && (
          <div className="flex items-center gap-2 px-6 py-2 bg-amber-50/80 border-b border-amber-200/60 text-amber-700 text-xs">
            <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
            <span>HF Qwen 72B requires your HuggingFace API key.&nbsp;</span>
            <button onClick={openKeyModal} className="underline font-medium hover:text-amber-900 transition-colors">Set key →</button>
          </div>
        )}
        {selectedModel === 'gemini' && !geminiToken && (
          <div className="flex items-center gap-2 px-6 py-2 bg-purple-50/80 border-b border-purple-200/60 text-purple-700 text-xs">
            <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
            <span>Gemini Flash requires your Google API key.&nbsp;</span>
            <button onClick={openKeyModal} className="underline font-medium hover:text-purple-900 transition-colors">Set key →</button>
          </div>
        )}

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
          {/* Mobile model picker */}
          <div className="sm:hidden px-4 pt-3">
            <ModelPicker
              models={MODELS}
              selected={selectedModel}
              onSelect={handleModelSelect}
              disabled={isLoading}
              localAvailable={localAvailable}
              mobile
            />
          </div>
          <ChatInput onSend={onSendMessage} disabled={isLoading} />
        </div>
      </div>
    </main>
  )
}

// ── Model Picker ──────────────────────────────────────────────────────────────

interface ModelPickerProps {
  models: ModelDef[]
  selected: ModelKey
  onSelect: (key: ModelKey) => void
  disabled: boolean
  localAvailable: boolean | null
  className?: string
  mobile?: boolean
}

function ModelPicker({ models, selected, onSelect, disabled, localAvailable, className, mobile }: ModelPickerProps) {
  return (
    <div
      className={cn(
        mobile
          ? 'grid grid-cols-4 gap-1 rounded-xl bg-white/35 border border-black/10 p-1 backdrop-blur-sm'
          : 'items-center gap-1 rounded-xl bg-white/35 border border-black/10 p-1',
        className,
      )}
    >
      {models.map((model) => {
        const Icon = model.icon
        const active = selected === model.key
        const unavailable = model.local && localAvailable === false
        const checking = model.local && localAvailable === null

        return (
          <div key={model.key} className="relative group">
            <button
              type="button"
              onClick={() => onSelect(model.key)}
              disabled={disabled || unavailable}
              title={
                unavailable
                  ? 'Local Qwen 72B — Ollama not running'
                  : checking
                  ? 'Checking local model…'
                  : model.label
              }
              className={cn(
                mobile
                  ? 'h-8 w-full rounded-lg inline-flex items-center justify-center gap-1 text-[10px] font-medium transition-colors'
                  : 'h-7 px-2.5 rounded-lg inline-flex items-center gap-1.5 text-[11px] font-medium transition-colors',
                active && !unavailable
                  ? 'bg-black/80 text-white'
                  : unavailable
                  ? 'text-black/25 cursor-not-allowed'
                  : 'text-black/55 hover:bg-black/10 hover:text-black',
                (disabled && !unavailable) && 'opacity-60 cursor-not-allowed',
              )}
            >
              <Icon className="w-3.5 h-3.5 flex-shrink-0" />
              <span className={mobile ? 'truncate text-[9px]' : ''}>
                {mobile ? model.label.split(' ').slice(-1)[0] : model.label}
              </span>
              {unavailable && (
                <AlertCircle className="w-2.5 h-2.5 text-black/30 ml-0.5" />
              )}
            </button>

            {/* Tooltip for unavailable local model */}
            {unavailable && (
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 rounded-lg bg-black/80 text-white text-[10px] whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50">
                Ollama not running
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ── Empty state ───────────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 px-6 py-10">
      <div className="text-center space-y-3">
        <div className="w-16 h-16 rounded-2xl bg-white/30 border border-black/10 flex items-center justify-center mx-auto backdrop-blur-sm">
          <Telescope className="w-8 h-8 text-black/60" />
        </div>
        <h2 className="text-black font-sans text-xl font-semibold">Researchy Berg</h2>
        <p className="text-black/55 font-sans text-sm max-w-sm">
          Your AI-powered research assistant. Ask me about academic papers, citations, and research topics.
        </p>
      </div>
    </div>
  )
}
