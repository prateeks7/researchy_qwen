import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Send, Timer, Zap, Brain, Sparkles, KeyRound, X, Check } from 'lucide-react'
import { cn } from '@/lib/utils'
import { streamCompareModel, saveCompareTurn, type SSEEvent } from '@/lib/api'
import type { CompareTurn, ModelKey } from '@/types'
import chatBg from '../../utils/backgrounds/chat.jpg'

// ── Types ─────────────────────────────────────────────────────────────────────

interface ColConfig {
  key: ModelKey
  label: string
  sub: string
  icon: React.ComponentType<{ className?: string }>
  accent: string
}

interface ToolLogEntry { name: string; done: boolean }

interface ColState {
  loading: boolean
  toolLog: ToolLogEntry[]
  response: string | null
  timing: number | null
  error: string | null
}

const EMPTY_COL: ColState = { loading: false, toolLog: [], response: null, timing: null, error: null }

// ── Column config ─────────────────────────────────────────────────────────────

const COLUMNS: ColConfig[] = [
  { key: 'qwen7b',  label: 'Qwen 7B',          sub: 'Fast · selectable backend',    icon: Zap,      accent: 'border-amber-400/50' },
  { key: 'qwen72b', label: 'Qwen 72B',          sub: 'Deep · selectable backend',    icon: Brain,    accent: 'border-blue-400/50'  },
  { key: 'gemini',  label: 'Gemini 2.5 Flash',  sub: 'Google · configurable',        icon: Sparkles, accent: 'border-purple-400/50' },
]

const TOOL_CONFIG: Record<string, { emoji: string; label: string }> = {
  cache_check:                               { emoji: '🌍', label: 'Checking ChromaDB cache' },
  cache_hit:                                 { emoji: '🌍', label: 'Using ChromaDB cache' },
  cache_miss:                                { emoji: '❌', label: 'ChromaDB cache miss' },
  search_internal_knowledge:                 { emoji: '🔍', label: 'Searching knowledge base' },
  search_paper_details:                      { emoji: '🌍', label: 'Reading ChromaDB raw text' },
  search_arxiv_papers:                       { emoji: '📡', label: 'Searching arXiv' },
  download_and_parse_arxiv_paper:            { emoji: '📥', label: 'Scraping & parsing paper' },
  search_semantic_scholar:                   { emoji: '🎓', label: 'Searching Semantic Scholar' },
  get_paper_citations:                       { emoji: '🔗', label: 'Fetching citations' },
  get_author_papers:                         { emoji: '👤', label: 'Looking up author papers' },
  download_and_parse_semantic_scholar_paper: { emoji: '📥', label: 'Scraping & parsing paper' },
  search_pubmed:                             { emoji: '🧬', label: 'Searching PubMed' },
  download_pubmed_paper:                     { emoji: '📥', label: 'Scraping paper' },
  web_search_tool:                           { emoji: '🌐', label: 'Searching the web' },
  compare_papers:                            { emoji: '⚖️',  label: 'Comparing papers' },
}

// Strip [FOLLOW_UP] marker — not relevant in compare view
function stripFollowUp(text: string): string {
  const idx = text.indexOf('[FOLLOW_UP]')
  return idx === -1 ? text : text.slice(0, idx).trimEnd()
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function TimingBadge({ seconds }: { seconds: number }) {
  return (
    <span className="inline-flex items-center gap-1 text-[10px] text-black/40 bg-black/5 border border-black/10 rounded-full px-2 py-0.5">
      <Timer className="w-2.5 h-2.5" />
      {seconds.toFixed(1)}s
    </span>
  )
}

function ColHeader({ col, state, elapsed }: { col: ColConfig; state: ColState; elapsed: number }) {
  const Icon = col.icon
  return (
    <div className={cn('flex items-center justify-between px-4 py-3 border-b border-black/10 bg-white/30 backdrop-blur-sm', col.accent)}>
      <div className="flex items-center gap-2">
        <Icon className="w-4 h-4 text-black/60" />
        <div>
          <p className="text-black font-semibold text-sm leading-tight">{col.label}</p>
          <p className="text-black/40 text-[10px]">{col.sub}</p>
        </div>
      </div>
      {state.loading && (
        <div className="flex items-center gap-1.5 text-[10px] text-black/50">
          <Timer className="w-3 h-3 animate-pulse" />
          {elapsed.toFixed(1)}s
        </div>
      )}
    </div>
  )
}

function AnimatedDots() {
  return (
    <span className="flex gap-0.5">
      {[0, 1, 2].map((i) => (
        <span key={i} className="w-1 h-1 rounded-full bg-black/35 animate-typing-dot"
          style={{ animationDelay: `${i * 0.15}s` }} />
      ))}
    </span>
  )
}

function ThinkingBubble({ toolLog }: { toolLog: ToolLogEntry[] }) {
  const allDone = toolLog.length > 0 && toolLog.every((e) => e.done)
  return (
    <div className="px-3 py-4">
      <div className="px-3 py-2.5 rounded-xl bg-white/40 border border-black/10 backdrop-blur-sm min-w-[160px] inline-block">
        {toolLog.length === 0 ? (
          <div className="flex items-center gap-2 text-[12px] text-black/50">
            <span className="font-medium">Thinking</span>
            <AnimatedDots />
          </div>
        ) : (
          <div className="flex flex-col gap-1">
            <span className="text-[10px] font-semibold text-black/35 uppercase tracking-wider mb-1">Researching</span>
            {toolLog.map((entry, i) => {
              const cfg = TOOL_CONFIG[entry.name] ?? { emoji: '🔧', label: entry.name.replace(/_/g, ' ') }
              const isActive = i === toolLog.length - 1 && !entry.done
              return (
                <div key={i} className={cn('flex items-center gap-2 text-[12px] transition-opacity', entry.done ? 'opacity-25' : 'opacity-90')}>
                  <span className="text-sm leading-none">{cfg.emoji}</span>
                  <span className={cn('font-medium', entry.done ? 'text-black/50' : 'text-black/80')}>{cfg.label}</span>
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
      </div>
    </div>
  )
}

function ColBody({
  col, turns, state, colRef, pendingMessage,
}: {
  col: ColConfig
  turns: CompareTurn[]
  state: ColState
  colRef: React.RefObject<HTMLDivElement>
  pendingMessage: string | null
}) {
  const isEmpty = turns.length === 0 && !state.loading && pendingMessage === null

  return (
    <div ref={colRef} className="flex-1 overflow-y-auto" style={{ scrollbarWidth: 'thin' }}>
      {isEmpty ? (
        <div className="flex flex-col items-center justify-center h-full gap-3 text-black/30 px-4">
          <col.icon className="w-8 h-8 opacity-40" />
          <p className="text-xs text-center">Send a research question to compare all three models side by side.</p>
        </div>
      ) : (
        <>
          {turns.map((turn, i) => (
            <div key={i} className="space-y-3 py-4 border-b border-black/6 last:border-0">
              <div className="flex justify-end px-3">
                <div className="max-w-[90%] px-3 py-2 rounded-xl rounded-tr-sm border border-gray-400/40 bg-transparent text-black text-sm">
                  {turn.user_message}
                </div>
              </div>
              <div className="px-3">
                <div className="prose-chat text-sm text-black leading-relaxed">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{stripFollowUp(turn.responses[col.key])}</ReactMarkdown>
                </div>
                <div className="mt-2 flex justify-end">
                  <TimingBadge seconds={turn.timings[col.key]} />
                </div>
              </div>
            </div>
          ))}

          {/* Pending turn — user message optimistic + loading/result */}
          {pendingMessage !== null && (
            <div className="space-y-3 py-4">
              <div className="flex justify-end px-3">
                <div className="max-w-[90%] px-3 py-2 rounded-xl rounded-tr-sm border border-gray-400/40 bg-transparent text-black text-sm">
                  {pendingMessage}
                </div>
              </div>
              {state.loading ? (
                <ThinkingBubble toolLog={state.toolLog} />
              ) : state.error ? (
                <div className="px-3">
                  <p className="text-xs text-red-500 italic">{state.error}</p>
                </div>
              ) : state.response !== null ? (
                <div className="px-3">
                  <div className="prose-chat text-sm text-black leading-relaxed">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{stripFollowUp(state.response)}</ReactMarkdown>
                  </div>
                  {state.timing !== null && (
                    <div className="mt-2 flex justify-end">
                      <TimingBadge seconds={state.timing} />
                    </div>
                  )}
                </div>
              ) : null}
            </div>
          )}
        </>
      )}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

interface CompareViewProps {
  token: string
  activeSessionId: string | null
  turns: CompareTurn[]
  onBeforeSend: (message: string) => Promise<string>
  onTurnComplete: (turn: CompareTurn) => void
  hfToken: string
  onSetHfToken: (t: string) => void
  geminiToken: string
  onSetGeminiToken: (t: string) => void
}

const INIT_STATES = (): Record<ModelKey, ColState> => ({
  qwen7b: { ...EMPTY_COL },
  qwen72b: { ...EMPTY_COL },
  gemini: { ...EMPTY_COL },
})

export function CompareView({ token, activeSessionId, turns, onBeforeSend, onTurnComplete, hfToken, onSetHfToken, geminiToken, onSetGeminiToken }: CompareViewProps) {
  const [input, setInput] = useState('')
  const [colStates, setColStates] = useState<Record<ModelKey, ColState>>(INIT_STATES)
  const [pendingMessage, setPendingMessage] = useState<string | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const [showKeyModal, setShowKeyModal] = useState(false)
  const [hfDraft, setHfDraft] = useState('')
  const [geminiDraft, setGeminiDraft] = useState('')
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const ignoreSessionChangeRef = useRef<string | null>(null)
  const colRefs = {
    qwen7b:  useRef<HTMLDivElement>(null),
    qwen72b: useRef<HTMLDivElement>(null),
    gemini:  useRef<HTMLDivElement>(null),
  }

  const isAnyLoading = Object.values(colStates).some((s) => s.loading)

  // Scroll each column to bottom when turns or states change
  useEffect(() => {
    Object.values(colRefs).forEach((ref) => {
      if (ref.current) ref.current.scrollTop = ref.current.scrollHeight
    })
  }, [turns, colStates, pendingMessage])

  // Reset pending state when activeSessionId changes (switching sessions)
  useEffect(() => {
    if (activeSessionId !== null && activeSessionId === ignoreSessionChangeRef.current) {
      ignoreSessionChangeRef.current = null
      return
    }
    setPendingMessage(null)
    setColStates(INIT_STATES())
  }, [activeSessionId])

  function setCol(key: ModelKey, patch: Partial<ColState>) {
    setColStates((prev) => ({ ...prev, [key]: { ...prev[key], ...patch } }))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const message = input.trim()
    if (!message || isAnyLoading) return
    setInput('')

    const sessionId = await onBeforeSend(message)
    ignoreSessionChangeRef.current = sessionId
    setPendingMessage(message)

    // Start elapsed timer
    setElapsed(0)
    timerRef.current = setInterval(() => setElapsed((t) => +(t + 0.1).toFixed(1)), 100)

    // Mark all cols loading
    setColStates({
      qwen7b:  { loading: true, toolLog: [], response: null, timing: null, error: null },
      qwen72b: { loading: true, toolLog: [], response: null, timing: null, error: null },
      gemini:  { loading: true, toolLog: [], response: null, timing: null, error: null },
    })

    const results: Record<ModelKey, { response: string; timing: number }> = {} as never

    const runModel = async (key: ModelKey) => {
      await streamCompareModel(token, key, message, sessionId, (event: SSEEvent) => {
        if (event.type === 'tool') {
          setColStates((prev) => ({
            ...prev,
            [key]: { ...prev[key], toolLog: [...prev[key].toolLog, { name: event.name, done: false }] },
          }))
        } else if (event.type === 'tool_done') {
          setColStates((prev) => {
            const toolLog = [...prev[key].toolLog]
            // Mark the last un-done entry as done (tools run sequentially)
            const idx = toolLog.map((e) => e.done).lastIndexOf(false)
            if (idx !== -1) {
              toolLog[idx] = {
                ...toolLog[idx],
                name: event.display_name ?? (event.cache_hit ? 'cache_hit' : toolLog[idx].name),
                done: true,
              }
            }
            return { ...prev, [key]: { ...prev[key], toolLog } }
          })
        } else if (event.type === 'done') {
          results[key] = { response: event.response, timing: event.timing }
          setCol(key, { loading: false, response: event.response, timing: event.timing })
        } else if (event.type === 'error') {
          const msg = `*Error: ${event.message}*`
          results[key] = { response: msg, timing: event.timing ?? 0 }
          setCol(key, { loading: false, error: event.message, timing: event.timing ?? 0 })
        }
      }, hfToken || undefined, geminiToken || undefined)
    }

    await Promise.all(COLUMNS.map((c) => runModel(c.key)))

    // Stop timer
    if (timerRef.current) clearInterval(timerRef.current)

    // Save turn to DB
    try {
      const responses = { qwen7b: results.qwen7b?.response ?? '', qwen72b: results.qwen72b?.response ?? '', gemini: results.gemini?.response ?? '' }
      const timings = { qwen7b: results.qwen7b?.timing ?? 0, qwen72b: results.qwen72b?.timing ?? 0, gemini: results.gemini?.timing ?? 0 }
      await saveCompareTurn(token, sessionId, message, responses, timings)
      const newTurn: CompareTurn = { user_message: message, responses, timings, timestamp: new Date().toISOString() }
      onTurnComplete(newTurn)
    } catch { /* silently ignore save errors */ }

    setPendingMessage(null)
    setColStates(INIT_STATES())
  }

  function openKeyModal() { setHfDraft(hfToken); setGeminiDraft(geminiToken); setShowKeyModal(true) }
  function saveKeys() {
    const hf = hfDraft.trim()
    const gemini = geminiDraft.trim()
    onSetHfToken(hf); onSetGeminiToken(gemini)
    if (hf) localStorage.setItem('berg_hf_token', hf)
    else localStorage.removeItem('berg_hf_token')
    if (gemini) localStorage.setItem('berg_gemini_token', gemini)
    else localStorage.removeItem('berg_gemini_token')
    setShowKeyModal(false)
  }
  function clearKeys() {
    onSetHfToken(''); onSetGeminiToken('')
    setHfDraft(''); setGeminiDraft('')
    localStorage.removeItem('berg_hf_token')
    localStorage.removeItem('berg_gemini_token')
    setShowKeyModal(false)
  }

  return (
    <div
      className="relative flex flex-col flex-1 h-full overflow-hidden"
      style={{ backgroundImage: `url(${chatBg})`, backgroundSize: 'cover', backgroundPosition: 'center' }}
    >
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
            <p className="text-xs text-black/40 mb-4">Memory only — never saved. Re-enter after page refresh.</p>

            <label className="block text-xs font-medium text-black/50 mb-1">HuggingFace API Key</label>
            <input type="password" value={hfDraft} onChange={(e) => setHfDraft(e.target.value)}
              placeholder="hf_••••••••••••••••••••" autoFocus
              className="w-full px-3 py-2 rounded-xl bg-black/5 border border-black/10 text-sm font-mono text-black placeholder:text-black/30 outline-none focus:border-blue-400/60 transition-all mb-3"
            />
            <label className="block text-xs font-medium text-black/50 mb-1">Google Gemini API Key</label>
            <input type="password" value={geminiDraft} onChange={(e) => setGeminiDraft(e.target.value)}
              placeholder="AIza••••••••••••••••••••"
              className="w-full px-3 py-2 rounded-xl bg-black/5 border border-black/10 text-sm font-mono text-black placeholder:text-black/30 outline-none focus:border-purple-400/60 transition-all mb-3"
            />

            <div className="flex gap-2">
              <button onClick={saveKeys}
                className="flex-1 h-9 rounded-xl bg-blue-500 hover:bg-blue-400 text-white text-sm font-medium transition-colors flex items-center justify-center gap-1.5">
                <Check className="w-3.5 h-3.5" /> Save for session
              </button>
              {(hfToken || geminiToken ) && (
                <button onClick={clearKeys}
                  className="h-9 px-3 rounded-xl bg-red-100 hover:bg-red-200 text-red-600 text-sm font-medium transition-colors">
                  Clear all
                </button>
              )}
            </div>
          </div>
        </div>
      )}
      {/* 3-column area */}
      <div className="flex flex-1 overflow-hidden divide-x divide-black/10">
        {COLUMNS.map((col) => (
          <div key={col.key} className="flex flex-col flex-1 overflow-hidden">
            <ColHeader col={col} state={colStates[col.key]} elapsed={elapsed} />
            <ColBody
              col={col}
              turns={turns}
              state={colStates[col.key]}
              colRef={colRefs[col.key]}
              pendingMessage={pendingMessage}
            />
          </div>
        ))}
      </div>

      {/* Shared input */}
      <div className="border-t border-black/10 bg-white/20 backdrop-blur-sm px-4 py-3">
        <form onSubmit={handleSubmit} className="flex items-center gap-2 max-w-3xl mx-auto">
          <button
            type="button"
            onClick={openKeyModal}
            title="Set API Keys (HuggingFace · Gemini )"
            className={cn(
              'flex-shrink-0 flex items-center gap-1 h-9 px-2.5 rounded-xl text-[11px] font-medium transition-colors',
              (hfToken || geminiToken )
                ? 'bg-emerald-100/80 text-emerald-700 hover:bg-emerald-200/80'
                : 'bg-white/50 text-black/40 hover:bg-white/70 hover:text-black/60 border border-black/10',
            )}
          >
            <KeyRound className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">
              {[hfToken && 'HF', geminiToken && 'Gemini'].filter(Boolean).join(' · ') || 'Keys'}
              {(hfToken || geminiToken ) ? ' ✓' : ''}
            </span>
          </button>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={isAnyLoading}
            placeholder="Ask a research question — all three models will answer…"
            className="flex-1 px-4 py-2.5 rounded-xl bg-white/70 border border-black/20 text-black placeholder:text-black/35 text-sm outline-none focus:border-black/40 transition-all disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!input.trim() || isAnyLoading}
            className={cn(
              'flex-shrink-0 w-9 h-9 rounded-xl flex items-center justify-center transition-all',
              input.trim() && !isAnyLoading ? 'bg-black/80 hover:bg-black text-white' : 'bg-black/10 text-black/30 cursor-not-allowed',
            )}
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
        <p className="text-[10px] text-black/30 text-center mt-1.5">
          Qwen 7B · Qwen 72B · Gemini 2.5 Flash — each column updates independently
        </p>
      </div>
    </div>
  )
}
