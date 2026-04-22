import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import { authLogin, authRegister, getMe } from '@/lib/api'

interface User {
  user_id: string
  email: string
}

interface AuthContextValue {
  user: User | null
  token: string | null
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('berg_token'))
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // On mount: handle OAuth callback token in URL (?token=...) or validate stored token
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const oauthToken = params.get('token')

    if (oauthToken) {
      // Clean the token from the URL immediately so it's not bookmarked
      window.history.replaceState({}, '', window.location.pathname)
      localStorage.setItem('berg_token', oauthToken)
      setToken(oauthToken)
      getMe(oauthToken)
        .then(setUser)
        .catch(() => {
          localStorage.removeItem('berg_token')
          setToken(null)
        })
        .finally(() => setIsLoading(false))
      return
    }

    if (!token) {
      setIsLoading(false)
      return
    }

    getMe(token)
      .then(setUser)
      .catch(() => {
        localStorage.removeItem('berg_token')
        setToken(null)
      })
      .finally(() => setIsLoading(false))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const login = useCallback(async (email: string, password: string) => {
    const { access_token } = await authLogin(email, password)
    localStorage.setItem('berg_token', access_token)
    setToken(access_token)
    const me = await getMe(access_token)
    setUser(me)
  }, [])

  const register = useCallback(async (email: string, password: string) => {
    const { access_token } = await authRegister(email, password)
    localStorage.setItem('berg_token', access_token)
    setToken(access_token)
    const me = await getMe(access_token)
    setUser(me)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('berg_token')
    setToken(null)
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, token, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
