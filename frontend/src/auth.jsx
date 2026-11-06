import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api, token } from './api'

const AuthCtx = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(undefined) // undefined = loading, null = signed out

  const refresh = useCallback(async () => {
    if (!token.get()) { setUser(null); return null }
    try { const u = await api('/api/auth/me'); setUser(u); return u } catch { setUser(null); return null }
  }, [])

  useEffect(() => {
    refresh()
    const onLogout = () => setUser(null)
    window.addEventListener('cc:logout', onLogout)
    return () => window.removeEventListener('cc:logout', onLogout)
  }, [refresh])

  const login = async (email, password) => {
    const { access_token } = await api('/api/auth/login', { method: 'POST', form: { username: email, password } })
    token.set(access_token)
    return refresh()
  }
  const register = async (data) => {
    const { access_token } = await api('/api/auth/register', { method: 'POST', body: data })
    token.set(access_token)
    return refresh()
  }
  const logout = () => { token.clear(); setUser(null) }

  return <AuthCtx.Provider value={{ user, refresh, login, register, logout }}>{children}</AuthCtx.Provider>
}

export const useAuth = () => useContext(AuthCtx)
