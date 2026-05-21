import type { Session, SessionDetail, User, CompareSession, CompareSessionDetail, ModelKey } from '@/types'

const API_BASE = 'http://localhost:8000'

// ── Helpers ───────────────────────────────────────────────────────────────────

function authHeaders(token: string) {
  return { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status}: ${detail}`)
  }
  return res.json() as Promise<T>
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export async function getMe(token: string): Promise<User> {
  const res = await fetch(`${API_BASE}/api/auth/me`, { headers: authHeaders(token) })
  return handleResponse<User>(res)
}

// ── Sessions ──────────────────────────────────────────────────────────────────

export async function getSessions(token: string): Promise<Session[]> {
  const res = await fetch(`${API_BASE}/api/sessions`, { headers: authHeaders(token) })
  return handleResponse<Session[]>(res)
}

export async function createSession(token: string, title: string): Promise<Session> {
  const res = await fetch(`${API_BASE}/api/sessions`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ title }),
  })
  return handleResponse<Session>(res)
}

export async function getSessionDetail(token: string, sessionId: string): Promise<SessionDetail> {
  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}`, { headers: authHeaders(token) })
  return handleResponse<SessionDetail>(res)
}

export async function deleteSession(token: string, sessionId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}`, {
    method: 'DELETE',
    headers: authHeaders(token),
  })
  if (!res.ok && res.status !== 204) {
    throw new Error(`${res.status}: ${res.statusText}`)
  }
}

// ── Chat ──────────────────────────────────────────────────────────────────────

export async function streamChatMessage(
  token: string,
  message: string,
  sessionId: string,
  modelKey: ModelKey,
  onEvent: (event: SSEEvent) => void,
  hfToken?: string,
  geminiToken?: string,
): Promise<void> {
  const body: Record<string, unknown> = { message, session_id: sessionId, model_key: modelKey }
  if (hfToken) body.hf_token = hfToken
  if (geminiToken) body.gemini_token = geminiToken
  const res = await fetch(`${API_BASE}/api/chat/stream`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify(body),
  })
  if (!res.ok || !res.body) {
    const detail = await res.text().catch(() => res.statusText)
    onEvent({ type: 'error', message: `${res.status}: ${detail}` })
    return
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try { onEvent(JSON.parse(line.slice(6))) } catch { /* ignore malformed */ }
      }
    }
  }
}

export async function sendMessage(token: string, message: string, sessionId: string, modelKey: ModelKey): Promise<string> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ message, session_id: sessionId, model_key: modelKey }),
  })
  const data = await handleResponse<{ response: string }>(res)
  return data.response
}

// ── Compare ───────────────────────────────────────────────────────────────────

export async function getCompareSessions(token: string): Promise<CompareSession[]> {
  const res = await fetch(`${API_BASE}/api/compare/sessions`, { headers: authHeaders(token) })
  return handleResponse<CompareSession[]>(res)
}

export async function createCompareSession(token: string, title: string): Promise<CompareSession> {
  const res = await fetch(`${API_BASE}/api/compare/sessions`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ title }),
  })
  return handleResponse<CompareSession>(res)
}

export async function getCompareSessionDetail(token: string, sessionId: string): Promise<CompareSessionDetail> {
  const res = await fetch(`${API_BASE}/api/compare/sessions/${sessionId}`, { headers: authHeaders(token) })
  return handleResponse<CompareSessionDetail>(res)
}

export async function deleteCompareSession(token: string, sessionId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/compare/sessions/${sessionId}`, {
    method: 'DELETE',
    headers: authHeaders(token),
  })
  if (!res.ok && res.status !== 204) throw new Error(`${res.status}: ${res.statusText}`)
}

export interface CompareResult {
  responses: { qwen7b: string; qwen72b: string; gemini: string }
  timings: { qwen7b: number; qwen72b: number; gemini: number }
}

export async function sendCompareMessage(token: string, message: string, sessionId: string): Promise<CompareResult> {
  const res = await fetch(`${API_BASE}/api/compare/chat`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ message, session_id: sessionId }),
  })
  return handleResponse<CompareResult>(res)
}

export type SSEEvent =
  | { type: 'tool'; name: string }
  | { type: 'tool_done'; name?: string; display_name?: string | null; cache_hit?: boolean }
  | { type: 'done'; response: string; timing: number }
  | { type: 'error'; message: string; timing?: number }

export async function streamCompareModel(
  token: string,
  modelKey: string,
  message: string,
  sessionId: string,
  onEvent: (event: SSEEvent) => void,
  hfToken?: string,
  geminiToken?: string,
): Promise<void> {
  const body: Record<string, unknown> = { message, session_id: sessionId }
  if (hfToken) body.hf_token = hfToken
  if (geminiToken) body.gemini_token = geminiToken
  const res = await fetch(`${API_BASE}/api/compare/stream/${modelKey}`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify(body),
  })
  if (!res.ok || !res.body) {
    const detail = await res.text().catch(() => res.statusText)
    onEvent({ type: 'error', message: `${res.status}: ${detail}` })
    return
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try { onEvent(JSON.parse(line.slice(6))) } catch { /* ignore malformed */ }
      }
    }
  }
}

export async function saveCompareTurn(
  token: string,
  sessionId: string,
  userMessage: string,
  responses: Record<string, string>,
  timings: Record<string, number>,
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/compare/sessions/${sessionId}/turns`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ user_message: userMessage, responses, timings }),
  })
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`)
}

// ── Models ────────────────────────────────────────────────────────────────────

export async function checkModelsStatus(): Promise<{ local_72b_available: boolean }> {
  try {
    const res = await fetch(`${API_BASE}/api/models/status`, { signal: AbortSignal.timeout(4000) })
    if (!res.ok) return { local_72b_available: false }
    return res.json()
  } catch {
    return { local_72b_available: false }
  }
}

// ── Health ────────────────────────────────────────────────────────────────────

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/health`, { signal: AbortSignal.timeout(3000) })
    if (!res.ok) return false
    const data = await res.json()
    return data.agent_ready === true
  } catch {
    return false
  }
}
