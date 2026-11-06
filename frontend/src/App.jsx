import { Navigate, NavLink, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth'
import { Spinner } from './components/ui'
import AuthPage from './pages/AuthPage'
import ProfilePage from './pages/ProfilePage'
import CirclePage from './pages/CirclePage'
import AccountPage from './pages/AccountPage'
import AdminDashboard from './pages/admin/Dashboard'
import AdminMatching from './pages/admin/Matching'
import AdminCircles from './pages/admin/Circles'
import AdminReports from './pages/admin/Reports'
import AdminUsers from './pages/admin/Users'

function Shell({ children }) {
  const { user, logout } = useAuth()
  const admin = user.role === 'admin'
  const links = admin
    ? [['/admin', 'Overview'], ['/admin/matching', 'Matching'], ['/admin/circles', 'Circles'], ['/admin/reports', 'Reports'], ['/admin/users', 'Students']]
    : [['/circle', 'My circle'], ['/profile', 'Commute'], ['/account', 'Account']]
  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand"><span className="logo" aria-hidden>◎</span> CommuteCircle {admin && <span className="tag">Admin</span>}</div>
        <nav className="nav">
          {links.map(([to, label]) => (
            <NavLink key={to} to={to} end>{label}</NavLink>
          ))}
        </nav>
        <button className="btn btn-ghost" onClick={logout}>Sign out</button>
      </header>
      <main className="content">{children}</main>
    </div>
  )
}

export default function App() {
  const { user } = useAuth()
  if (user === undefined) return <div className="center"><Spinner /></div>
  if (!user) return <Routes><Route path="*" element={<AuthPage />} /></Routes>

  if (user.role === 'admin') {
    return (
      <Shell>
        <Routes>
          <Route path="/admin" element={<AdminDashboard />} />
          <Route path="/admin/matching" element={<AdminMatching />} />
          <Route path="/admin/circles" element={<AdminCircles />} />
          <Route path="/admin/reports" element={<AdminReports />} />
          <Route path="/admin/users" element={<AdminUsers />} />
          <Route path="*" element={<Navigate to="/admin" replace />} />
        </Routes>
      </Shell>
    )
  }
  return (
    <Shell>
      <Routes>
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/circle" element={user.has_profile ? <CirclePage /> : <Navigate to="/profile" replace />} />
        <Route path="/account" element={<AccountPage />} />
        <Route path="*" element={<Navigate to={user.has_profile ? '/circle' : '/profile'} replace />} />
      </Routes>
    </Shell>
  )
}
