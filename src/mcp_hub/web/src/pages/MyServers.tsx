import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { apiGet, apiPost, ServerInfo } from '../api/client'
import StatusBadge from '../components/StatusBadge'

export default function MyServers() {
  const [servers, setServers] = useState<ServerInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState('')

  const load = async () => {
    try {
      const r = await apiGet<ServerInfo[]>('/servers/')
      if (r.data) setServers(r.data)
    } catch { setMessage('加载失败') }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const handleAction = async (sid: string, action: 'start' | 'stop' | 'uninstall') => {
    try {
      const r = await apiPost(`/servers/${encodeURIComponent(sid)}/${action}`)
      setMessage(r.message || `✅ ${action} 成功`)
      load()
      setTimeout(() => setMessage(''), 3000)
    } catch { setMessage(`❌ ${action} 失败`) }
  }

  if (loading) return <div className="text-center py-16 text-gray-400">加载中...</div>

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">📦 我的 Server</h1>
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
          <p className="text-lg mb-2">还没有安装任何 MCP Server</p>
          <p className="text-sm mb-6">去市场搜索并一键安装你需要的 Server</p>
          <Link to="/market" className="inline-block px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium">
            去市场看看
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {servers.map((s) => (
            <div key={s.id} className="bg-white rounded-xl border border-gray-200 p-4 flex items-center justify-between hover:border-gray-300 transition-colors">
              <div className="flex items-center gap-3 min-w-0">
                <StatusBadge status={s.status} />
                <div className="min-w-0">
                  <Link to={`/servers/${encodeURIComponent(s.id)}`} className="font-medium text-gray-900 hover:text-blue-600 truncate block">
                    {s.id}
                  </Link>
                  <p className="text-xs text-gray-400 truncate">{s.description}</p>
                </div>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0 ml-4">
                {s.status !== 'running' ? (
                  <button onClick={() => handleAction(s.id, 'start')}
                    className="px-3 py-1.5 bg-green-100 text-green-700 rounded-lg text-xs font-medium hover:bg-green-200">
                    ▶ 启动
                  </button>
                ) : (
                  <button onClick={() => handleAction(s.id, 'stop')}
                    className="px-3 py-1.5 bg-yellow-100 text-yellow-700 rounded-lg text-xs font-medium hover:bg-yellow-200">
                    ⏹ 停止
                  </button>
                )}
                <button onClick={() => handleAction(s.id, 'uninstall')}
                  className="px-3 py-1.5 bg-red-50 text-red-600 rounded-lg text-xs font-medium hover:bg-red-100">
                  卸载
                </button>
                <Link to={`/servers/${encodeURIComponent(s.id)}`}
                  className="px-3 py-1.5 bg-gray-100 text-gray-600 rounded-lg text-xs font-medium hover:bg-gray-200">
                  详情
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
