import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Send, Timer, Zap, Brain, Sparkles, Wrench } from 'lucide-react'
import { cn } from '@/lib/utils'
import { streamCompareModel, saveCompareTurn, type SSEEvent } from '@/lib/api'
import type { CompareTurn } from '@/types'
import chatBg from '../../utils/backgrounds/chat.jpg'

// ── Types ─────────────────────────────────────────────────────────────────────

type ModelKey = 'qwen7b' | 'qwen72b' | 'gemini'

interface ColConfig {
  key: ModelKey
  label: string
  sub: string
  icon: React.ComponentType<{ className?: string }>
  accent: string
}

interface ColState {
  loading: boolean
  currentTool: string | null
  response: string | null
  timing: number | null
  error: string | null
}

const EMPTY_COL: ColState = { loading: false, currentTool: null, response: null, timing: null, error: null }

// ── Column config ─────────────────────────────────────────────────────────────

const COLUMNS: ColConfig[] = [
  { key: 'qwen7b',  label: 'Qwen 7B',          sub: 'Fast · OpenRouter',          icon: Zap,      accent: 'border-amber-400/50' },
  { key: 'qwen72b', label: 'Qwen 72B',          sub: 'Powerful · HuggingFace',     icon: Brain,    accent: 'border-blue-400/50'  },
  { key: 'gemini',  label: 'Gemini 2.5 Flash',  sub: 'Google · Multimodal',        icon: Sparkles, accent: 'border-purple-400/50' },
]

// Human-readable tool labels shown in typing indicator
const TOOL_LABELS: Record<string, string> = {
  search_arxiv_papers:                      'Searching arXiv…',
  download_and_parse_arxiv_paper:           'Downloading paper…',
  search_semantic_scholar:                  'Searching Semantic Scholar…',
  get_paper_citations:                      'Fetching citations…',
  get_author_papers:                        'Looking up author…',
  download_and_parse_semantic_scholar_paper:'Downloading paper…',
  search_pubmed:                            'Searching PubMed…',
  download_pubmed_paper:                    'Downloading paper…',
  web_search_tool:                          'Searching web…',
  search_internal_knowledge:               'Checking knowledge base…',
  search_paper_details:                     'Reading paper details…',
}

function toolLabel(name: string): string {
  return TOOL_LABELS[name] ?? `Calling ${name}…`
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

function ThinkingBubble({ tool }: { tool: string | null }) {
  return (
    <div className="flex flex-col items-start gap-2 px-3 py-4">
      <div className="flex items-center gap-2 px-3 py-2.5 rounded-xl bg-white/40 border border-black/10 backdrop-blur-sm">
        <div className="flex gap-1">
          {[0, 1, 2].map((i) => (
            <span key={i} className="w-1.5 h-1.5 rounded-full bg-black/35 animate-typing-dot"
              style={{ animationDelay: `${i * 0.15}s` }} />
          ))}
        </div>
        {tool && (
          <span className="flex items-center gap-1 text-[11px] text-black/50 italic">
            <Wrench className="w-3 h-3" />
            {toolLabel(tool)}
          </span>
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
                <ThinkingBubble tool={state.currentTool} />
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
  onBeforeSend: (message: string) => Promise<string>   // ensures session exists, returns sessionId
  onTurnComplete: (turn: CompareTurn) => void
}

const INIT_STATES = (): Record<ModelKey, ColState> => ({
  qwen7b: { ...EMPTY_COL },
  qwen72b: { ...EMPTY_COL },
  gemini: { ...EMPTY_COL },
})

export function CompareView({ token, activeSessionId, turns, onBeforeSend, onTurnComplete }: CompareViewProps) {
  const [input, setInput] = useState('')
  const [colStates, setColStates] = useState<Record<ModelKey, ColState>>(INIT_STATES)
  const [pendingMessage, setPendingMessage] = useState<string | null>(null)
  const [elapsed, setElapsed] = useState(0)
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
      qwen7b:  { loading: true, currentTool: null, response: null, timing: null, error: null },
      qwen72b: { loading: true, currentTool: null, response: null, timing: null, error: null },
      gemini:  { loading: true, currentTool: null, response: null, timing: null, error: null },
    })

    const results: Record<ModelKey, { response: string; timing: number }> = {} as never

    const runModel = async (key: ModelKey) => {
      await streamCompareModel(token, key, message, sessionId, (event: SSEEvent) => {
        if (event.type === 'tool') {
          setCol(key, { currentTool: event.name })
        } else if (event.type === 'tool_done') {
          setCol(key, { currentTool: null })
        } else if (event.type === 'done') {
          results[key] = { response: event.response, timing: event.timing }
          setCol(key, { loading: false, currentTool: null, response: event.response, timing: event.timing })
        } else if (event.type === 'error') {
          const msg = `*Error: ${event.message}*`
          results[key] = { response: msg, timing: event.timing ?? 0 }
          setCol(key, { loading: false, currentTool: null, error: event.message, timing: event.timing ?? 0 })
        }
      })
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

  return (
    <div
      className="flex flex-col flex-1 h-full overflow-hidden"
      style={{ backgroundImage: `url(${chatBg})`, backgroundSize: 'cover', backgroundPosition: 'center' }}
    >
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
        <form onSubmit={handleSubmit} className="flex items-center gap-3 max-w-3xl mx-auto">
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
