import { Link, useLocation } from 'react-router-dom'
import { ReactNode, useState, useEffect, useRef } from 'react'
import { getAuthState, clearAuth, AuthState, searchServers, ServerInfo, apiGet, getMe } from '../api/client'
import { NOTIFICATION_COUNT_EVENT } from '../utils/notifications'
import McpWorkspaceNav from './McpWorkspaceNav'
import TelemetryWorkspaceNav from './TelemetryWorkspaceNav'

const navItems = [
  { path: '/', label: '概览', icon: '📊', matches: ['/'] },
  { path: '/market', label: '发现 MCP', icon: '🔎', matches: ['/market', '/servers', '/compare'] },
  { path: '/my-servers', label: '我的 MCP', icon: '📦', matches: ['/my-servers'] },
  { path: '/my-config', label: '配置', icon: '⚙️', matches: ['/my-config', '/config'] },
  { path: '/devices', label: '设备', icon: '🖥️', matches: ['/devices', '/inventory', '/local'] },
  { path: '/monitor', label: '监控', icon: '📈', matches: ['/monitor', '/analytics', '/validation'] },
  { path: '/alerts', label: '告警', icon: '🔔', matches: ['/alerts', '/notifications'] },
  { path: '/reports', label: '报告', icon: '📄', matches: ['/reports'] },
  { path: '/publish', label: '发布', icon: '📤', matches: ['/publish', '/builder'] },
] as const

// 面包屑映射
const breadcrumbLabels: Record<string, string> = {
  '': '概览', guide: '指南', market: '发现 MCP', 'my-servers': '我的 MCP',
  'my-config': '配置与同步', compare: 'Server 对比', presets: '方案市场', builder: '项目脚手架',
  monitor: '运行监控', devices: '设备与接入', inventory: '本地清单', local: '本地清单',
  analytics: '调用分析', validation: '用户验证', alerts: '告警', reports: '报告',
  publish: '发布', profile: '个人中心', notifications: '告警', config: '配置与同步', login: '登录',
  servers: 'Server 详情', admin: '管理后台',
}

function matchesRoute(pathname: string, prefixes: readonly string[]): boolean {
  return prefixes.some(prefix => (
    prefix === '/'
      ? pathname === '/'
      : pathname === prefix || pathname.startsWith(`${prefix}/`)
  ))
}

export default function Layout({ children }: { children: ReactNode }) {
  const location = useLocation()
  const [auth, setAuthState] = useState<AuthState>({ token: null, userId: null })
  const [isAdmin, setIsAdmin] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
  const [unreadNotif, setUnreadNotif] = useState(0)
  // Dark mode
  const [dark, setDark] = useState(() => localStorage.getItem('mcp_hub_dark') === 'true')
  // Mobile
  const [sidebarOpen, setSidebarOpen] = useState(false)
  // Search
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<ServerInfo[]>([])
  const [searchOpen, setSearchOpen] = useState(false)
  const searchRef = useRef<HTMLDivElement>(null)
  const loginTimers = useRef<ReturnType<typeof setInterval>[]>([])
  useEffect(() => () => loginTimers.current.forEach(clearInterval), [])

  // Dark mode effect
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem('mcp_hub_dark', String(dark))
  }, [dark])

  // Close sidebar on mobile when route changes
  useEffect(() => { setSidebarOpen(false); setSearchQuery(''); setSearchOpen(false) }, [location.pathname])

  // Close search on click outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) setSearchOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  // Search debounce with abort
  useEffect(() => {
    if (!searchQuery.trim()) { setSearchResults([]); return }
    const ac = new AbortController()
    const t = setTimeout(async () => {
      try {
        const r = await searchServers({ q: searchQuery, page: 1 })
        if (!ac.signal.aborted) { setSearchResults(r.data.slice(0, 8)); setSearchOpen(true) }
      } catch { if (!ac.signal.aborted) setSearchResults([]) }
    }, 300)
    return () => { clearTimeout(t); ac.abort() }
  }, [searchQuery])

  // 轮询未读通知数
  useEffect(() => {
    if (!auth.token) {
      setUnreadNotif(0)
      return
    }

    const poll = async () => {
      try {
        const r = await apiGet<{ count: number }>('/notifications/unread-count')
        if (r.data) setUnreadNotif(r.data.count || 0)
      } catch {
        // Keep the last known count while the optional notification request is unavailable.
      }
    }
    poll()
    const t = setInterval(poll, 30000)
    return () => clearInterval(t)
  }, [auth.token])

  useEffect(() => {
    const updateCount = (event: Event) => {
      const count = (event as CustomEvent<{ count?: number }>).detail?.count
      if (typeof count === 'number') setUnreadNotif(Math.max(0, count))
    }
    window.addEventListener(NOTIFICATION_COUNT_EVENT, updateCount)
    return () => window.removeEventListener(NOTIFICATION_COUNT_EVENT, updateCount)
  }, [])

  useEffect(() => {
    setAuthState(getAuthState())
    const handler = () => setAuthState(getAuthState())
    window.addEventListener('storage', handler)
    return () => window.removeEventListener('storage', handler)
  }, [])

  useEffect(() => {
    let cancelled = false
    if (!auth.token) {
      setIsAdmin(false)
      return () => { cancelled = true }
    }
    getMe()
      .then(result => {
        if (!cancelled) setIsAdmin((result.data?.role || result.role) === 'admin')
      })
      .catch(() => {
        if (!cancelled) setIsAdmin(false)
      })
    return () => { cancelled = true }
  }, [auth.token])

  const handleLogin = () => {
    const popup = window.open('/api/v1/auth/login', 'github-oauth', 'width=600,height=700')
    if (!popup) { alert('请允许弹出窗口以完成登录'); return }
    const timer = setInterval(() => {
      if (popup.closed) { clearInterval(timer); const s = getAuthState(); if (s.token) { setAuthState(s); window.location.reload() } }
    }, 500)
    loginTimers.current.push(timer)
    const safetyTimeout = setTimeout(() => { clearInterval(timer); loginTimers.current = loginTimers.current.filter(t => t !== timer) }, 120_000)
    loginTimers.current.push(safetyTimeout as any)
  }

  const handleLogout = () => { clearAuth(); setAuthState({ token: null, userId: null }) }

  // 面包屑
  const pathParts = location.pathname.split('/').filter(Boolean)
  const breadcrumbs = pathParts.length > 0
    ? [{ label: '首页', path: '/' }, ...pathParts.map((p, i) => ({
        label: breadcrumbLabels[p] || p,
        path: '/' + pathParts.slice(0, i + 1).join('/'),
      }))]
    : [{ label: '概览', path: '/' }]
  const sidebarCollapsed = collapsed && !sidebarOpen

  const sidebar = (
    <>
      {/* Logo */}
      <Link to="/" className="flex flex-shrink-0 items-center gap-2 px-3 py-4 border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors">
        <svg width="28" height="28" viewBox="0 0 64 64" className="flex-shrink-0">
          <defs><linearGradient id="ls" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stopColor="#3B82F6"/><stop offset="100%" stopColor="#8B5CF6"/></linearGradient></defs>
          <circle cx="32" cy="32" r="30" fill="url(#ls)"/>
          <text x="32" y="36" textAnchor="middle" fill="white" fontSize="26" fontWeight="800" fontFamily="system-ui,sans-serif">M</text>
        </svg>
        {!sidebarCollapsed && <span className="font-bold text-lg text-gray-900 dark:text-white whitespace-nowrap">MCP Hub</span>}
      </Link>

      {/* Search */}
      <div className="flex-shrink-0 px-2 py-2" ref={searchRef}>
        <div className="relative">
          <input
            type="text" value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
            onFocus={() => searchResults.length > 0 && setSearchOpen(true)}
            placeholder={sidebarCollapsed ? '' : '搜索 Server...'}
            className="w-full px-2.5 py-1.5 text-xs border border-gray-200 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-700 dark:text-gray-200 focus:ring-1 focus:ring-blue-400 outline-none"
          />
          {searchOpen && searchResults.length > 0 && (
            <div className="absolute left-0 right-0 top-full mt-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-lg shadow-lg z-50 max-h-64 overflow-y-auto">
              {searchResults.map(s => (
                <Link key={s.id} to={`/servers/${encodeURIComponent(s.id)}`} onClick={() => { setSearchOpen(false); setSearchQuery('') }}
                  className="block px-3 py-2 text-xs hover:bg-gray-50 dark:hover:bg-gray-700 border-b border-gray-50 dark:border-gray-700 last:border-0">
                  <span className="font-medium text-gray-800 dark:text-gray-200">{s.id.split('/').pop()}</span>
                  <span className="text-gray-400 ml-2">{s.description?.slice(0, 40)}</span>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Nav items */}
      <nav className="min-h-0 flex-1 overflow-y-auto py-1" aria-label="主导航">
        {navItems.map((item) => {
          const active = matchesRoute(location.pathname, item.matches)
          return (
            <Link key={item.path} to={item.path} title={sidebarCollapsed ? item.label : undefined}
              className={`flex items-center gap-2.5 mx-2 mb-0.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                active ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400'
                       : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800'
              }`}
              aria-current={active ? 'page' : undefined}>
              <span className="text-base flex-shrink-0 w-5 text-center">{item.icon}</span>
              {!sidebarCollapsed && <span className="whitespace-nowrap">{item.label}</span>}
            </Link>
          )
        })}
      </nav>

      <div className="flex-shrink-0 border-t border-gray-100 py-1 dark:border-gray-700">
        {isAdmin && (
          <Link to="/admin"
            className="mx-2 flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-100 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-200"
            title={sidebarCollapsed ? '管理后台' : undefined}>
            <span aria-hidden="true">🛡️</span>
            {!sidebarCollapsed && <span className="whitespace-nowrap text-xs">管理后台</span>}
          </Link>
        )}
        <Link to="/guide"
          className="mx-2 flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-200"
          title={sidebarCollapsed ? '指南' : undefined}>
          <span aria-hidden="true">📖</span>
          {!sidebarCollapsed && <span className="whitespace-nowrap text-xs">指南</span>}
        </Link>
        <Link to="/alerts"
          className="relative mx-2 flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-200"
          title={sidebarCollapsed ? '通知' : undefined}>
          <span className="relative" aria-hidden="true">🔔
            {unreadNotif > 0 && (
              <span className="absolute -top-1.5 -right-2 min-w-[18px] h-[18px] flex items-center justify-center bg-red-500 text-white text-[10px] font-bold rounded-full px-1">
                {unreadNotif > 99 ? '99+' : unreadNotif}
              </span>
            )}
          </span>
          {!sidebarCollapsed && <span className="whitespace-nowrap text-xs">通知{unreadNotif > 0 ? ` (${unreadNotif})` : ''}</span>}
        </Link>
      </div>

      {/* 底部工具栏 */}
      <div className="mx-2 mb-1 flex flex-shrink-0 items-center gap-1">
        <button onClick={() => setDark(!dark)}
          className="flex-1 py-1.5 text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
          title={dark ? '切换亮色模式' : '切换深色模式'}>
          {dark ? '☀️' : '🌙'}
        </button>
        <button onClick={() => setCollapsed(!collapsed)}
          className="hidden flex-1 py-1.5 text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors md:block"
          title={collapsed ? '展开菜单' : '收起菜单'}>
          {collapsed ? '▶' : '◀'}
        </button>
      </div>

      {/* Auth */}
      <div className="flex-shrink-0 border-t border-gray-100 px-3 py-3 dark:border-gray-700">
        {auth.userId ? (
          <div className={sidebarCollapsed ? 'text-center' : ''}>
            {sidebarCollapsed ? (
              <Link to="/profile" className="inline-flex h-8 w-8 items-center justify-center rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700" title="个人中心">👤</Link>
            ) : (
              <div className="flex items-center justify-between">
                <Link to="/profile" className="max-w-[120px] truncate text-xs text-gray-600 hover:text-blue-700 dark:text-gray-400 dark:hover:text-blue-300" title="个人中心">
                  👤 {auth.userId}
                </Link>
                <button onClick={handleLogout} className="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">退出</button>
              </div>
            )}
          </div>
        ) : (
          <button onClick={handleLogin}
            className={`flex items-center gap-1.5 rounded-lg text-sm font-medium bg-gray-900 dark:bg-white dark:text-gray-900 text-white hover:bg-gray-800 dark:hover:bg-gray-200 transition-colors ${
              sidebarCollapsed ? 'justify-center w-8 h-8 mx-auto p-0' : 'w-full px-3 py-1.5'}`} title="登录 GitHub">
            <svg className="w-4 h-4 flex-shrink-0" viewBox="0 0 16 16" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>
            {!sidebarCollapsed && <span className="whitespace-nowrap">登录 GitHub</span>}
          </button>
        )}
      </div>
    </>
  )

  return (
    <div className={`min-h-screen flex ${dark ? 'dark' : ''}`}>
      <div className="min-h-screen flex w-full bg-gray-50 dark:bg-gray-900">
        {/* 移动端遮罩 */}
        {sidebarOpen && (
          <div className="fixed inset-0 bg-black/50 z-40 md:hidden" onClick={() => setSidebarOpen(false)} />
        )}

        {/* Sidebar — 桌面端常显，移动端 overlay */}
        <aside className={`z-50 flex flex-shrink-0 flex-col overflow-hidden border-r border-gray-200 bg-white transition-all duration-200 dark:border-gray-700 dark:bg-gray-800
          ${sidebarOpen ? 'fixed inset-y-0 left-0' : 'hidden'}
          md:sticky md:top-0 md:flex md:h-screen md:self-start
          ${sidebarCollapsed ? 'w-16' : 'w-52'}`}>
          {/* 移动端关闭按钮 */}
          <button onClick={() => setSidebarOpen(false)} className="md:hidden absolute top-3 right-3 text-gray-400 hover:text-gray-600 text-lg">✕</button>
          {sidebar}
        </aside>

        {/* Main content */}
        <div className="flex-1 min-w-0">
          <a href="#main-content" className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:px-4 focus:py-2 focus:bg-blue-600 focus:text-white focus:rounded-lg">跳到主内容</a>

          {/* 移动端顶栏 */}
          <div className="md:hidden flex items-center justify-between px-4 py-2 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
            <button onClick={() => setSidebarOpen(true)} className="text-gray-600 dark:text-gray-300 text-xl">☰</button>
            <span className="font-bold text-gray-900 dark:text-white">MCP Hub</span>
            <button onClick={() => setDark(!dark)} className="text-lg">{dark ? '☀️' : '🌙'}</button>
          </div>

          {/* 面包屑 */}
          <div className="hidden md:flex items-center gap-1 px-6 pt-4 pb-0 text-xs text-gray-400 dark:text-gray-500">
            {breadcrumbs.map((b, i) => (
              <span key={b.path} className="flex items-center gap-1">
                {i > 0 && <span>/</span>}
                {i < breadcrumbs.length - 1 ? (
                  <Link to={b.path} className="hover:text-blue-600 dark:hover:text-blue-400">{b.label}</Link>
                ) : (
                  <span className="text-gray-600 dark:text-gray-300 font-medium">{b.label}</span>
                )}
              </span>
            ))}
          </div>

          <main id="main-content" className="px-4 md:px-6 py-4 md:py-8">
            <McpWorkspaceNav />
            <TelemetryWorkspaceNav />
            {children}
          </main>
        </div>
      </div>
    </div>
  )
}
