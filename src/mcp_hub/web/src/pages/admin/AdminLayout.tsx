import { useEffect, useState } from 'react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { getMe } from '../../api/client'
import { useAuthState } from '../../hooks/useAuthState'

const adminNav = [
  { path: '/admin', label: '平台概览', icon: '📊', end: true },
  { path: '/admin/users', label: '用户与设备', icon: '👥' },
  { path: '/admin/servers', label: 'Server 与市场', icon: '📦' },
  { path: '/admin/analytics', label: '平台分析', icon: '📈' },
  { path: '/admin/validation', label: '接入验证', icon: '✅' },
  { path: '/admin/reviews', label: '内容审核', icon: '🛡️' },
  { path: '/admin/audit', label: '操作审计', icon: '📋' },
]

export default function AdminLayout() {
  const auth = useAuthState()
  const location = useLocation()
  const navigate = useNavigate()
  const [authorized, setAuthorized] = useState(false)
  const [checking, setChecking] = useState(true)
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

  useEffect(() => {
    if (!auth.token || !auth.userId) {
      setAuthorized(false)
      setChecking(false)
      navigate('/')
      return
    }
    setChecking(true)
    getMe()
      .then(d => {
        if ((d.data?.role || d.role) === 'admin') { setAuthorized(true) }
        else { navigate('/') }
      })
      .catch(() => navigate('/'))
      .finally(() => setChecking(false))
  }, [auth.token, auth.userId, navigate])

  useEffect(() => {
    setMobileOpen(false)
  }, [location.pathname])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMobileOpen(false)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  if (checking) return <div className="flex items-center justify-center h-64 text-gray-400">验证权限中...</div>
  if (!authorized) return null

  const navigationCollapsed = collapsed && !mobileOpen

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-gray-200 bg-white px-4 py-3 dark:border-gray-700 dark:bg-gray-800 md:hidden">
        <span className="font-bold text-gray-900 dark:text-white">🛡️ 平台管理</span>
        <button
          type="button"
          onClick={() => setMobileOpen(true)}
          aria-label="打开管理员导航"
          aria-expanded={mobileOpen}
          className="border border-gray-300 px-3 py-1.5 text-sm text-gray-700 dark:border-gray-600 dark:text-gray-200"
        >
          菜单
        </button>
      </header>

      <div className="flex min-h-[calc(100vh-53px)] md:min-h-screen">
        {mobileOpen && (
          <button
            type="button"
            aria-label="关闭管理员导航"
            onClick={() => setMobileOpen(false)}
            className="fixed inset-0 z-40 bg-gray-900/40 md:hidden"
          />
        )}
        <aside className={`fixed inset-y-0 left-0 z-50 flex w-64 flex-shrink-0 -translate-x-full flex-col border-r border-gray-200 bg-white transition-transform dark:border-gray-700 dark:bg-gray-800 ${mobileOpen ? 'translate-x-0' : ''} ${collapsed ? 'md:w-16' : 'md:w-52'} md:static md:translate-x-0`}>
        <div className="px-3 py-4 border-b border-gray-100 dark:border-gray-700">
          <div className="flex items-center justify-between gap-2">
            <span className={`font-bold text-gray-900 dark:text-white ${navigationCollapsed ? 'text-sm' : 'text-base'}`}>
              {navigationCollapsed ? '🛡️' : '🛡️ 平台管理'}
            </span>
            <button
              type="button"
              onClick={() => setMobileOpen(false)}
              aria-label="关闭管理员导航"
              className="text-lg text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 md:hidden"
            >
              ×
            </button>
          </div>
        </div>
        <nav className="flex-1 py-2">
          {adminNav.map(item => {
            const active = item.end ? location.pathname === item.path : location.pathname.startsWith(item.path)
            return (
              <Link key={item.path} to={item.path} title={navigationCollapsed ? item.label : undefined}
                className={`flex items-center gap-2.5 mx-2 mb-0.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  active ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400'
                         : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
                }`}>
                <span className="text-base flex-shrink-0">{item.icon}</span>
                {!navigationCollapsed && <span>{item.label}</span>}
              </Link>
            )
          })}
        </nav>
        <button type="button" onClick={() => setCollapsed(!collapsed)}
          aria-label={collapsed ? '展开管理员导航' : '收起管理员导航'}
          className="mx-2 mb-2 hidden rounded-lg px-3 py-1.5 text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 md:block">
          {collapsed ? '▶' : '◀'}
        </button>
        <div className="border-t border-gray-100 dark:border-gray-700 px-3 py-3">
          <Link to="/" className="text-xs text-gray-400 hover:text-blue-600" onClick={() => setMobileOpen(false)}>← 返回 Hub</Link>
        </div>
        </aside>
        <main className="min-w-0 flex-1 overflow-auto px-4 py-5 md:px-6 md:py-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
