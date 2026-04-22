import { useState, useCallback, useEffect, useRef } from 'react'
import { AuthProvider, useAuth } from '@/contexts/AuthContext'
import { LoginPage } from '@/pages/LoginPage'
import { Sidebar } from '@/components/Sidebar'
import { ChatArea } from '@/components/ChatArea'
import { CompareView } from '@/components/CompareView'
import type { Conversation, Message, CompareSession, CompareTurn } from '@/types'
import {
  sendMessage,
  getSessions, createSession, getSessionDetail, deleteSession,
  getCompareSessions, createCompareSession,
  getCompareSessionDetail, deleteCompareSession,
} from '@/lib/api'

function generateId() {
  return Math.random().toString(36).slice(2, 11)
}

function ChatApp() {
  const { token } = useAuth()

  // ── Chat state ────────────────────────────────────────────────────────────
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [isChatLoading, setIsChatLoading] = useState(false)

  // ── Compare state ─────────────────────────────────────────────────────────
  const [compareMode, setCompareMode] = useState(false)
  const [compareSessions, setCompareSessions] = useState<CompareSession[]>([])
  const [activeCompareId, setActiveCompareId] = useState<string | null>(null)
  const [compareTurns, setCompareTurns] = useState<CompareTurn[]>([])

  const activeConversation = conversations.find((c) => c.id === activeId) ?? null

  // ── Load sessions ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (!token) return
    getSessions(token).then((sessions) => {
      setConversations(
        sessions.map((s) => ({
          id: s.session_id, title: s.title, messages: [],
          createdAt: new Date(s.created_at),
        })),
      )
    })
    getCompareSessions(token).then(setCompareSessions)
  }, [token])

  // ── Chat handlers ─────────────────────────────────────────────────────────
  const handleSelect = useCallback(async (id: string) => {
    setActiveId(id)
    const already = conversations.find((c) => c.id === id)
    if (!already || already.messages.length > 0) return
    try {
      const detail = await getSessionDetail(token!, id)
      setConversations((prev) =>
        prev.map((c) =>
          c.id !== id ? c : {
            ...c,
            messages: detail.messages.map((m) => ({
              id: generateId(), role: m.role as 'user' | 'assistant',
              content: m.content, timestamp: new Date(m.timestamp),
            })),
          },
        ),
      )
    } catch { /* silently ignore */ }
  }, [token, conversations])

  const handleNewChat = useCallback(async () => {
    if (!token) return
    const session = await createSession(token, 'New conversation')
    const newConv: Conversation = {
      id: session.session_id, title: session.title, messages: [],
      createdAt: new Date(session.created_at),
    }
    setConversations((prev) => [newConv, ...prev])
    setActiveId(newConv.id)
    setCompareMode(false)
  }, [token])

  const handleSendMessage = useCallback(async (content: string) => {
    if (!token) return
    let targetId = activeId
    if (!targetId) {
      const title = content.slice(0, 48) + (content.length > 48 ? '…' : '')
      const session = await createSession(token, title)
      const newConv: Conversation = {
        id: session.session_id, title: session.title, messages: [],
        createdAt: new Date(session.created_at),
      }
      setConversations((prev) => [newConv, ...prev])
      setActiveId(newConv.id)
      targetId = newConv.id
    }
    const userMsg: Message = { id: generateId(), role: 'user', content, timestamp: new Date() }
    setConversations((prev) =>
      prev.map((c) => {
        if (c.id !== targetId) return c
        const isFirst = c.messages.length === 0
        return {
          ...c,
          title: isFirst ? content.slice(0, 48) + (content.length > 48 ? '…' : '') : c.title,
          messages: [...c.messages, userMsg],
        }
      }),
    )
    setIsChatLoading(true)
    try {
      const response = await sendMessage(token, content, targetId)
      const assistantMsg: Message = { id: generateId(), role: 'assistant', content: response, timestamp: new Date() }
      setConversations((prev) =>
        prev.map((c) => c.id === targetId ? { ...c, messages: [...c.messages, assistantMsg] } : c),
      )
    } catch (err) {
      const errorMsg: Message = {
        id: generateId(), role: 'assistant',
        content: `**Error:** ${err instanceof Error ? err.message : 'Unknown error'}`,
        timestamp: new Date(),
      }
      setConversations((prev) =>
        prev.map((c) => c.id === targetId ? { ...c, messages: [...c.messages, errorMsg] } : c),
      )
    } finally {
      setIsChatLoading(false)
    }
  }, [activeId, token])

  const handleDeleteConversation = useCallback(async (id: string) => {
    if (!token) return
    try { await deleteSession(token, id) } catch { /* ignore */ }
    setConversations((prev) => {
      const filtered = prev.filter((c) => c.id !== id)
      if (id === activeId) setActiveId(filtered.length > 0 ? filtered[0].id : null)
      return filtered
    })
  }, [activeId, token])

  // ── Compare handlers ──────────────────────────────────────────────────────
  const handleSelectCompare = useCallback(async (id: string) => {
    setActiveCompareId(id)
    setCompareTurns([])
    try {
      const detail = await getCompareSessionDetail(token!, id)
      setCompareTurns(detail.turns)
    } catch { /* silently ignore */ }
  }, [token])

  const handleNewCompare = useCallback(async () => {
    if (!token) return
    const session = await createCompareSession(token, 'New comparison')
    setCompareSessions((prev) => [session, ...prev])
    setActiveCompareId(session.session_id)
    setCompareTurns([])
    setCompareMode(true)
  }, [token])

  const handleDeleteCompare = useCallback(async (id: string) => {
    if (!token) return
    try { await deleteCompareSession(token, id) } catch { /* ignore */ }
    setCompareSessions((prev) => {
      const filtered = prev.filter((s) => s.session_id !== id)
      if (id === activeCompareId) {
        setActiveCompareId(filtered.length > 0 ? filtered[0].session_id : null)
        setCompareTurns([])
      }
      return filtered
    })
  }, [activeCompareId, token])

  // Called by CompareView before sending — ensures a session exists, returns sessionId
  const handleBeforeCompareSend = useCallback(async (message: string): Promise<string> => {
    if (!token) throw new Error('Not authenticated')
    if (activeCompareId) return activeCompareId
    const title = message.slice(0, 48) + (message.length > 48 ? '…' : '')
    const session = await createCompareSession(token, title)
    setCompareSessions((prev) => [session, ...prev])
    setActiveCompareId(session.session_id)
    return session.session_id
  }, [activeCompareId, token])

  // Called by CompareView after all 3 streams complete
  const handleCompareTurnComplete = useCallback((turn: CompareTurn) => {
    setCompareTurns((prev) => [...prev, turn])
    setCompareSessions((prev) =>
      prev.map((s) =>
        s.session_id === activeCompareId && s.title === 'New comparison'
          ? { ...s, title: turn.user_message.slice(0, 48) + (turn.user_message.length > 48 ? '…' : '') }
          : s,
      ),
    )
  }, [activeCompareId])

  const handleToggleCompareMode = useCallback(() => {
    setCompareMode((m) => !m)
  }, [])

  return (
    <div className="flex h-screen w-screen overflow-hidden">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        onSelect={(id) => { handleSelect(id); setCompareMode(false) }}
        onNewChat={handleNewChat}
        onDelete={handleDeleteConversation}
        compareSessions={compareSessions}
        activeCompareId={activeCompareId}
        onSelectCompare={handleSelectCompare}
        onNewCompare={handleNewCompare}
        onDeleteCompare={handleDeleteCompare}
        compareMode={compareMode}
        onToggleCompareMode={handleToggleCompareMode}
      />
      {compareMode ? (
        <CompareView
          token={token!}
          activeSessionId={activeCompareId}
          turns={compareTurns}
          onBeforeSend={handleBeforeCompareSend}
          onTurnComplete={handleCompareTurnComplete}
        />
      ) : (
        <ChatArea
          conversation={activeConversation}
          onSendMessage={handleSendMessage}
          isLoading={isChatLoading}
        />
      )}

    </div>
  )
}

function AuthGate() {
  const { user, isLoading } = useAuth()
  if (isLoading) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-black">
        <div className="flex gap-1.5">
          {[0, 150, 300].map((delay) => (
            <span key={delay} className="w-2 h-2 rounded-full bg-white/40 animate-bounce" style={{ animationDelay: `${delay}ms` }} />
          ))}
        </div>
      </div>
    )
  }
  return user ? <ChatApp /> : <LoginPage />
}

export default function App() {
  return (
    <AuthProvider>
      <AuthGate />
    </AuthProvider>
  )
}
