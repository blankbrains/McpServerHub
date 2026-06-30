import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getLoginUrl, getAuthState, clearAuth } from '../api/client'

export default function Login() {
  const navigate = useNavigate()
  const [auth, setAuth] = useState(getAuthState())
  const [loggingIn, setLoggingIn] = useState(false)

  const handleLogin = () => {
    setLoggingIn(true)
    window.open(getLoginUrl(), 'github-oauth', 'width=600,height=700')
  }

  const handleLogout = () => {
    clearAuth()
    setAuth({ token: null, userId: null })
  }

  // 自动轮询检测登录状态（OAuth 回调写入 localStorage）
  useEffect(() => {
    if (!loggingIn) return
    const timer = setInterval(() => {
      const state = getAuthState()
      if (state.token && state.userId) {
        setAuth(state)
        setLoggingIn(false)
        clearInterval(timer)
        // 登录成功后跳转到仪表盘
        navigate('/')
      }
    }, 500)
    return () => clearInterval(timer)
  }, [loggingIn, navigate])

  // 页面打开时也检测一次（从其他页面跳转过来可能已经登录）
  useEffect(() => {
    const state = getAuthState()
    if (state.token !== auth.token) {
      setAuth(state)
    }
  }, [])

  if (auth.token && auth.userId) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="w-16 h-16 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white text-2xl font-bold mx-auto">
            {auth.userId[0]?.toUpperCase()}
          </div>
          <h2 className="text-xl font-semibold text-gray-800">
            已登录为 <span className="text-blue-600">{auth.userId}</span>
          </h2>
          <p className="text-sm text-gray-500">通过 GitHub OAuth 登录</p>
          <div className="flex gap-3 justify-center pt-2">
            <button
              onClick={handleLogout}
              className="px-4 py-2 text-sm text-red-600 border border-red-300 rounded-lg hover:bg-red-50 transition-colors"
            >
              退出登录
            </button>
            <button
              onClick={() => navigate('/')}
              className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              返回仪表盘
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-[60vh] flex items-center justify-center">
      <div className="text-center space-y-6">
        <div className="w-20 h-20 rounded-full bg-gradient-to-br from-gray-700 to-gray-900 flex items-center justify-center text-white text-3xl mx-auto">
          <svg className="w-10 h-10" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
          </svg>
        </div>
        <h2 className="text-2xl font-bold text-gray-800">登录 MCP Server Hub</h2>
        <p className="text-sm text-gray-500 max-w-xs">
          使用 GitHub 账号登录，即可收藏 Server、提交评价、发布自己的 MCP Server
        </p>
        <button
          onClick={handleLogin}
          disabled={loggingIn}
          className="inline-flex items-center gap-2 px-6 py-3 bg-gray-900 text-white rounded-xl hover:bg-gray-800 transition-colors text-base font-medium disabled:opacity-50"
        >
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
          </svg>
          {loggingIn ? '正在打开 GitHub 授权...' : 'GitHub 登录'}
        </button>
        {loggingIn && (
          <p className="text-xs text-blue-500">等待 GitHub 授权完成，如果弹窗被拦截请允许弹出窗口</p>
        )}
        <p className="text-xs text-gray-400">
          登录即表示同意服务条款。我们仅获取您的公开信息。
        </p>
      </div>
    </div>
  )
}
