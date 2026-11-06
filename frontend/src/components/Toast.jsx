import { createContext, useCallback, useContext, useRef, useState } from 'react'

const Ctx = createContext(() => {})

export function ToastProvider({ children }) {
  const [msg, setMsg] = useState('')
  const [on, setOn] = useState(false)
  const timer = useRef()
  const toast = useCallback((t) => {
    setMsg(t); setOn(true)
    clearTimeout(timer.current)
    timer.current = setTimeout(() => setOn(false), 2600)
  }, [])
  return (
    <Ctx.Provider value={toast}>
      {children}
      <div id="toast" className={on ? 'on' : ''} role="status" aria-live="polite">{msg}</div>
    </Ctx.Provider>
  )
}

export const useToast = () => useContext(Ctx)
