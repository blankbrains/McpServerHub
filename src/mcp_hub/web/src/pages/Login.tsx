import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { getLoginUrl, getAuthState, clearAuth, getMe } from '../api/client'

export default function Login() {
  const navigate = useNavigate()
  const [auth, setAuth] = useState(getAuthState())
  const [loggingIn, setLoggingIn] = useState(false)
  const [userInfo, setUserInfo] = useState<any>(null)
  const [userInfoLoading, setUserInfoLoading] = useState(true)
  const [imgFailed, setImgFailed] = useState(false)

  const handleLogin = () => {
    setLoggingIn(true)
    window.open(getLoginUrl(), 'github-oauth', 'width=600,height=700')
  }

  const handleLogout = () => {
    clearAuth()
    setAuth({ token: null, userId: null })
    setUserInfo(null)
  }

  // 获取用户详细信息
  useEffect(() => {
    if (!auth.token || !auth.userId) { setUserInfoLoading(false); return }
    getMe().then(r => setUserInfo(r.data || r)).catch(() => {}).finally(() => setUserInfoLoading(false))
  }, [auth.token, auth.userId])

  // 自动轮询检测登录状态（OAuth 回调写入 localStorage）
  useEffect(() => {
    if (!loggingIn) return
    const timer = setInterval(() => {
      const state = getAuthState()
      if (state.token && state.userId) {
        setAuth(state)
        setLoggingIn(false)
        clearInterval(timer)
        navigate('/')
      }
    }, 500)
    return () => clearInterval(timer)
  }, [loggingIn, navigate])

  // 页面打开时也检测一次
  useEffect(() => {
    const state = getAuthState()
    if (state.token !== auth.token) setAuth(state)
  }, [])

  if (auth.token && auth.userId) {
    const avatarUrl = userInfo?.avatar_url || `https://github.com/${auth.userId}.png`
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="text-center space-y-5">
          {!imgFailed ? (
            <img src={avatarUrl} alt={auth.userId}
              className="w-20 h-20 rounded-full mx-auto border-4 border-gray-100"
              onError={() => setImgFailed(true)} />
          ) : null}
          {imgFailed ? (
            <div className="w-20 h-20 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white text-3xl font-bold mx-auto">
              {auth.userId[0]?.toUpperCase()}
            </div>
          ) : null}
          <div>
            <h2 className="text-xl font-semibold text-gray-800">{userInfo?.display_name || auth.userId}</h2>
            <p className="text-sm text-gray-500">@{auth.userId}</p>
            {userInfo?.email && <p className="text-xs text-gray-400">{userInfo.email}</p>}
          </div>
          <div className="flex gap-2 text-xs text-gray-400 justify-center">
            <Link to="/my-servers" className="hover:text-blue-600">📦 我的 Server</Link>
            <span>·</span>
            <Link to="/my-config" className="hover:text-blue-600">⚙️ 我的配置</Link>
            <span>·</span>
            <Link to="/publish/mine" className="hover:text-blue-600">📤 我的发布</Link>
          </div>
          <div className="flex gap-3 justify-center pt-2">
            <button onClick={handleLogout}
              className="px-4 py-2 text-sm text-red-600 border border-red-300 rounded-lg hover:bg-red-50 transition-colors">
              退出登录
            </button>
            <button onClick={() => navigate('/')}
              className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">
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
