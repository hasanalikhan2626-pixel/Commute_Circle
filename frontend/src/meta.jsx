import { createContext, useContext, useEffect, useState } from 'react'
import { api } from './api'

const Ctx = createContext(null)
export function MetaProvider({ children }) {
  const [meta, setMeta] = useState(null)
  useEffect(() => { api('/api/meta').then(setMeta).catch(() => {}) }, [])
  return <Ctx.Provider value={meta}>{children}</Ctx.Provider>
}
export const useMeta = () => useContext(Ctx)
