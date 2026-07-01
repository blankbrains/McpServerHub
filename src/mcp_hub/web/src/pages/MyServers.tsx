import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { apiGet, apiPost, getAuthState } from '../api/client'
import StatusBadge from '../components/StatusBadge'

interface TrackedServer {
  server_id: string
  name: string
  description: string
  status: string
  running: boolean
  enabled: boolean
  pid: number | null
  location: string
  uptime_seconds: number
  reliability_score: number
  call_count_7d: number
  token_consumption: number
  security_level: string
}

export default function MyServers() {
  const [servers, setServers] = useState<TrackedServer[]>([])
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState('')

  const load = async () => {
    try {
      const r = await apiGet<any>('/monitor/dashboard')
      if (r.data?.servers) setServers(r.data.servers)
    } catch { setMessage('加载失败') }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const handleAction = async (sid: string, action: 'start' | 'stop') => {
    try {
      const r = await apiPost(`/servers/${encodeURIComponent(sid)}/${action}`)
      setMessage(r.message || `✅ ${action} 成功`)
      load()
      setTimeout(() => setMessage(''), 3000)
    } catch { setMessage(`❌ ${action} 失败`) }
  }

  const toggleEnabled = async (sid: string, current: boolean) => {
    const { userId: uid } = getAuthState()
    if (!uid) return
    // 直接调用 toggle API，不再加载全部再保存
    try {
      await fetch('/api/v1/config/user-servers/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-user-id': uid },
        body: JSON.stringify({ server_id: sid, enabled: !current }),
      })
      // 乐观更新本地状态
      setServers(prev => prev.map(s =>
        (s.server_id === sid) ? { ...s, enabled: !current } : s
      ))
    } catch {}
  }

  const installed = servers.filter(s => s.status !== 'not_installed')
  const tracked = servers.filter(s => s.status === 'not_installed')

  if (loading) return <div className="text-center py-16 text-gray-400">加载中...</div>

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">📦 我的 Server</h1>
          <p className="text-sm text-gray-500">共 {servers.length} 个 Server（{installed.length} 已安装 / {tracked.length} 追踪中）</p>
        </div>
        <Link to="/market" className="text-sm text-blue-600 hover:text-blue-800">去市场安装 →</Link>
      </div>

      {message && (
        <div className="p-3 rounded-lg text-sm" style={{ backgroundColor: message.startsWith('✅') ? '#F0FDF4' : '#FEF2F2', color: message.startsWith('✅') ? '#166534' : '#991B1B' }}>
          {message}
        </div>
      )}

      {servers.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center text-gray-400">
          <p className="text-5xl mb-4">📭</p>
          <p className="text-lg mb-2">还没有添加任何 MCP Server</p>
          <p className="text-sm mb-2">上传你的 mcp.json 配置文件，或去市场搜索安装</p>
          <div className="flex gap-3 justify-center">
            <Link to="/config" className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm hover:bg-gray-200">上传配置</Link>
            <Link to="/market" className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">去市场看看</Link>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          {/* 已安装部分 */}
          {installed.length > 0 && (
            <>
              <p className="text-xs text-gray-400 font-medium px-1">✅ 已安装（{installed.length}）</p>
              {installed.map(s => (
                <div key={s.server_id} className="bg-white rounded-xl border border-gray-200 p-4 flex items-center justify-between hover:border-gray-300 transition-colors">
                  <div className="flex items-center gap-3 min-w-0">
                    <StatusBadge status={s.running ? 'running' : s.status} />
                    <div className="min-w-0">
                      <Link to={`/servers/${encodeURIComponent(s.server_id)}`} className="font-medium text-gray-900 hover:text-blue-600 truncate block">
                        {s.name || s.server_id}
                      </Link>
                      <p className="text-xs text-gray-400 truncate">{s.description || s.server_id}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0 ml-4">
                    {s.running ? (
                      <button onClick={() => handleAction(s.server_id, 'stop')}
                        className="px-3 py-1.5 bg-yellow-100 text-yellow-700 rounded-lg text-xs font-medium hover:bg-yellow-200">⏹ 停止</button>
                    ) : (
                      <button onClick={() => handleAction(s.server_id, 'start')}
                        className="px-3 py-1.5 bg-green-100 text-green-700 rounded-lg text-xs font-medium hover:bg-green-200">▶ 启动</button>
                    )}
                    <Link to={`/servers/${encodeURIComponent(s.server_id)}`}
                      className="px-3 py-1.5 bg-gray-100 text-gray-600 rounded-lg text-xs font-medium hover:bg-gray-200">详情</Link>
                  </div>
                </div>
              ))}
            </>
          )}

          {/* 追踪中部分 */}
          {tracked.length > 0 && (
            <>
              <p className="text-xs text-gray-400 font-medium px-1 pt-3">📋 追踪中（{tracked.length}）— 来自上传配置或市场添加</p>
              {tracked.map(s => (
                <div key={s.server_id} className="bg-white rounded-xl border border-gray-200 p-4 flex items-center justify-between hover:border-gray-300 transition-colors opacity-70 hover:opacity-100">
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="text-xs text-gray-400">📥</span>
                    <div className="min-w-0">
                      <Link to={`/servers/${encodeURIComponent(s.server_id)}`} className="font-medium text-gray-600 hover:text-blue-600 truncate block">
                        {s.name || s.server_id}
                      </Link>
                      <p className="text-xs text-gray-400 truncate">{s.description || '未安装'}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0 ml-4">
                    <button onClick={() => toggleEnabled(s.server_id, s.enabled !== false)}
                      className={`px-2 py-1 rounded-lg text-xs font-medium transition-colors ${s.enabled !== false ? 'bg-green-100 text-green-700 hover:bg-red-100 hover:text-red-700' : 'bg-gray-100 text-gray-400 hover:bg-green-100 hover:text-green-700'}`}>
                      {s.enabled !== false ? '🟢 已启用' : '⭕ 已禁用'}
                    </button>
                    <Link to={`/servers/${encodeURIComponent(s.server_id)}`}
                      className="px-3 py-1.5 bg-blue-50 text-blue-600 rounded-lg text-xs font-medium hover:bg-blue-100">查看</Link>
                  </div>
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  )
}
