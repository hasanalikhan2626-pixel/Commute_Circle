import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { Link, Navigate, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { api } from './api'
import { useAuth } from './auth'
import { Loading, Logo } from './components/ui'
import AuthPage from './pages/AuthPage'
import PrivacyPage from './pages/PrivacyPage'
import AccountPage from './pages/AccountPage'
import Find from './pages/Find'
import Today from './pages/Today'
import MyCircle from './pages/MyCircle'
import Money from './pages/Money'
import Savings from './pages/Savings'
import Usage from './pages/admin/Usage'
import Fares from './pages/admin/Fares'
import Health from './pages/admin/Health'
import Approvals from './pages/admin/Approvals'
import Reports from './pages/admin/Reports'
import Lab from './pages/admin/Lab'
import Students from './pages/admin/Students'

const CircleCtx = createContext(null)
export const useCircle = () => useContext(CircleCtx)

function Header({ tabs }) {
  const { user, logout } = useAuth()
  return (
    <header className="bar">
      <div className="wrap top">
        <Link to="/" className="brand" style={{ color: 'inherit', textDecoration: 'none' }}>
          <Logo />
          <div><h1>CommuteCircle</h1><small>Travel to campus with classmates on your route · BIC Karachi</small></div>
        </Link>
        {user.role === 'admin' && <span className="tag">Student Affairs</span>}
        <div className="me-menu">
          <span className="who">{user.full_name}</span>
          <NavLink to="/account" className="btn sm">Account</NavLink>
          <button className="btn sm" onClick={logout}>Sign out</button>
        </div>
      </div>
      <div className="wrap">
        <nav className="atabs" role="tablist">
          {tabs.map(([to, label, n]) => (
            <NavLink key={to} to={to} role="tab">{label}{n ? <> <span className="badge sign">{n}</span></> : null}</NavLink>
          ))}
        </nav>
      </div>
    </header>
  )
}

function StudentApp() {
  const [circle, setCircle] = useState(undefined)
  const [rematch, setRematch] = useState(false)
  const reload = useCallback(() => api('/api/circle').then(setCircle).catch(() => setCircle(null)), [])
  useEffect(() => { reload() }, [reload])
  const loc = useLocation()
  if (circle === undefined) return <Loading />
  const active = circle?.status === 'active'
  const tabs = active
    ? [['/today', 'Today'], ['/circle', 'My circle'], ['/money', 'Money'], ['/savings', 'My savings'], ...(rematch ? [['/find', 'Re-match']] : [])]
    : [['/find', 'Find my circle'], ['/savings', 'My savings']]
  const home = active ? '/today' : '/find'
  return (
    <CircleCtx.Provider value={{ circle, reload, rematch, setRematch }}>
      <Header tabs={tabs} />
      <main className="wrap" key={loc.pathname}>
        <Routes>
          <Route path="/find" element={!active || rematch ? <Find /> : <Navigate to="/today" replace />} />
          <Route path="/savings" element={<Savings />} />
          {active && <Route path="/today" element={<Today />} />}
          {active && <Route path="/circle" element={<MyCircle />} />}
          {active && <Route path="/money" element={<Money />} />}
          <Route path="/account" element={<AccountPage />} />
          <Route path="/privacy" element={<PrivacyPage />} />
          <Route path="*" element={<Navigate to={home} replace />} />
        </Routes>
      </main>
    </CircleCtx.Provider>
  )
}

function AdminApp() {
  const [counts, setCounts] = useState({})
  const loc = useLocation()
  useEffect(() => { api('/api/admin/usage').then((u) => setCounts({ p: u.pending, r: u.open_reports })).catch(() => {}) }, [loc.pathname])
  const tabs = [['/admin/usage', 'Usage'], ['/admin/fares', 'Fares'], ['/admin/health', 'Circle health'],
    ['/admin/approvals', 'Approvals', counts.p], ['/admin/reports', 'Reports', counts.r],
    ['/admin/lab', 'Matching lab'], ['/admin/students', 'Students']]
  return (
    <>
      <Header tabs={tabs} />
      <main className="wrap" key={loc.pathname}>
        <Routes>
          <Route path="/admin/usage" element={<Usage />} />
          <Route path="/admin/fares" element={<Fares />} />
          <Route path="/admin/health" element={<Health />} />
          <Route path="/admin/approvals" element={<Approvals />} />
          <Route path="/admin/reports" element={<Reports />} />
          <Route path="/admin/lab" element={<Lab />} />
          <Route path="/admin/students" element={<Students />} />
          <Route path="/account" element={<AccountPage />} />
          <Route path="/privacy" element={<PrivacyPage />} />
          <Route path="*" element={<Navigate to="/admin/usage" replace />} />
        </Routes>
      </main>
    </>
  )
}

export default function App() {
  const { user } = useAuth()
  if (user === undefined) return <Loading />
  if (!user) {
    return (
      <Routes>
        <Route path="/privacy" element={<main className="wrap"><PrivacyPage standalone /></main>} />
        <Route path="*" element={<AuthPage />} />
      </Routes>
    )
  }
  return user.role === 'admin' ? <AdminApp /> : <StudentApp />
}
