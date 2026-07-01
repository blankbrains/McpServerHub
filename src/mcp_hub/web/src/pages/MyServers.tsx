import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { apiGet, apiPost, getAuthState, installServer } from '../api/client'
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

type TabId = 'installed' | 'tracked' | 'favorites'

export default function MyServers() {
  const [servers, setServers] = useState<TrackedServer[]>([])
  const [favorites, setFavorites] = useState<string[]>(() => {
    try { return JSON.parse(localStorage.getItem('mcp_hub_favorites') || '[]') } catch { return [] }
  })
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<TabId>('installed')
  const [installing, setInstalling] = useState<Set<string>>(new Set())

  const load = async () => {
    try {
      const r = await apiGet<any>('/monitor/dashboard')
      if (r.data?.servers) setServers(r.data.servers)
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const handleAction = async (sid: string, action: 'start' | 'stop') => {
    try {
      await apiPost(`/servers/${encodeURIComponent(sid)}/${action}`)
      load()
    } catch {}
  }

  const toggleEnabled = async (sid: string, current: boolean) => {
    const { userId: uid } = getAuthState()
    if (!uid) return
    try {
      await fetch('/api/v1/config/user-servers/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-user-id': uid },
        body: JSON.stringify({ server_id: sid, enabled: !current }),
      })
      setServers(prev => prev.map(s =>
        (s.server_id === sid) ? { ...s, enabled: !current } : s
      ))
    } catch {}
  }

  const handleInstall = async (sid: string) => {
    setInstalling(prev => new Set([...prev, sid]))
    try {
      await installServer(sid)
      load()
    } catch {} finally {
      setInstalling(prev => { const n = new Set(prev); n.delete(sid); return n })
    }
  }

  const handleRemove = async (sid: string) => {
    if (tab === 'favorites') {
      const next = favorites.filter(f => f !== sid)
      setFavorites(next)
      localStorage.setItem('mcp_hub_favorites', JSON.stringify(next))
      // also call unfavorite API
      try { await fetch('/api/v1/community/favorite', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-user-id': getAuthState().userId || 'anonymous' },
        body: JSON.stringify({ server_id: sid }),
      }) } catch {}
      return
    }
    // remove from user_servers
    const { userId: uid } = getAuthState()
    if (!uid) return
    try {
      const res = await fetch('/api/v1/config/user-servers', { headers: { 'x-user-id': uid } })
      const r = await res.json()
      if (r.data) {
        const updated = r.data.filter((s: any) => (s.name || s.hub_id) !== sid)
        await fetch('/api/v1/config/user-servers/save', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'x-user-id': uid },
          body: JSON.stringify({ servers: updated.map((s: any) => ({ name: s.name || s.hub_id, hub_id: s.hub_id, matched: s.matched, enabled: s.enabled, agent: s.agent })) }),
        })
        localStorage.setItem('mcp_hub_my_servers', JSON.stringify(updated.map((s: any) => ({ name: s.name || s.hub_id, hub_id: s.hub_id, matched: s.matched, enabled: s.enabled }))))
        load()
      }
    } catch {}
  }

  const installed = servers.filter(s => s.status !== 'not_installed')
  const tracked = servers.filter(s => s.status === 'not_installed')

  // 收藏列表：从已安装和追踪中筛选
  const favServers = servers.filter(s => favorites.includes(s.server_id))

  const tabCounts: Record<TabId, number> = {
    installed: installed.length,
    tracked: tracked.length,
    favorites: favorites.length,
  }

  if (loading) return <div className="text-center py-16 text-gray-400">加载中...</div>

  const renderList = (list: TrackedServer[], isInstalled: boolean) => (
    <div className="space-y-2">
      {list.length === 0 ? (
        <div className="text-center py-12 text-gray-400 text-sm">
          {tab === 'tracked' ? '没有追踪中的 Server，去市场添加或上传配置' :
           tab === 'favorites' ? '还没有收藏任何 Server' :
           '没有已安装的 Server，请上传配置或去市场安装'}
        </div>
      ) : list.map((s, i) => (
        <div key={s.server_id} className="bg-white rounded-xl border border-gray-200 p-4 flex items-center justify-between hover:border-gray-300 transition-colors">
          <div className="flex items-center gap-3 min-w-0">
            <span className="text-xs text-gray-400 w-6 text-right flex-shrink-0">({i + 1})</span>
            <StatusBadge status={s.running ? 'running' : s.status} />
            <div className="min-w-0">
              <Link to={`/servers/${encodeURIComponent(s.server_id)}`} className="font-medium text-gray-900 hover:text-blue-600 truncate block">
                {s.name || s.server_id}
              </Link>
              <p className="text-xs text-gray-400 truncate">{s.description || s.server_id}</p>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0 ml-4">
            {isInstalled ? (
              <>
                {s.running ? (
                  <button onClick={() => handleAction(s.server_id, 'stop')}
                    className="px-3 py-1.5 bg-yellow-100 text-yellow-700 rounded-lg text-xs font-medium hover:bg-yellow-200">⏹ 停止</button>
                ) : (
                  <button onClick={() => handleAction(s.server_id, 'start')}
                    className="px-3 py-1.5 bg-green-100 text-green-700 rounded-lg text-xs font-medium hover:bg-green-200">▶ 启动</button>
                )}
                <button onClick={() => toggleEnabled(s.server_id, s.enabled !== false)}
                  className={`px-2 py-1 rounded-lg text-xs font-medium ${s.enabled !== false ? 'bg-green-100 text-green-700 hover:bg-red-100' : 'bg-gray-100 text-gray-400 hover:bg-green-100'}`}>
                  {s.enabled !== false ? '🟢' : '⭕'}
                </button>
              </>
            ) : (
              <button onClick={() => handleInstall(s.server_id)}
                disabled={installing.has(s.server_id)}
                className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-xs font-medium hover:bg-blue-700 disabled:opacity-50">
                {installing.has(s.server_id) ? '安装中...' : '📥 安装'}
              </button>
            )}
            <Link to={`/servers/${encodeURIComponent(s.server_id)}`}
              className="px-3 py-1.5 bg-gray-100 text-gray-600 rounded-lg text-xs font-medium hover:bg-gray-200">详情</Link>
            <button onClick={() => handleRemove(s.server_id)}
              className="px-2 py-1.5 text-xs text-red-400 hover:text-red-600 hover:bg-red-50 rounded">✕</button>
          </div>
        </div>
      ))}
    </div>
  )

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">📦 我的 Server</h1>
          <p className="text-sm text-gray-500">共 {servers.length} 个（{installed.length} 已安装 / {tracked.length} 追踪 / {favorites.length} 收藏）</p>
        </div>
        <Link to="/market" className="text-sm text-blue-600 hover:text-blue-800">去市场 →</Link>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 rounded-lg p-1 w-fit">
        {([
          ['installed', '已安装'],
          ['tracked', '追踪中'],
          ['favorites', '⭐ 收藏'],
        ] as [TabId, string][]).map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${tab === id ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}
            aria-pressed={tab === id}
          >
            {label} ({tabCounts[id]})
          </button>
        ))}
      </div>

      {/* Content */}
      {tab === 'installed' && renderList(installed, true)}
      {tab === 'tracked' && renderList(tracked, false)}
      {tab === 'favorites' && renderList(favServers, true)}
    </div>
  )
}
