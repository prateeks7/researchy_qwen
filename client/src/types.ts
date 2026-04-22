export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
}

export interface Conversation {
  id: string          // maps to session_id
  title: string
  messages: Message[]
  createdAt: Date     // maps to created_at
}

export interface User {
  user_id: string
  email: string
}

export interface Session {
  session_id: string
  title: string
  created_at: string
  updated_at: string
}

export interface SessionDetail extends Session {
  messages: Array<{ role: string; content: string; timestamp: string }>
}

export interface CompareSession {
  session_id: string
  title: string
  created_at: string
  updated_at: string
}

export interface CompareTurn {
  user_message: string
  responses: { qwen7b: string; qwen72b: string; gemini: string }
  timings: { qwen7b: number; qwen72b: number; gemini: number }
  timestamp: string
}

export interface CompareSessionDetail extends CompareSession {
  turns: CompareTurn[]
}
