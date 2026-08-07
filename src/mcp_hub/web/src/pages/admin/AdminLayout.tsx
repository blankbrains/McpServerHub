import { useEffect, useState } from 'react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { getAuthState, getMe } from '../../api/client'

const adminNav = [
  { path: '/admin', label: '概览', icon: '📊', end: true },
  { path: '/admin/users', label: '用户', icon: '👥' },
  { path: '/admin/servers', label: 'Server', icon: '📦' },
  { path: '/admin/analytics', label: '分析', icon: '📈' },
  { path: '/admin/reviews', label: '审核', icon: '🛡️' },
  { path: '/admin/audit', label: '审计', icon: '📋' },
]

export default function AdminLayout() {
  const location = useLocation()
  const navigate = useNavigate()
  const [authorized, setAuthorized] = useState(false)
  const [checking, setChecking] = useState(true)
  const [collapsed, setCollapsed] = useState(false)

  useEffect(() => {
    const { userId, token } = getAuthState()
    if (!token || !userId) { navigate('/'); return }
    getMe()
      .then(d => {
        if ((d.data?.role || d.role) === 'admin') { setAuthorized(true) }
        else { navigate('/') }
      })
      .catch(() => navigate('/'))
      .finally(() => setChecking(false))
  }, [])

  if (checking) return <div className="flex items-center justify-center h-64 text-gray-400">验证权限中...</div>
  if (!authorized) return null

  return (
    <div className="flex min-h-screen bg-gray-50 dark:bg-gray-900">
      <aside className={`flex-shrink-0 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex flex-col transition-all ${collapsed ? 'w-16' : 'w-48'}`}>
        <div className="px-3 py-4 border-b border-gray-100 dark:border-gray-700">
          <span className={`font-bold text-gray-900 dark:text-white ${collapsed ? 'text-sm' : 'text-base'}`}>
            {collapsed ? '🛡️' : '🛡️ 管理后台'}
          </span>
        </div>
        <nav className="flex-1 py-2">
          {adminNav.map(item => {
            const active = item.end ? location.pathname === item.path : location.pathname.startsWith(item.path)
            return (
              <Link key={item.path} to={item.path} title={collapsed ? item.label : undefined}
                className={`flex items-center gap-2.5 mx-2 mb-0.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  active ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400'
                         : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
                }`}>
                <span className="text-base flex-shrink-0">{item.icon}</span>
                {!collapsed && <span>{item.label}</span>}
              </Link>
            )
          })}
        </nav>
        <button onClick={() => setCollapsed(!collapsed)}
          className="mx-2 mb-2 px-3 py-1.5 text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded-lg">
          {collapsed ? '▶' : '◀'}
        </button>
        <div className="border-t border-gray-100 dark:border-gray-700 px-3 py-3">
          <Link to="/" className="text-xs text-gray-400 hover:text-blue-600">← 返回 Hub</Link>
        </div>
      </aside>
      <main className="flex-1 px-6 py-6 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
