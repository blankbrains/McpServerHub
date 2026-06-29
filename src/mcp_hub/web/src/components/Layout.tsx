import { Link, useLocation } from 'react-router-dom'
import { ReactNode, useState, useEffect } from 'react'
import { getAuthState, clearAuth, AuthState } from '../api/client'

const navItems = [
  { path: '/', label: '仪表盘', icon: '📊' },
  { path: '/market', label: '市场', icon: '🏪' },
  { path: '/my-servers', label: '我的 Server', icon: '📦' },
  { path: '/my-config', label: '配置', icon: '⚙️' },
  { path: '/builder', label: '构建', icon: '🛠️' },
]

export default function Layout({ children }: { children: ReactNode }) {
  const location = useLocation()
  const [auth, setAuthState] = useState<AuthState>({ token: null, userId: null })

  // 从 localStorage 读取登录状态（OAuth 回调写入的）
  useEffect(() => {
    const s = getAuthState()
    setAuthState(s)

    // 监听 OAuth 回调窗口关闭后刷新
    const handler = () => {
      const s2 = getAuthState()
      if (s2.token !== s.token) setAuthState(s2)
    }
    window.addEventListener('storage', handler)
    return () => window.removeEventListener('storage', handler)
  }, [])

  const handleLogin = () => {
    // 打开 popup 进行 GitHub OAuth
    const popup = window.open('/api/v1/auth/login', 'github-oauth', 'width=600,height=700')
    // 轮询等待 popup 关闭（回调页面会写 localStorage）
    const timer = setInterval(() => {
      if (popup?.closed) {
        clearInterval(timer)
        const s = getAuthState()
        if (s.token) {
          setAuthState(s)
          window.location.reload()
        }
      }
    }, 500)
  }

  const handleLogout = () => {
    clearAuth()
    setAuthState({ token: null, userId: null })
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-8">
              <Link to="/" className="flex items-center gap-2">
                <svg width="32" height="32" viewBox="0 0 64 64" className="flex-shrink-0">
                  <defs><linearGradient id="lg" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="#3B82F6"/><stop offset="100%" stopColor="#8B5CF6"/>
                  </linearGradient></defs>
                  <circle cx="32" cy="32" r="30" fill="url(#lg)"/>
                  <text x="32" y="36" text-anchor="middle" fill="white" font-size="26" fontWeight="800" fontFamily="system-ui,sans-serif">M</text>
                </svg>
                <span className="font-bold text-xl text-gray-900">MCP Hub</span>
              </Link>
              <nav className="flex items-center gap-1">
                {navItems.map((item) => (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      location.pathname === item.path
                        ? 'bg-blue-50 text-blue-700'
                        : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                    }`}
                  >
                    <span className="mr-1.5">{item.icon}</span>
                    {item.label}
                  </Link>
                ))}
              </nav>
            </div>
            <div className="flex items-center gap-3">
              {auth.userId ? (
                <>
                  <span className="text-sm text-gray-600">👤 {auth.userId}</span>
                  <button
                    onClick={handleLogout}
                    className="text-sm text-gray-500 hover:text-gray-700"
                  >
                    退出
                  </button>
                </>
              ) : (
                <button
                  onClick={handleLogin}
                  className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-sm font-medium bg-gray-900 text-white hover:bg-gray-800 transition-colors"
                >
                  <svg className="w-4 h-4" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
                  </svg>
                  登录 GitHub
                </button>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
    </div>
  )
}
